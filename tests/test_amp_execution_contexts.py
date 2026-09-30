"""Run real AMP wrapper source in CAI/PBJ-style namespaces, without cloud calls."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
STEPS = {
    "launch_tensorboard": ("amp/tensorboard_app.py", ["deploy"]),
    "validate_pilot": ("amp/bootstrap.py", ["validate"]),
    "configure_project_resources": ("amp/bootstrap.py", ["resources"]),
    "setup_cluster_environment": ("amp/bootstrap.py", ["cluster-env"]),
    "setup_training_environment": ("amp/bootstrap.py", ["training-env"]),
    "launch_training_cluster": ("amp/bootstrap.py", ["launch"]),
    "run_cluster_smoke": ("amp/jobs.py", ["submit", "--config", "configs/training/cluster-smoke.json",
                                        "--submission-id", "cluster-smoke", "--wait"]),
}


class AMPExecutionContextTests(unittest.TestCase):
    def test_manifest_uses_argument_free_wrappers(self):
        manifest = yaml.safe_load((ROOT / ".project-metadata.yaml").read_text())
        creates = [t for t in manifest["tasks"] if t["type"] == "create_job"]
        self.assertEqual({t["script"] for t in creates}, {f"amp/{name}.py" for name in STEPS})
        for task in creates:
            self.assertNotIn("arguments", task)

    def test_wrappers_strip_kernel_args_in_all_execution_contexts(self):
        with tempfile.TemporaryDirectory() as temp:
            for name, (script, arguments) in STEPS.items():
                source = ROOT / "amp" / f"{name}.py"
                for mode in ("script", "notebook-root", "notebook-subdir", "notebook-env"):
                    with self.subTest(step=name, mode=mode):
                        namespace = {"__name__": "__main__", "__package__": None}
                        if mode == "script":
                            namespace["__file__"] = str(source)
                        cwd = ROOT / "amp" if mode == "notebook-subdir" else ROOT
                        if mode in {"script", "notebook-env"}:
                            cwd = Path(temp)
                        env = {"CDSW_PROJECT_DIR": str(ROOT) if mode == "notebook-env" else ""}
                        with patch.dict(os.environ, env), patch.object(Path, "cwd", return_value=cwd), \
                             patch.object(sys, "path", list(sys.path)), \
                             patch.object(sys, "argv", ["ipykernel_launcher.py", "-f", "/tmp/jupyter/runtime/kernel.json"]), \
                             patch("subprocess.run") as run, \
                             patch("os.execv", side_effect=AssertionError("Do not replace the notebook kernel")):
                            exec(compile(source.read_text(), "<CAI-cell>", "exec"), namespace)
                            run.assert_called_once_with([sys.executable, "-u", str(ROOT / script), *arguments],
                                                        cwd=str(ROOT), check=True)

    def test_wrapper_failure_is_not_reported_as_success(self):
        from amp.entrypoints import run
        failure = subprocess.CalledProcessError(1, ["python", "bootstrap.py", "resources"])
        with patch("subprocess.run", side_effect=failure):
            with self.assertRaises(subprocess.CalledProcessError):
                run(ROOT, "amp/bootstrap.py", ["resources"])

    def test_importing_wrappers_does_not_run_jobs(self):
        with patch("subprocess.run", side_effect=AssertionError("Unexpected job execution")):
            for name in STEPS:
                path = ROOT / "amp" / f"{name}.py"
                exec(compile(path.read_text(), str(path), "exec"), {"__name__": "imported_wrapper"})


if __name__ == "__main__":
    unittest.main()
