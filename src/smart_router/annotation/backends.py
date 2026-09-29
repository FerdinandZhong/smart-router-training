"""Small HTTP adapters. No implicit retries and no tool/action execution."""

import json
import os
import hashlib
from pathlib import Path
import urllib.error
import urllib.request

from smart_router.schemas import DataError, canonical_json


class CallError(Exception):
    """A missing observation, never evidence that a candidate failed its task."""


def credential(model):
    if "api_key_file" in model:
        try:
            key = Path(model["api_key_file"]).expanduser().read_text().strip()
        except OSError:
            raise DataError("Cannot read configured API credential file") from None
        if not key:
            raise DataError("Configured API credential file is empty")
        return key
    key = os.environ.get(model["api_key_env"], "")
    if not key:
        raise DataError(f"Missing credential environment variable: {model['api_key_env']}")
    return key


def external_key(model, body, context):
    """Bind an externally executed response to its exact evaluation request."""
    return hashlib.sha256(canonical_json({"model": model["model"], "body": body, "context": context}).encode()).hexdigest()


def external_response(model, body, context):
    key = external_key(model, body, context)
    path = Path(model["response_directory"]) / (key + ".json")
    if not path.exists():
        raise CallError("external_response_missing")
    try:
        receipt = json.loads(path.read_text())
        if receipt["request_hash"] != key or receipt["requested_model"] != model["model"]:
            raise CallError("external_response_identity_mismatch")
        if not isinstance(receipt["text"], str) or not receipt["text"].strip():
            raise CallError("external_response_has_no_text")
        if not receipt.get("execution", {}).get("task_name") or not receipt["execution"].get("tool"):
            raise CallError("external_execution_provenance_missing")
        if receipt["execution"].get("model_override") != model["model"]:
            raise CallError("external_execution_model_mismatch")
        return {"text": receipt["text"], "actual_model": receipt.get("actual_model"),
                "response_id": receipt["execution"]["task_name"], "usage": receipt.get("usage", {}),
                "external_execution": receipt["execution"],
                "response_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    except (ValueError, KeyError, TypeError):
        raise CallError("invalid_external_receipt") from None


def request_body(model: dict, system: str, user: str) -> dict:
    common = {"model": model["model"], **model.get("generation", {})}
    if model["api"] == "responses":
        return {**common, "instructions": system, "input": user,
                "max_output_tokens": model["max_output_tokens"], "store": False}
    return {**common, "messages": [{"role": "system", "content": system},
                                   {"role": "user", "content": user}],
            "max_tokens": model["max_output_tokens"]}


def parse_response(api: str, data: dict) -> dict:
    """Require complete textual output; truncations/refusals remain unknown."""
    if api == "responses":
        if data.get("status") != "completed":
            raise CallError("response_incomplete")
        chunks = [part["text"] for item in data.get("output", [])
                  if item.get("type") == "message"
                  for part in item.get("content", []) if part.get("type") == "output_text"]
        content = "\n".join(chunks)
    else:
        choices = data.get("choices", [])
        if not choices or choices[0].get("finish_reason") != "stop":
            raise CallError("response_incomplete_or_native_tool_call")
        content = choices[0].get("message", {}).get("content")
    if not isinstance(content, str) or not content.strip():
        raise CallError("response_has_no_text")
    return {"text": content, "actual_model": data.get("model"),
            "response_id": data.get("id"), "usage": data.get("usage", {})}


def call(model: dict, body: dict, context: dict, fixtures: dict) -> dict:
    if model["api"] == "external":
        return external_response(model, body, context)
    if model["api"] == "mock":
        key = ":".join(str(context[k]) for k in ("role", "example_id", "candidate", "trial"))
        if context["role"] == "judge":
            key += ":" + context["judge"]
        if key not in fixtures:
            raise CallError("missing_mock_response")
        value = fixtures[key]
        if isinstance(value, dict) and "error" in value:
            raise CallError(value["error"])
        return {"text": value if isinstance(value, str) else canonical_json(value),
                "actual_model": model["model"], "response_id": None, "usage": {}}
    key = credential(model)
    endpoint = "/responses" if model["api"] == "responses" else "/chat/completions"
    request = urllib.request.Request(
        model["base_url"].rstrip("/") + endpoint,
        data=canonical_json(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
        method="POST",
    )
    # Refuse redirects so a misconfigured endpoint cannot forward credentials.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=model["timeout_seconds"]) as response:
            return parse_response(model["api"], json.load(response))
    except urllib.error.HTTPError as exc:
        # Provider error bodies/URLs may contain sensitive data; do not persist them.
        raise CallError(f"http_{exc.code}") from None
    except TimeoutError:
        raise CallError("request_timeout") from None
    except (urllib.error.URLError, OSError):
        raise CallError("transport_error") from None
    except (ValueError, KeyError, TypeError, AttributeError):
        raise CallError("malformed_provider_response") from None
