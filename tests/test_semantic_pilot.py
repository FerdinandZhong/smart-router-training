"""Integrity, leakage and review-gate tests using invented fixture metadata."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from smart_router.semantic_intake import encoded, write_jsonl
from smart_router.semantic_pilot import (
    approved_record, audit_reviews, build_pilot, checked_bundle, export_training,
    finish_bundle, metadata_units, read_jsonl, unit_id, balanced_queue, structure_stratum, prepare_review_workspace,
)
from smart_router.training.semantic_retriever import load_training, query_text, validate_config


def create_fixture(root):
    intake = root / "intake"
    (intake / "catalogs").mkdir(parents=True)
    records, catalogs, evidence, queue = [], [], [], []
    for i, db in enumerate(["alpha", "beta", "future"]):
        model = {"version": "0.2.0.dev0", "name": db, "metrics": [], "relationships": [],
                 "datasets": [{"name": "people", "source": db + ".people", "description": "Person ages",
                    "fields": [{"name": "age", "description": "Age in years",
                    "expression": {"dialects": [{"dialect": "ANSI_SQL", "expression": '"age"'}]}}]}]}
        (intake / "catalogs" / f"{db}.json").write_bytes(encoded(model))
        catalogs.append({"catalog_id": db, "path": f"catalogs/{db}.json", "review_status": "draft"})
        records.append({"record_id": db, "data_group_id": db, "episode_group": db,
                        "source": {"source_id": "spider" if i == 0 else "bird", "database_id": db},
                        "proposed_split": "test" if i == 2 else "train",
                        "input": {"question": f"What age in {db}?", "confirmed_history": [],
                                  "catalog_snapshot": "inventory", "SQL": "LEAK_SENTINEL"}})
        evidence.append({"record_id": db, "observed_sql_tables": ["people"],
                         "source_sql": "LEAK_SENTINEL", "source_question_evidence": "LEAK_SENTINEL"})
        if i < 2:
            queue.append({"record_id": db})
    write_jsonl(intake / "records.jsonl", records)
    write_jsonl(intake / "catalog_index.jsonl", catalogs)
    write_jsonl(intake / "supervision_only.jsonl", evidence)
    write_jsonl(intake / "pilot_review_queue.jsonl", queue)
    finish_bundle(intake, {"format": "semantic-intake-v1", "source_registry_sha256": "fixture"})
    pilot = root / "pilot"
    build_pilot(intake, pilot, 2, selection="intake")
    return intake, pilot


def approve_fixture(pilot, root):
    """Test identities are explicitly invented; never used with source records."""
    reviews = read_jsonl(pilot / "reviews.template.jsonl")
    for review in reviews:
        own = unit_id(review["record_id"], "table", "people")
        review.update({"review_status": "approved", "reviewer_id": "fixture-reviewer-A",
            "second_reviewer_id": "fixture-reviewer-B", "reviewed_at": "2026-10-10T00:00:00Z",
            "answerability": "answerable", "global_catalog_scope": "reviewed_unambiguous",
            "question_sql_consistency": True, "group_alias_review": "approved", "dependency_review": True,
            "value_evidence_needed": False, "acceptable_context_sets": [[own]], "conflicting_definition_ids": []})
        for judgment in review["candidate_judgments"]:
            judgment.update({"label": int(judgment["unit_id"] == own), "reason": "Invented test fixture"})
    catalogs = read_jsonl(pilot / "catalog_reviews.template.jsonl")
    for catalog in catalogs:
        catalog.update({"review_status": "approved", "reviewer_id": "fixture-catalog-author",
                        "reviewed_at": "2026-10-10T00:00:00Z", "schema_review": True,
                        "description_review": True, "reference_review": True})
    rpath, cpath = root / "reviews.jsonl", root / "catalog-reviews.jsonl"
    write_jsonl(rpath, reviews)
    write_jsonl(cpath, catalogs)
    return rpath, cpath


class SemanticPilotTests(unittest.TestCase):
    def test_editable_workspace_cannot_overwrite_review_or_approve_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, pilot = create_fixture(root)
            workspace = root / "review"
            prepare_review_workspace(pilot, workspace)
            self.assertIn("LEAK_SENTINEL", (workspace / "first80.md").read_text())  # Explicit supervisor-only file.
            self.assertTrue(all(j["label"] is None for r in read_jsonl(workspace / "reviews.jsonl") for j in r["candidate_judgments"]))
            audit, _ = audit_reviews(pilot, workspace / "reviews.jsonl", workspace / "catalog-reviews.jsonl")
            self.assertFalse(audit["ready_for_training"])
            with self.assertRaisesRegex(ValueError, "overwrite reviewer"):
                prepare_review_workspace(pilot, workspace)

    def test_balanced_selection_retains_complexity_and_excludes_future_groups(self):
        records, evidence = {}, {}
        for source in ["spider_1_train", "bird_filtered_train"]:
            for i, sql in enumerate(["SELECT age FROM people", "SELECT count(*) FROM people",
                                     "SELECT * FROM a JOIN b ON a.id=b.id", "SELECT * FROM a WHERE id IN (SELECT id FROM b)"]):
                rid = source + str(i)
                records[rid] = {"record_id": rid, "source": {"source_id": source}, "episode_group": rid,
                                "catalog_status": "draft_available", "proposed_split": "train",
                                "input": {"question": rid}}
                tables = ["a"] if i < 2 else ["a", "b"] if i == 2 else ["a", "b", "c"]
                evidence[rid] = {"source_sql": sql, "observed_sql_tables": tables if source.startswith("spider") else None}
        records["held_out"] = {**records["spider_1_train0"], "record_id": "held_out", "proposed_split": "test"}
        evidence["held_out"] = evidence["spider_1_train0"]
        result = balanced_queue(records, evidence, per_source=4)
        self.assertEqual(len(result), 8)
        self.assertNotIn("held_out", {r["record_id"] for r in result})
        self.assertEqual(result, balanced_queue(dict(reversed(list(records.items()))), evidence, per_source=4))
        self.assertEqual(structure_stratum({"source_sql": "SELECT 'join SELECT count(' FROM a", "observed_sql_tables": None}), "simple_hint")

    def test_future_catalogs_and_supervision_cannot_enter_descriptors_or_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, pilot = create_fixture(Path(tmp))
            units = read_jsonl(pilot / "metadata_units.jsonl")
            self.assertEqual({u["catalog_id"] for u in units}, {"alpha", "beta"})
            self.assertNotIn("LEAK_SENTINEL", json.dumps(units))
            for row in read_jsonl(pilot / "episodes.supervision.jsonl"):
                self.assertNotIn("LEAK_SENTINEL", json.dumps(row["input"]))
                self.assertNotIn("inventory", json.dumps(row["input"]))
                self.assertEqual(len(row["candidate_hits"]), 2)  # Both catalogs, no oracle filter.

    def test_pending_records_cannot_export_or_become_negatives(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, pilot = create_fixture(root)
            reviews, catalogs = pilot / "reviews.template.jsonl", pilot / "catalog_reviews.template.jsonl"
            audit, rows = audit_reviews(pilot, reviews, catalogs)
            self.assertEqual(audit["pending_count"], 2)
            self.assertFalse(audit["ready_for_training"])
            self.assertEqual(rows, [])
            with self.assertRaisesRegex(ValueError, "blocked"):
                export_training(pilot, reviews, catalogs, root / "export")
            self.assertFalse((root / "export").exists())

    def test_export_and_loader_preserve_whitelist_groups_and_reviewed_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, pilot = create_fixture(root)
            rp, cp = approve_fixture(pilot, root)
            export_training(pilot, rp, cp, root / "export")
            _, train, val = load_training(root / "export")
            self.assertEqual((len(train), len(val)), (1, 1))
            self.assertNotEqual(train[0]["data_group_id"], val[0]["data_group_id"])
            self.assertNotIn("LEAK_SENTINEL", json.dumps(train + val))
            self.assertEqual({c["label"] for c in train[0]["candidates"]}, {0, 1})
            self.assertNotIn(train[0]["input"]["catalog_snapshot"], query_text(train[0]))

    def test_bad_approvals_labels_and_contexts_fail_closed(self):
        mutations = [
            lambda r: r.update(second_reviewer_id=r["reviewer_id"]),
            lambda r: r.update(catalog_snapshot="stale"),
            lambda r: r.update(value_evidence_needed=None),
            lambda r: r.update(acceptable_context_sets=[["missing"]]),
            lambda r: r["candidate_judgments"][0].update(label=True),
            lambda r: r["candidate_judgments"][0].update(reason=None),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, pilot = create_fixture(root)
            rp, cp = approve_fixture(pilot, root)
            original = read_jsonl(rp)
            for mutate in mutations:
                with self.subTest(mutation=mutate):
                    reviews = deepcopy(original)
                    mutate(reviews[0])
                    write_jsonl(rp, reviews)
                    report, _ = audit_reviews(pilot, rp, cp)
                    self.assertTrue(report["failures"])
                    self.assertFalse(report["ready_for_training"])

    def test_exact_metadata_and_review_snapshot_are_bound_to_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, pilot = create_fixture(root)
            rp, cp = approve_fixture(pilot, root)
            catalogs = read_jsonl(cp)
            catalogs[0]["catalog_sha256"] = "different"
            write_jsonl(cp, catalogs)
            with self.assertRaisesRegex(ValueError, "identity changed"):
                audit_reviews(pilot, rp, cp)
            (pilot / "metadata_units.jsonl").write_text("[]\n")
            with self.assertRaisesRegex(ValueError, "integrity"):
                checked_bundle(pilot, "semantic-pilot-v1")

    def test_declared_relationship_dependencies_must_be_present(self):
        model = {"name": "fixture", "datasets": [
            {"name": "a", "fields": [{"name": "id"}]},
            {"name": "b", "fields": [{"name": "a_id"}]}],
            "relationships": [{"name": "fk", "from": "b", "to": "a", "from_columns": ["a_id"], "to_columns": ["id"]}]}
        units = {u["unit_id"]: u for u in metadata_units("fixture", model)}
        relation = next(u for u in units.values() if u["kind"] == "relationship")
        self.assertEqual(len(relation["dependencies"]), 2)
        model["relationships"][0]["to_columns"] = ["nonexistent"]
        with self.assertRaisesRegex(ValueError, "absent field"):
            metadata_units("fixture", model)

    def test_review_cannot_approve_a_context_without_field_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, pilot = create_fixture(root)
            rp, cp = approve_fixture(pilot, root)
            reviews = read_jsonl(rp)
            review = reviews[0]
            review["acceptable_context_sets"] = [[unit_id(review["record_id"], "field", "people", "age")]]
            write_jsonl(rp, reviews)
            report, _ = audit_reviews(pilot, rp, cp)
            self.assertTrue(any("omits a declared dependency" in x["reason"] for x in report["failures"]))

    def test_duplicate_input_cannot_cross_pilot_groups_at_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            intake, _ = create_fixture(root)
            records = read_jsonl(intake / "records.jsonl")
            records[1]["input"]["question"] = records[0]["input"]["question"].upper()
            write_jsonl(intake / "records.jsonl", records)
            (intake / "manifest.json").unlink()
            finish_bundle(intake, {"format": "semantic-intake-v1", "source_registry_sha256": "fixture"})
            pilot = root / "duplicate-pilot"
            build_pilot(intake, pilot, 2, selection="intake")
            rp, cp = approve_fixture(pilot, root)
            report, _ = audit_reviews(pilot, rp, cp)
            self.assertTrue(any("duplicate input" in f["reason"] for f in report["failures"]))

    def test_encoder_revision_and_numerical_settings_are_validated(self):
        config = {"revision": "a" * 40, "epochs": 10, "patience": 2, "max_seq_length": 256,
                  "learning_rate": 2e-5, "temperature": .1, "max_grad_norm": 1., "device": "cpu"}
        validate_config(config)
        for key, value in [("revision", "main"), ("learning_rate", float("nan")), ("temperature", 0), ("epochs", True)]:
            with self.subTest(key=key):
                changed = {**config, key: value}
                with self.assertRaises(ValueError):
                    validate_config(changed)


if __name__ == "__main__":
    unittest.main()
