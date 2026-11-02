#!/usr/bin/env python3
"""CAI application wrapper: argument-free, independent of Jupyter kernel arguments."""
import os
from pathlib import Path
import sys


def main():
    script_file = globals().get("__file__")
    roots = [Path(script_file).resolve().parent.parent] if script_file else []
    roots += [Path(os.environ.get("CDSW_PROJECT_DIR") or Path.cwd()), Path.cwd(), Path.cwd().parent]
    root = next((p for p in roots if (p / "amp/entrypoints.py").is_file()), None)
    if root is None:
        raise RuntimeError("Cannot locate amp/entrypoints.py; run from the AMP project or set CDSW_PROJECT_DIR")
    sys.path.insert(0, str(root.resolve()))
    from amp.entrypoints import project_root
    from amp.training_dashboard_app import serve
    serve(project_root(script_file))


if __name__ == "__main__":
    main()
