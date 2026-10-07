"""Authenticated Ray Jobs facade exposed in the management Swagger UI."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..auth import require_admin

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


class SubmitJobRequest(BaseModel):
    """Ray Jobs submission; runtime paths must be available to the cluster."""
    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {
        "submission_id": "cluster-smoke-gpu-002",
        "entrypoint": "/home/cdsw/.venv-router-train/bin/python -m smart_router.training.cluster_smoke --config /home/cdsw/configs/training/cluster-smoke.json --project-root /home/cdsw --run-id cluster-smoke-gpu-002",
        "entrypoint_num_cpus": 1,
        "entrypoint_num_gpus": 0,
        "runtime_env": {
            "py_executable": "/home/cdsw/.venv-router-train/bin/python",
            "env_vars": {"PYTHONPATH": "/home/cdsw/src:/home/cdsw",
                         "PYTHONNOUSERSITE": "1", "NCCL_IB_DISABLE": "1",
                         "NCCL_SOCKET_IFNAME": "eth0", "GLOO_SOCKET_IFNAME": "eth0"},
        },
    }})
    submission_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
                               description="Unique ID; choose a new ID for each run.")
    entrypoint: str = Field(min_length=1, description="Command executed by the Ray job driver.")
    entrypoint_num_cpus: float = Field(default=1, ge=0, allow_inf_nan=False)
    entrypoint_num_gpus: float = Field(default=0, ge=0, allow_inf_nan=False)
    runtime_env: dict = Field(default_factory=dict,
                              description="Ray runtime environment. Use shared paths; do not include credentials.")


def dashboard_request(path, method="GET", payload=None):
    """Talk to the local dashboard without forwarding caller credentials."""
    port = int(os.environ.get("RAY_DASHBOARD_PORT", "8265"))
    request = Request(f"http://127.0.0.1:{port}/api/jobs/{path}", method=method,
                      data=json.dumps(payload).encode() if payload is not None else None,
                      headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as exc:
        # Return actionable Ray validation/not-found errors; suppress server internals.
        if exc.code in (400, 404, 409):
            raise HTTPException(status_code=exc.code, detail=exc.read().decode(errors="replace")) from exc
        raise HTTPException(status_code=502, detail="Ray Jobs API request failed") from exc
    except (URLError, TimeoutError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Ray Jobs API unavailable or returned invalid JSON") from exc


@router.post("", status_code=201, dependencies=[Depends(require_admin)])
def submit_job(body: SubmitJobRequest):
    """Submit a Ray job (not a Ray Serve application). Returns its submission ID.

    For the AMP smoke, use the example with a fresh submission/run ID. This
    endpoint returns immediately; poll status and logs. It does not install
    environments, configure networking, or certify GPU readiness.
    """
    return dashboard_request("", "POST", body.model_dump())


@router.get("")
def list_jobs():
    """List Ray jobs."""
    return dashboard_request("")


@router.get("/{submission_id}")
def get_job(submission_id: str):
    """Get job status and details."""
    return dashboard_request(quote(submission_id, safe=""))


@router.get("/{submission_id}/logs")
def get_job_logs(submission_id: str):
    """Get captured job output."""
    return dashboard_request(quote(submission_id, safe="") + "/logs")


@router.post("/{submission_id}/stop", dependencies=[Depends(require_admin)])
def stop_job(submission_id: str):
    """Request job termination."""
    return dashboard_request(quote(submission_id, safe="") + "/stop", "POST")
