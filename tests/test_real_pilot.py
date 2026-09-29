"""Leakage boundaries and executable-format checks for recorded trajectories."""

from copy import deepcopy
import importlib.util
from pathlib import Path
import tempfile
import unittest

from smart_router.data.swe_gym import clean_null_fields, source_states
from smart_router.schemas import canonical_json


class SourceTests(unittest.TestCase):
    def row(self):
        return {"instance_id": "org__repo-123", "run_id": "recorded-run", "resolved": True,
                "tools": [{"type": "function", "function": {"name": "execute_bash", "parameters": {"type": "object", "properties": {"command": {"type": "string"}, "unused": None}, "required": ["command"]}}}],
                "messages": [{"role": "system", "content": "Runtime instructions"},
                             {"role": "user", "content": "Fix issue"},
                             {"role": "assistant", "tool_calls": [{"function": {"name": "execute_bash", "arguments": '{"command":"cat file.py"}'}}]},
                             {"role": "tool", "content": "Visible source\n" + "x = 1\n" * 100},
                             {"role": "assistant", "content": "HELD_OUT_NEXT_ACTION", "tool_calls": [{"function": {"name": "execute_bash", "arguments": '{"command":"pytest"}'}}]},
                             {"role": "tool", "content": "FUTURE_TEST_SUCCESS"}]}

    def test_exact_pre_call_prefix_and_outcomes_excluded(self):
        row = self.row()
        record = source_states(row, 12)[0]
        self.assertEqual(record["input"]["state"]["messages"], clean_null_fields(row["messages"][:4]))
        self.assertNotIn("HELD_OUT_NEXT_ACTION", canonical_json(record["input"]))
        self.assertNotIn("FUTURE_TEST_SUCCESS", canonical_json(record["input"]))
        self.assertNotIn("resolved", canonical_json(record["input"]))
        self.assertEqual(record["metadata"]["source_message_index"], 4)
        self.assertEqual(record["group_id"], row["instance_id"])
        self.assertTrue(record["label_evidence"]["source_trace"]["resolved"])
        self.assertFalse(record["metadata"]["synthetic"])

    def test_filter_uses_only_prior_observations_and_never_truncates(self):
        row = self.row()
        row["messages"][3]["content"] = "Empty directory"
        row["messages"][5]["content"] = "Long future observation " * 200
        self.assertEqual(source_states(row, 0), [])
        self.assertEqual(source_states(self.row(), 0, max_characters=10), [])

    def test_null_padding_removed_without_modifying_text(self):
        value = {"text": "null in code should stay", "unused": None, "nested": [{"x": 1, "pad": None}]}
        self.assertEqual(clean_null_fields(value), {"text": "null in code should stay", "nested": [{"x": 1}]})


@unittest.skipUnless(importlib.util.find_spec("jsonschema"), "optional annotation dependency not installed")
class ToolContractTests(unittest.TestCase):
    def test_tool_arguments_and_json_are_validated(self):
        from smart_router.annotation.checks import check_action, validate_tools
        record = source_states(SourceTests().row(), 0)[0]
        validate_tools(record["input"]["state"])
        self.assertTrue(check_action(record, '{"tool":"execute_bash","arguments":{"command":"pytest"}}')["passed"])
        for text in ('{"tool":"execute_bash","arguments":{}}', '{"tool":"unknown","arguments":{}}',
                     '{"tool":"execute_bash","arguments":{"command":3}}', '```json\n{}\n```'):
            self.assertFalse(check_action(record, text)["passed"])

    def test_judge_cannot_override_invalid_action_schema(self):
        from smart_router.annotation.pipeline import prepare, run, read_jsonl
        root = Path(__file__).resolve().parents[1]
        frozen = prepare(root / "configs/annotation/mock.json")
        state = source_states(SourceTests().row(), 0)[0]["input"]
        for record in frozen["records"]:
            record["input"] = deepcopy(state)
        with tempfile.TemporaryDirectory() as tmp:
            run(frozen, Path(tmp) / "run")
            labels = read_jsonl(Path(tmp) / "run/silver_labels.jsonl")
            self.assertTrue(all(v == 0 for r in labels for v in r["targets"].values()))
            trial = labels[0]["classes"]["GENERAL"]["trials"][0]
            self.assertEqual(trial["judges"][0]["verdict"], "pass")
            self.assertEqual(trial["verdict"], "fail")
            self.assertFalse(trial["deterministic_check"]["passed"])


if __name__ == "__main__":
    unittest.main()
