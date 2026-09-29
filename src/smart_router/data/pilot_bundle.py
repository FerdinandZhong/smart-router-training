"""Validate portable AMP training data before any cluster resources are created."""
import hashlib
import json
from pathlib import Path

from smart_router.schemas import TaskSpec, validate_input


def validate_bundle(directory):
    root = Path(directory)
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest.get("purpose") != "engineering_smoke":
        raise ValueError("Expected an engineering_smoke bundle")
    required = {"task.json", "train.jsonl", "validation.jsonl", "calibration.jsonl", "test.jsonl"}
    if set(manifest["files_sha256"]) != required:
        raise ValueError("Bundle manifest must cover task and all four splits")
    for name, expected in manifest["files_sha256"].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Checksum mismatch: {name}")
    task = TaskSpec.from_dict(json.loads((root / "task.json").read_text()))
    ids, groups = set(), {}
    support = {c: {"pass": 0, "fail": 0, "unknown": 0} for c in task.class_ids}
    for split in ("train", "validation", "calibration", "test"):
        count = 0
        for line in (root / f"{split}.jsonl").read_text().splitlines():
            row = json.loads(line); key = row["example_id"]; group = row["group_id"]
            if key in ids or row["split"] != split or groups.get(group, split) != split:
                raise ValueError(f"Duplicate ID or split leakage: {key}")
            ids.add(key); groups[group] = split; count += 1
            validate_input(row["input"])
            if set(row["targets"]) != set(task.class_ids) or set(row["observation_mask"]) != set(task.class_ids):
                raise ValueError(f"Class mismatch: {key}")
            task.targets(row["targets"], "probabilities", "complete")
            for c, p in row["targets"].items():
                if row["observation_mask"][c] != int(p is not None):
                    raise ValueError(f"Unknown/observation mask mismatch: {key}/{c}")
                support[c]["unknown" if p is None else "pass" if p == 1 else "fail"] += 1
        if count != manifest["splits"][split]:
            raise ValueError(f"Split count mismatch: {split}")
    if len(groups) != manifest["group_count"] or support != manifest["class_support"]:
        raise ValueError("Support or group count mismatch")
    return manifest
