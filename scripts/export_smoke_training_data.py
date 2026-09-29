#!/usr/bin/env python3
"""Freeze the existing pilot for AMP import; requires the local annotation runs."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from smart_router.schemas import TaskSpec, validate_input


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def export(prepared, labels, output):
    task = json.loads((prepared / "task.json").read_text())
    spec = TaskSpec.from_dict(task)
    by_id = {}
    for path in labels:
        for row in read_rows(path):
            key = row["example_id"]
            if key in by_id:
                raise ValueError(f"Duplicate annotation ID: {key}")
            by_id[key] = row
    splits = {}
    seen, groups = set(), {}
    support = {c: {"pass": 0, "fail": 0, "unknown": 0} for c in spec.class_ids}
    for split in ("train", "validation", "calibration", "test"):
        rows = []
        for record in read_rows(prepared / f"{split}.jsonl"):
            key, group = record["example_id"], record["group_id"]
            if key in seen or groups.get(group, split) != split:
                raise ValueError(f"Duplicate ID or cross-split group: {key}")
            seen.add(key); groups[group] = split
            label = by_id[key]
            for field in ("group_id", "task_id", "task_schema_version", "customer_id", "dataset_id"):
                if record[field] != label[field]:
                    raise ValueError(f"Label identity mismatch: {key}/{field}")
            if label["split"] != split or record["split"] != split:
                raise ValueError(f"Split mismatch: {key}")
            if set(label["targets"]) != set(spec.class_ids):
                raise ValueError(f"Class mismatch: {key}")
            targets = spec.targets(label["targets"], "probabilities", "complete")["values"]
            validate_input(record["input"])
            for c, p in targets.items():
                support[c]["unknown" if p is None else "pass" if p == 1 else "fail"] += 1
            rows.append({
                "schema_version": "1.0", "example_id": key, "group_id": group,
                "split": split, "input": record["input"], "targets": targets,
                "observation_mask": {c: int(p is not None) for c, p in targets.items()},
                "metadata": record["metadata"],
                "provenance": {**record["provenance"], "annotation_quality": label["quality"],
                               "annotation_scope": label["scope"], "contract_hash": label["contract_hash"]},
            })
        splits[split] = rows
    if seen != set(by_id):
        raise ValueError("Inputs and annotations must have identical ID coverage")
    output.mkdir(parents=True, exist_ok=True)
    for split, rows in splits.items():
        (output / f"{split}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n" for r in rows))
    (output / "task.json").write_text(json.dumps(task, indent=2) + "\n")
    source_manifest = json.loads((prepared / "manifest.json").read_text())
    manifest = {
        "schema_version": "1.0", "dataset_id": "pilot-smoke-v1", "purpose": "engineering_smoke",
        "label_semantics": "Single-trial, local-step silver observations; unknowns masked; no executable replay.",
        "source": source_manifest["source"],
        "source_manifest_sha256": digest(prepared / "manifest.json"),
        "annotation_sources": [{"path": str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else p.name, "sha256": digest(p)} for p in labels],
        "splits": {s: len(r) for s, r in splits.items()}, "group_count": len(groups),
        "class_support": support,
        "files_sha256": {p.name: digest(p) for p in sorted(output.iterdir()) if p.name in {"task.json", *(f"{s}.jsonl" for s in splits)}},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, default=ROOT / "data/prepared/swe-gym-pilot-v2")
    parser.add_argument("--labels", type=Path, nargs="+", default=[ROOT / "runs/real-pilot-001-combined/silver_labels.jsonl", ROOT / "runs/real-pilot-002/silver_labels.jsonl"])
    parser.add_argument("--output", type=Path, default=ROOT / "data/pilot/pilot-smoke-v1")
    args = parser.parse_args()
    result = export(args.prepared, args.labels, args.output)
    print(json.dumps({"splits": result["splits"], "class_support": result["class_support"]}, indent=2))
