"""Check a served model without printing credentials or following login redirects."""

import argparse
import json
from pathlib import Path
import sys
import time
import re
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--token-file")
    parser.add_argument("--output", required=True)
    parser.add_argument("--generate", action="store_true", help="Also send one minimal non-thinking completion")
    args = parser.parse_args()
    headers = {"Accept": "application/json"}
    token = ""
    if args.token_file:
        token = Path(args.token_file).expanduser().read_text().strip()
        if not token:
            raise ValueError("Credential file is empty")
        headers["Authorization"] = "Bearer " + token
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    report = {"base_url": args.base_url, "requested_model": args.model,
              "authenticated_request": bool(args.token_file), "checked_at_unix": time.time()}
    request = urllib.request.Request(args.base_url.rstrip("/") + "/models", headers=headers)
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
            data = json.load(response)
            models = [m["id"] for m in data.get("data", [])]
            report.update(http_status=response.status, served_models=models, model_found=args.model in models)
    except urllib.error.HTTPError as exc:
        report.update(http_status=exc.code, error="authentication_redirect" if exc.code in {301,302,303,307,308} else "http_error")
    except (urllib.error.URLError, OSError):
        report.update(error="transport_error")
    except (ValueError, TypeError, KeyError):
        report.update(error="invalid_model_list")
    if args.generate and report.get("model_found"):
        body = {"model": args.model, "messages": [{"role": "user", "content": "Reply exactly OK."}],
                "max_tokens": 16, "chat_template_kwargs": {"enable_thinking": False}}
        request = urllib.request.Request(args.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(body).encode(), headers={**headers, "Content-Type": "application/json"}, method="POST")
        start = time.monotonic()
        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=45) as response:
                result = json.load(response)
                report["generation"] = {"http_status": response.status, "response": result}
        except urllib.error.HTTPError as exc:
            detail = exc.read(8192).decode(errors="replace")
            if token:
                detail = detail.replace(token, "[REDACTED]")
            detail = re.sub(r'(?i)(bearer\s+)[^\s"<>]+', r'\1[REDACTED]', detail)
            report["generation"] = {"http_status": exc.code, "error_detail": detail[:2000]}
        except (urllib.error.URLError, OSError, ValueError):
            report["generation"] = {"error": "transport_or_invalid_response"}
        report["generation"]["latency_seconds"] = time.monotonic() - start
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report.get("model_found") and (not args.generate or report.get("generation", {}).get("http_status") == 200) else 1


if __name__ == "__main__":
    sys.exit(main())
