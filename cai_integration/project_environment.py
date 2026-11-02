"""Validate stored AMP inputs and refresh application names; never log values."""

import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import re

SUBDOMAIN_INPUTS = ("RAY_HEAD_SUBDOMAIN", "TENSORBOARD_SUBDOMAIN", "TRAINING_DASHBOARD_SUBDOMAIN")
EVENT_FIELDS = {"dispatchConfig", "nativeEvent", "target", "_targetInst"}


def validate_project_environment(raw):
    """Validate the JSON string returned by API v2 GetProject."""
    if raw in (None, ""):
        return {}
    try:
        values = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        raise ValueError("Project environment is invalid JSON (values omitted)") from None
    if not isinstance(values, dict):
        raise ValueError("Project environment must be an object of string values")
    invalid = [key for key, value in values.items() if not isinstance(value, str)]
    if invalid:
        event_keys = [key for key in invalid if isinstance(values[key], dict)
                      and EVENT_FIELDS.issubset(values[key])]
        if event_keys:
            raise ValueError(
                "Browser AMP import stored event objects instead of input strings for: "
                + ", ".join(sorted(event_keys))
                + ". Re-enter the intended values in Project Settings > Environment Variables, "
                "then start a new execution of the failed setup job. "
                "The stored event objects do not preserve the entered text. "
                "No defaults were substituted and no project settings were changed."
            )
        if invalid == ["HUGGING_FACE_HUB_TOKEN"]:
            raise ValueError(
                "Project HUGGING_FACE_HUB_TOKEN is not a string. "
                "From the project terminal, run "
                "python -m cai_integration.repair_project_hf_token to re-enter it "
                "through a hidden prompt. No settings were changed."
            )
        raise ValueError(
            "Project environment contains non-string values for: "
            + ", ".join(sorted(invalid))
            + ". Values must be strings, not browser events or AMP definitions. "
            "Lost input values cannot be reconstructed from defaults. "
            "Use the input-safe cai_integration.create_amp entry point for new "
            "imports. No settings were changed."
        )

    for key in SUBDOMAIN_INPUTS:
        if key in values and not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", values[key]):
            raise ValueError(f"{key}: expected a nonempty DNS label; value omitted")
    return values


def refresh_subdomain_inputs(values, environment):
    """Use verified stored names, even when the job inherited stale serialized events."""
    for key in SUBDOMAIN_INPUTS:
        if key in values:
            environment[key] = values[key]


def preflight_project_environment():
    """Fail before costly setup/application creation using the job's credentials."""
    host = os.environ.get("CML_HOST") or "https://" + os.environ.get("CDSW_DOMAIN", "")
    token = os.environ.get("CDSW_APIV2_KEY") or os.environ.get("CML_API_KEY")
    project = os.environ.get("CDSW_PROJECT_ID") or os.environ.get("CML_PROJECT_ID")
    if host == "https://" or not token or not project:
        raise RuntimeError("AMP project preflight requires host, project ID and API credentials")
    request = Request(
        f"{host.rstrip('/')}/api/v2/projects/{project}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            data = json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"AMP project preflight failed: HTTP {exc.code}; no settings changed") from None
    if "environment" not in data:
        raise RuntimeError("GetProject omitted environment; cannot validate AMP setup")
    values = validate_project_environment(data["environment"])
    refresh_subdomain_inputs(values, os.environ)
    print("Project environment preflight passed (string values; values not logged)")


if __name__ == "__main__":
    preflight_project_environment()
