"""Single-device structural retrieval training with explicit reviewed negatives.

Uses standard positive-versus-negative softmax contrastive training. Other
positives, unknown candidates and other batch records never become negatives.
Pilot development ranking is not full-catalog context completeness.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
from pathlib import Path
import random
import re

from smart_router.semantic_intake import digest, encoded
from smart_router.semantic_pilot import checked_bundle, read_jsonl, unique
from smart_router.models.semantic_embedding import encode_documents


def query_text(row: dict) -> str:
    data = row["input"]
    # Snapshot IDs are selection metadata, never encoder text.
    return data["question"] + ("\nConfirmed history: " + json.dumps(data["confirmed_history"], ensure_ascii=False)
                                if data["confirmed_history"] else "")


def load_training(root: Path) -> tuple[dict, list[dict], list[dict]]:
    manifest = checked_bundle(root, "semantic-training-v1")
    if manifest.get("status") != "reviewed_structural_pilot":
        raise ValueError("Reviewed structural training release required")
    train, validation = [read_jsonl(root / f"{s}.jsonl") for s in ["train", "validation"]]
    if not train or not validation:
        raise ValueError("Both train and development records are required")
    unique(train + validation, "record_id")
    seen_groups, seen_inputs, snapshots = {}, {}, set()
    for split, rows in [("train", train), ("validation", validation)]:
        if manifest["splits"][split] != len(rows):
            raise ValueError("Split count mismatch")
        for row in rows:
            if row["split"] != split or row["label_scope"] != "reviewed_structural_metadata_only":
                raise ValueError("Wrong split or label scope")
            if set(row["input"]) != {"question", "confirmed_history", "catalog_snapshot"}:
                raise ValueError("Non-whitelisted model input")
            if not isinstance(row["input"]["question"], str) or not row["input"]["question"].strip():
                raise ValueError("Question must be nonempty text")
            if not isinstance(row["input"]["confirmed_history"], list):
                raise ValueError("History must be a list")
            snapshots.add(row["input"]["catalog_snapshot"])
            unique(row["candidates"], "unit_id")
            for candidate in row["candidates"]:
                if set(candidate) != {"unit_id", "text", "label"} or not candidate["text"].strip():
                    raise ValueError("Non-whitelisted or empty candidate")
                label = candidate["label"]
                if label is not None and (type(label) is not int or label not in [0, 1]):
                    raise ValueError("Unknown labels must remain null")
            if not any(c["label"] == 1 for c in row["candidates"]) or not any(c["label"] == 0 for c in row["candidates"]):
                raise ValueError("Each ranking example needs reviewed positive and negative candidates")
            for seen, key in [(seen_groups, row["data_group_id"]),
                              (seen_inputs, " ".join(row["input"]["question"].casefold().split()))]:
                if key in seen and seen[key] != split:
                    raise ValueError("Group or duplicate question crosses splits")
                seen[key] = split
    if len(snapshots) != 1:
        raise ValueError("Training rows must share one frozen pilot snapshot")
    return manifest, train, validation


def validate_config(config: dict) -> None:
    if not re.fullmatch(r"[a-f0-9]{40}", config.get("revision", "")):
        raise ValueError("Pin the encoder to an exact 40-character revision")
    for key in ["epochs", "patience", "max_seq_length"]:
        if type(config.get(key)) is not int or config[key] < 1:
            raise ValueError(f"Positive integer {key} required")
    for key in ["learning_rate", "temperature", "max_grad_norm"]:
        if not isinstance(config.get(key), (int, float)) or not math.isfinite(config[key]) or config[key] <= 0:
            raise ValueError(f"Positive finite {key} required")
    if config.get("device") not in ["cpu", "cuda", "mps"]:
        raise ValueError("Specify cpu, cuda, or mps explicitly")


def preflight(data: Path, config: dict) -> dict:
    validate_config(config)
    manifest, train, validation = load_training(data)
    return {"status": "ready_for_structural_pilot_training", "train_records": len(train),
            "development_records": len(validation), "dataset_manifest_sha256": digest((data / "manifest.json").read_bytes()),
            "config_sha256": digest(encoded(config)), "label_scope": manifest["label_scope"],
            "unknown_candidates_masked": sum(c["label"] is None for r in train + validation for c in r["candidates"]),
            "formal_evaluation": False, "gpu_execution_verified": False}


def embeddings(model, texts: list[str]):
    return encode_documents(model, texts)[0]


def candidate_scores(model, row: dict):
    observed = [c for c in row["candidates"] if c["label"] is not None]
    vectors = embeddings(model, [query_text(row)] + [c["text"] for c in observed])
    return vectors[1:] @ vectors[0], [c["label"] for c in observed]


def contrastive_loss(scores, labels: list[int], temperature: float):
    """Average one-positive softmax losses against explicit reviewed negatives."""
    import torch
    if temperature <= 0 or any(type(x) is not int or x not in [0, 1] for x in labels):
        raise ValueError("Observed labels and positive temperature required")
    positive = scores[[i for i, label in enumerate(labels) if label == 1]] / temperature
    negative = scores[[i for i, label in enumerate(labels) if label == 0]] / temperature
    if not len(positive) or not len(negative):
        raise ValueError("Positive and negative scores required")
    logits = torch.cat([positive[:, None], negative[None, :].expand(len(positive), -1)], dim=1)
    return (torch.logsumexp(logits, dim=1) - positive).mean()


def evaluate(model, rows: list[dict], temperature: float) -> dict:
    import torch
    losses, accuracies, reciprocal = [], [], []
    model.eval()
    with torch.no_grad():
        for row in rows:
            scores, labels = candidate_scores(model, row)
            losses.append(float(contrastive_loss(scores, labels, temperature)))
            pos = scores[[i for i, label in enumerate(labels) if label == 1]]
            neg = scores[[i for i, label in enumerate(labels) if label == 0]]
            delta = pos[:, None] - neg[None, :]
            accuracies.append(float(((delta > 0).float() + .5 * (delta == 0).float()).mean()))
            order = sorted(range(len(labels)), key=lambda i: (-float(scores[i]), i))
            reciprocal.append(1 / next(rank for rank, i in enumerate(order, 1) if labels[i] == 1))
    return {"contrastive_loss": sum(losses) / len(losses),
            "reviewed_pair_accuracy": sum(accuracies) / len(accuracies),
            "reviewed_pool_mrr": sum(reciprocal) / len(reciprocal), "episodes": len(rows)}


def fit(model, train: list[dict], validation: list[dict], config: dict, output: Path) -> dict:
    """Core loop, also exercised with an offline tiny SentenceTransformer fixture."""
    import torch
    if output.exists():
        raise ValueError("Use a new run directory")
    output.mkdir(parents=True)
    torch.manual_seed(config["seed"])
    rng = random.Random(config["seed"])
    optimizer = torch.optim.AdamW(model.parameters(), lr=config["learning_rate"])
    initial = evaluate(model, validation, config["temperature"])
    best_loss, best_epoch, stale = initial["contrastive_loss"], 0, 0
    model.save_pretrained(str(output / "best"))
    history = [{"epoch": 0, "development": initial}]
    for epoch in range(1, config["epochs"] + 1):
        model.train()
        order = list(range(len(train)))
        rng.shuffle(order)
        total = 0.0
        for index in order:
            optimizer.zero_grad(set_to_none=True)
            scores, labels = candidate_scores(model, train[index])
            loss = contrastive_loss(scores, labels, config["temperature"])
            if not torch.isfinite(loss):
                raise ValueError("Non-finite training loss")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), config["max_grad_norm"], error_if_nonfinite=True)
            optimizer.step()
            total += float(loss.detach())
        metrics = evaluate(model, validation, config["temperature"])
        row = {"epoch": epoch, "training_loss": total / len(train), "development": metrics}
        history.append(row)
        print(json.dumps(row), flush=True)
        if metrics["contrastive_loss"] < best_loss:
            best_loss, best_epoch, stale = metrics["contrastive_loss"], epoch, 0
            model.save_pretrained(str(output / "best"))
        else:
            stale += 1
        (output / "history.json").write_bytes(encoded(history))
        if stale >= config["patience"]:
            break
    result = {"selected_epoch": best_epoch, "epochs_completed": len(history) - 1,
              "initial_development": initial, "best_development": history[best_epoch]["development"],
              "metric_scope": "reviewed_candidate_pool_only_not_catalog_retrieval_or_context_completeness",
              "resume_supported": False}
    (output / "result.json").write_bytes(encoded(result))
    return result


def train_model(data: Path, config: dict, output: Path, local_files_only: bool = False) -> dict:
    receipt = preflight(data, config)  # Reject unreviewed data before imports, downloads, or GPU allocation.
    if output.exists():
        raise ValueError("Use a new run directory")
    import torch
    from sentence_transformers import SentenceTransformer
    if config["device"] == "cuda" and not torch.cuda.is_available():
        raise ValueError("Configured CUDA device is unavailable")
    if config["device"] == "mps" and not torch.backends.mps.is_available():
        raise ValueError("Configured MPS device is unavailable")
    model = SentenceTransformer(config["model_id"], revision=config["revision"], device=config["device"],
                                trust_remote_code=False, local_files_only=local_files_only)
    if config["max_seq_length"] > model.max_seq_length:
        raise ValueError("Requested length exceeds the pinned model's configured context")
    model.max_seq_length = config["max_seq_length"]
    _, train, validation = load_training(data)
    texts = list({query_text(r) for r in train + validation} | {c["text"] for r in train + validation
                  for c in r["candidates"] if c["label"] is not None})
    lengths = [len(model.tokenizer(t, truncation=False, verbose=False)["input_ids"]) for t in texts]
    receipt["token_audit"] = {"unique_texts": len(texts), "max_tokens": max(lengths),
                               "texts_needing_chunks": sum(n > model.max_seq_length for n in lengths),
                               "max_seq_length": model.max_seq_length, "tokens_discarded": 0,
                               "pooling": "normalized_mean_of_normalized_chunk_vectors"}
    receipt["packages"] = {p: importlib.metadata.version(p) for p in ["torch", "sentence-transformers", "transformers"]}
    result = fit(model, train, validation, config, output)
    restored = SentenceTransformer(str(output / "best"), device=config["device"], local_files_only=True)
    reload_metrics = evaluate(restored, validation, config["temperature"])
    if abs(reload_metrics["contrastive_loss"] - result["best_development"]["contrastive_loss"]) > 1e-5:
        raise ValueError("Reloaded checkpoint metrics differ")
    receipt.update({"config": config, "checkpoint_reload_verified": True, "reload_development": reload_metrics,
                    "code_sha256": digest(Path(__file__).read_bytes()),
                    "checkpoint_files": {str(p.relative_to(output)): digest(p.read_bytes())
                                         for p in sorted((output / "best").rglob("*")) if p.is_file()}})
    (output / "receipt.json").write_bytes(encoded(receipt))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["preflight", "train"])
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--local-files-only", action="store_true")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if args.command == "preflight":
        result = preflight(args.data, config)
    else:
        if args.output is None:
            parser.error("train requires --output")
        result = train_model(args.data, config, args.output, args.local_files_only)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
