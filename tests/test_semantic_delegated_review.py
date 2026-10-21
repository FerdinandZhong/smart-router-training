"""Delegated model review cannot invent human approval or silently drop unknowns."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.test_semantic_pilot import create_fixture
from smart_router.semantic_pilot import finish_bundle, prepare_review_workspace
from smart_router.semantic_intake import write_jsonl
from smart_router.semantic_review_ui import ReviewStore
from smart_router.semantic_review_judge import build_input, draft_path
from smart_router.semantic_delegated_review import apply_review, run


class DelegatedReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        _, pilot = create_fixture(self.root)
        workspace = self.root / "source"
        prepare_review_workspace(pilot, workspace)
        baseline = self.root / "baseline"
        baseline.mkdir()
        write_jsonl(baseline / "rankings.jsonl", [{"record_id": k, "rankings": {}} for k in ["alpha", "beta"]])
        finish_bundle(baseline, {"format": "semantic-baseline-diagnostic-v1"})
        self.store = ReviewStore(pilot, workspace, baseline)
        self.key = self.store.first80[0]
        self.config = {"model": "INVENTED-OPUS-FIXTURE", "api": "chat_completions", "base_url": "https://invalid.test",
            "max_output_tokens": 1000, "generation": {}, "protocol": "fixture", "candidate_description_chars": 100, "field_description_chars": 100}
        self.evidence = build_input(self.store, self.key, self.config)
        self.proposal = {"recommended_disposition": "needs_clarification", "confidence": .8, "summary": "Fixture ambiguity",
            "review": {"answerability": "ambiguous", "global_catalog_scope": "ambiguous", "group_alias_review": "pending",
                "question_sql_consistency": True, "dependency_review": None, "value_evidence_needed": None,
                "reviewer_notes_supervision_only": "Specify domain", "clarification_options": ["Which domain?"],
                "conflicting_definition_ids": [], "acceptable_context_sets": [],
                "candidate_judgments": [{"unit_id": c["unit_id"], "label": None, "reason": "Unknown domain"} for c in self.evidence["candidate_tables"]]},
            "catalog_reviews": [{"catalog_id": c, "schema_review": None, "description_review": None,
                "reference_review": None, "notes": "Fixture unknown"} for c in {t["catalog_id"] for t in self.evidence["candidate_tables"]}]}

    def decision(self, kind="accept", patch_data=None):
        return {"decision": kind, "reason": "Fixture evaluation", "issues": [], "patch": patch_data or {}}

    def test_accept_preserves_unknowns_and_does_not_mutate_source(self):
        final = apply_review(self.proposal, self.decision(), self.evidence, self.store.units)
        self.assertEqual(final, self.proposal)
        self.assertTrue(all(j["label"] is None for j in final["review"]["candidate_judgments"]))
        with self.assertRaises(ValueError):
            apply_review(self.proposal, self.decision(patch_data={"confidence": 1}), self.evidence, self.store.units)

    def test_patch_cannot_insert_fake_candidate_or_approve_incomplete_context(self):
        with self.assertRaises(ValueError):
            apply_review(self.proposal, self.decision("revise", {"review": {"candidate_judgments": [{"unit_id": "fake", "label": 1, "reason": "fake"}]}}), self.evidence, self.store.units)
        with self.assertRaisesRegex(ValueError, "incomplete evidence"):
            apply_review(self.proposal, self.decision("revise", {"recommended_disposition": "approved"}), self.evidence, self.store.units)

    def test_live_workflow_fixture_preserves_human_files_and_caches_model_receipt(self):
        draft = {"status": "ready", "request_hash": "invented-sonnet-request", "proposal": self.proposal}
        p = draft_path(self.store.workspace, self.key)
        p.parent.mkdir()
        p.write_text(json.dumps(draft))
        original = (self.store.workspace / "reviews.jsonl").read_bytes()
        response = {"text": json.dumps(self.decision()), "actual_model": self.config["model"], "usage": {}}
        output = self.root / "opus"
        with patch("smart_router.semantic_delegated_review.call", return_value=response) as invoke:
            first = run(self.store, self.config, output, limit=1)
            second = run(self.store, self.config, output, limit=1)
            self.assertEqual(invoke.call_count, 1)
        self.assertEqual(first["reviewed"], 1)
        self.assertEqual(second["failed"], 0)
        self.assertEqual(original, (self.store.workspace / "reviews.jsonl").read_bytes())
        label = json.loads((output / "silver-labels.jsonl").read_text().splitlines()[0])
        self.assertFalse(label["human_approved"])
        self.assertNotIn("LEAK_SENTINEL", str(label["input"]))
        self.assertTrue(all(j["label"] is None for j in label["candidates"]))
