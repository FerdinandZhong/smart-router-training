"""Deterministic validation of the runtime-visible tool response contract."""

import json
from smart_router.schemas import DataError


def validate_tools(state):
    if state.get("response_format", {}).get("type") != "single_tool_json":
        return
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        raise DataError("Tool-contract annotation requires the annotation optional dependency (jsonschema)") from None
    for tool in state["tools"]:
        Draft202012Validator.check_schema(tool["function"]["parameters"])


def check_action(record, text):
    state = record["input"].get("state", {})
    if not isinstance(state, dict) or state.get("response_format", {}).get("type") != "single_tool_json":
        return None
    from jsonschema import Draft202012Validator
    try:
        output = json.loads(text)
    except ValueError:
        return {"passed": False, "errors": ["Response is not a single JSON object"]}
    if not isinstance(output, dict) or set(output) != {"tool", "arguments"}:
        return {"passed": False, "errors": ["Expected exactly tool and arguments"]}
    tools = {t["function"]["name"]: t["function"]["parameters"] for t in state["tools"]}
    if not isinstance(output["tool"], str) or output["tool"] not in tools:
        return {"passed": False, "errors": ["Unknown tool name"]}
    if not isinstance(output["arguments"], dict):
        return {"passed": False, "errors": ["arguments must be an object"]}
    errors = sorted(Draft202012Validator(tools[output["tool"]]).iter_errors(output["arguments"]), key=lambda e: str(e.path))
    return {"passed": not errors, "errors": [e.message for e in errors], "tool": output["tool"], "executed": False}
