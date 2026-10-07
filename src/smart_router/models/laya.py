"""Pinned Laya typed binary head adaptation; no inference temperature scaling."""
import hashlib
import json
from pathlib import Path

from smart_router.schemas import TaskSpec, canonical_json, model_input


def question(class_spec):
    return {"t": "noul", "ins": class_spec["description"],
            "crit": {"false": "The statement does not hold.", "true": "The statement holds."}}


def prepare_rows(records, task, tokenizer, max_len=512, head_max_len=192):
    """Versioned prefix/tail token view. Targets/evidence never enter inputs."""
    from laya.common import build_sequence
    spec = TaskSpec.from_dict(task)
    if spec.kind != "independent_binary":
        raise ValueError("Laya first trial supports independent_binary only")
    if not 64 <= head_max_len < max_len:
        raise ValueError("Require 64 <= head_max_len < max_len")
    rows, audits = [], []
    for record in records:
        text = canonical_json(model_input(record)).replace(tokenizer.mask_token, " ")
        original = tokenizer(text, add_special_tokens=False, verbose=False)["input_ids"]
        for cls in task["classes"]:
            q = question(cls)
            empty, _ = build_sequence(tokenizer, "", q, max_len, head_max_len, state_ids=[])
            budget = max_len - len(empty)
            if budget <= 0:
                raise ValueError("Question leaves no state token budget")
            if len(original) <= budget:
                retained = original
                spans = [[0, len(original)]]
            else:
                prefix = budget // 2
                tail = budget - prefix
                retained = original[:prefix] + original[-tail:]
                spans = [[0, prefix], [len(original) - tail, len(original)]]
            ids, markers = build_sequence(tokenizer, "", q, max_len, head_max_len, state_ids=retained)
            if len(markers) != 2 or len(ids) > max_len:
                raise ValueError("Invalid binary option markers or token budget")
            value = record["targets"][cls["id"]]
            observed = record["observation_mask"][cls["id"]]
            if observed != int(value is not None):
                raise ValueError("Observation mask disagrees with null target")
            rows.append({"input_ids": ids, "marker_pos": markers,
                         "target": float(value) if value is not None else None,
                         "observed": observed, "class_id": cls["id"], "example_id": record["example_id"]})
            audits.append({"example_id": record["example_id"], "class_id": cls["id"],
                           "view_policy": "canonical_input_prefix_tail_tokens_v1",
                           "original_state_tokens": len(original), "retained_state_tokens": len(retained),
                           "omitted_state_tokens": len(original) - len(retained),
                           "selected_token_spans": spans, "sequence_tokens": len(ids),
                           "input_sha256": hashlib.sha256(text.encode()).hexdigest()})
    return rows, audits


def batch(row, device):
    import torch
    return {"input_ids": torch.tensor([row["input_ids"]], device=device),
            "attention_mask": torch.ones((1, len(row["input_ids"])), dtype=torch.long, device=device),
            "marker_pos": torch.tensor([row["marker_pos"]], device=device),
            "marker_mask": torch.ones((1, 2), dtype=torch.bool, device=device),
            "qtype": torch.tensor([2], device=device)}


def load_model(model_dir):
    import torch
    from laya.common import build_model
    from safetensors.torch import load_file
    from transformers import AutoTokenizer
    root = Path(model_dir)
    cfg = json.loads((root / "rl_agent_config.json").read_text())
    # All encoder weights/config/tokenizer come from the same pinned snapshot.
    model = build_model(cfg, encoder_dir=str(root / "encoder"), pretrained=False)
    model.load_state_dict(load_file(str(root / "model.safetensors")), strict=True)
    model.encoder.config.reference_compile = False
    model.temperature.fill_(1)
    for name, param in model.named_parameters():
        param.requires_grad_(not name.startswith(("encoder.", "act_head.")))
    class Scores(torch.nn.Module):
        def __init__(self, inner):
            super().__init__()
            self.inner = inner
        def train(self, mode=True):
            super().train(mode)
            self.inner.encoder.eval()
            return self
        def forward(self, **inputs):
            return self.inner(**inputs, detach_encoder=True)[0]
    return Scores(model), AutoTokenizer.from_pretrained(str(root / "tokenizer"), local_files_only=True)


def head_state(model):
    return {name: p.detach().cpu().clone() for name, p in model.named_parameters() if p.requires_grad}


def head_hash(model):
    digest = hashlib.sha256()
    for name, value in head_state(model).items():
        digest.update(name.encode())
        digest.update(value.contiguous().numpy().tobytes())
    return digest.hexdigest()
