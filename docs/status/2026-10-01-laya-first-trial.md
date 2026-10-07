# Laya first pilot trial — 2026-10-01

Ray Jobs `laya-setup-20261001-001` and `laya-first-trial-20261001-001`
SUCCEEDED. The latter performed 20 initial updates, validation, independent fresh
CPU head reload, and two resumed updates on the same two L40S worker nodes.
Read-only artifact job `laya-evidence-20261001-002` independently retrieved
`SUCCESS.json`, stage metrics, validation summaries, worker identities and view
coverage. Its first attempt (`...001`) had a report-string syntax error; it did
not affect the completed training job and the corrected report succeeded.

## Model and environment

Source commit: `4066d5d5fbf08b66c6757ddeedbd797bd7655bc0`, Laya 0.3.20.
Checkpoint: `convaiinnovations/laya` revision
`55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851`.
The same snapshot supplies weights, encoder configuration and tokenizer. Setup
verified the package's installed VCS commit and saved snapshot SHA-256 hashes and
full package inventory under `/home/cdsw/.amp-state/`.

Both ranks report Torch 2.8.0+cu128, CUDA 12.8, Ray 2.58.0, NVIDIA L40S and BF16.
Recipe dependencies include Transformers 4.57.6, tokenizers 0.22.2,
huggingface-hub 0.36.0 and safetensors 0.7.0. The encoder and unused action head
are frozen. The 26,248,193 trainable parameters belong to the typed decision head.

## Distributed and checkpoint gates

| Gate | Observed result |
|---|---|
| Distinct Ray nodes | `0a7fec928ac8894b64a642054a328782fd25a9d31c42a61e08c47684` and `51cd2c8b7ddf8e652f39fb7ff4d1609311ac343aaafa45b957141e4c` |
| Data identity | Both stages/ranks: manifest SHA-256 `20d9c8ac81ff12e806711bdc5a3c21559737d8794c4933a6e8d54d031de2321f` |
| Head gradients | Finite and nonzero on both ranks |
| Initial updates | Step 0 → 20; changed head, identical per-rank head hashes |
| Fresh reload | Head hash matched; finite class-aligned probabilities returned |
| Resume | Restored optimizer, step/data position and per-rank RNG; step 20 → 22 |
| Resume updates | Head changed again; per-rank hashes matched |
| Peak CUDA allocated | Initial: 2,245,836,800 bytes (2.092 GiB); resume rank-zero metric: 2,243,706,880 bytes |
| Completion | SUCCESS.json, reload checkpoint and both stage event files present |
| Resource release | Live capacity reported both GPUs available after completion |

Initial head hash: `206a3c4cb53553f7442af4773de41f462bd295a6a2ea90d89e16de50acd0497d`.
Resumed head hash: `bbe32b14efdadaed16f751f7cde83408109378acea02506a8be31e7fb250d1bd`.
Fresh reload example probabilities: FAST 0.36362144, GENERAL 0.38294843,
REASONING 0.36169493. They are independent and uncalibrated.

## Validation versus constant training priors

All 30 validation states were evaluated, without sampler padding. Unknown targets
are excluded. No calibration/test labels were used for optimization or selection.
Lower log loss and Brier are better. The short trained model underperformed the
constant training-prior baseline on every class.

| Class | Observed / unknown | Positive / negative | Prior probability | Initial log loss | Resumed log loss | Prior log loss | Resumed Brier | Prior Brier |
|---|---|---|---|---|---|---|---|---|
| FAST | 24 / 6 | 3 / 21 | 0.116959 | 0.550085 | 0.550526 | 0.377077 | 0.179977 | 0.109440 |
| GENERAL | 30 / 0 | 26 / 4 | 0.976190 | 0.643014 | 0.643328 | 0.519240 | 0.225414 | 0.127551 |
| REASONING | 30 / 0 | 29 / 1 | 0.985714 | 0.814786 | 0.814483 | 0.155526 | 0.309442 | 0.032585 |

The deterministic short recipe consumes 44 question rows across 22 two-rank steps,
not a full epoch across the 210 training states. Changing samples and masks mean
adjacent training-loss values are not a controlled before/after comparison.
Useful routing, calibration or downstream success cannot be inferred from this run.

## Context loss

Every prepared question row required truncation. Median retained state-token
fraction was 5.135% for train (630 question rows) and 6.004% for validation
(90 question rows). The actual model sequence never exceeded 512 tokens,
including question/options. The prefix/tail view is a compatibility policy, not
validated retrieval or complete-history comprehension. Source-token counting
triggered a tokenizer >8192 warning; the overlong sequence was counted for audit,
not passed to the model. Subsequent code suppresses that counting-only warning.

## Artifacts and local evidence

Remote root: `/home/cdsw/training-runs/laya-first-trial-20261001-001`.
Stage metrics, validation predictions and context audits are readable JSON/JSONL;
head checkpoints include optimizer, task/classes, data position and rank RNG.
TensorBoard reads `laya-first-trial-20261001-001/tensorboard/{initial,resume}`.

All 86 local unit tests passed, including four new masking, global normalization,
configurable-class and leakage/view tests. The adapter is explicitly limited to
independent-binary tasks. The source-use release/redistribution gate in the pilot
manifest remains applicable. Next work should improve the context view, run a
fuller training recipe and strengthen class-negative/unknown evidence before
claiming quality.
