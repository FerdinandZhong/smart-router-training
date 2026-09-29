"""Campaign execution boundaries, frozen inputs and receipt integrity."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import annotation_campaign as campaign


class CampaignTests(unittest.TestCase):
    def events(self, answer="{\"verdict\":\"pass\"}"):
        return [
            {"type": "thread.started", "thread_id": "thread-1"},
            {"type": "turn.started"},
            {"type": "item.completed", "item": {"type": "agent_message", "text": answer}},
            {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 5}},
        ]

    def parse(self, events, answer='{"verdict":"pass"}', code=0):
        return campaign.parse_cli("\n".join(map(json.dumps, events)), answer, code)

    def test_cli_captures_real_thread_and_usage(self):
        thread, usage = self.parse(self.events())
        self.assertEqual(thread, "thread-1")
        self.assertEqual(usage["input_tokens"], 10)

    def test_archived_completion_can_be_recovered_without_claiming_exit_code(self):
        self.assertEqual(self.parse(self.events(), code=None)[0], "thread-1")
        with self.assertRaises(ValueError):
            self.parse(self.events()[:-1], code=None)

    def test_cli_rejects_tools_even_if_answer_looks_correct(self):
        events = self.events()
        events.insert(2, {"type": "item.completed", "item": {"type": "command_execution", "command": "cat other-labels.json"}})
        with self.assertRaises(ValueError):
            self.parse(events)

    def test_known_startup_warning_is_not_tool_use_but_other_errors_are_rejected(self):
        events = self.events()
        events.insert(1, {"type": "item.completed", "item": {"type": "error", "message":
            "Under-development features enabled: skip_host_skill_discovery. To suppress this warning, set config."}})
        self.assertEqual(self.parse(events)[0], "thread-1")
        events[1]["item"]["message"] = "Model execution failed"
        with self.assertRaises(ValueError):
            self.parse(events)

    def test_cli_rejects_failure_missing_completion_and_mismatched_answer(self):
        for events, answer, code in ((self.events(), "different", 0), (self.events()[:-1], '{"verdict":"pass"}', 0),
                                     (self.events(), '{"verdict":"pass"}', 1)):
            with self.subTest(events=events, code=code):
                with self.assertRaises(ValueError):
                    self.parse(events, answer, code)

    def test_frozen_file_cannot_be_replaced_with_different_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            campaign.save_once(path, {"model": "original"})
            campaign.save_once(path, {"model": "original"})
            with self.assertRaises(ValueError):
                campaign.save_once(path, {"model": "replacement"})
            self.assertEqual(json.loads(path.read_text()), {"model": "original"})

    def test_command_keeps_requested_model_and_read_only_isolation(self):
        cmd = campaign.cli_command("gpt-5.6-sol", Path("/tmp/answer.json"))
        self.assertEqual(cmd[cmd.index("--model") + 1], "gpt-5.6-sol")
        self.assertEqual(cmd[cmd.index("--sandbox") + 1], "read-only")
        self.assertIn("--ephemeral", cmd)
        self.assertIn("--ignore-user-config", cmd)
        self.assertNotIn("--output-schema", cmd)


if __name__ == "__main__":
    unittest.main()
