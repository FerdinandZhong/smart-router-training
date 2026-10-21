"""Review durability, concurrency and human-example evidence separation."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from tests.test_semantic_pilot import create_fixture
from smart_router.semantic_intake import write_jsonl
from smart_router.semantic_pilot import finish_bundle, prepare_review_workspace, read_jsonl
from smart_router.semantic_review_ui import ReviewStore


class ReviewUITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        _, pilot = create_fixture(root)
        workspace = root / "workspace"
        prepare_review_workspace(pilot, workspace)
        baseline = root / "baseline"
        baseline.mkdir()
        packets = read_jsonl(pilot / "episodes.supervision.jsonl")
        write_jsonl(baseline / "rankings.jsonl", [{"record_id": p["record_id"], "rankings": {"dense": []}} for p in packets])
        finish_bundle(baseline, {"format": "semantic-baseline-diagnostic-v1"})
        self.store = ReviewStore(pilot, workspace, baseline)
        self.key = packets[0]["record_id"]

    def payload(self):
        record = self.store.record(self.key)
        return {"record_id": self.key, "version": record["version"],
                "updates": {"reviewer_id": "invented-test-reviewer", "reviewer_notes_supervision_only": "Test draft only"}}

    def test_revision_durable_and_stale_browser_cannot_overwrite(self):
        payload = self.payload()
        result = self.store.save(payload)
        self.assertNotEqual(payload["version"], result["version"])
        self.assertEqual(self.store.record(self.key)["review"]["reviewer_id"], "invented-test-reviewer")
        self.assertTrue(list(self.store.backups.glob("*-reviews.jsonl")))
        event = read_jsonl(self.store.events)[0]
        self.assertIsNone(event["before"]["reviewer_id"])
        self.assertEqual(event["after"]["review_status"], "pending")
        with self.assertRaises(RuntimeError):
            self.store.save(payload)

    def test_unknowns_survive_save_and_input_cannot_be_edited(self):
        self.store.save(self.payload())
        self.assertTrue(all(j["label"] is None for j in self.store.record(self.key)["review"]["candidate_judgments"]))
        payload = self.payload()
        payload["updates"]["catalog_snapshot"] = "different"
        with self.assertRaises(ValueError):
            self.store.save(payload)

    def test_reject_unexplained_labels_and_premature_approval(self):
        payload = self.payload()
        judgments = deepcopy(self.store.record(self.key)["review"]["candidate_judgments"])
        judgments[0]["label"] = 1
        payload["updates"]["candidate_judgments"] = judgments
        with self.assertRaisesRegex(ValueError, "reason"):
            self.store.save(payload)
        payload = self.payload()
        payload["updates"]["review_status"] = "approved"
        with self.assertRaisesRegex(ValueError, "Two distinct"):
            self.store.save(payload)

    def test_behavior_export_separates_reference_sql_and_preserves_drafts(self):
        self.store.append_event({"type": "evidence_viewed", "record_id": self.key,
                                 "actor": "invented-test-reviewer", "evidence": "reference_sql"})
        self.store.save(self.payload())
        export = self.store.export_examples()
        example = read_jsonl(Path(export["path"]))[0]
        self.assertNotIn("LEAK_SENTINEL", str(example["input"]))
        self.assertIn("LEAK_SENTINEL", str(example["reference_evidence_supervision_only"]))
        self.assertFalse(example["training_eligible"])
        self.assertTrue(example["reference_sql_viewed"])
        self.assertEqual(example["human_decision_supervision_only"]["review_status"], "pending")

    def test_deferral_saved_with_real_reason_without_second_approval(self):
        payload = self.payload()
        payload["updates"]["review_status"] = "needs_clarification"
        payload["updates"]["reviewer_notes_supervision_only"] = "Multiple domains lack confirmed context"
        self.store.save(payload)
        self.assertEqual(self.store.record(self.key)["review"]["review_status"], "needs_clarification")


if __name__ == "__main__":
    unittest.main()
