"""Launch ordinary CLI processes from CAI's notebook-backed job runtime.

Do not forward sys.argv: PBJ may expose only ipykernel's connection-file args.
The AMP step's identity belongs to its dedicated wrapper, not kernel argv.
"""
import os
from pathlib import Path
import subprocess
import sys


def project_root(script_file=None):
    candidates = []
    if script_file:
        candidates.append(Path(script_file).resolve().parent.parent)
    candidates.extend((Path(os.environ.get("CDSW_PROJECT_DIR") or Path.cwd()),
                       Path.cwd(), Path.cwd().parent))
    for root in candidates:
        if (root / "amp/bootstrap.py").is_file() and (root / ".project-metadata.yaml").is_file():
            return root.resolve()
    raise RuntimeError("Cannot locate the smart-router AMP project; set CDSW_PROJECT_DIR or run from the project directory")


def run(root, script, arguments):
    """Keep the notebook kernel alive and propagate child-process failure."""
    return subprocess.run(
        [sys.executable, "-u", str(root / script), *arguments],
        cwd=str(root), check=True,
    )
