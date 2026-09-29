"""Offline correctness gates for labels, leakage, import parity, and export."""

import contextlib
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from smart_router.cli import main
from smart_router.data.prepare import assign_splits, audit, import_records, write_bundle
from smart_router.schemas import DataError, TaskSpec, model_input


def config():
    return {
        "config_version": "1.0", "customer_id": "fixture_customer",
        "task": {"task_id": "intent", "schema_version": "1.0", "kind": "single_label",
                 "classes": [{"id": c, "description": c + " requests"} for c in ["billing", "technical", "sales"]]},
        "dataset": {"dataset_id": "fixture_v1", "path": "source.jsonl", "path_base": "project_root",
                    "format": "jsonl", "columns": {"example_id": "id", "group_id": "group", "text": "text", "label": "label"},
                    "label_source": "synthetic_fixture", "label_completeness": "complete",
                    "split": {"strategy": "grouped", "seed": 42, "train": .7, "validation": .1, "calibration": .1, "test": .1}},
        "annotation": {"mode": "disabled"},
    }


def rows(n=30):
    return [{"id": f"row-{i:03}", "group": f"group-{i//2}", "text": f"Unique request {i}",
             "label": ["billing", "technical", "sales"][i % 3]} for i in range(n)]


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cfg = config()

    def load(self, data=None, cfg=None):
        cfg = cfg or self.cfg
        data = rows() if data is None else data
        (self.root / cfg["dataset"]["path"]).write_text("".join(json.dumps(r) + "\n" for r in data))
        return import_records(cfg, self.root)

    def test_single_label_hard_and_soft(self):
        task = TaskSpec.from_dict(self.cfg["task"])
        self.assertEqual(task.targets("billing", "label", "complete")["values"],
                         {"billing": 1., "technical": 0., "sales": 0.})
        self.assertEqual(task.targets({"billing": .2, "technical": .3, "sales": .5}, "probabilities", "complete")["values"]["sales"], .5)
        for bad in [{"billing": 1.}, {"billing": .2, "technical": .3, "sales": .9}, {"billing": float('nan'), "technical": 0, "sales": 0}]:
            with self.assertRaises(DataError):
                task.targets(bad, "probabilities", "complete")

    def test_unknown_and_duplicate_alias_rejected(self):
        task = TaskSpec.from_dict(self.cfg["task"])
        with self.assertRaisesRegex(DataError, "Unknown label"):
            task.targets("made_up", "label", "complete")
        spec = copy.deepcopy(self.cfg["task"])
        spec["classes"][0]["aliases"] = ["invoice"]
        task = TaskSpec.from_dict(spec)
        self.assertEqual(task.targets("invoice", "label", "complete")["values"]["billing"], 1.)
        with self.assertRaisesRegex(DataError, "Duplicate normalized"):
            task.targets({"invoice": .5, "billing": .5}, "probabilities", "complete")
        spec["classes"][1]["aliases"] = ["invoice"]
        with self.assertRaisesRegex(DataError, "Ambiguous alias"):
            TaskSpec.from_dict(spec)

    def test_binary_targets_not_normalized_or_imputed(self):
        self.cfg["task"]["kind"] = "independent_binary"
        task = TaskSpec.from_dict(self.cfg["task"])
        result = task.targets({"billing": .9, "technical": .95}, "probabilities", "complete")
        self.assertEqual(result["values"], {"billing": .9, "technical": .95, "sales": None})

    def test_multilabel_partial_and_complete_empty(self):
        self.cfg["task"]["kind"] = "multi_label"
        task = TaskSpec.from_dict(self.cfg["task"])
        partial = task.targets(["billing"], "labels", "positive_only")
        self.assertIsNone(partial["values"]["technical"])
        self.assertEqual(task.targets([], "labels", "complete")["values"], dict.fromkeys(task.class_ids, 0.))
        self.assertEqual(task.targets(None, "labels", "complete")["values"], dict.fromkeys(task.class_ids))

    def test_customer_classes_are_configurable(self):
        spec = copy.deepcopy(self.cfg["task"])
        spec["classes"] = [{"id": f"private-{i}", "description": f"Definition {i}"} for i in range(5)]
        task = TaskSpec.from_dict(spec)
        self.assertEqual(len(task.targets("private-4", "label", "complete")["values"]), 5)

    def test_future_evidence_rejected_and_input_projection(self):
        cfg = copy.deepcopy(self.cfg)
        cfg["dataset"]["columns"].pop("text")
        cfg["dataset"]["columns"]["state"] = "state"
        data = [{"id": "x", "group": "e", "state": {"nested": [{"final_outcome": "pass"}]}, "label": "billing"}]
        with self.assertRaisesRegex(DataError, "Forbidden model-input"):
            self.load(data, cfg)
        data[0]["state"] = {"goal": "fix charge"}
        data[0]["final_outcome"] = "ignored by configured input mapping"
        records, _ = self.load(data, cfg)
        self.assertEqual(model_input(records[0]), {"state": {"goal": "fix charge"}})
        self.assertNotIn("targets", model_input(records[0]))

    def test_duplicate_ids_and_missing_inputs_fail(self):
        with self.assertRaisesRegex(DataError, "Duplicate example_id"):
            self.load([rows(1)[0], rows(1)[0]])
        with self.assertRaisesRegex(DataError, "Missing mapped field"):
            self.load([{"id": "a", "group": "b", "label": "sales"}])

    def test_episode_integrity(self):
        self.cfg["task"]["unit"] = "agent_step"
        self.cfg["dataset"]["columns"].update({"episode_id": "episode", "step_id": "step", "step_index": "index"})
        data = rows(2)
        for i, r in enumerate(data):
            r.update(episode="ep1", step=f"s{i}", index=i)
        records, _ = self.load(data)
        self.assertEqual(audit(records, TaskSpec.from_dict(self.cfg["task"]))["episodes"], 1)
        data[1]["group"] = "different"
        with self.assertRaisesRegex(DataError, "multiple group_ids"):
            self.load(data)

    def test_evidence_preserved_outside_input(self):
        self.cfg["dataset"]["columns"].update({"metadata": "meta", "label_evidence": "evidence"})
        data = rows(1)
        data[0].update(meta={"model_pool_version": "pool1"}, evidence={"final_outcome": True, "trials": ["trial-1"]})
        records, _ = self.load(data)
        self.assertEqual(records[0]["label_evidence"], data[0]["evidence"])
        self.assertEqual(records[0]["metadata"]["model_pool_version"], "pool1")
        self.assertEqual(model_input(records[0]), {"text": data[0]["text"]})

    def test_csv_partial_labels_and_structured_state(self):
        self.cfg["task"]["kind"] = "multi_label"
        self.cfg["dataset"].update(path="source.csv", format="csv", label_completeness="positive_only")
        self.cfg["dataset"]["columns"] = {"example_id": "id", "group_id": "group", "state": "state", "labels": "labels"}
        with (self.root / "source.csv").open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "group", "state", "labels"])
            writer.writeheader()
            writer.writerow({"id": "a", "group": "b", "state": json.dumps({"message": "Help"}), "labels": '["technical"]'})
        result, _ = import_records(self.cfg, self.root)
        self.assertEqual(result[0]["targets"]["values"], {"billing": None, "technical": 1., "sales": None})
        self.assertEqual(result[0]["input"], {"state": {"message": "Help"}})

    def test_grouped_split_reproducible_under_row_order(self):
        records, _ = self.load()
        a = assign_splits(records, self.cfg["dataset"]["split"])
        b = assign_splits(list(reversed(records)), self.cfg["dataset"]["split"])
        self.assertEqual(a, b)
        self.assertEqual({r["split"] for r in a}, {"train", "validation", "calibration", "test"})
        by_group = {}
        for r in a:
            self.assertEqual(by_group.setdefault(r["group_id"], r["split"]), r["split"])

    def test_duplicate_input_connects_different_groups(self):
        data = rows()
        data[4]["text"] = "  " + data[0]["text"] + "   "
        records, _ = self.load(data)
        split = assign_splits(records, self.cfg["dataset"]["split"])
        by_id = {r["example_id"]: r for r in split}
        self.assertEqual(by_id["row-000"]["split"], by_id["row-004"]["split"])
        self.assertEqual(by_id["row-001"]["split"], by_id["row-005"]["split"])

    def test_provided_splits_preserved_and_leaks_rejected(self):
        records, _ = self.load()
        records = assign_splits(records, self.cfg["dataset"]["split"])
        self.assertEqual(records, assign_splits(records, {"strategy": "provided"}))
        with self.assertRaisesRegex(DataError, "must be preserved"):
            assign_splits(records, self.cfg["dataset"]["split"])
        records[1]["split"] = "test" if records[0]["split"] != "test" else "train"
        with self.assertRaisesRegex(DataError, "Split leakage"):
            assign_splits(records, {"strategy": "provided"})

    def test_tiny_dataset_can_audit_but_not_create_four_splits(self):
        records, _ = self.load(rows(3))
        self.assertEqual(audit(records, TaskSpec.from_dict(self.cfg["task"]))["states"], 3)
        with self.assertRaisesRegex(DataError, "independent groups"):
            assign_splits(records, self.cfg["dataset"]["split"])

    def test_csv_jsonl_parquet_import_parity(self):
        expected, _ = self.load()
        self.cfg["dataset"].update(path="source.csv", format="csv")
        with (self.root / "source.csv").open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows()[0]))
            writer.writeheader()
            writer.writerows(rows())
        actual, _ = import_records(self.cfg, self.root)
        self.assertEqual(expected, actual)
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            self.skipTest("Optional pyarrow not installed; CSV/JSONL parity passed")
        self.cfg["dataset"].update(path="source.parquet", format="parquet")
        pq.write_table(pa.Table.from_pylist(rows()), self.root / "source.parquet")
        actual, _ = import_records(self.cfg, self.root)
        self.assertEqual(expected, actual)

    def test_bundle_hashes_queue_and_no_overwrite(self):
        self.cfg["task"]["kind"] = "independent_binary"
        self.cfg["dataset"]["columns"].pop("label")
        self.cfg["dataset"]["columns"]["probabilities"] = "probs"
        self.cfg["annotation"]["mode"] = "queue_missing"
        data = rows()
        for r in data:
            r["probs"] = {"billing": .9}
        records, source = self.load(data)
        records = assign_splits(records, self.cfg["dataset"]["split"])
        out = self.root / "bundle"
        write_bundle(self.cfg, records, source, out)
        manifest = json.loads((out / "manifest.json").read_text())
        for name, expected in manifest["files_sha256"].items():
            self.assertEqual(hashlib.sha256((out / name).read_bytes()).hexdigest(), expected)
        queue = [json.loads(line) for line in (out / "annotation_queue.jsonl").read_text().splitlines()]
        self.assertEqual(len(queue), 30)
        self.assertEqual(queue[0]["missing_class_ids"], ["technical", "sales"])
        with self.assertRaises(FileExistsError):
            write_bundle(self.cfg, records, source, out)

    def test_cli_disabled_annotation_creates_no_queue_items(self):
        self.load()
        path = self.root / "config.json"
        path.write_text(json.dumps(self.cfg))
        with contextlib.redirect_stdout(io.StringIO()):
            code = main(["prepare", "--config", str(path), "--project-root", str(self.root), "--output", str(self.root / "result")])
        self.assertEqual(code, 0)
        self.assertEqual((self.root / "result/annotation_queue.jsonl").read_text(), "")


if __name__ == "__main__":
    unittest.main()
