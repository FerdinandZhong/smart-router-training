#!/usr/bin/env python3
"""Build an allowlisted AMP source archive; excludes credentials and run output."""
from pathlib import Path
import hashlib
import json
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from amp.bootstrap import validate


def members(root):
    selected = {".project-metadata.yaml", ".gitignore", "pyproject.toml", "README.md",
                "AGENTS.md", "DESIGN.md", "TODO.md", "project-overview.md",
                "architecture.md", "user-guide.md", "development.md", "component-api.md",
                "configs/ray_cluster_config.yaml", "scripts/build_amp_bundle.py",
                "scripts/export_smoke_training_data.py", "docs/amp-deployment.md",
                "scripts/setup_cross_node_gpu.fish", "scripts/run_collective_probe.fish",
                "scripts/collective_probe.py",
                "docs/ray-first-trial-implementation-plan.md", "tests/test_amp.py",
                "tests/test_amp_execution_contexts.py", "tests/test_amp_environment.py", "tests/test_tensorboard_app.py",
                "tests/run_tensorboard_smoke.py",
                "tests/run_distributed_amp_smoke.py"}
    for folder in ("src", "amp", "ray_serve_cai", "cai_integration", "vendor/ray-serve-cai", "configs/training", "data/pilot/pilot-smoke-v1"):
        for path in (root / folder).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                selected.add(path.relative_to(root).as_posix())
    for path in (root / "docs").rglob("*.md"):
        selected.add(path.relative_to(root).as_posix())
    for folder in ("configs/examples", "data/examples"):
        for path in (root / folder).rglob("*"):
            if path.is_file():
                selected.add(path.relative_to(root).as_posix())
    return sorted(selected)


if __name__ == "__main__":
    validate()
    output = ROOT / "dist"; output.mkdir(exist_ok=True)
    archive = output / "smart-router-training-amp.tar.gz"
    files = members(ROOT)
    with tarfile.open(archive, "w:gz") as tar:
        for name in files:
            path = ROOT / name
            if path.is_symlink():
                raise ValueError(f"Symlinks are not allowed in the AMP bundle: {name}")
            tar.add(path, arcname=name, recursive=False)
    manifest = {"archive": archive.name, "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                "files_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files}}
    (output / "smart-router-training-amp.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Built {archive}: {len(files)} files, {archive.stat().st_size:,} bytes")
