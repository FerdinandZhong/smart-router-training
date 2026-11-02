"""Training dashboard API and readiness gate with a fake Ray client: no Ray, CAI or network."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import patch

import yaml

from amp.cluster_ready import gpu_nodes, wait_ready
from amp.jobs import build_submission
from amp.training_demo.monitor import Dashboard, make_handler

ROOT = Path(__file__).resolve().parents[1]
HEADERS = {"Content-Type": "application/json", "X-Training-Dashboard": "1"}


def node(alive=True, gpus=1, node_id="n"):
    return {"node_id": node_id, "alive": alive,"resources": {"CPU": 12, "GPU": gpus} if gpus else {"CPU": 8}}


class FakeRay:
    def __init__(self):
        self.jobs, self.submitted, self.stopped = {}, [], []

    def list_jobs(self):
        return [SimpleNamespace(submission_id=k, status=v) for k, v in self.jobs.items()]

    def submit_job(self, **kwargs):
        self.submitted.append(kwargs)
        self.jobs[kwargs["submission_id"]] = "RUNNING"

    def get_job_status(self, job_id):
        return self.jobs[job_id]

    def get_job_logs(self, job_id):
        return f"logs for {job_id}"

    def stop_job(self, job_id):
        self.stopped.append(job_id)
        return True


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp()).resolve()
        (cls.root / "configs/training").mkdir(parents=True)
        shutil.copy(ROOT / "configs/training/cluster-smoke.json", cls.root / "configs/training")
        shutil.copytree(ROOT / "data/pilot/pilot-smoke-v1", cls.root / "data/pilot/pilot-smoke-v1")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root)

    def setUp(self):
        for name in ("training-jobs", "training-runs"):
            shutil.rmtree(self.root / name, ignore_errors=True)
        self.ray, self.nodes = FakeRay(), [node(node_id="a"), node(node_id="b")]
        self.start(Dashboard(self.root, client=lambda: self.ray, nodes=lambda: self.nodes))

    def start(self, dashboard):
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(dashboard))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.url = f"http://127.0.0.1:{server.server_port}"

    def call(self, path, body=None, headers=HEADERS):
        request = urllib.request.Request(self.url + path, None if body is None else json.dumps(body).encode(),
                                         {} if body is None else headers)
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def pass_gate(self, success='{"initial": {}, "resume": {}}', node_ids=("a", "b")):
        run = self.root / "training-runs/smoke-ok"
        shutil.rmtree(run, ignore_errors=True)
        run.mkdir(parents=True)
        (run / "SUCCESS.json").write_text(success)
        (run / "run-manifest.json").write_text(json.dumps(
            {"config": {"purpose": "infrastructure_smoke", "use_gpu": True, "num_workers": len(node_ids)}}))
        for rank, node_id in enumerate(node_ids):
            (run / f"initial-worker-{rank}.json").write_text(json.dumps({"rank": rank, "ray_node_id": node_id}))

    def gate_passed(self):
        return self.call("/api/cluster")[1]["smoke_gate"]["passed"]

    def test_gate_needs_valid_evidence_from_current_alive_nodes(self):
        self.pass_gate()
        self.assertTrue(self.gate_passed())
        for success in ("not json", "{}", '{"initial": {}}'):
            self.pass_gate(success=success)
            self.assertFalse(self.gate_passed(), success)
        self.pass_gate(node_ids=("a", "a"))  # both ranks on one node
        self.assertFalse(self.gate_passed())
        self.pass_gate()
        self.nodes = [node(node_id="c"), node(node_id="d")]  # workers replaced since the smoke
        self.assertFalse(self.gate_passed())

    def test_smoke_output_outside_project_root_is_rejected(self):
        config = json.loads((self.root / "configs/training/cluster-smoke.json").read_text())
        (self.root / "configs/training/escape.json").write_text(json.dumps({**config, "output_dir": "../outside-project"}))
        code, error = self.call("/api/jobs", {"kind": "cluster_smoke", "submission_id": "esc",
                                              "config": {"config_path": "configs/training/escape.json"}})
        self.assertEqual(code, 400)
        self.assertIn("outside the project root", error["error"])
        self.assertEqual(self.ray.submitted, [])

    def test_smoke_entrypoint_enforces_job_timeout(self):
        self.call("/api/jobs", {"kind": "cluster_smoke", "submission_id": "t"})
        self.assertTrue(self.ray.submitted[0]["entrypoint"].startswith("timeout --kill-after=60 900 "))
        self.assertTrue(build_submission(ROOT, ROOT / "c.json", "x")["entrypoint"].startswith(str(ROOT)))

    def test_submit_failure_does_not_return_exception_text(self):
        def fail(**kwargs):
            raise RuntimeError("Authorization: Bearer SECRET-SENTINEL")
        self.ray.submit_job = fail
        code, error = self.call("/api/jobs", {"kind": "cluster_smoke", "submission_id": "f"})
        self.assertEqual(code, 502)
        self.assertNotIn("SECRET-SENTINEL", json.dumps(error))
        self.assertNotIn("SECRET-SENTINEL", (self.root / "training-jobs/f/events.jsonl").read_text())

    def sft(self, sid="sft-1", **dataset):
        return {"kind": "sft", "submission_id": sid, "config": {"method": "sft", "weights": {"source": "hub", "location": "org/m"},
                "dataset": {"source": "file", "location": "data/train.jsonl", **dataset}}}

    def test_smoke_submits_and_reports_observed_ray_status(self):
        code, job = self.call("/api/jobs", {"kind": "cluster_smoke", "submission_id": "smoke-1"})
        self.assertEqual((code, job["status"]), (201, "RUNNING"))
        self.assertIn("smart_router.training.cluster_smoke", self.ray.submitted[0]["entrypoint"])
        record = self.root / "training-jobs/smoke-1"
        self.assertEqual(json.loads((record / "job.json").read_text())["kind"], "cluster_smoke")
        self.ray.jobs["smoke-1"] = "SUCCEEDED"
        self.assertEqual(self.call("/api/jobs/smoke-1")[1]["status"], "SUCCEEDED")
        self.assertEqual([j["status"] for j in self.call("/api/jobs")[1]["jobs"]], ["SUCCEEDED"])
        states = [json.loads(line)["state"] for line in (record / "events.jsonl").read_text().splitlines()]
        self.assertEqual(states, ["submitted", "RUNNING", "SUCCEEDED"])
        self.assertEqual(self.call("/api/jobs/smoke-1/logs")[1]["logs"], "logs for smoke-1")

    def test_duplicate_id_is_rejected_without_overwrite(self):
        self.call("/api/jobs", {"kind": "cluster_smoke", "submission_id": "dup"})
        before = (self.root / "training-jobs/dup/job.json").read_text()
        self.assertEqual(self.call("/api/jobs", {"kind": "cluster_smoke", "submission_id": "dup"})[0], 409)
        self.assertEqual(len(self.ray.submitted), 1)
        self.assertEqual((self.root / "training-jobs/dup/job.json").read_text(), before)
        self.assertEqual(self.call("/api/jobs", {"kind": "cluster_smoke", "submission_id": "../x"})[0], 400)

    def test_smoke_needs_two_alive_gpu_nodes(self):
        self.nodes = [node(), node(alive=False), node(gpus=0)]
        self.assertEqual(self.call("/api/jobs", {"kind": "cluster_smoke", "submission_id": "s"})[0], 409)
        self.assertEqual(self.ray.submitted, [])

    def test_training_kinds_need_gate_then_report_trainer_not_implemented(self):
        code, error = self.call("/api/jobs", self.sft())
        self.assertEqual((code, error["error"]), (409, "Cluster smoke has not passed"))
        self.assertFalse((self.root / "training-jobs/sft-1").exists())
        self.pass_gate()
        code, error = self.call("/api/jobs", {**self.sft("grpo-1"), "kind": "grpo"})
        self.assertEqual(code, 400)  # method must match kind
        code, error = self.call("/api/jobs", self.sft())
        self.assertEqual((code, error["error"]), (409, "trainer not implemented"))
        self.assertEqual(self.ray.submitted, [])
        self.assertEqual(self.call("/api/jobs/sft-1")[1]["status"], "NOT_SUBMITTED")

    def test_cluster_reports_launch_reasons(self):
        info = self.call("/api/cluster")[1]
        self.assertEqual((info["gpu_nodes_alive"], info["smoke_gate"]["passed"], info["launch"]["cluster_smoke"]),
                         (2, False, None))
        self.assertEqual(info["launch"]["sft"], "Cluster smoke has not passed")
        self.pass_gate()
        info = self.call("/api/cluster")[1]
        self.assertEqual((info["smoke_gate"]["run_id"], info["launch"]["grpo"]), ("smoke-ok", "Trainer not implemented"))
        self.nodes = [node()]
        self.assertIn("Needs 2", self.call("/api/cluster")[1]["launch"]["cluster_smoke"])

    def test_paths_outside_project_root_are_rejected(self):
        self.pass_gate()
        for location in ("/etc/passwd", "../outside.jsonl"):
            self.assertEqual(self.call("/api/jobs", self.sft(location=location))[0], 400, location)
        self.assertEqual(self.call("/api/jobs", self.sft(source="hub", location="org/dataset", validation="split"))[0], 409)
        code, _ = self.call("/api/jobs", {"kind": "cluster_smoke", "submission_id": "s", "config": {"config_path": "../x.json"}})
        self.assertEqual(code, 400)
        self.assertEqual(self.ray.submitted, [])

    def test_missing_key_or_cluster_info_is_an_explicit_503(self):
        self.start(Dashboard(self.root))
        with patch.dict(os.environ, {"CDSW_APIV2_KEY": "", "CML_API_KEY": ""}):
            code, error = self.call("/api/jobs")
            self.assertEqual(code, 503)
            self.assertIn("API key", error["error"])
            self.assertEqual(self.call("/api/cluster")[0], 503)
        with patch.dict(os.environ, {"CDSW_APIV2_KEY": "SECRET-VALUE"}):
            code, error = self.call("/api/jobs")
            self.assertEqual(code, 503)
            self.assertIn("ray_cluster_info.json", error["error"])
            self.assertNotIn("SECRET-VALUE", json.dumps(error))

    def test_stop_requests_ray_stop_and_records_event(self):
        self.call("/api/jobs", {"kind": "cluster_smoke", "submission_id": "s"})
        self.assertEqual(self.call("/api/jobs/s/stop", {})[1], {"stopped": True})
        self.assertEqual(self.ray.stopped, ["s"])
        self.assertIn("stop_requested", (self.root / "training-jobs/s/events.jsonl").read_text())
        self.assertEqual(self.call("/api/jobs/unknown/stop", {})[0], 404)

    def test_state_changes_require_json_and_same_origin_header(self):
        body = {"kind": "cluster_smoke", "submission_id": "csrf"}
        self.assertEqual(self.call("/api/jobs", body, {"Content-Type": "application/json"})[0], 403)
        self.assertEqual(self.call("/api/jobs", body, {"Content-Type": "text/plain", "X-Training-Dashboard": "1"})[0], 415)
        self.assertEqual(self.call("/api/jobs/x/stop", {}, {"Content-Type": "application/json"})[0], 403)
        self.assertEqual(self.ray.submitted, [])

    def test_submission_can_name_another_module(self):
        payload = build_submission(ROOT, ROOT / "c.json", "x", module="smart_router.training.other")
        self.assertIn("-m smart_router.training.other", payload["entrypoint"])


class ReadinessTests(unittest.TestCase):
    def test_only_alive_nodes_with_gpus_count(self):
        self.assertEqual(len(gpu_nodes([node(), node(alive=False), node(gpus=0)])), 1)

    def test_ready_after_workers_join_and_tolerates_fetch_errors(self):
        answers = [RuntimeError("starting"), [node()], [node(), node()]]

        def fetch():
            value = answers.pop(0)
            if isinstance(value, Exception):
                raise value
            return value
        ok, nodes = wait_ready(fetch, timeout=100, sleep=lambda s: None, clock=iter(range(0, 100)).__next__)
        self.assertTrue(ok)
        self.assertEqual(len(nodes), 2)

    def test_timeout_returns_observed_nodes(self):
        ok, nodes = wait_ready(lambda: [node(), node(alive=False)], timeout=3, interval=1,
                               sleep=lambda s: None, clock=iter(range(0, 100)).__next__)
        self.assertFalse(ok)
        self.assertEqual([n["alive"] for n in nodes], [True, False])


class DeploymentContractTests(unittest.TestCase):
    def test_gpu_worker_group_and_amp_overrides(self):
        group, = yaml.safe_load((ROOT / "configs/ray_cluster_config.yaml").read_text())["ray_cluster"]["worker_groups"]
        self.assertEqual({k: group[k] for k in ("count", "cpu", "memory", "gpus", "accelerator_type", "input_template")},
                         {"count": 2, "cpu": 12, "memory": 80, "gpus": 1, "accelerator_type": "L40S", "input_template": True})
        manifest = yaml.safe_load((ROOT / ".project-metadata.yaml").read_text())
        defaults = {k: v["default"] for k, v in manifest["environment_variables"].items()}
        self.assertEqual([defaults[k] for k in ("RAY_WORKER_CPU", "RAY_WORKER_MEMORY", "RAY_WORKER_GPUS", "RAY_WORKER_ACCELERATOR_TYPE")],
                         ["12", "80", "1", "L40S"])
        self.assertIn("TRAINING_DASHBOARD_SUBDOMAIN", defaults)
        names = [t["name"] for t in manifest["tasks"] if t["type"] == "create_job"]
        self.assertEqual(names[names.index("launch_training_cluster"):][:4],
                         ["launch_training_cluster", "launch_training_dashboard", "launch_tensorboard", "check_cluster_ready"])
        self.assertEqual(names[-1], "cluster-smoke")

    def test_dashboard_application_is_authenticated_cpu_only(self):
        from amp.training_dashboard_app import application_spec
        spec = application_spec(ROOT, {})
        self.assertEqual((spec["num_gpus"], spec["bypass_authentication"]), (0, False))
        self.assertTrue((ROOT / spec["script"]).is_file())


if __name__ == "__main__":
    unittest.main()
