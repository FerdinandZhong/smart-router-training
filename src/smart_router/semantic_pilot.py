"""Build metadata-only pilot packets and export only explicitly reviewed labels.

This is a structural retrieval pilot. Business-semantic completion and SQL
execution require separate evidence. Neither weak SQL labels nor retrieval
scores can approve a record.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
from copy import deepcopy
from datetime import datetime
import csv
import json
import math
from pathlib import Path
import re

from smart_router.semantic_intake import digest, encoded, model_input, write_jsonl


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def unique(rows: list[dict], key: str) -> dict:
    result = {row[key]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError(f"Duplicate {key}")
    return result


def checked_bundle(root: Path, expected: str) -> dict:
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest["format"] != expected:
        raise ValueError(f"Expected {expected}")
    for name, sha in manifest["files"].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()) or digest(path.read_bytes()) != sha:
            raise ValueError(f"Artifact integrity failure: {name}")
    return manifest


def finish_bundle(output: Path, manifest: dict) -> dict:
    manifest["files"] = {str(p.relative_to(output)): digest(p.read_bytes())
                         for p in sorted(output.rglob("*")) if p.is_file()}
    (output / "manifest.json").write_bytes(encoded(manifest))
    return manifest


def unit_id(catalog_id: str, *parts: str) -> str:
    return "u_" + digest(encoded([catalog_id, *parts]))[:24]


def metadata_units(catalog_id: str, model: dict) -> list[dict]:
    """Derive descriptions from catalog fields only, never question/SQL evidence.

    Table descriptions include source field meanings. Exact fields and declared
    relationships remain addressable units; no graph traversal is performed.
    Metrics need a reviewed dependency adapter before this structural exporter.
    """
    if model.get("metrics"):
        raise ValueError("Metric-bearing models require the semantic dependency adapter")
    units = []
    tables = unique(model["datasets"], "name")
    for table in model["datasets"]:
        parent = unit_id(catalog_id, "table", table["name"])
        fields = unique(table["fields"], "name")
        if any(k not in fields for k in table.get("primary_key", [])):
            raise ValueError("Primary key references an absent field")
        text = "\n".join([f"Model: {model['name']}", f"Dataset: {table['name']}",
                          f"Description: {table.get('description', '')}",
                          "Fields: " + "; ".join(f"{f['name']}: {f.get('description', '')}" for f in table["fields"])])
        units.append({"unit_id": parent, "catalog_id": catalog_id, "kind": "table",
                      "name": table["name"], "parent_id": None, "text": text,
                      "definition": deepcopy(table), "dependencies": []})
        for field in table["fields"]:
            units.append({"unit_id": unit_id(catalog_id, "field", table["name"], field["name"]),
                          "catalog_id": catalog_id, "kind": "field", "name": field["name"],
                          "parent_id": parent, "text": f"{table['name']}.{field['name']}: {field.get('description', '')}",
                          "definition": deepcopy(field), "dependencies": [parent]})
    unique(model.get("relationships", []), "name")
    for relation in model.get("relationships", []):
        dependencies = []
        if not relation["from_columns"] or len(relation["from_columns"]) != len(relation["to_columns"]):
            raise ValueError("Invalid relationship columns")
        for side in ["from", "to"]:
            table = tables[relation[side]]
            fields = {f["name"] for f in table["fields"]}
            for name in relation[f"{side}_columns"]:
                if name not in fields:
                    raise ValueError("Relationship references an absent field")
                dependencies.append(unit_id(catalog_id, "field", table["name"], name))
        units.append({"unit_id": unit_id(catalog_id, "relationship", relation["name"]),
                      "catalog_id": catalog_id, "kind": "relationship", "name": relation["name"],
                      "parent_id": None, "text": json.dumps(relation, sort_keys=True),
                      "definition": deepcopy(relation), "dependencies": sorted(set(dependencies))})
    unique(units, "unit_id")
    return units


def tokens(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", text.casefold())


class BM25:
    """Small deterministic reference baseline; not a production latency claim."""
    def __init__(self, units: list[dict], k1: float = 1.2, b: float = 0.75):
        self.units = sorted(units, key=lambda u: u["unit_id"])
        self.tf = [Counter(tokens(u["text"])) for u in self.units]
        self.lengths = [sum(t.values()) for t in self.tf]
        self.average = sum(self.lengths) / max(1, len(self.lengths)) or 1
        self.df = Counter(t for counts in self.tf for t in counts)
        self.k1, self.b = k1, b

    def rank(self, question: str, k: int) -> list[dict]:
        ranked = []
        for unit, counts, length in zip(self.units, self.tf, self.lengths):
            score = 0.0
            for token in sorted(set(tokens(question))):
                n = counts[token]
                if n:
                    idf = math.log(1 + (len(self.units) - self.df[token] + .5) / (self.df[token] + .5))
                    score += idf * n * (self.k1 + 1) / (n + self.k1 * (1 - self.b + self.b * length / self.average))
            ranked.append({"unit_id": unit["unit_id"], "score": score})
        return sorted(ranked, key=lambda r: (-r["score"], r["unit_id"]))[:k]


def structure_stratum(evidence: dict) -> str:
    # These tags are sampling aids in supervision files, not semantic labels.
    sql = re.sub(r"'(?:''|[^'])*'|--[^\n]*|/\*.*?\*/", " ", evidence["source_sql"], flags=re.S).casefold()
    tables = evidence["observed_sql_tables"]
    nested = len(re.findall(r"\bselect\b", sql)) > 1
    aggregate = bool(re.search(r"\b(count|sum|avg|min|max)\s*\(", sql))
    if tables is not None:
        if len(tables) >= 3:
            return "three_plus_tables"
        if len(tables) == 2:
            return "two_tables"
        return "single_complex_hint" if nested or aggregate else "single_simple_hint"
    return "nested_hint" if nested else "join_hint" if re.search(r"\bjoin\b", sql) else "aggregation_hint" if aggregate else "simple_hint"


def balanced_queue(records: dict, evidence: dict, per_source: int = 120) -> list[dict]:
    """Equal structural strata, database round-robin, globally unique questions."""
    selected, used = [], set()
    for source in ["bird_filtered_train", "spider_1_train"]:
        eligible = [r for r in records.values() if r["source"]["source_id"] == source and r["proposed_split"] == "train"
                    and r["catalog_status"] == "draft_available"]
        strata = defaultdict(lambda: defaultdict(list))
        for record in sorted(eligible, key=lambda r: digest(r["record_id"].encode())):
            strata[structure_stratum(evidence[record["record_id"]])][record["episode_group"]].append(record)
        if len(strata) != 4 or per_source % 4:
            raise ValueError("Balanced pilot requires four populated strata and a quota divisible by four")
        buckets = {}
        for tag, groups in sorted(strata.items()):
            rotation = deque(deque(groups[g]) for g in sorted(groups, key=lambda x: digest(x.encode())))
            buckets[tag] = deque()
            while rotation:
                group = rotation.popleft()
                buckets[tag].append(group.popleft())
                if group:
                    rotation.append(group)
        for _ in range(per_source // 4):
            for tag, bucket in buckets.items():
                while bucket:
                    row = bucket.popleft()
                    question = " ".join(row["input"]["question"].casefold().split())
                    if question not in used:
                        used.add(question)
                        selected.append({"record_id": row["record_id"], "structure_stratum": tag})
                        break
                else:
                    raise ValueError(f"Not enough unique questions in {source}/{tag}")
    return selected


def build_pilot(intake: Path, output: Path, k: int = 32, selection: str = "balanced") -> dict:
    source_manifest = checked_bundle(intake, "semantic-intake-v1")
    if output.exists() or k < 1:
        raise ValueError("Use a new output directory and positive k")
    records = unique(read_jsonl(intake / "records.jsonl"), "record_id")
    evidence = unique(read_jsonl(intake / "supervision_only.jsonl"), "record_id")
    original_queue = read_jsonl(intake / "pilot_review_queue.jsonl")
    if selection not in ["balanced", "intake"]:
        raise ValueError("Unknown pilot selection strategy")
    queue = balanced_queue(records, evidence) if selection == "balanced" else original_queue
    unique(queue, "record_id")
    catalog_rows = unique(read_jsonl(intake / "catalog_index.jsonl"), "catalog_id")
    # All train-reserved catalogs are eligible distractors; never use gold DB to filter a query.
    allowed = sorted({r["episode_group"] for r in records.values() if r["proposed_split"] == "train"})
    models = {key: json.loads((intake / catalog_rows[key]["path"]).read_text()) for key in allowed}
    snapshot = digest(encoded(models))
    units = [u for key, model in models.items() for u in metadata_units(key, model)]
    by_unit = unique(units, "unit_id")
    tables = [u for u in units if u["kind"] == "table"]
    retriever = BM25(tables)
    queue_records = [records[q["record_id"]] for q in queue]
    groups = sorted({r["data_group_id"] for r in queue_records}, key=lambda x: digest(x.encode()))
    if len(groups) < 2:
        raise ValueError("Pilot needs at least two independent groups")
    dev_groups = set(groups[:max(1, len(groups) // 5)])
    first_counts, packets, reviews, diagnostics = Counter(), [], [], []
    for record in queue_records:
        if record["proposed_split"] != "train":
            raise ValueError("Pilot contains a held-out domain")
        source = record["source"]["source_id"]
        first_counts[source] += 1
        first = first_counts[source] <= 40
        projected = model_input(record)
        projected["catalog_snapshot"] = snapshot
        hits = retriever.rank(projected["question"], k)
        weak_names = evidence[record["record_id"]]["observed_sql_tables"]
        weak_ids = None if weak_names is None else [unit_id(record["episode_group"], "table", n) for n in weak_names]
        if weak_ids is not None and any(u not in by_unit for u in weak_ids):
            raise ValueError("Weak SQL table absent from metadata")
        split = "validation" if record["data_group_id"] in dev_groups else "train"
        packet = {"record_id": record["record_id"], "input": projected,
                  "data_group_id": record["data_group_id"], "source": record["source"],
                  "structure_stratum": structure_stratum(evidence[record["record_id"]]),
                  "first_review_batch": first, "pilot_split": split, "candidate_hits": hits,
                  "supervision_only": {**evidence[record["record_id"]], "weak_table_ids": weak_ids},
                  "review_status": "pending", "training_eligible": False}
        packets.append(packet)
        reviews.append({"record_id": record["record_id"], "catalog_snapshot": snapshot,
                        "review_status": "pending", "reviewer_id": None, "second_reviewer_id": None,
                        "reviewed_at": None, "track": "A_structural", "answerability": None,
                        "global_catalog_scope": "unreviewed", "question_sql_consistency": None,
                        "group_alias_review": "pending", "dependency_review": None,
                        "value_evidence_needed": None, "acceptable_context_sets": None,
                        "conflicting_definition_ids": None, "clarification_options": None,
                        "candidate_judgments": [{"unit_id": h["unit_id"], "label": None, "reason": None} for h in hits],
                        "execution": {"status": "not_run", "database_sha256": None, "reference_result_sha256": None},
                        "reviewer_notes_supervision_only": None})
        if weak_ids:
            found = {h["unit_id"] for h in hits}
            diagnostics.append({"record_id": record["record_id"], "weak_table_count": len(weak_ids),
                                "weak_recall_at_k": len(found.intersection(weak_ids)) / len(weak_ids),
                                "weak_complete_at_k": set(weak_ids).issubset(found)})
    output.mkdir(parents=True)
    (output / "catalogs").mkdir()
    catalog_reviews = []
    for key, model in models.items():
        name = digest(key.encode())[:20] + ".json"
        (output / "catalogs" / name).write_bytes(encoded(model))
        catalog_reviews.append({"catalog_id": key, "catalog_snapshot": snapshot,
                                "path": f"catalogs/{name}", "catalog_sha256": digest(encoded(model)),
                                "review_status": "pending", "reviewer_id": None, "reviewed_at": None,
                                "scope": "structural_only", "schema_review": None,
                                "description_review": None, "reference_review": None,
                                "authoring_inputs": "pinned_schema_and_independent_descriptions_only",
                                "source_details": catalog_rows[key], "notes": None})
    write_jsonl(output / "metadata_units.jsonl", units)
    write_jsonl(output / "catalog_reviews.template.jsonl", catalog_reviews)
    write_jsonl(output / "episodes.supervision.jsonl", packets)
    write_jsonl(output / "reviews.template.jsonl", reviews)
    write_jsonl(output / "first80.jsonl", [{"record_id": p["record_id"], "source_id": p["source"]["source_id"]} for p in packets if p["first_review_batch"]])
    write_jsonl(output / "bm25.weak_diagnostics.jsonl", diagnostics)
    old_ids, new_ids = {q["record_id"] for q in original_queue}, {q["record_id"] for q in queue}
    (output / "sampling-audit.json").write_bytes(encoded({
        "strategy": selection, "reason": "Balance source-SQL structure before review; not semantic labels",
        "retained": sorted(old_ids & new_ids), "added": sorted(new_ids - old_ids), "removed": sorted(old_ids - new_ids),
        "strata": dict(Counter(p["source"]["source_id"] + "/" + p["structure_stratum"] for p in packets)),
        "first_review_strata": dict(Counter(p["source"]["source_id"] + "/" + p["structure_stratum"]
                                            for p in packets if p["first_review_batch"]))}))
    (output / "README.md").write_text(
        "# Structural pilot review package\n\n"
        "Unreviewed preparation artifacts. Do not train on templates or SQL-derived weak labels.\n\n"
        "Catalog authors receive only catalogs/, metadata_units.jsonl and catalog_reviews.template.jsonl.\n"
        "Query reviewers additionally receive episodes.supervision.jsonl and reviews.template.jsonl.\n"
        "Copy templates outside this immutable package before editing. Keep labels null when uncertain.\n"
        "The first80 queue contains 40 episodes per source. Pilot validation uses whole train-reserved groups.\n"
        "Metadata-only training is separate from business-semantic and SQL-execution validation.\n"
        "Sources and declared terms: ../raw sources are pinned by configs/semantic_retrieval/sources.json.\n"
        "Spider/BIRD content is reused under their recorded CC BY-SA 4.0 terms; this package is not a new license grant.\n")
    return finish_bundle(output, {"format": "semantic-pilot-v1", "status": "review_ready_not_training_ready",
        "intake_manifest_sha256": digest((intake / "manifest.json").read_bytes()),
        "source_registry_sha256": source_manifest["source_registry_sha256"],
        "catalog_snapshot": snapshot, "catalog_count": len(models), "metadata_unit_count": len(units),
        "table_count": len(tables), "episode_count": len(packets), "first_review_count": sum(p["first_review_batch"] for p in packets),
        "selection": selection,
        "proposed_pilot_splits": dict(Counter(p["pilot_split"] for p in packets)),
        "reviewed_count": 0, "training_eligible_count": 0, "candidate_k": k,
        "protocol": "pilot_internal_development_all_domains_reserved_for_formal_train",
        "bm25_weak_diagnostics": {"source": "spider_only", "episodes": len(diagnostics),
            "mean_weak_table_recall_at_k": sum(d["weak_recall_at_k"] for d in diagnostics) / max(1, len(diagnostics)),
            "weak_complete_coverage_at_k": sum(d["weak_complete_at_k"] for d in diagnostics) / max(1, len(diagnostics)),
            "quality_claim_allowed": False},
        "limitations": ["No human review", "No SQL execution or physical schema verification",
                        "Table-level structural training only; no semantic metrics or clarification trainer",
                        "BM25 diagnostic only, not tuned hybrid", "Aliases require human review"]})


def reviewed_identity(row: dict, second: bool = False) -> None:
    if row.get("review_status") != "approved" or not str(row.get("reviewer_id") or "").strip():
        raise ValueError("Missing approval or reviewer identity")
    try:
        stamp = datetime.fromisoformat(str(row["reviewed_at"]).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("Review timestamp needs timezone")
    except (KeyError, ValueError) as exc:
        raise ValueError("Missing valid review timestamp") from exc
    if second and (not row.get("second_reviewer_id") or row["second_reviewer_id"] == row["reviewer_id"]):
        raise ValueError("Two distinct reviewer identities are required")


def approved_record(packet: dict, review: dict, units: dict, catalogs: dict, snapshot: str) -> dict:
    reviewed_identity(review, second=True)
    if review.get("catalog_snapshot") != snapshot or review.get("record_id") != packet["record_id"]:
        raise ValueError("Review refers to a different record or snapshot")
    for key, value in {"track": "A_structural", "answerability": "answerable",
                       "global_catalog_scope": "reviewed_unambiguous", "group_alias_review": "approved"}.items():
        if review.get(key) != value:
            raise ValueError(f"Structural training requires {key}={value}")
    for key in ["question_sql_consistency", "dependency_review"]:
        if review.get(key) is not True:
            raise ValueError(f"Missing {key}")
    if review.get("value_evidence_needed") is not False:
        raise ValueError("Value-dependent or unknown tasks cannot enter metadata-only training")
    judgments = unique(review["candidate_judgments"], "unit_id")
    candidates = []
    for uid, judgment in judgments.items():
        if uid not in units or units[uid]["kind"] != "table":
            raise ValueError("Structural candidate must reference an existing table unit")
        label = judgment.get("label")
        if label is not None and (type(label) is not int or label not in [0, 1]):
            raise ValueError("Label must be 0, 1, or null")
        if label is not None and not str(judgment.get("reason") or "").strip():
            raise ValueError("Every observed label needs review evidence")
        unit = units[uid]
        catalog = catalogs[unit["catalog_id"]]
        reviewed_identity(catalog)
        for key in ["schema_review", "description_review", "reference_review"]:
            if catalog.get(key) is not True:
                raise ValueError(f"Missing catalog {key}")
        candidates.append({"unit_id": uid, "text": unit["text"], "label": label})
    positive = {c["unit_id"] for c in candidates if c["label"] == 1}
    negative = {c["unit_id"] for c in candidates if c["label"] == 0}
    if not positive or not negative:
        raise ValueError("Need reviewed positive and negative table candidates")
    sets = review.get("acceptable_context_sets")
    conflicts = review.get("conflicting_definition_ids")
    if not isinstance(sets, list) or not sets or not isinstance(conflicts, list):
        raise ValueError("Complete context sets and conflict review are required")
    if any(u not in units for u in conflicts):
        raise ValueError("Unknown conflicting definition")
    if positive.intersection(conflicts):
        raise ValueError("A positive table is also marked conflicting")
    for context in sets:
        if not isinstance(context, list) or not context or len(set(context)) != len(context):
            raise ValueError("Context set must contain unique unit IDs")
        if any(u not in units for u in context) or set(context).intersection(conflicts):
            raise ValueError("Unknown or conflicting context unit")
        if len({units[u]["catalog_id"] for u in context}) != 1:
            raise ValueError("Cross-model composition is outside the pilot contract")
        for uid in context:
            if not set(units[uid]["dependencies"]).issubset(context):
                raise ValueError("Context set omits a declared dependency")
        needed_tables = {u for u in context if units[u]["kind"] == "table"}
        if not needed_tables or not needed_tables.issubset(positive):
            raise ValueError("Context tables need explicit positive judgments")
    return {"record_id": packet["record_id"], "data_group_id": packet["data_group_id"],
            "input": model_input(packet), "candidates": sorted(candidates, key=lambda c: c["unit_id"]),
            "acceptable_context_sets": sets, "conflicting_definition_ids": conflicts,
            "label_scope": "reviewed_structural_metadata_only", "split": packet["pilot_split"]}


def audit_reviews(pilot: Path, review_path: Path, catalog_path: Path) -> tuple[dict, list[dict]]:
    manifest = checked_bundle(pilot, "semantic-pilot-v1")
    packets = unique(read_jsonl(pilot / "episodes.supervision.jsonl"), "record_id")
    units = unique(read_jsonl(pilot / "metadata_units.jsonl"), "unit_id")
    original_catalogs = unique(read_jsonl(pilot / "catalog_reviews.template.jsonl"), "catalog_id")
    catalogs = unique(read_jsonl(catalog_path), "catalog_id")
    reviews = unique(read_jsonl(review_path), "record_id")
    if set(reviews) - set(packets) or set(catalogs) != set(original_catalogs):
        raise ValueError("Review identifiers do not match the pilot package")
    for key, catalog in catalogs.items():
        original = original_catalogs[key]
        for field in ["catalog_snapshot", "catalog_sha256", "path", "scope", "authoring_inputs"]:
            if catalog.get(field) != original[field]:
                raise ValueError(f"Catalog review identity changed: {field}")
    valid, failures, pending, deferred = [], [], 0, []
    for record_id, packet in packets.items():
        review = reviews.get(record_id)
        if review is None or review.get("review_status") == "pending":
            pending += 1
        elif review.get("review_status") in ["excluded", "needs_clarification", "needs_metadata", "value_dependent"]:
            try:
                reviewed_identity({**review, "review_status": "approved"})
                if not review.get("reviewer_notes_supervision_only"):
                    raise ValueError("Disposition requires a reason")
                deferred.append({"record_id": record_id, "status": review["review_status"]})
            except ValueError as exc:
                failures.append({"record_id": record_id, "reason": str(exc)})
        else:
            try:
                valid.append(approved_record(packet, review, units, catalogs, manifest["catalog_snapshot"]))
            except (ValueError, KeyError, TypeError) as exc:
                failures.append({"record_id": record_id, "reason": str(exc)})
    groups, inputs = {}, {}
    for row in valid:
        for mapping, key in [(groups, row["data_group_id"]), (inputs, " ".join(row["input"]["question"].casefold().split()))]:
            if key in mapping and mapping[key] != row["split"]:
                failures.append({"record_id": row["record_id"], "reason": "Cross-split group or duplicate input"})
            mapping[key] = row["split"]
    report = {"format": "semantic-pilot-review-audit-v1", "episode_count": len(packets),
              "pending_count": pending, "eligible_count": len(valid), "deferred": deferred,
              "failures": failures, "eligible_splits": dict(Counter(r["split"] for r in valid)),
              "ready_for_training": not failures and all(any(r["split"] == s for r in valid) for s in ["train", "validation"])}
    return report, valid


def export_training(pilot: Path, review_path: Path, catalog_path: Path, output: Path) -> dict:
    if output.exists():
        raise ValueError("Use a new export directory")
    audit, rows = audit_reviews(pilot, review_path, catalog_path)
    if not audit["ready_for_training"]:
        raise ValueError("Training export blocked: approved train/development records and error-free review are required")
    output.mkdir(parents=True)
    for split in ["train", "validation"]:
        write_jsonl(output / f"{split}.jsonl", [r for r in rows if r["split"] == split])
    (output / "review-audit.json").write_bytes(encoded(audit))
    return finish_bundle(output, {"format": "semantic-training-v1", "status": "reviewed_structural_pilot",
        "pilot_manifest_sha256": digest((pilot / "manifest.json").read_bytes()),
        "reviews_sha256": digest(review_path.read_bytes()), "catalog_reviews_sha256": digest(catalog_path.read_bytes()),
        "splits": audit["eligible_splits"], "protocol": "pilot_internal_development_not_formal_evaluation",
        "label_scope": "reviewed_structural_metadata_only", "business_semantics_validated": False,
        "execution_validated": False})


def prepare_review_workspace(pilot: Path, output: Path, baselines: Path | None = None) -> dict:
    """Create editable null-label forms and a readable first-80 supervisor packet."""
    checked_bundle(pilot, "semantic-pilot-v1")
    if output.exists():
        raise ValueError("Use a new workspace; do not overwrite reviewer edits")
    rankings = {}
    if baselines is not None:
        baseline_manifest = checked_bundle(baselines, "semantic-baseline-diagnostic-v1")
        if baseline_manifest["pilot_manifest_sha256"] != digest((pilot / "manifest.json").read_bytes()):
            raise ValueError("Baseline rankings refer to a different pilot")
        rankings = unique(read_jsonl(baselines / "rankings.jsonl"), "record_id")
    reviews = read_jsonl(pilot / "reviews.template.jsonl")
    units = unique(read_jsonl(pilot / "metadata_units.jsonl"), "unit_id")
    for review in reviews:
        judgments = {j["unit_id"]: j for j in review["candidate_judgments"]}
        for ids in rankings.get(review["record_id"], {}).get("rankings", {}).values():
            for uid in ids:
                if uid not in units or units[uid]["kind"] != "table":
                    raise ValueError("Baseline ranking has an unknown table")
                judgments.setdefault(uid, {"unit_id": uid, "label": None, "reason": None})
        review["candidate_judgments"] = [judgments[k] for k in sorted(judgments)]
        review["pool_origin"] = "baseline_union_review_only" if baselines else "bm25_review_only"
    episodes = read_jsonl(pilot / "episodes.supervision.jsonl")
    if rankings and set(rankings) != {p["record_id"] for p in episodes}:
        raise ValueError("Baseline episode coverage differs")
    output.mkdir(parents=True)
    write_jsonl(output / "reviews.jsonl", reviews)
    (output / "catalog-reviews.jsonl").write_bytes((pilot / "catalog_reviews.template.jsonl").read_bytes())
    with (output / "review-index.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["record_id", "source", "stratum", "pilot_split", "first80", "question"])
        for p in episodes:
            writer.writerow([p["record_id"], p["source"]["source_id"], p["structure_stratum"],
                             p["pilot_split"], p["first_review_batch"], p["input"]["question"]])
    lines = ["# First 80: query-review packet", "", "Supervision-only material. Catalog authors should use the separate catalog package.",
             "No labels are approved. SQL and table references are source evidence, not sufficient context labels.",
             "Edit reviews.jsonl and catalog-reviews.jsonl. Leave uncertain labels null; record all deferrals.", ""]
    for p in episodes:
        if not p["first_review_batch"]:
            continue
        lines.extend([f"## {p['record_id']}", "", f"Source: {p['source']['source_id']}; stratum: {p['structure_stratum']}; internal split: {p['pilot_split']}.",
                      "", p["input"]["question"], "", "Source SQL (supervision only):", "", "```sql",
                      p["supervision_only"]["source_sql"], "```", "",
                      "Question-specific evidence (supervision only): " + str(p["supervision_only"].get("source_question_evidence") or "None supplied"), ""])
        for method, ids in rankings.get(p["record_id"], {}).get("rankings", {}).items():
            lines.append(f"{method} first eight candidates (full rankings remain in the baseline artifact):")
            lines.append("")
            lines.extend(f"- `{uid}`: {units[uid]['catalog_id']}.{units[uid]['name']}" for uid in ids[:8])
            lines.append("")
    (output / "first80.md").write_text("\n".join(lines) + "\n")
    receipt = {"format": "semantic-review-workspace-v1", "status": "editable_pending_review",
               "pilot_manifest_sha256": digest((pilot / "manifest.json").read_bytes()),
               "baseline_manifest_sha256": digest((baselines / "manifest.json").read_bytes()) if baselines else None,
               "episodes": len(reviews), "candidate_judgments": sum(len(r["candidate_judgments"]) for r in reviews),
               "approved_labels": 0, "initial_files": {p.name: digest(p.read_bytes()) for p in sorted(output.iterdir())}}
    (output / "prepared-from.json").write_bytes(encoded(receipt))
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--intake", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--candidate-k", type=int, default=32)
    build.add_argument("--selection", choices=["balanced", "intake"], default="balanced")
    workspace = sub.add_parser("workspace")
    workspace.add_argument("--pilot", type=Path, required=True)
    workspace.add_argument("--output", type=Path, required=True)
    workspace.add_argument("--baselines", type=Path)
    for command in ["audit", "export"]:
        p = sub.add_parser(command)
        p.add_argument("--pilot", type=Path, required=True)
        p.add_argument("--reviews", type=Path, required=True)
        p.add_argument("--catalog-reviews", type=Path, required=True)
        if command == "export":
            p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "build":
        result = build_pilot(args.intake, args.output, args.candidate_k, args.selection)
    elif args.command == "workspace":
        result = prepare_review_workspace(args.pilot, args.output, args.baselines)
    elif args.command == "audit":
        result, _ = audit_reviews(args.pilot, args.reviews, args.catalog_reviews)
    else:
        result = export_training(args.pilot, args.reviews, args.catalog_reviews, args.output)
    print(json.dumps({k: v for k, v in result.items() if k != "files"}, indent=2))
    if args.command == "audit" and result["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
