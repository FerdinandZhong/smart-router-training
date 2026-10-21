"""Shared, differentiable chunk encoding for structural metadata baselines.

Fast-tokenizer overflow windows preserve all input tokens. Mean chunk pooling
produces one normalized vector per table/query. This representation is a pilot
choice to ablate, not a claim of optimal treatment of long semantic definitions.
"""
from __future__ import annotations


def encode_documents(model, texts: list[str], batch_size: int = 32, overlap: int = 32):
    import torch
    import torch.nn.functional as F
    if not texts or batch_size < 1:
        raise ValueError("Nonempty documents and a positive batch size are required")
    tokenizer = model.tokenizer
    if not tokenizer.is_fast:
        raise ValueError("Chunk mapping requires a fast tokenizer")
    limit = model.max_seq_length
    payload = limit - tokenizer.num_special_tokens_to_add(pair=False)
    stride = min(overlap, max(0, payload // 4))
    features = tokenizer(texts, truncation=True, max_length=limit, stride=stride,
                         return_overflowing_tokens=True, padding=True, return_tensors="pt")
    mapping = features.pop("overflow_to_sample_mapping").to(model.device)
    features = {k: v for k, v in features.items() if k in {"input_ids", "attention_mask", "token_type_ids"}}
    chunks = []
    for start in range(0, len(mapping), batch_size):
        batch = {k: v[start:start + batch_size].to(model.device) for k, v in features.items()}
        chunks.append(F.normalize(model(batch)["sentence_embedding"], p=2, dim=-1))
    vectors = torch.cat(chunks)
    counts = torch.bincount(mapping, minlength=len(texts))
    sums = torch.zeros(len(texts), vectors.shape[1], device=vectors.device, dtype=vectors.dtype).index_add(0, mapping, vectors)
    pooled = F.normalize(sums / counts[:, None], p=2, dim=-1)
    if not torch.isfinite(pooled).all():
        raise ValueError("Non-finite embeddings")
    return pooled, {"documents": len(texts), "chunks": len(mapping),
                    "multi_chunk_documents": int((counts > 1).sum()),
                    "max_chunks_per_document": int(counts.max()), "max_seq_length": limit,
                    "overlap_tokens": stride, "pooling": "normalized_mean_of_normalized_chunk_vectors",
                    "tokens_discarded": 0}
