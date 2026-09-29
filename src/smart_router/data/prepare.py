"""Offline construction only: no model downloads, teacher calls, or training."""

from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from smart_router.schemas import (
    DataError, TaskSpec, canonical_json, identifier, model_input, require,
)

SPLITS = ("train", "validation", "calibration", "test")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def lookup(row: dict, path: str, optional: bool = False) -> Any:
    if path in row:
        return row[path]
    value = row
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            if optional:
                return None
            raise DataError(f"Missing mapped field: {path}")
        value = value[key]
    return value


def read_rows(path: Path, file_format: str) -> list[dict]:
    if file_format == "jsonl":
        rows = []
        with path.open(encoding="utf-8") as handle:
            for number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError as exc:
                    raise DataError(f"Invalid JSON at line {number}: {exc}") from exc
        return rows
    if file_format == "csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            require(reader.fieldnames is not None, "CSV has no header")
            require(len(set(reader.fieldnames)) == len(reader.fieldnames), "Duplicate CSV column names")
            rows = list(reader)
            require(all(None not in row for row in rows), "CSV row has more fields than the header")
            return rows
    if file_format == "parquet":
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise DataError("Parquet needs the optional pyarrow dependency: pip install '.[parquet]'") from exc
        return pq.read_table(path).to_pylist()
    raise DataError(f"Unsupported format: {file_format}")


def load_config(path: Path) -> dict:
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise DataError(f"Invalid config JSON: {exc}") from exc
    require(isinstance(config, dict), "Configuration must be an object")
    require(config.get("config_version") == "1.0", "Expected config_version=1.0")
    return config


def import_records(config: dict, project_root: Path) -> tuple[list[dict], dict]:
    task = TaskSpec.from_dict(config.get("task"))
    ds = config.get("dataset")
    require(isinstance(ds, dict), "dataset must be an object")
    identifier(config.get("customer_id"), "customer_id")
    identifier(ds.get("dataset_id"), "dataset_id")
    identifier(ds.get("label_source"), "label_source")
    require(ds.get("path_base") == "project_root", "Use dataset.path_base=project_root and --project-root")
    path = Path(identifier(ds.get("path"), "dataset path"))
    if not path.is_absolute():
        path = project_root / path
    require(path.is_file(), f"Source dataset not found: {path}")
    columns = ds.get("columns")
    require(isinstance(columns, dict), "dataset.columns must be an object")
    allowed = {"example_id", "group_id", "text", "state", "label", "labels", "probabilities",
               "split", "episode_id", "step_id", "step_index", "metadata", "label_evidence"}
    require(not (set(columns) - allowed), f"Unknown column mappings: {sorted(set(columns) - allowed)}")
    for key, field in columns.items():
        identifier(field, f"column mapping {key}")
    require({"example_id", "group_id"} <= set(columns), "Map example_id and group_id explicitly")
    require(len({"text", "state"} & set(columns)) == 1, "Map exactly one input: text or state")
    encodings = {"label", "labels", "probabilities"} & set(columns)
    require(len(encodings) <= 1, "Map at most one target encoding")
    completeness = ds.get("label_completeness")
    require(completeness in {"complete", "positive_only"}, "Declare label_completeness=complete or positive_only")
    mode = config.get("annotation", {}).get("mode", "disabled")
    require(mode in {"disabled", "queue_missing"}, "Data construction supports annotation.mode disabled or queue_missing only")
    if task.unit == "agent_step":
        require({"episode_id", "step_id", "step_index"} <= set(columns), "agent_step requires episode_id, step_id and step_index mappings")
    file_format = ds.get("format")
    # Hash and parse from the same immutable-by-contract source; reject concurrent edits.
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    rows = read_rows(path, file_format)
    require(hashlib.sha256(path.read_bytes()).hexdigest() == source_hash, "Source changed while being read")
    require(bool(rows), "Dataset is empty")
    records = []
    seen_ids, seen_steps, episode_groups = set(), set(), {}
    for index, row in enumerate(rows, 1):
        try:
            require(isinstance(row, dict), "Each source record must be an object")
            values = {key: lookup(row, field, key in encodings) for key, field in columns.items()}
            if file_format == "csv":
                for key in {"state", "labels", "probabilities", "metadata", "label_evidence"} & set(values):
                    values[key] = json.loads(values[key]) if values[key] else None
                if "label" in values and values["label"] == "":
                    values["label"] = None
                if "step_index" in values:
                    require(isinstance(values["step_index"], str) and values["step_index"].isdigit(), "CSV step_index must be a nonnegative integer")
                    values["step_index"] = int(values["step_index"])
            eid = identifier(values["example_id"], "example_id")
            group = identifier(values["group_id"], "group_id")
            require(eid not in seen_ids, f"Duplicate example_id: {eid}")
            seen_ids.add(eid)
            input_key = "text" if "text" in columns else "state"
            value = values[input_key]
            if input_key == "text":
                require(isinstance(value, str) and bool(value.strip()), "text must be a nonempty string")
            else:
                require(isinstance(value, dict) and bool(value), "state must be a nonempty JSON object")
            inputs = {input_key: value}
            model_input({"input": inputs})
            encoding = next(iter(encodings), "label")
            raw_target = values.get(encoding)
            targets = task.targets(raw_target, encoding, completeness)
            metadata = values.get("metadata", {})
            require(isinstance(metadata, dict), "metadata must be a JSON object")
            metadata = dict(metadata)
            for key in ("episode_id", "step_id", "step_index"):
                if key in values:
                    require(key not in metadata or metadata[key] == values[key], f"Conflicting metadata field: {key}")
                    metadata[key] = values[key]
            evidence = values.get("label_evidence", {})
            require(isinstance(evidence, dict), "label_evidence must be a JSON object")
            canonical_json(metadata)
            canonical_json(evidence)
            if task.unit == "agent_step":
                episode = identifier(metadata["episode_id"], "episode_id")
                step = identifier(metadata["step_id"], "step_id")
                si = metadata["step_index"]
                require(isinstance(si, int) and not isinstance(si, bool) and si >= 0, "step_index must be a nonnegative integer")
                require((episode, step) not in seen_steps and (episode, si) not in seen_steps, "Duplicate step within episode")
                seen_steps.update({(episode, step), (episode, si)})
                require(episode_groups.setdefault(episode, group) == group, "One episode maps to multiple group_ids")
            split = values.get("split")
            if "split" in columns:
                require(split in SPLITS, f"Invalid supplied split: {split}")
            leakage_view = {"text": " ".join(value.split())} if input_key == "text" else inputs
            records.append({
                "schema_version": "1.0", "customer_id": config["customer_id"],
                "dataset_id": ds["dataset_id"], "task_id": task.task_id,
                "task_schema_version": task.schema_version,
                "example_id": eid, "group_id": group, "input": inputs,
                "targets": targets, "metadata": metadata, "label_evidence": evidence, "split": split,
                "provenance": {"label_source": ds["label_source"], "original_target": raw_target,
                               "source_row": index, "input_hash": digest(inputs),
                               "leakage_hash": digest(leakage_view)},
            })
        except (DataError, ValueError, TypeError) as exc:
            raise DataError(f"Source row {index}: {exc}") from exc
    return records, {"sha256": source_hash, "format": file_format, "rows": len(rows)}


def components(records: list[dict]) -> list[list[dict]]:
    """Merge entire groups transitively when duplicate model inputs join them."""
    parents = {r["group_id"]: r["group_id"] for r in records}

    def find(key):
        while parents[key] != key:
            parents[key] = parents[parents[key]]
            key = parents[key]
        return key

    hashes = {}
    for row in records:
        key, group = row["provenance"]["leakage_hash"], row["group_id"]
        if key in hashes:
            left, right = find(group), find(hashes[key])
            parents[max(left, right)] = min(left, right)
        else:
            hashes[key] = group
    result = defaultdict(list)
    for row in records:
        result[find(row["group_id"])].append(row)
    return list(result.values())


def assign_splits(records: list[dict], settings: dict) -> list[dict]:
    require(isinstance(settings, dict), "dataset.split must be an object")
    groups = components(records)
    strategy = settings.get("strategy")
    assignments = {}
    if strategy == "provided":
        for group in groups:
            names = {r["split"] for r in group}
            require(None not in names, "provided split strategy requires a split for every row")
            require(len(names) == 1, "Split leakage: a group or duplicate input spans supplied splits")
            assignments.update({r["example_id"]: next(iter(names)) for r in group})
    else:
        require(strategy == "grouped", "split strategy must be grouped or provided")
        require(all(r["split"] is None for r in records), "Supplied splits must be preserved with strategy=provided")
        ratios = {}
        for name in SPLITS:
            ratio = settings.get(name, 0)
            require(isinstance(ratio, (int, float)) and not isinstance(ratio, bool) and 0 <= ratio <= 1,
                    f"Invalid split ratio: {name}")
            ratios[name] = ratio
        require(abs(sum(ratios.values()) - 1) < 1e-8, "Split ratios must sum to one")
        active = [name for name in SPLITS if ratios[name] > 0]
        require(len(groups) >= len(active), f"Need at least {len(active)} independent groups after duplicate merging; got {len(groups)}. Use audit for tiny fixtures.")
        seed = settings.get("seed", 42)
        require(isinstance(seed, int) and not isinstance(seed, bool), "split.seed must be an integer")
        groups.sort(key=lambda g: (-len(g), digest([seed, sorted({r['group_id'] for r in g})])))
        counts = dict.fromkeys(active, 0)
        for index, group in enumerate(groups):
            empty = [name for name in active if counts[name] == 0]
            available = empty if len(groups) - index == len(empty) else active
            name = max(available, key=lambda n: (len(records) * ratios[n] - counts[n], -SPLITS.index(n)))
            counts[name] += len(group)
            assignments.update({r["example_id"]: name for r in group})
    return [{**r, "split": assignments[r["example_id"]]} for r in sorted(records, key=lambda r: r["example_id"])]


def audit(records: list[dict], task: TaskSpec) -> dict:
    per_split = {}
    for split in (None,) + SPLITS:
        rows = [r for r in records if r["split"] == split]
        if not rows:
            continue
        per_split[split or "unassigned"] = {
            "states": len(rows), "groups": len({r["group_id"] for r in rows}),
            "observed_targets": {c: sum(r["targets"]["values"][c] is not None for r in rows) for c in task.class_ids},
            "positive_target_mass": {c: sum(r["targets"]["values"][c] or 0 for r in rows) for c in task.class_ids},
        }
    duplicate_counts = Counter(r["provenance"]["leakage_hash"] for r in records)
    signatures = defaultdict(set)
    for row in records:
        signatures[row["provenance"]["leakage_hash"]].add(canonical_json(row["targets"]["values"]))
    fully_labeled = sum(all(v is not None for v in r["targets"]["values"].values()) for r in records)
    groups = components(records)
    warnings = []
    if len(records) < 1000:
        warnings.append("Small construction pilot: not sufficient evidence for reliable model selection or calibration.")
    if fully_labeled < len(records):
        warnings.append("Missing labels remain unknown; annotation or masked training is required.")
    for split, info in per_split.items():
        missing = [c for c, count in info["positive_target_mass"].items() if count == 0]
        if missing:
            warnings.append(f"{split}: no positive target mass for {missing}; per-class evaluation is limited.")
    conflicts = sum(len(v) > 1 for v in signatures.values())
    if conflicts:
        warnings.append("Duplicate inputs have different target vectors; review before training.")
    supplied_leaks = sum(len({r["split"] for r in g if r["split"] is not None}) > 1 for g in groups)
    require(supplied_leaks == 0, "Split leakage: a group or duplicate input spans supplied splits")
    lengths = sorted(len(canonical_json(model_input(r))) for r in records)
    return {
        "unit": task.unit, "states": len(records), "fully_labeled_states": fully_labeled,
        "observed_state_class_pairs": sum(v is not None for r in records for v in r["targets"]["values"].values()),
        "episodes": len({r["metadata"]["episode_id"] for r in records if "episode_id" in r["metadata"]}),
        "groups": len({r["group_id"] for r in records}), "independent_split_components": len(groups),
        "duplicate_extra_rows": sum(n - 1 for n in duplicate_counts.values()),
        "duplicate_inputs_with_differing_targets": conflicts,
        "input_characters": {"min": lengths[0], "median": lengths[len(lengths)//2], "max": lengths[-1]},
        "length_note": "JSON character lengths, not model-token counts; tokenization audit is a later stage.",
        "splits": per_split, "warnings": warnings,
    }


def write_bundle(config: dict, records: list[dict], source: dict, output: Path) -> dict:
    task = TaskSpec.from_dict(config["task"])
    report = audit(records, task)
    require(all(r["split"] in SPLITS for r in records), "Assign splits before export")
    queue = []
    if config.get("annotation", {}).get("mode") == "queue_missing":
        for row in records:
            missing = [c for c, v in row["targets"]["values"].items() if v is None]
            if missing:
                queue.append({"example_id": row["example_id"], "task_id": task.task_id,
                              "split": row["split"], "missing_class_ids": missing})
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive directory creation prevents accidental replacement of a frozen pilot.
    output.mkdir(exist_ok=False)
    hashes = {}

    def save(name, value, jsonl=False):
        text = "".join(canonical_json(r) + "\n" for r in value) if jsonl else json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        (output / name).write_text(text, encoding="utf-8")
        hashes[name] = hashlib.sha256(text.encode()).hexdigest()

    for name in SPLITS:
        save(name + ".jsonl", [r for r in records if r["split"] == name], jsonl=True)
    save("task.json", config["task"])
    save("audit.json", report)
    save("annotation_queue.jsonl", queue, jsonl=True)
    save("split_manifest.json", [{"example_id": r["example_id"], "group_id": r["group_id"],
                                  "input_hash": r["provenance"]["input_hash"], "split": r["split"]} for r in records])
    manifest = {"bundle_version": "1.0", "customer_id": config["customer_id"],
                "dataset_id": config["dataset"]["dataset_id"], "source": source,
                "task_hash": digest(config["task"]), "dataset_spec_hash": digest(config["dataset"]),
                "dataset_spec": config["dataset"], "annotation_mode": config.get("annotation", {}).get("mode", "disabled"),
                "split_settings": config["dataset"]["split"], "files_sha256": hashes.copy(),
                "status": "constructed_not_training_validated"}
    # Written last: an interrupted export with no manifest is incomplete.
    save("manifest.json", manifest)
    return report
