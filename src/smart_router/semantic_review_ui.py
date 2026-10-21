"""Loopback-only human review UI with version checks and durable review traces."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import uuid
from urllib.parse import urlparse, parse_qs

from smart_router.semantic_pilot import (
    approved_record, audit_reviews, checked_bundle, read_jsonl, reviewed_identity, unique,
)

REVIEW_FIELDS = {
    "acceptable_context_sets", "answerability", "candidate_judgments", "clarification_options",
    "conflicting_definition_ids", "dependency_review", "global_catalog_scope", "group_alias_review",
    "question_sql_consistency", "review_status", "reviewer_id", "second_reviewer_id",
    "value_evidence_needed", "reviewer_notes_supervision_only",
}
CATALOG_FIELDS = {"description_review", "notes", "reference_review", "review_status", "reviewer_id", "schema_review"}
STATUSES = {"pending", "approved", "excluded", "needs_clarification", "needs_metadata", "value_dependent"}


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def version(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()


class ReviewStore:
    def __init__(self, pilot: Path, workspace: Path, baselines: Path):
        self.pilot, self.workspace = pilot.resolve(), workspace.resolve()
        self.baselines = baselines.resolve()
        checked_bundle(self.pilot, "semantic-pilot-v1")
        self.packets = unique(read_jsonl(self.pilot / "episodes.supervision.jsonl"), "record_id")
        self.units = unique(read_jsonl(self.pilot / "metadata_units.jsonl"), "unit_id")
        self.first80 = [r["record_id"] for r in read_jsonl(self.pilot / "first80.jsonl")]
        checked_bundle(baselines, "semantic-baseline-diagnostic-v1")
        self.rankings = {r["record_id"]: r["rankings"] for r in read_jsonl(baselines / "rankings.jsonl")}
        self.lock = threading.RLock()
        self.events = workspace / "review-events.jsonl"
        self.backups = workspace / "ui-backups"
        audit_reviews(self.pilot, workspace / "reviews.jsonl", workspace / "catalog-reviews.jsonl")

    def rows(self, catalog=False):
        return read_jsonl(self.workspace / ("catalog-reviews.jsonl" if catalog else "reviews.jsonl"))

    def append_event(self, event):
        event = {"event_id": uuid.uuid4().hex, "recorded_at": timestamp(), **event}
        with self.lock, self.events.open("a") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return event["event_id"]

    def record(self, key):
        from smart_router.semantic_review_judge import draft_path, digest
        review = unique(self.rows(), "record_id")[key]
        catalogs = unique(self.rows(True), "catalog_id")
        path = draft_path(self.workspace, key)
        delegated = self.delegated_directory()
        delegated_path = delegated / "receipts" / (digest(key) + ".json") if delegated else None
        return {"packet": self.packets[key], "review": review, "version": version(review),
                "delegatedReview": json.loads(delegated_path.read_text()) if delegated_path and delegated_path.exists() else None,
                "judgeDraft": json.loads(path.read_text()) if path.exists() else None,
                "rankings": self.rankings[key], "catalogs": catalogs,
                "catalogVersions": {k: version(v) for k, v in catalogs.items()},
                "catalogDocuments": {k: json.loads((self.pilot / v["path"]).read_text()) for k, v in catalogs.items()}}

    def delegated_directory(self):
        pointer = self.workspace / "delegated-review-active.json"
        if not pointer.exists():
            return None
        output = Path(json.loads(pointer.read_text())["output"]).resolve()
        return output if output.is_relative_to(self.workspace) else None

    def errors(self, key, row):
        if row["review_status"] == "approved":
            try:
                approved_record(self.packets[key], row, self.units, unique(self.rows(True), "catalog_id"), row["catalog_snapshot"])
            except (ValueError, TypeError, KeyError) as exc:
                return [str(exc)]
        elif row["review_status"] != "pending":
            try:
                reviewed_identity({**row, "review_status": "approved"})
                if not str(row.get("reviewer_notes_supervision_only") or "").strip():
                    raise ValueError("Explain the disposition in your review notes")
            except ValueError as exc:
                return [str(exc)]
        return []

    def save(self, payload, catalog=False):
        key_field = "catalog_id" if catalog else "record_id"
        key = payload[key_field]
        with self.lock:
            rows = self.rows(catalog)
            existing = unique(rows, key_field)[key]
            if payload.get("version") != version(existing):
                raise RuntimeError("This review changed elsewhere. Reload before saving.")
            updates = payload["updates"]
            allowed = CATALOG_FIELDS if catalog else REVIEW_FIELDS
            if set(updates) - allowed:
                raise ValueError("Immutable or unsupported review fields")
            revised = {**deepcopy(existing), **updates, "reviewed_at": timestamp()}
            if not str(revised.get("reviewer_id") or "").strip():
                raise ValueError("Enter your reviewer name before saving")
            if revised.get("review_status") not in (STATUSES if not catalog else {"pending", "approved"}):
                raise ValueError("Unsupported disposition")
            if catalog:
                if revised["review_status"] == "approved":
                    reviewed_identity(revised)
                    if any(revised.get(f) is not True for f in ["schema_review", "description_review", "reference_review"]):
                        raise ValueError("Complete all three catalog checks before approval")
            else:
                ids = set()
                for judgment in revised["candidate_judgments"]:
                    uid, label = judgment["unit_id"], judgment.get("label")
                    if uid not in self.units or self.units[uid]["kind"] != "table" or uid in ids:
                        raise ValueError("Candidates must be unique table IDs from the pilot")
                    ids.add(uid)
                    if label is not None and (type(label) is not int or label not in [0, 1]):
                        raise ValueError("Judgments must be positive, negative or unknown")
                    if label is not None and not str(judgment.get("reason") or "").strip():
                        raise ValueError("Give a reason for every positive or negative judgment")
                errors = self.errors(key, revised)
                if errors:
                    raise ValueError(errors[0])
            path = self.workspace / ("catalog-reviews.jsonl" if catalog else "reviews.jsonl")
            self.backups.mkdir(exist_ok=True)
            before = path.read_bytes()
            backup = self.backups / (uuid.uuid4().hex + "-" + path.name)
            backup.write_bytes(before)
            content = "".join(json.dumps(revised if r[key_field] == key else r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)
            temporary = path.with_suffix(".tmp")
            with temporary.open("w") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            try:
                feedback = self.judge_feedback(key, payload.get("judge_feedback")) if not catalog and payload.get("judge_feedback") else None
                event_id = self.append_event({"type": "catalog_saved" if catalog else "review_saved", "actor": revised["reviewer_id"],
                    key_field: key, "before": existing, "after": revised, "source": "human_local_ui",
                    "judge_assistance": feedback,
                    "packet_sha256": version(self.packets[key]) if not catalog else None})
            except Exception:
                path.write_bytes(before)
                raise
            return {"review": revised, "version": version(revised), "event_id": event_id}

    def judge_feedback(self, key, feedback):
        from smart_router.semantic_review_judge import draft_path
        draft = json.loads(draft_path(self.workspace, key).read_text())
        if draft["status"] != "ready" or feedback.get("request_hash") != draft["request_hash"]:
            raise ValueError("Judge proposal changed; reload before responding")
        if feedback.get("decision") not in {"agree", "disagree", "edited"}:
            raise ValueError("Unknown judge response")
        return {"decision": feedback["decision"], "comment": feedback.get("comment", ""), "draft": draft}

    def export_examples(self):
        """Export observed human behavior, not automatically approved training labels."""
        with self.lock:
            events = read_jsonl(self.events) if self.events.exists() else []
            views = {}
            examples = []
            catalog_examples = []
            for event in events:
                key = event.get("record_id")
                if event["type"] == "catalog_saved":
                    row = event["after"]
                    catalog_examples.append({"event_id": event["event_id"], "recorded_at": event["recorded_at"],
                        "catalog_id": row["catalog_id"], "reviewer_id": event["actor"],
                        "input": {"catalog": json.loads((self.pilot / row["path"]).read_text()),
                                  "catalog_snapshot": row["catalog_snapshot"]},
                        "human_decision_supervision_only": row,
                        "previous_decision_supervision_only": event["before"], "source": "human_local_ui"})
                if event["type"] == "evidence_viewed":
                    views.setdefault((key, event["actor"]), []).append(event)
                if event["type"] != "review_saved":
                    continue
                packet = self.packets[key]
                row = event["after"]
                unit_ids = {j["unit_id"] for j in row["candidate_judgments"]}
                for context in row.get("acceptable_context_sets") or []:
                    unit_ids.update(context)
                viewed = views.get((key, event["actor"]), [])
                unit_ids.update(v["unit_id"] for v in viewed if v.get("unit_id") in self.units)
                examples.append({"event_id": event["event_id"], "record_id": key, "recorded_at": event["recorded_at"],
                    "input": {"question": packet["input"]["question"], "confirmed_history": packet["input"]["confirmed_history"],
                              "catalog_snapshot": packet["input"]["catalog_snapshot"],
                              "metadata": [self.units[u] for u in sorted(unit_ids)], "rankings": self.rankings[key]},
                    "human_decision_supervision_only": row, "previous_decision_supervision_only": event["before"],
                    "judge_assistance_supervision_only": event.get("judge_assistance"),
                    "reference_evidence_supervision_only": packet["supervision_only"],
                    "interaction_trace": viewed, "reviewer_id": event["actor"], "source": "human_local_ui",
                    "reference_sql_viewed": any(v.get("evidence") == "reference_sql" for v in viewed),
                    "training_eligible": row["review_status"] == "approved" and not self.errors(key, row),
                    "usage": "Human review behavior examples; drafts and deferrals are not approved retrieval labels"})
            path = self.workspace / "human-review-examples.jsonl"
            tmp = path.with_suffix(".tmp")
            tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in examples))
            os.replace(tmp, path)
            catalog_path = self.workspace / "human-catalog-review-examples.jsonl"
            catalog_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in catalog_examples))
            feedback_path = self.workspace / "human-judge-feedback.jsonl"
            feedback_rows = []
            for e in events:
                if e["type"] != "judge_feedback":
                    continue
                key = e["record_id"]
                feedback_rows.append({"event_id": e["event_id"], "record_id": key, "recorded_at": e["recorded_at"],
                    "reviewer_id": e["actor"], "input": self.packets[key]["input"],
                    "judge_proposal_supervision_only": e["judge_assistance"]["draft"],
                    "human_feedback_supervision_only": {k: v for k, v in e["judge_assistance"].items() if k != "draft"},
                    "reference_supervision_only": self.packets[key]["supervision_only"]})
            feedback_path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in feedback_rows))
            return {"examples": len(examples), "path": str(path), "catalog_examples": len(catalog_examples), "catalog_path": str(catalog_path)}


def handler(store, static):
    class Handler(BaseHTTPRequestHandler):
        def send(self, data, status=200, content_type="application/json"):
            body = data.encode() if isinstance(data, str) else json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.headers.get("Host") not in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}:
                return self.send({"error": "Local host only"}, 403)
            try:
                parsed = urlparse(self.path)
                if parsed.path == "/":
                    return self.send(static.read_text(), content_type="text/html")
                if parsed.path == "/api/bootstrap":
                    reviews = unique(store.rows(), "record_id")
                    decisions = {}
                    for e in read_jsonl(store.events) if store.events.exists() else []:
                        assistance = e.get("judge_assistance")
                        if assistance and e.get("record_id"):
                            decisions[e["record_id"]] = assistance["decision"]
                    return self.send({"records": [{"record_id": k, "question": store.packets[k]["input"]["question"],
                        "source": store.packets[k]["source"]["source_id"], "status": reviews[k]["review_status"], "judge_response": decisions.get(k)} for k in store.first80],
                        "units": store.units, "workspace": str(store.workspace)})
                if parsed.path == "/api/record":
                    return self.send(store.record(parse_qs(parsed.query)["id"][0]))
                if parsed.path == "/api/audit":
                    report, _ = audit_reviews(store.pilot, store.workspace / "reviews.jsonl", store.workspace / "catalog-reviews.jsonl")
                    return self.send(report)
                if parsed.path == "/api/judge-status":
                    p = store.workspace / "judge-batch-status.json"
                    return self.send(json.loads(p.read_text()) if p.exists() else {"state": "not_started"})
                if parsed.path == "/api/delegated-status":
                    output = store.delegated_directory()
                    p = output / "status.json" if output else None
                    return self.send(json.loads(p.read_text()) if p and p.exists() else {"state": "not_started"})
                self.send({"error": "Not found"}, 404)
            except (KeyError, ValueError) as exc:
                self.send({"error": str(exc)}, 400)

        def do_POST(self):
            origin = self.headers.get("Origin")
            expected = f"http://{self.headers.get('Host')}"
            if self.headers.get("Host") not in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"} or self.headers.get("X-Review-UI") != "1" or (origin and origin != expected):
                return self.send({"error": "Local UI requests only"}, 403)
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size < 1 or size > 2_000_000:
                    raise ValueError("Invalid request size")
                payload = json.loads(self.rfile.read(size))
                if self.path == "/api/save":
                    return self.send(store.save(payload))
                if self.path == "/api/catalog":
                    return self.send(store.save(payload, catalog=True))
                if self.path == "/api/export":
                    return self.send(store.export_examples())
                if self.path == "/api/feedback":
                    key = payload["record_id"]
                    if key not in store.packets or not str(payload.get("actor") or "").strip():
                        raise ValueError("Enter your reviewer name")
                    assistance = store.judge_feedback(key, payload["judge_feedback"])
                    return self.send({"event_id": store.append_event({"type": "judge_feedback", "source": "human_local_ui",
                        "record_id": key, "actor": payload["actor"], "judge_assistance": assistance})})
                if self.path == "/api/event":
                    key = payload["record_id"]
                    if key not in store.packets or payload.get("evidence") not in {"metadata", "reference_sql"}:
                        raise ValueError("Unknown evidence")
                    if payload.get("unit_id") and payload["unit_id"] not in store.units:
                        raise ValueError("Unknown metadata unit")
                    return self.send({"event_id": store.append_event({"type": "evidence_viewed", "source": "human_local_ui",
                        "actor": str(payload.get("actor") or "unidentified"), "record_id": key,
                        "evidence": payload["evidence"], "unit_id": payload.get("unit_id")})})
                self.send({"error": "Not found"}, 404)
            except RuntimeError as exc:
                self.send({"error": str(exc)}, 409)
            except (ValueError, KeyError, TypeError) as exc:
                self.send({"error": str(exc)}, 400)

    return Handler


def main():
    root = Path.cwd()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--pilot", type=Path, default=root / "data/semantic-research/pilot-20261010-v3")
    parser.add_argument("--workspace", type=Path, default=root / "data/semantic-research/review-work-20261010-v2")
    parser.add_argument("--baselines", type=Path, default=root / "data/semantic-research/baselines-20261010-v3")
    args = parser.parse_args()
    store = ReviewStore(args.pilot, args.workspace, args.baselines)
    static = Path(__file__).parent / "review_ui/index.html"
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler(store, static))
    print(f"Review UI: http://127.0.0.1:{args.port} — {store.workspace}", flush=True)
    server.serve_forever()
