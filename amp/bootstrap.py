#!/usr/bin/env python3
"""Setup CLI invoked with explicit arguments by the dedicated CAI job wrappers."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import venv


def project_root():
    candidates = []
    if globals().get("__file__"):
        candidates.append(Path(__file__).resolve().parents[1])
    candidates += [Path(os.environ.get("CDSW_PROJECT_DIR") or Path.cwd()), Path.cwd()]
    for root in candidates:
        if (root / ".project-metadata.yaml").is_file() and (root / "src/smart_router").is_dir():
            return root.resolve()
    raise RuntimeError("Run from the smart-router AMP project directory")


ROOT = project_root()
sys.path[:0] = [str(ROOT), str(ROOT / "src")]


def validate():
    from smart_router.data.pilot_bundle import validate_bundle
    manifest = validate_bundle(ROOT / "data/pilot/pilot-smoke-v1")
    snapshot = json.loads((ROOT / "vendor/ray-serve-cai/SNAPSHOT.json").read_text())
    for name, expected in snapshot["files_sha256"].items():
        expected = snapshot.get("local_modifications", {}).get(name, {}).get("sha256", expected)
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"Cluster source differs from recorded snapshot: {name}")
    print(json.dumps({"dataset": manifest["dataset_id"], "splits": manifest["splits"],
                      "cluster_source_commit": snapshot["source_commit"]}, indent=2))


def setup_environment(kind):
    """Provision one shared environment under a nonblocking inter-process lock."""
    if sys.version_info[:2] != (3, 11):
        raise RuntimeError("AMP setup requires Python 3.11 to match the head and GPU runtime images")
    if ROOT != Path("/home/cdsw"):
        raise RuntimeError("Cluster setup must run in the CAI project at /home/cdsw")
    from cai_integration.project_environment import preflight_project_environment
    preflight_project_environment()
    state = ROOT / ".amp-state"; state.mkdir(exist_ok=True)
    with (state / "environment.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another environment setup is running; retry this AMP step after it finishes") from None
        target = ROOT / (".venv" if kind == "cluster" else ".venv-router-train")
        python = target / "bin/python"
        if not python.exists():
            venv.EnvBuilder(with_pip=True).create(target)
        env = {**os.environ, "PIP_USER": "0", "PYTHONNOUSERSITE": "1"}
        subprocess.run([str(python), "-m", "pip", "install", "-e", f"{ROOT}[{kind}]"], env=env, check=True)
        subprocess.run([str(python), "-m", "pip", "check"], env=env, check=True)
        check = "import ray; assert ray.__version__ == '2.58.0', ray.__version__; print(ray.__version__)"
        if kind == "training":
            check += "; import torch; assert torch.__version__.split('+')[0] == '2.8.0'; print(torch.__version__)"
        subprocess.run([str(python), "-c", check], env=env, check=True)
        freeze = subprocess.check_output([str(python), "-m", "pip", "freeze"], env=env, text=True)
        (state / f"{kind}-environment.txt").write_text(freeze)
        if kind == "cluster":
            from cai_integration.setup_environment import install_nginx
            if not install_nginx():
                raise RuntimeError("nginx installation failed")
    print(f"Verified {kind} environment: {target}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["validate", "resources", "cluster-env", "training-env", "launch"])
    args = parser.parse_args()
    if args.operation == "validate":
        validate()
    elif args.operation == "resources":
        from cai_integration.configure_project_resources import configure_project_resources
        configure_project_resources()
    elif args.operation in {"cluster-env", "training-env"}:
        setup_environment("cluster" if args.operation == "cluster-env" else "training")
    elif args.operation == "launch":
        validate()
        subprocess.run([str(ROOT / ".venv/bin/python"), "-u", str(ROOT / "cai_integration/launch_ray_cluster.py")], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
