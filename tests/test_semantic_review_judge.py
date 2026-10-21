"""LLM proposals cannot become fabricated human review or lose provenance."""
from copy import deepcopy
import json
from unittest.mock import patch

from tests.test_semantic_review_ui import ReviewUITests
from smart_router.semantic_review_judge import build_input, generate, validate, normalize_catalog_unknowns


class JudgeTests(ReviewUITests):
    def proposal(self, request):
        return {"recommended_disposition": "needs_clarification", "confidence": .8, "summary": "Two possible domains",
                "review": {"answerability": "ambiguous", "global_catalog_scope": "ambiguous", "group_alias_review": "pending",
                    "question_sql_consistency": True, "dependency_review": None, "value_evidence_needed": None,
                    "reviewer_notes_supervision_only": "Specify the domain before selecting a table",
                    "clarification_options": ["Which domain?"], "conflicting_definition_ids": [], "acceptable_context_sets": [],
                    "candidate_judgments": [{"unit_id": c["unit_id"], "label": None, "reason": "Unconfirmed domain"} for c in request["candidate_tables"]]},
                "catalog_reviews": [{"catalog_id": c, "schema_review": None, "description_review": None, "reference_review": None,
                    "notes": "Incomplete verification"} for c in {t["catalog_id"] for t in request["candidate_tables"]}]}

    def config(self):
        return {"model": "invented-test-model", "generation": {}, "protocol": "fixture", "candidate_description_chars": 1000,
                "field_description_chars": 200, "api": "chat_completions", "max_output_tokens": 10000}

    def test_cached_proposal_does_not_change_human_review_and_accepted_export_keeps_judge(self):
        config = self.config()
        request = build_input(self.store, self.key, config)
        original = self.store.record(self.key)["review"]
        proposal = self.proposal(request)
        response = {"text": json.dumps(proposal), "actual_model": config["model"], "usage": {}}
        with patch("smart_router.semantic_review_judge.call", return_value=response) as invoke:
            draft = generate(self.store, self.key, config)
            self.assertEqual(draft["status"], "ready")
            self.assertEqual(generate(self.store, self.key, config), draft)
            self.assertEqual(invoke.call_count, 1)
        self.assertEqual(self.store.record(self.key)["review"], original)
        payload = self.payload()
        payload["updates"].update(proposal["review"], review_status="needs_clarification")
        payload["judge_feedback"] = {"request_hash": draft["request_hash"], "decision": "agree"}
        self.store.save(payload)
        export = self.store.export_examples()
        example = json.loads(__import__("pathlib").Path(export["path"]).read_text().splitlines()[0])
        self.assertEqual(example["judge_assistance_supervision_only"]["decision"], "agree")
        self.assertFalse(example["training_eligible"])
        self.assertFalse(example["judge_assistance_supervision_only"]["draft"]["human_approved"])

    def test_judge_cannot_skip_candidates_or_invent_context_ids(self):
        request = build_input(self.store, self.key, self.config())
        proposal = self.proposal(request)
        invalid = deepcopy(proposal)
        invalid["review"]["candidate_judgments"].pop()
        with self.assertRaisesRegex(ValueError, "every supplied"):
            validate(invalid, request, self.store.units)
        invalid = deepcopy(proposal)
        invalid["review"]["acceptable_context_sets"] = [["invented-id"]]
        with self.assertRaisesRegex(ValueError, "context IDs"):
            validate(invalid, request, self.store.units)

    def test_omitted_catalog_is_explicit_unknown_not_fabricated_verification(self):
        request = build_input(self.store, self.key, self.config())
        proposal = self.proposal(request)
        proposal["catalog_reviews"].pop()
        actions = normalize_catalog_unknowns(proposal, request)
        self.assertEqual(len(actions), 1)
        added = proposal["catalog_reviews"][-1]
        self.assertIsNone(added["description_review"])
        self.assertIn("omitted", added["notes"])
        validate(proposal, request, self.store.units)
