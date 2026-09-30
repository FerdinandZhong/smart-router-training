"""Child-process environments isolated from CAI's injected Python add-ons."""
import os
from pathlib import Path


def isolated_environment(root, python, base=None):
    env = dict(os.environ if base is None else base)
    env.pop("PYTHONHOME", None)
    env["PYTHONPATH"] = os.pathsep.join([str(Path(root) / "src"), str(root)])
    env["PYTHONNOUSERSITE"] = "1"
    env["PIP_USER"] = "0"
    binary_dir = str(Path(python).parent)
    paths = env.get("PATH", "/usr/bin:/bin").split(os.pathsep)
    env["PATH"] = os.pathsep.join([binary_dir, *(p for p in paths if p != binary_dir)])
    return env
