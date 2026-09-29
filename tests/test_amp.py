"""Local deployment-contract tests: no cloud mutation or model downloads."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import yaml

from amp.jobs import build_submission, cluster_address, load_config, wait_for_job
from smart_router.data.pilot_bundle import validate_bundle

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data/pilot/pilot-smoke-v1"


class AMPTests(unittest.TestCase):
    def test_manifest_tasks_exist_and_run_sequentially(self):
        manifest = yaml.safe_load((ROOT / ".project-metadata.yaml").read_text())
        tasks = manifest["tasks"]
        for index in range(0, len(tasks) - 1, 2):
            create, run = tasks[index:index + 2]
            self.assertTrue((ROOT / create["script"]).is_file())
            self.assertEqual(create["type"], "create_job")
            self.assertGreater(create["timeout"], 0)
            self.assertEqual(run, {"type": "run_job", "entity_label": create["entity_label"], "wait_for": True})
        self.assertEqual(tasks[-1]["name"], "cluster-smoke")
        self.assertTrue((ROOT / tasks[-1]["script"]).is_file())
        self.assertTrue(all(isinstance(v["default"], str) for v in manifest["environment_variables"].values()))

    def test_amp_starts_head_only_with_no_worker_allocations(self):
        from cai_integration.autoscaling.bootstrap import bootstrap_policy
        config = yaml.safe_load((ROOT / "configs/ray_cluster_config.yaml").read_text())
        policy = bootstrap_policy({**config["ray_cluster"], "worker_runtime_identifier": config["cai"]["worker_runtime_identifier"]})
        self.assertEqual(policy.pools, [])
        self.assertEqual(config["ray_cluster"]["worker_groups"], [])
        self.assertFalse(config["ray_cluster"]["launch_initial_workers"])
        manifest = yaml.safe_load((ROOT / ".project-metadata.yaml").read_text())
        self.assertNotIn("RAY_INITIAL_WORKER_POOLS", manifest["environment_variables"])
        self.assertNotEqual(config["cai"]["head_app_name"], "ray-cluster-head")

    def test_submission_uses_shared_paths_and_excludes_auth(self):
        with patch.dict(os.environ, {"CDSW_APIV2_KEY": "DO_NOT_FORWARD", "CML_API_KEY": "DO_NOT_FORWARD"}):
            payload = build_submission(Path("/home/cdsw"), Path("/home/cdsw/configs/training/cluster-smoke.json"), "trial-01")
        self.assertNotIn("DO_NOT_FORWARD", json.dumps(payload))
        self.assertNotIn("working_dir", payload["runtime_env"])
        self.assertEqual(payload["entrypoint_num_gpus"], 0)
        self.assertIn(".venv-router-train/bin/python", payload["entrypoint"])
        self.assertTrue(payload["runtime_env"]["env_vars"]["PATH"].startswith("/home/cdsw/.venv-router-train/bin:"))
        with self.assertRaises(ValueError):
            build_submission(ROOT, ROOT / "config.json", "../outside")

    def test_cluster_address_is_discovered_from_own_project(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ray_cluster_info.json").write_text(json.dumps({"head_url": "https://training.example"}))
            self.assertEqual(cluster_address(root), "https://training.example/dashboard/")

    def test_collective_settings_reach_training_workers(self):
        config_path = ROOT / "configs/training/cluster-smoke.json"
        config = load_config(config_path)
        payload = build_submission(ROOT, config_path, "smoke", config["collective_env"])
        for key, value in config["collective_env"].items():
            self.assertEqual(payload["runtime_env"]["env_vars"][key], value)
        from scripts.build_amp_bundle import members
        self.assertIn("scripts/setup_cross_node_gpu.fish", members(ROOT))
        setup = (ROOT / "scripts/setup_cross_node_gpu.fish").read_text()
        self.assertIn("vendor/ray-serve-cai/deploy/istio/", setup)
        for name in ("setup_cross_node_gpu.fish", "run_collective_probe.fish"):
            script = (ROOT / "scripts" / name).read_text()
            self.assertIn(".venv-router-train/bin/python", script)
            self.assertNotIn(".venv-vllm/bin/python", script)

    def test_timeout_stops_job(self):
        from unittest.mock import Mock
        client = Mock()
        with self.assertRaises(TimeoutError):
            wait_for_job(client, "smoke", 0)
        client.stop_job.assert_called_once_with("smoke")

    def test_failed_job_propagates_failure(self):
        from unittest.mock import Mock
        client = Mock(); client.get_job_status.return_value = "FAILED"
        with self.assertRaises(RuntimeError):
            wait_for_job(client, "smoke", 5)

    def test_pilot_preserves_coverage_and_unknowns(self):
        manifest = validate_bundle(BUNDLE)
        self.assertEqual(manifest["splits"], {"train": 210, "validation": 30, "calibration": 30, "test": 30})
        self.assertEqual(manifest["class_support"]["FAST"]["unknown"], 54)
        self.assertEqual(manifest["group_count"], 100)

    def test_tampered_data_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bundle"; shutil.copytree(BUNDLE, path)
            with (path / "train.jsonl").open("a") as stream:
                stream.write("{}\n")
            with self.assertRaisesRegex(ValueError, "Checksum"):
                validate_bundle(path)

    def test_masked_unknown_cannot_become_observed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bundle"; shutil.copytree(BUNDLE, path)
            rows = [json.loads(line) for line in (path / "train.jsonl").read_text().splitlines()]
            row = next(r for r in rows if r["targets"]["FAST"] is None)
            row["observation_mask"]["FAST"] = 1
            (path / "train.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
            manifest = json.loads((path / "manifest.json").read_text())
            manifest["files_sha256"]["train.jsonl"] = hashlib.sha256((path / "train.jsonl").read_bytes()).hexdigest()
            (path / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "mask mismatch"):
                validate_bundle(path)

    def test_invalid_smoke_settings_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            value = json.loads((ROOT / "configs/training/cluster-smoke.json").read_text())
            value["steps"] = 0
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "steps"):
                load_config(path)

    def test_bundle_excludes_private_annotation_runs_and_runtime_state(self):
        from scripts.build_amp_bundle import members
        files = members(ROOT)
        self.assertIn("data/pilot/pilot-smoke-v1/train.jsonl", files)
        self.assertIn(".project-metadata.yaml", files)
        self.assertFalse(any(name.startswith(("runs/", "data/raw/", "data/prepared/", ".venv", "training-runs/")) for name in files))

    def test_rendered_launcher_templates_compile(self):
        from jinja2 import Environment, FileSystemLoader, StrictUndefined
        env = Environment(loader=FileSystemLoader(str(ROOT / "cai_integration/templates")), undefined=StrictUndefined)
        context = dict(venv_python="/home/cdsw/.venv/bin/python", project_dir="/home/cdsw", ray_port=6379,
                       dashboard_port=8265, metrics_port=9090, mgmt_cpu=2, mgmt_memory_gb=8,
                       prometheus_host=None, grafana_host=None, grafana_iframe_host=None, grafana_org_id="1",
                       proxy_health_check_period_s=None, proxy_health_check_timeout_s=None,
                       proxy_ready_check_timeout_s=None, proxy_min_draining_period_s=None,
                       head_address="10.0.0.1:6379", node_type="gpu-worker", accelerator_type="L40S",
                       worker_memory_gb=64, worker_cpu=16, worker_gpus=1)
        for template in ("ray_head_launcher.py.j2", "ray_worker_launcher.py.j2"):
            rendered = env.get_template(template).render(**context)
            compile(rendered, template, "exec")


if __name__ == "__main__":
    unittest.main()
