"""Prepare unreviewed public-source semantic retrieval material, never training labels."""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
import hashlib
import json
from pathlib import Path
import urllib.request


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def model_input(record: dict) -> dict:
    """Keep oracle database IDs, SQL, source evidence and weak labels out of inputs."""
    return {key: record["input"][key] for key in ("question", "confirmed_history", "catalog_snapshot")}


def checked_assets(registry: dict, raw: Path) -> dict[str, Path]:
    result = {}
    for asset in registry["assets"]:
        name = asset["name"]
        if Path(name).name != name or name in result:
            raise ValueError(f"Invalid or duplicate asset name: {name}")
        path = raw / name
        data = path.read_bytes()
        if len(data) != asset["bytes"] or digest(data) != asset["sha256"]:
            raise ValueError(f"Source checksum mismatch: {name}")
        result[name] = path
    return result


def fetch(registry: dict, raw: Path) -> None:
    """Fetch only explicitly pinned assets, with per-file size and hash checks."""
    raw.mkdir(parents=True, exist_ok=True)
    for asset in registry["assets"]:
        name = asset["name"]
        if Path(name).name != name:
            raise ValueError(f"Invalid asset name: {name}")
        target = raw / name
        if target.exists():
            if digest(target.read_bytes()) != asset["sha256"]:
                raise ValueError(f"Existing file differs from pinned asset: {name}")
            continue
        if not asset["url"].startswith("https://"):
            raise ValueError("Pinned downloads must use HTTPS")
        with urllib.request.urlopen(asset["url"], timeout=60) as response:
            content = response.read(asset["max_bytes"] + 1)
        if len(content) > asset["max_bytes"] or len(content) != asset["bytes"]:
            raise ValueError(f"Unexpected download size: {name}")
        if digest(content) != asset["sha256"]:
            raise ValueError(f"Downloaded checksum mismatch: {name}")
        target.write_bytes(content)
    checked_assets(registry, raw)


def expression(column: str) -> dict:
    quoted = '"' + column.replace('"', '""') + '"'
    return {"dialects": [{"dialect": "ANSI_SQL", "expression": quoted}]}


def spider_catalog(schema: dict) -> tuple[dict, dict]:
    """Use schema only; questions and gold SQL cannot author the catalog."""
    columns = schema["column_names_original"]
    tables = schema["table_names_original"]
    primary = defaultdict(list)
    for index in schema["primary_keys"]:
        table_index, column = columns[index]
        primary[table_index].append(column)
    datasets = []
    for index, table in enumerate(tables):
        fields = []
        for column_index, (table_index, column) in enumerate(columns):
            if table_index != index:
                continue
            fields.append({"name": column, "description": schema["column_names"][column_index][1],
                           "expression": expression(column)})
        dataset = {"name": table, "source": f"{schema['db_id']}.{table}",
                   "description": schema["table_names"][index], "fields": fields}
        if primary[index]:
            dataset["primary_key"] = primary[index]
        datasets.append(dataset)
    relationships, unresolved = [], []
    for i, (left, right) in enumerate(schema["foreign_keys"]):
        source_index, source_column = columns[left]
        target_index, target_column = columns[right]
        # A flat FK pair cannot establish membership in a composite unique key.
        if primary[target_index] != [target_column]:
            unresolved.append({"foreign_key_indices": [left, right], "reason": "target_single_column_uniqueness_unverified"})
            continue
        relationships.append({"name": f"declared_fk_{i}", "from": tables[source_index],
                              "to": tables[target_index], "from_columns": [source_column],
                              "to_columns": [target_column]})
    model = {"version": "0.2.0.dev0", "name": f"spider__{schema['db_id']}",
             "datasets": datasets, "relationships": relationships, "metrics": []}
    return model, {"unresolved_relationships": unresolved, "description_origin": "source_normalized_names",
                   "business_semantics": "not_established", "physical_schema_verified": False}


def bird_catalogs(meanings: dict, allowed_dbs: set[str], issues: list | None = None) -> dict:
    grouped = defaultdict(lambda: defaultdict(list))
    for key, description in meanings.items():
        parts = key.split("|")
        if len(parts) != 3 or not all(parts):
            if issues is None:
                raise ValueError(f"Invalid column identifier: {key}")
            issues.append({"source_id": "bird_filtered_train", "source_key": key,
                           "reason": "invalid_column_identifier", "action": "quarantined_not_converted"})
            continue
        db, table, column = parts
        if db in allowed_dbs:
            grouped[db][table].append({"name": column, "description": str(description),
                                       "expression": expression(column)})
    return {db: {"version": "0.2.0.dev0", "name": f"bird__{db}",
                 "datasets": [{"name": table, "source": f"{db}.{table}",
                               "fields": sorted(fields, key=lambda f: f["name"])}
                              for table, fields in sorted(tables.items())],
                 "relationships": [], "metrics": []}
            for db, tables in sorted(grouped.items())}


def observed_tables(ast) -> set[int]:
    """Read table references from Spider's supplied AST, including nested queries."""
    result = set()
    if isinstance(ast, dict):
        for key, value in ast.items():
            if key == "table_units":
                for kind, table in value:
                    if kind == "table_unit":
                        if not isinstance(table, int) or table < 0:
                            raise ValueError("Invalid source AST table index")
                        result.add(table)
            result.update(observed_tables(value))
    elif isinstance(ast, list):
        for value in ast:
            result.update(observed_tables(value))
    return result


def select_pilot(records: list[dict], per_source: int) -> list[dict]:
    """Round-robin database groups; exact question duplicates cannot fill quotas."""
    selected = []
    used_questions = set()
    for source in sorted({r["source"]["source_id"] for r in records}):
        groups = defaultdict(list)
        seen = set()
        for record in sorted(records, key=lambda r: r["record_id"]):
            if (record["source"]["source_id"] != source or record["catalog_status"] != "draft_available"
                    or record["proposed_split"] != "train"):
                continue
            key = " ".join(record["input"]["question"].casefold().split())
            if key in seen or key in used_questions:
                continue
            seen.add(key)
            groups[record["source"]["database_id"]].append(record)
        queue = deque(deque(groups[k]) for k in sorted(groups))
        count = 0
        while queue and count < per_source:
            group = queue.popleft()
            record = group.popleft()
            used_questions.add(" ".join(record["input"]["question"].casefold().split()))
            selected.append({"record_id": record["record_id"], "source_id": source,
                             "database_id": record["source"]["database_id"],
                             "review_status": "pending", "training_eligible": False})
            count += 1
            if group:
                queue.append(group)
        if count != per_source:
            raise ValueError(f"Insufficient distinct review candidates for {source}: {count}")
    return selected


def propose_splits(records: list[dict], catalogs: dict) -> None:
    """Reserve groups before pilot review; aliases and exact duplicate inputs stay together."""
    parents = {r["episode_group"]: r["episode_group"] for r in records}

    def root(key):
        while parents[key] != key:
            parents[key] = parents[parents[key]]
            key = parents[key]
        return key

    def merge(left, right):
        a, b = sorted((root(left), root(right)))
        parents[b] = a

    aliases, shapes, inputs = {}, {}, {}
    for record in records:
        group = record["episode_group"]
        alias = record["source"]["database_id"].casefold()
        if alias in aliases:
            merge(group, aliases[alias])
        aliases[alias] = group
        question = " ".join(record["input"]["question"].casefold().split())
        if question in inputs:
            merge(group, inputs[question])
        inputs[question] = group
    for group, model in catalogs.items():
        shape = sorted((d["name"].casefold(), sorted(f["name"].casefold() for f in d["fields"])) for d in model["datasets"])
        fingerprint = digest(encoded(shape))
        if fingerprint in shapes:
            merge(group, shapes[fingerprint])
        shapes[fingerprint] = group
    members = defaultdict(list)
    for group in parents:
        members[root(group)].append(group)
    assignments = {}
    for parent, groups in members.items():
        group_id = digest(encoded(sorted(groups)))
        bucket = int(group_id[:8], 16) % 100
        split = "train" if bucket < 60 else "validation" if bucket < 75 else "calibration" if bucket < 80 else "test"
        assignments[parent] = (group_id, split)
    for record in records:
        record["data_group_id"], record["proposed_split"] = assignments[root(record["episode_group"])]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows))


def build(registry: dict, raw: Path, output: Path, per_source: int = 120) -> dict:
    from jsonschema import Draft202012Validator

    if output.exists():
        raise ValueError("Use a new output directory; intake releases are immutable")
    if per_source < 1:
        raise ValueError("per_source must be positive")
    assets = checked_assets(registry, raw)
    spider = json.loads(assets["spider_train.json"].read_text())
    bird = [json.loads(line) for line in assets["bird_train.jsonl"].read_text().splitlines() if line.strip()]
    schemas = {s["db_id"]: s for s in json.loads(assets["spider_tables.json"].read_text())}
    validator = Draft202012Validator(json.loads(assets["ossie-schema.json"].read_text()))
    catalogs, details, source_issues = {}, {}, []
    for db in sorted({r["db_id"] for r in spider}):
        key = f"spider_1_train:{db}"
        catalogs[key], details[key] = spider_catalog(schemas[db])
    for db, model in bird_catalogs(json.loads(assets["bird_column_meaning.json"].read_text()), {r["db_id"] for r in bird}, source_issues).items():
        key = f"bird_filtered_train:{db}"
        catalogs[key] = model
        details[key] = {"description_origin": "publisher_column_meaning_summary",
                        "business_semantics": "unreviewed", "physical_schema_verified": False,
                        "missing": ["DDL validation", "primary/foreign keys", "reviewed metrics"]}
    for model in catalogs.values():
        validator.validate(model)
    snapshot = digest(encoded(catalogs))
    records, evidence = [], []
    for source_id, rows in [("spider_1_train", spider), ("bird_filtered_train", bird)]:
        for index, row in enumerate(rows):
            db = row["db_id"]
            source_hash = digest(encoded(row))
            record_id = f"{source_id}:{index}:{source_hash[:16]}"
            sql = row.get("query", row.get("SQL"))
            weak_tables = None
            if source_id == "spider_1_train":
                weak_tables = [schemas[db]["table_names_original"][i] for i in sorted(observed_tables(row["sql"]))]
            record = {"record_id": record_id, "episode_group": f"{source_id}:{db}",
                      "input": {"question": row["question"], "confirmed_history": [], "catalog_snapshot": snapshot},
                      "source": {"source_id": source_id, "source_split": "train", "row_index": index,
                                 "database_id": db, "record_sha256": source_hash},
                      "catalog_status": "draft_available" if f"{source_id}:{db}" in catalogs else "missing",
                      "review_status": "pending", "training_eligible": False, "assigned_split": None,
                      "labels": {"anchor_ids": None, "acceptable_context_sets": None, "answerability": None}}
            records.append(record)
            evidence.append({"record_id": record_id, "source_sql": sql, "source_question_evidence": row.get("evidence"),
                             "observed_sql_tables": weak_tables, "label_status": "weak_unreviewed",
                             "execution_checked": False, "model_input_allowed": False})
    propose_splits(records, catalogs)
    pilot = select_pilot(records, per_source)
    (output / "catalogs").mkdir(parents=True)
    catalog_index = []
    for key, model in sorted(catalogs.items()):
        filename = digest(key.encode())[:20] + ".json"
        path = output / "catalogs" / filename
        path.write_bytes(encoded(model))
        catalog_index.append({"catalog_id": key, "path": f"catalogs/{filename}", "sha256": digest(path.read_bytes()),
                              "review_status": "draft", "json_schema_valid": True, **details[key]})
    write_jsonl(output / "catalog_index.jsonl", catalog_index)
    write_jsonl(output / "records.jsonl", records)
    write_jsonl(output / "supervision_only.jsonl", evidence)
    write_jsonl(output / "pilot_review_queue.jsonl", pilot)
    write_jsonl(output / "source_issues.jsonl", source_issues)
    manifest = {"format": "semantic-intake-v1", "status": "unreviewed_intake_not_training_data",
                "source_registry_sha256": digest(encoded(registry)), "catalog_snapshot": snapshot,
                "record_count": len(records), "pilot_review_count": len(pilot), "reviewed_count": 0,
                "training_eligible_count": 0, "catalog_count": len(catalogs),
                "quarantined_source_fields": len(source_issues),
                "table_count": sum(len(m["datasets"]) for m in catalogs.values()),
                "missing_catalog_records": sum(r["catalog_status"] == "missing" for r in records),
                "source_counts": {source: sum(r["source"]["source_id"] == source for r in records)
                                  for source in sorted({r["source"]["source_id"] for r in records})},
                "limitations": ["No physical database rows or SQL execution", "No approved business metrics",
                                "No official Ossie compiler validation", "JSON Schema validation only",
                                "BIRD schema coverage and keys unverified", "Proposed splits need semantic alias review",
                                "No formal training labels", "Pooled-catalog ambiguity requires review"],
                "files": {str(p.relative_to(output)): digest(p.read_bytes()) for p in sorted(output.rglob("*")) if p.is_file()}}
    (output / "manifest.json").write_bytes(encoded(manifest))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["fetch", "build"])
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pilot-per-source", type=int, default=120)
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text())
    if args.command == "fetch":
        fetch(registry, args.raw_dir)
        print(json.dumps({"status": "pinned_sources_verified", "asset_count": len(registry["assets"])}))
    else:
        if args.output is None:
            parser.error("build requires --output")
        manifest = build(registry, args.raw_dir, args.output, args.pilot_per_source)
        print(json.dumps({k: v for k, v in manifest.items() if k != "files"}, indent=2))


if __name__ == "__main__":
    main()
