"""BM25, dense and reciprocal-rank-fusion diagnostics on an unreviewed pilot.

Weak reference-SQL table coverage is a data diagnostic, never semantic accuracy.
No gold database filtering, injected positives, fine-tuning or query rewriting.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import time

from smart_router.semantic_intake import digest, encoded, write_jsonl
from smart_router.semantic_pilot import BM25, checked_bundle, finish_bundle, read_jsonl
from smart_router.training.semantic_retriever import query_text, validate_config
from smart_router.models.semantic_embedding import encode_documents


def rrf(rankings: list[list[str]], constant: int = 60) -> list[str]:
    scores = {}
    for ranking in rankings:
        if len(ranking) != len(set(ranking)):
            raise ValueError("Duplicate candidate in ranking")
        for rank, uid in enumerate(ranking, 1):
            scores[uid] = scores.get(uid, 0.0) + 1 / (constant + rank)
    return sorted(scores, key=lambda uid: (-scores[uid], uid))


def run(pilot: Path, config: dict, output: Path, local_files_only: bool = False) -> dict:
    manifest = checked_bundle(pilot, "semantic-pilot-v1")
    validate_config(config)
    if output.exists():
        raise ValueError("Use a new baseline output directory")
    from sentence_transformers import SentenceTransformer
    import numpy as np
    import torch
    model = SentenceTransformer(config["model_id"], revision=config["revision"], device=config["device"],
                                trust_remote_code=False, local_files_only=local_files_only)
    if config["max_seq_length"] > model.max_seq_length:
        raise ValueError("Configured text length exceeds the model's context")
    model.max_seq_length = config["max_seq_length"]
    model.eval()
    units = sorted([u for u in read_jsonl(pilot / "metadata_units.jsonl") if u["kind"] == "table"], key=lambda u: u["unit_id"])
    episodes = read_jsonl(pilot / "episodes.supervision.jsonl")
    started = time.perf_counter()
    with torch.inference_mode():
        index, index_audit = encode_documents(model, [u["text"] for u in units])
    index_seconds = time.perf_counter() - started
    bm25 = BM25(units)
    k, candidate_ids = manifest["candidate_k"], [u["unit_id"] for u in units]
    predictions, diagnostics, durations = [], [], []
    # Warm the model once. Timings below are single-process diagnostics, not serving-load tests.
    with torch.inference_mode():
        encode_documents(model, [query_text(episodes[0])])
    for episode in episodes:
        started = time.perf_counter()
        with torch.inference_mode():
            vectors, _ = encode_documents(model, [query_text(episode)])
            dense_scores = (index * vectors[0]).sum(dim=1).cpu().tolist()
        if not all(np.isfinite(score) for score in dense_scores):
            raise ValueError("Non-finite dense similarity scores")
        dense = [candidate_ids[i] for i in sorted(range(len(units)), key=lambda i: (-float(dense_scores[i]), candidate_ids[i]))]
        lexical = [h["unit_id"] for h in bm25.rank(episode["input"]["question"], len(units))]
        hybrid = rrf([lexical, dense])
        durations.append(time.perf_counter() - started)
        ranks = {"bm25": lexical[:k], "dense": dense[:k], "hybrid_rrf": hybrid[:k]}
        predictions.append({"record_id": episode["record_id"], "rankings": ranks})
        weak = episode["supervision_only"]["weak_table_ids"]
        if weak:
            diagnostics.append({"record_id": episode["record_id"], "structure_stratum": episode["structure_stratum"],
                "methods": {name: {"weak_table_recall_at_k": len(set(ids).intersection(weak)) / len(weak),
                                    "weak_complete_at_k": set(weak).issubset(ids)} for name, ids in ranks.items()}})
    summary = {}
    for method in ["bm25", "dense", "hybrid_rrf"]:
        summary[method] = {"weak_table_recall_at_k": float(np.mean([d["methods"][method]["weak_table_recall_at_k"] for d in diagnostics])),
                           "weak_complete_at_k": float(np.mean([d["methods"][method]["weak_complete_at_k"] for d in diagnostics]))} if diagnostics else None
    texts = [u["text"] for u in units] + [query_text(e) for e in episodes]
    lengths = [len(model.tokenizer(t, truncation=False, verbose=False)["input_ids"]) for t in texts]
    output.mkdir(parents=True)
    write_jsonl(output / "rankings.jsonl", predictions)
    write_jsonl(output / "weak_diagnostics.jsonl", diagnostics)
    return finish_bundle(output, {"format": "semantic-baseline-diagnostic-v1", "quality_claim_allowed": False,
        "pilot_manifest_sha256": digest((pilot / "manifest.json").read_bytes()), "catalog_snapshot": manifest["catalog_snapshot"],
        "config": config, "code_sha256": digest(Path(__file__).read_bytes()),
        "methods": ["bm25_k1_1.2_b_0.75", "unadapted_dense", "rrf_constant_60_not_tuned"],
        "packages": {p: importlib.metadata.version(p) for p in ["torch", "sentence-transformers", "transformers"]},
        "catalog_tables": len(units), "episodes": len(episodes), "weak_diagnostic_episodes": len(diagnostics),
        "candidate_k": k, "weak_spider_coverage": summary,
        "token_audit": {"max_seq_length": model.max_seq_length, "texts": len(texts),
                        "texts_needing_chunks": sum(n > model.max_seq_length for n in lengths),
                        "max_tokens": max(lengths), "index": index_audit, "tokens_discarded": 0},
        "timing": {"index_seconds": index_seconds, "serial_all_methods_p50_ms": float(np.percentile(durations, 50) * 1000),
                   "serial_all_methods_p95_ms": float(np.percentile(durations, 95) * 1000),
                   "scope": "single_process_warm_serial_diagnostic_no_queue_reranker_assembly_or_serving_load"},
        "limitations": ["Unreviewed structural SQL table evidence only", "BIRD gold table sets unavailable",
                        "No tuning, no context assembly, no business-semantic or SQL execution metric",
                        "Closed pilot catalog only; no large-catalog or arrival claim"]})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--local-files-only", action="store_true")
    args = parser.parse_args()
    result = run(args.pilot, json.loads(args.config.read_text()), args.output, args.local_files_only)
    print(json.dumps({k: v for k, v in result.items() if k != "files"}, indent=2))


if __name__ == "__main__":
    main()
