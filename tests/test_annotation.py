"""Offline annotation tests; no network calls or credentials required."""

from copy import deepcopy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from smart_router.annotation import backends
from smart_router.annotation.pipeline import (
    aggregate, plan, prepare, read_json, read_jsonl, resolve_model, run, run_lock,
)
from smart_router.schemas import DataError


ROOT = Path(__file__).resolve().parents[1]


class AnnotationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "run"
        self.frozen = prepare(ROOT / "configs/annotation/mock.json")

    def test_fixture_probabilities_evidence_and_resume(self):
        report = run(self.frozen, self.output)
        self.assertEqual(report["attempts_reserved"], 36)
        labels = read_jsonl(self.output / "silver_labels.jsonl")
        self.assertEqual(labels[0]["targets"], {"FAST": 0.5, "GENERAL": 1.0, "REASONING": 1.0})
        self.assertIsNone(labels[1]["targets"]["REASONING"])
        self.assertEqual(labels[0]["quality"], "synthetic")
        rows = read_jsonl(self.output / "annotated.jsonl")
        for old, new in zip(self.frozen["records"], rows):
            for key in ("input", "targets", "split", "group_id", "metadata"):
                self.assertEqual(old[key], new[key])
        with patch.object(backends, "call", side_effect=AssertionError("Resume should not call models")):
            self.assertEqual(run(self.frozen, self.output), report)

    def test_unknowns_are_not_failures_and_errors_retry_explicitly(self):
        key = "candidate:fixture-1:fast:0"
        self.frozen["mock_responses"][key] = {"error": "http_429"}
        run(self.frozen, self.output)
        row = read_jsonl(self.output / "silver_labels.jsonl")[0]
        self.assertIsNone(row["targets"]["FAST"])
        self.assertEqual(row["classes"]["FAST"]["failed"], 1)
        self.assertEqual(row["classes"]["FAST"]["unknown_trials"], 1)
        with patch.object(backends, "call", side_effect=AssertionError("Errors should be cached")):
            run(self.frozen, self.output)
        original = backends.call
        def recovered(model, body, context, fixtures):
            if context == {"role": "candidate", "example_id": "fixture-1", "candidate": "fast", "trial": 0}:
                return {"text": "Recovered read-only lookup", "actual_model": model["model"], "usage": {}}
            return original(model, body, context, fixtures)
        with patch.object(backends, "call", side_effect=recovered):
            report = run(self.frozen, self.output, retry_errors=True)
        self.assertEqual(report["attempts_reserved"], 37)
        self.assertEqual(read_jsonl(self.output / "silver_labels.jsonl")[0]["targets"]["FAST"], 0.5)
        self.assertTrue(list((self.output / "calls").glob("*.attempt-2.json")))

    def test_disagreement_malformed_low_confidence_abstain(self):
        for judge_value in (
            {"verdict": "fail", "confidence": 0.99, "reason": "Different judgment"},
            "not JSON",
            {"verdict": "pass", "confidence": 0.1, "reason": "Uncertain"},
            {"verdict": "abstain", "confidence": 1.0, "reason": "Missing evidence"},
            {"verdict": "pass", "confidence": True, "reason": "Invalid numeric type"},
        ):
            with self.subTest(judge_value=judge_value), tempfile.TemporaryDirectory() as out:
                frozen = deepcopy(self.frozen)
                frozen["mock_responses"]["judge:fixture-1:general:0:judge-b"] = judge_value
                run(frozen, Path(out) / "run")
                row = read_jsonl(Path(out) / "run/silver_labels.jsonl")[0]
                self.assertIsNone(row["targets"]["GENERAL"])

    def test_budget_reservations_survive_resume(self):
        self.frozen["config"]["max_calls"] = 2
        report = run(self.frozen, self.output)
        self.assertEqual(report["attempts_reserved"], 2)
        self.assertEqual(report["labeled_state_class_pairs"], 0)
        with patch.object(backends, "call", side_effect=AssertionError("Budget must remain exhausted")):
            self.assertEqual(run(self.frozen, self.output, retry_errors=True)["attempts_reserved"], 2)

    def test_output_token_cap_before_network(self):
        self.frozen["config"]["max_reserved_output_tokens"] = 255
        with patch.object(backends, "call", side_effect=AssertionError("No calls fit")):
            report = run(self.frozen, self.output)
        self.assertEqual(report["attempts_reserved"], 0)

    def test_changed_input_rejected_and_lock_exclusive(self):
        run(self.frozen, self.output)
        self.frozen["contracts"]["fixture-1"]["version"] = "changed"
        with self.assertRaisesRegex(DataError, "changed"):
            run(self.frozen, self.output)
        with run_lock(self.output):
            with self.assertRaisesRegex(DataError, "locked"):
                run(self.frozen, self.output)

    def test_candidate_input_and_judge_blinding(self):
        original = backends.call
        seen = []
        self.frozen["records"][0]["label_evidence"] = {"reference_answer": "SECRET_REFERENCE"}
        def capture(model, body, context, fixtures):
            content = json.dumps(body)
            self.assertNotIn("SECRET_REFERENCE", content)
            if context["role"] == "candidate":
                self.assertNotIn("required_conditions", content)
            else:
                self.assertNotIn('"class_id"', content)
                self.assertNotIn('"example_id"', content)
                self.assertNotIn('"split"', content)
                for candidate in self.frozen["config"]["candidates"]:
                    self.assertNotIn(candidate["model"], content)
            seen.append(context["role"])
            return original(model, body, context, fixtures)
        with patch.object(backends, "call", side_effect=capture):
            run(self.frozen, self.output)
        self.assertEqual(set(seen), {"candidate", "judge"})

    def test_uncertainty_and_custom_class_names(self):
        result = aggregate([{"verdict": "pass"}], 1)
        self.assertEqual(result["probability"], 1.0)
        self.assertLess(result["wilson_95_interval"][0], 0.21)
        self.assertIsNone(aggregate([{"verdict": None}], 1)["probability"])
        for record in self.frozen["records"]:
            record["targets"]["values"]["CUSTOM_SMALL"] = record["targets"]["values"].pop("FAST")
        self.frozen["config"]["candidates"][0]["class_id"] = "CUSTOM_SMALL"
        run(self.frozen, self.output)
        self.assertEqual(read_jsonl(self.output / "silver_labels.jsonl")[0]["targets"]["CUSTOM_SMALL"], 0.5)

    def test_preflight_model_constraints(self):
        config = read_json(ROOT / "configs/annotation/mock.json")
        for key in ("records", "task", "contracts", "mock_responses"):
            config[key] = str((ROOT / "configs/annotation" / config[key]).resolve())
        path = Path(self.temp.name) / "config.json"
        for mutation, message in (
            (lambda c: c["judges"][0].update(model=c["candidates"][0]["model"]), "different model"),
            (lambda c: c["candidates"][1].update(model=c["candidates"][0]["model"]), "distinct deployed"),
            (lambda c: c["candidates"][0].update(class_id="UNKNOWN"), "customer-defined class"),
        ):
            modified = deepcopy(config)
            mutation(modified)
            path.write_text(json.dumps(modified))
            with self.assertRaisesRegex(DataError, message):
                prepare(path)

    def test_live_requires_explicit_flag_and_credentials(self):
        for model in self.frozen["config"]["candidates"] + self.frozen["config"]["judges"]:
            model.update(api="responses", api_key_env="TEST_MISSING_ANNOTATION_KEY")
        with self.assertRaisesRegex(DataError, "--live"):
            run(self.frozen, self.output)
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(DataError, "credential"):
                run(self.frozen, self.output, live=True)
        self.assertFalse(self.output.exists())

    def test_live_example_models_and_call_plan(self):
        with patch.dict(os.environ, {"ANNOTATION_JUDGE_MODEL": "independent-judge"}):
            frozen = prepare(ROOT / "configs/annotation/models.example.json")
        self.assertEqual([m["model"] for m in frozen["config"]["candidates"]], ["gpt-5.6-luna", "gpt-6-sol", "gpt-6-astra"])
        self.assertEqual(plan(frozen)["total_calls_without_retries"], 36)

    def test_endpoint_and_request_validation(self):
        base = {"id": "test", "api": "responses", "model": "model", "base_url": "https://api.example.com/v1", "api_key_env": "KEY"}
        model = resolve_model(base)
        body = backends.request_body(model, "SYSTEM", "INPUT")
        self.assertFalse(body["store"])
        self.assertEqual(body["input"], "INPUT")
        self.assertNotIn("Authorization", body)
        for url in ("https://secret@api.example.com/v1", "https://api.example.com/v1?key=secret", "http://example.com/v1"):
            with self.assertRaises(DataError):
                resolve_model({**base, "base_url": url})
        with self.assertRaises(DataError):
            resolve_model({**base, "generation": {"model": "override"}})
        chat = resolve_model({**base, "api": "chat_completions"})
        self.assertEqual(backends.request_body(chat, "SYSTEM", "INPUT")["messages"][1]["content"], "INPUT")

    def test_api_response_parsing_and_truncation(self):
        response = {"status": "completed", "model": "snapshot", "output": [{"type": "reasoning"},
            {"type": "message", "content": [{"type": "output_text", "text": "answer"}]}]}
        self.assertEqual(backends.parse_response("responses", response)["text"], "answer")
        with self.assertRaises(backends.CallError):
            backends.parse_response("responses", {**response, "status": "incomplete"})
        chat = {"choices": [{"finish_reason": "stop", "message": {"content": "answer"}}]}
        self.assertEqual(backends.parse_response("chat_completions", chat)["text"], "answer")
        for reason in ("length", "tool_calls", "content_filter"):
            chat["choices"][0]["finish_reason"] = reason
            with self.assertRaises(backends.CallError):
                backends.parse_response("chat_completions", chat)

    def test_http_payload_auth_and_error_redaction(self):
        model = resolve_model({"id": "test", "api": "responses", "model": "model",
                               "base_url": "https://api.example.com/v1", "api_key_env": "TEST_API_KEY"})
        body = backends.request_body(model, "SYSTEM", "INPUT")
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value = io.BytesIO(json.dumps({
            "status": "completed", "model": "actual-snapshot", "usage": {"input_tokens": 10},
            "output": [{"type": "message", "content": [{"type": "output_text", "text": "answer"}]}],
        }).encode())
        with patch.dict(os.environ, {"TEST_API_KEY": "test-secret"}), patch.object(backends.urllib.request, "build_opener", return_value=opener):
            result = backends.call(model, body, {"candidate": "PRIVATE_ROLE"}, {})
            self.assertEqual(result["actual_model"], "actual-snapshot")
            request = opener.open.call_args.args[0]
            self.assertEqual(request.full_url, "https://api.example.com/v1/responses")
            self.assertEqual(request.get_header("Authorization"), "Bearer test-secret")
            self.assertNotIn(b"PRIVATE_ROLE", request.data)
            self.assertNotIn(b"test-secret", request.data)
            opener.open.side_effect = urllib.error.HTTPError(request.full_url, 429, "sensitive-provider-error", {}, None)
            with self.assertRaisesRegex(backends.CallError, "^http_429$"):
                backends.call(model, body, {}, {})

    def test_interrupted_call_reservation_is_not_lost(self):
        self.frozen["config"]["max_attempts_per_call"] = 1
        with patch.object(backends, "call", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                run(self.frozen, self.output)
        self.assertFalse((self.output / "run.lock").exists())
        self.assertEqual(len(read_jsonl(self.output / "attempts.jsonl")), 1)
        report = run(self.frozen, self.output)
        self.assertEqual(report["attempts_reserved"], 34)
        first = read_jsonl(self.output / "silver_labels.jsonl")[0]
        self.assertEqual(first["classes"]["FAST"]["unknown_trials"], 1)

    def test_external_receipt_is_bound_to_request_and_model(self):
        model = resolve_model({"id": "external", "api": "external", "model": "requested-model",
                               "response_directory": self.temp.name})
        body = backends.request_body(model, "SYSTEM", "INPUT")
        context = {"role": "candidate", "example_id": "e1", "trial": 0}
        key = backends.external_key(model, body, context)
        path = Path(self.temp.name) / (key + ".json")
        receipt = {"request_hash": key, "requested_model": model["model"], "actual_model": None,
                   "text": "Observed output", "execution": {"tool": "test_executor", "task_name": "test-1", "model_override": model["model"]}}
        path.write_text(json.dumps(receipt))
        with patch.object(backends.urllib.request, "build_opener", side_effect=AssertionError("No HTTP for imported receipts")):
            result = backends.call(model, body, context, {})
        self.assertEqual(result["text"], "Observed output")
        self.assertIsNone(result["actual_model"])
        self.assertEqual(len(result["response_sha256"]), 64)
        with self.assertRaisesRegex(backends.CallError, "missing"):
            backends.call(model, {**body, "model": "different-request"}, context, {})
        receipt["execution"]["model_override"] = "wrong-model"
        path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(backends.CallError, "execution_model_mismatch"):
            backends.call(model, body, context, {})
        receipt["request_hash"] = "tampered"
        path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(backends.CallError, "identity_mismatch"):
            backends.call(model, body, context, {})

    def test_external_import_needs_no_api_key_and_does_not_claim_inference_latency(self):
        for model in self.frozen["config"]["candidates"] + self.frozen["config"]["judges"]:
            model.update(api="external", response_directory=self.temp.name)
        original = backends.call
        def canned(model, body, context, fixtures):
            return original({**model, "api": "mock"}, body, context, fixtures)
        with patch.dict(os.environ, {}, clear=True), patch.object(backends, "call", side_effect=canned):
            report = run(self.frozen, self.output, live=True)
        self.assertTrue(report["external_execution"])
        self.assertEqual(report["synthetic_source_examples"], 2)
        self.assertIn("not measured or enforced", report["note"])
        row = read_jsonl(self.output / "silver_labels.jsonl")[0]
        self.assertTrue(row["source_is_synthetic"])
        call = read_json(next((self.output / "calls").glob("*.json")))
        self.assertIn("import_latency_seconds", call)
        self.assertNotIn("latency_seconds", call)

    def test_batch_001_configuration_and_receipts(self):
        frozen = prepare(ROOT / "configs/annotation/batch-001.json")
        self.assertEqual([m["model"] for m in frozen["config"]["candidates"]], ["gpt-5.6-sol", "gpt-5.6-terra"])
        self.assertEqual(frozen["config"]["judges"][0]["model"], "gpt-6-astra")
        self.assertNotIn("review_note", frozen["contracts"]["fixture-2"])
        report = run(frozen, self.output, live=True)
        self.assertEqual(report["labeled_state_class_pairs"], 4)
        labels = read_jsonl(self.output / "silver_labels.jsonl")
        self.assertEqual(labels[1]["targets"], {"GPT56_SOL": 1.0, "GPT56_TERRA": 0.0})

    def test_credential_file_is_not_serialized_into_request(self):
        token_file = Path(self.temp.name) / "credential"
        token_file.write_text("test-file-secret\n")
        model = resolve_model({"id": "file", "api": "chat_completions", "model": "test",
                               "base_url": "https://example.com/v1", "api_key_file": str(token_file)})
        self.assertEqual(backends.credential(model), "test-file-secret")
        self.assertNotIn("test-file-secret", json.dumps(backends.request_body(model, "system", "input")))
        with self.assertRaisesRegex(DataError, "exactly one"):
            resolve_model({**model, "api_key_env": "ALSO_SET"})
        token_file.write_text("")
        with self.assertRaisesRegex(DataError, "empty"):
            backends.credential(model)

    def test_candidate_stage_does_not_call_judges_or_repeat_candidates(self):
        original = backends.call
        def only_candidates(model, body, context, fixtures):
            self.assertEqual(context["role"], "candidate")
            return original(model, body, context, fixtures)
        with patch.object(backends, "call", side_effect=only_candidates):
            report = run(self.frozen, self.output, candidates_only=True)
        self.assertEqual(report["statuses"], {"ok": 12})
        def only_judges(model, body, context, fixtures):
            self.assertEqual(context["role"], "judge")
            return original(model, body, context, fixtures)
        with patch.object(backends, "call", side_effect=only_judges):
            report = run(self.frozen, self.output)
        self.assertEqual(report["attempts_reserved"], 36)

    def test_pending_external_candidates_consume_no_import_budget(self):
        for model in self.frozen["config"]["candidates"] + self.frozen["config"]["judges"]:
            model.update(api="external", response_directory=self.temp.name)
        with patch.object(backends, "call", side_effect=AssertionError("No receipts available")):
            report = run(self.frozen, self.output, live=True, candidates_only=True)
        self.assertEqual(report["attempts_reserved"], 0)
        self.assertEqual(report["statuses"], {"pending_external_execution": 12})

    def test_qwen_thinking_switch_is_explicit_and_forwarded(self):
        base = {"id": "qwen", "api": "chat_completions", "model": "qwen",
                "base_url": "https://example.com/v1", "api_key_env": "QWEN_KEY",
                "generation": {"chat_template_kwargs": {"enable_thinking": False}, "top_k": 20}}
        model = resolve_model(base)
        self.assertEqual(backends.request_body(model, "s", "u")["chat_template_kwargs"], {"enable_thinking": False})
        with self.assertRaisesRegex(DataError, "booleans"):
            resolve_model({**base, "generation": {"chat_template_kwargs": {"enable_thinking": "false"}}})


if __name__ == "__main__":
    unittest.main()
