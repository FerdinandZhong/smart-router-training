#!/usr/bin/env python3
"""Submit and monitor a Ray Job from within this AMP's shared project filesystem."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import sys
import time
from urllib.parse import urlsplit

_file = globals().get("__file__")
ROOT = Path(_file).resolve().parents[1] if _file else Path(os.environ.get("CDSW_PROJECT_DIR") or Path.cwd()).resolve()
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from amp.environment import isolated_environment


def load_config(path):
    config = json.loads(path.read_text())
    if config.get("purpose") != "infrastructure_smoke":
        raise ValueError("This entry point runs infrastructure_smoke only; Laya first-trial is a separate experiment")
    for key in ("num_workers", "cpus_per_worker", "steps", "collective_timeout_seconds", "job_timeout_seconds"):
        if type(config.get(key)) is not int or config[key] <= 0:
            raise ValueError(f"{key} must be a positive integer")
    if type(config.get("use_gpu")) is not bool:
        raise ValueError("use_gpu must be boolean")
    if config["num_workers"] != 2:
        raise ValueError("This infrastructure diagnostic requires exactly two workers")
    for key in ("dataset", "output_dir"):
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise ValueError(f"{key} must be a nonempty path")
    collective_env = config.get("collective_env", {})
    allowed = {"NCCL_IB_DISABLE", "NCCL_SOCKET_IFNAME", "GLOO_SOCKET_IFNAME", "NCCL_DEBUG"}
    if not isinstance(collective_env, dict) or set(collective_env) - allowed or not all(isinstance(v, str) for v in collective_env.values()):
        raise ValueError("collective_env must contain only supported NCCL/Gloo string settings")
    return config


def build_submission(root, config_path, run_id, collective_env=None):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", run_id):
        raise ValueError("Submission ID must contain only letters, digits, underscores and hyphens")
    python = root / ".venv-router-train/bin/python"
    entrypoint = shlex.join([str(python), "-m", "smart_router.training.cluster_smoke",
                            "--config", str(config_path), "--project-root", str(root), "--run-id", run_id])
    # No working_dir upload: all applications belong to this project and share NFS.
    # Runtime setup never forwards the submitter's credentials in this payload.
    return {
        "submission_id": run_id, "entrypoint": entrypoint,
        "entrypoint_num_cpus": 1, "entrypoint_num_gpus": 0,
        "runtime_env": {
            "py_executable": str(python),
            "env_vars": {"PYTHONPATH": os.pathsep.join([str(root / "src"), str(root)]),
                         "PATH": str(python.parent) + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"),
                         "PYTHONNOUSERSITE": "1", "PYTHONUNBUFFERED": "1", **(collective_env or {})},
        },
    }


def cluster_address(root):
    info = json.loads((root / "ray_cluster_info.json").read_text())
    address = info.get("head_url") or info.get("management_api_url")
    if not address or urlsplit(address).scheme != "https":
        raise RuntimeError("Cluster launch has not recorded an HTTPS head URL")
    return address.rstrip("/") + "/dashboard/"


def wait_for_job(client, job_id, timeout):
    deadline = time.monotonic() + timeout
    terminal = {"SUCCEEDED", "FAILED", "STOPPED"}
    while time.monotonic() < deadline:
        status = str(client.get_job_status(job_id))
        print(f"{job_id}: {status}", flush=True)
        if status in terminal:
            print(client.get_job_logs(job_id))
            if status != "SUCCEEDED":
                raise RuntimeError(f"Ray job {job_id} ended with {status}")
            return
        time.sleep(5)
    client.stop_job(job_id)
    print(client.get_job_logs(job_id))
    raise TimeoutError(f"Stopped {job_id} after the configured timeout")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["plan", "submit", "status", "logs", "stop"])
    parser.add_argument("--config", default="configs/training/cluster-smoke.json")
    parser.add_argument("--submission-id", default="cluster-smoke")
    parser.add_argument("--wait", action="store_true")
    args = parser.parse_args()
    config_path = (ROOT / args.config).resolve()
    config = load_config(config_path)
    submission = build_submission(ROOT, config_path, args.submission_id, config.get("collective_env"))
    if args.operation == "plan":
        print(json.dumps(submission, indent=2))
        return
    python = ROOT / ".venv-router-train/bin/python"
    if not python.exists():
        raise RuntimeError("Run the AMP setup_training_environment job first")
    env = isolated_environment(ROOT, python)
    if Path(sys.prefix).resolve() != python.parent.parent.resolve() or any(
        os.environ.get(key) != env.get(key) for key in ("PYTHONPATH", "PYTHONHOME", "PYTHONNOUSERSITE")
    ):
        os.execve(str(python), [str(python), str(ROOT / "amp/jobs.py"), *sys.argv[1:]], env)
    import ray
    from ray.job_submission import JobSubmissionClient
    if ray.__version__ != "2.58.0":
        raise RuntimeError("Submitter Ray version must be 2.58.0")
    token = os.environ.get("CDSW_APIV2_KEY") or os.environ.get("CML_API_KEY")
    if not token:
        raise RuntimeError("Run inside the CAI project with its injected API credentials")
    client = JobSubmissionClient(cluster_address(ROOT), headers={"Authorization": f"Bearer {token.strip()}"})
    if args.operation == "submit":
        from smart_router.data.pilot_bundle import validate_bundle
        validate_bundle(ROOT / config["dataset"])
        if any(job.submission_id == args.submission_id for job in client.list_jobs()):
            raise ValueError("Submission ID already exists; choose a new ID for a rerun")
        print(client.submit_job(**submission))
        if args.wait:
            wait_for_job(client, args.submission_id, config["job_timeout_seconds"])
    elif args.operation == "status":
        print(client.get_job_status(args.submission_id))
    elif args.operation == "logs":
        print(client.get_job_logs(args.submission_id))
    elif args.operation == "stop":
        print(client.stop_job(args.submission_id))


if __name__ == "__main__":
    main()
