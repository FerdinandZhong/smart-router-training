"""Offline, single-CPU training/reload smoke on invented text and random tiny BERT.

This exercises the actual SentenceTransformer training path without downloads,
source-data approvals, GPU allocation, or benchmark-quality claims.
"""
from pathlib import Path
import tempfile
import json

import torch
from transformers import BertConfig, BertModel, BertTokenizerFast
from sentence_transformers import SentenceTransformer, models

from smart_router.training.semantic_retriever import fit, evaluate, contrastive_loss
from smart_router.models.semantic_embedding import encode_documents


def run(root: Path) -> dict:
    torch.set_num_threads(1)
    torch.manual_seed(123)
    base = root / "tiny-bert"
    base.mkdir()
    vocab = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]", "people", "age", "animals", "count", "person", "dog"]
    (base / "vocab.txt").write_text("\n".join(vocab) + "\n")
    BertTokenizerFast(vocab_file=str(base / "vocab.txt"), do_lower_case=True).save_pretrained(base)
    BertModel(BertConfig(vocab_size=len(vocab), hidden_size=24, num_hidden_layers=1,
                        num_attention_heads=2, intermediate_size=32, max_position_embeddings=64,
                        hidden_dropout_prob=0., attention_probs_dropout_prob=0.)).save_pretrained(base)
    model = SentenceTransformer(modules=[models.Transformer(str(base), max_seq_length=32), models.Pooling(24)], device="cpu")
    model.eval()
    long_text = "people age " * 60
    pooled, audit = encode_documents(model, [long_text, "animals dog"])
    assert pooled.shape == (2, 24) and audit["multi_chunk_documents"] == 1 and audit["tokens_discarded"] == 0
    # Manual overflow-token mapping must cover every original input token.
    ids = model.tokenizer(long_text, add_special_tokens=False, verbose=False)["input_ids"]
    windows = model.tokenizer(long_text, truncation=True, max_length=32, stride=7, return_overflowing_tokens=True)["input_ids"]
    restored_ids = windows[0][1:-1]
    for window in windows[1:]:
        restored_ids.extend(window[1:-1][7:])
    assert restored_ids == ids
    rows = [{"record_id": "synthetic", "input": {"question": "people age", "confirmed_history": [], "catalog_snapshot": "fixture"},
             "candidates": [{"unit_id": "a", "text": "person age", "label": 1},
                            {"unit_id": "b", "text": "people person", "label": 1},
                            {"unit_id": "c", "text": "animals dog", "label": 0},
                            {"unit_id": "d", "text": "people age", "label": None}]}]
    config = {"seed": 7, "epochs": 4, "patience": 4, "learning_rate": .003, "temperature": .1, "max_grad_norm": 1.}
    before = torch.cat([p.detach().flatten().clone() for p in model.parameters()])
    result = fit(model, rows, rows, config, root / "run")
    after = torch.cat([p.detach().flatten() for p in model.parameters()])
    assert not torch.equal(before, after), "Weights did not change"
    assert result["best_development"]["contrastive_loss"] < result["initial_development"]["contrastive_loss"]
    restored = SentenceTransformer(str(root / "run" / "best"), device="cpu", local_files_only=True)
    actual = evaluate(restored, rows, .1)
    assert abs(actual["contrastive_loss"] - result["best_development"]["contrastive_loss"]) < 1e-6
    changed_unknown = json.loads(json.dumps(rows))
    changed_unknown[0]["candidates"][-1]["text"] = "animals dog unknown text"
    assert actual == evaluate(restored, changed_unknown, .1), "Unknown candidate affected training metrics"
    scores = torch.tensor([.8, .7, .1], requires_grad=True)
    contrastive_loss(scores, [1, 1, 0], .1).backward()
    assert scores.grad[0] < 0 and scores.grad[1] < 0 and scores.grad[2] > 0
    return {"status": "passed", "scope": "invented_fixture_single_CPU_not_research_results",
            "weights_changed": True, "unknown_mask_verified": True, "multiple_positive_gradients_verified": True,
            "reload_verified": True, "chunk_coverage_verified": True, "selected_epoch": result["selected_epoch"]}


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="semantic-training-smoke-") as tmp:
        print(json.dumps(run(Path(tmp)), indent=2))
