#!/usr/bin/env python3
"""CAI job wrapper: explicit operation, independent of Jupyter kernel arguments."""
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
    from amp.entrypoints import project_root, run
    run(project_root(script_file), 'amp/bootstrap.py', ['launch'])


if __name__ == "__main__":
    main()
