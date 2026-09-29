# Jev, Laya, and Ray readiness review

Reviewed: 2026-09-27. This is a source/code review, not a local model benchmark or live cluster validation.

Follow-up: the [CLM/GLiNER comparison and customer framework contract](decision-models-and-customer-training.md) expands the candidate set and generalizes the training framework. The Laya-first recommendation below records the initial review; v2.1 requires a configurable multi-model comparison.

## Decision

Adopt a Jev-style typed decision interface and make Laya the first fine-tuning experiment. Keep the backbone replaceable: Laya is useful pretrained decision infrastructure, but it does not remove the long-context or outcome-labeling problems. The [v2 implementation plan](agent-step-router-implementation-plan.md) turns this into staged work.

## What the supplied paper establishes

The 12-page [Jev Engineering for Coding Agents](Jev-Engineering-for-Coding-Agents.pdf) explicitly identifies itself on pp. 1 and 12 as an independent synthesis of design notes, not an official TypeSafe research publication. Treat its architecture as inspiration and its cost examples as illustrative, not measured performance on our workloads.

| Pages | Useful idea | Change to our project |
|---|---|---|
| 2–3 | Typed decisions over explicit state | Keep generation in the routed models; return probabilities through a stable router interface |
| 3–4 | Switching models can create context reload costs | Optimize measured episode cost, including cache hits, uncached prefill, verification, retries, and return-to-strong-model costs |
| 6–7 | Query-aware context selection | Store addressable observations and assemble a bounded decision view; do not blindly truncate a transcript |
| 9–10 | Conditional instructions and trust-aware routing | Preserve applicable instructions and enforce deterministic eligibility before cost optimization |
| 10–11 | Shared retrieval for background work | Reuse retrieval artifacts eventually; this is outside the first router training milestone |

The routing example on p. 4 compares `25Y + 5Z` against `3X + 20Y + 8Z`. It demonstrates why transfer and reread costs matter under its assumptions. It does not establish that routing universally loses money, and the listed provider prices are not current pricing inputs.

TypeSafe's [official introduction](https://typesafe.ai/blog/introducing-system-one-models-and-jev) corroborates the typed, parallel probability-output concept. It does not give us an open Jev checkpoint or establish Laya as the same architecture. Typed output validity also does not guarantee a correct decision or calibrated confidence.

## Laya: verified behavior and implementation consequences

Reviewed upstream source commit `4066d5d5fbf08b66c6757ddeedbd797bd7655bc0`, package version `0.3.20`. Public checkpoint configurations were fetched separately; their weight revisions still need pinning before experiments.

| Candidate | Evidence | Consequence |
|---|---|---|
| English Laya | [Root configuration](https://huggingface.co/convaiinnovations/laya/blob/main/rl_agent_config.json): `answerdotai/ModernBERT-large`, `max_len=512`, `head_max_len=192` | A decision-finetuned ModernBERT model, not a longer-context replacement |
| Multilingual Laya | [Configuration](https://huggingface.co/convaiinnovations/laya-multilingual/blob/main/rl_agent_config.json): `jhu-clsp/mmBERT-base`, `max_len=1024`, `head_max_len=256` | First candidate for a shared English/Chinese enterprise router |
| Longer input | [Multilingual model card](https://huggingface.co/convaiinnovations/laya-multilingual) describes an 8,192-token override and variable long-document accuracy | Test 1K/2K/4K/8K; supported length is not evidence of reliable long-range reasoning |
| Long-context alternative | [Qwen3-0.6B-Base model card](https://huggingface.co/Qwen/Qwen3-0.6B-Base) lists 32,768 context | A sequence-classification adaptation is a fallback experiment, not an existing Laya checkpoint |

The root [model card](https://huggingface.co/convaiinnovations/laya) reports weak zero-shot results on its typed-decisions benchmark, sensitivity to option wording, overconfidence, and an unreliable act/escalate signal. Use task-specific training and fresh calibration. Do not use `act_probability` as our abstention detector. Published short-input timings and unmatched Jev comparisons do not predict our long-context routing latency.

Source findings, with permanent links:

- [`common.py`](https://github.com/NandhaKishorM/laya/blob/4066d5d5fbf08b66c6757ddeedbd797bd7655bc0/laya/common.py): `build_sequence` inserts option markers mechanically. `DecisionModel` uses encoder states, two additional transformer layers by default, option scoring, and a separate action head. `[MASK]` identifies option positions; we do not need teacher-generated cloze examples. Head layers attend over the sequence, so their long-input memory cost must be measured too.
- [`agent.py`](https://github.com/NandhaKishorM/laya/blob/4066d5d5fbf08b66c6757ddeedbd797bd7655bc0/laya/agent.py): questions become separate batch rows, repeating state encoding per question. “One forward pass” is a batch operation, not constant work for arbitrarily many questions. `predict_long` uses window-based maximum/most-confident selection; it is unsuitable as an unvalidated success-probability aggregator. `predict` is an inference path, not the training API.
- [Fine-tuning notebook](https://github.com/NandhaKishorM/laya/blob/4066d5d5fbf08b66c6757ddeedbd797bd7655bc0/notebooks/laya_finetune_typed_decisions_2xT4_kaggle.ipynb): contains an actual PyTorch DDP training example with RLCD-style updates plus soft cross entropy. It is a Kaggle script, not Ray integration. Port model construction and target handling, but implement grouped splits, synchronized DDP batching, and complete resume state ourselves.

ModernBERT already supports [sequence classification](https://huggingface.co/docs/transformers/v5.13.0/en/model_doc/modernbert). MLM pretraining and supervised router fine-tuning are different objectives. Neither plain ModernBERT classification nor Laya adaptation requires paying an LLM to manufacture masked sentences. Both require reliable routing labels; Laya may improve sample efficiency, but that remains an experiment.

## Ray: latest repository evidence

Inspected `../ray-serve-cai`, branch `feature/blueprint_fix`, HEAD `d5d43f7` (2026-09-24), including existing uncommitted documentation. No changes were made to that repository.

The current [cross-node runbook](../../ray-serve-cai/docs/CROSS_NODE_GPU_DEPLOYMENT.md) describes two L40S GPU worker pods, one GPU each, vLLM 0.29.0, and TP=2. Its September 24 follow-up records:

- Qwen3.8: 100/100 HTTP 200 and exact `OK` responses at concurrency 4, zero errors/timeouts, p95 1.903 s.
- Qwen3.6: 100/100 HTTP 200 with nonempty content, zero errors/timeouts, p95 1.567 s; responses were `OK.`.

These are repeated short-generation tests. They support starting the training integration; they do not prove long-context throughput, DDP backward, optimizer synchronization, or recovery. The runbook includes TCPStore/Gloo/NCCL probe instructions. A fresh Ray Train run must save its own evidence.

The working mesh solution replaces both HTTP and TLS inspection filters for a scoped set of GPU pods and an ephemeral-port range. Preserve its scope. The old [September 6 training design](../../ray-serve-cai/docs/superpowers/specs/2026-09-06-cross-node-training-readiness-design.md) and `AGENTS.md` describe earlier constraints; the later validated runbook supersedes the old statement that cross-node TP remains blocked. Pod replacement can require restoring the selected labels. Ray Train rendezvous ports must be checked separately; setting `MASTER_PORT` blindly is not proof they match the runbook.

The current checkout has no `cai_ray/train` implementation. Read-only inspection of local branch `feature/ray-cai-v2-platform` at `98b9a5c` found `cai_ray/cli.py` still routes `train` to `_cmd_stub`, and `causal_lm.py` declares unimplemented training stages. Do not depend on a working `cai-ray train` command or merge the whole old platform branch to begin this project.

Ray's [PyTorch guide](https://docs.ray.io/en/latest/train/getting-started-pytorch.html) provides the appropriate `TorchTrainer` path. Pin the actual cluster's Ray version rather than assuming the latest documentation version matches the deployment. Use one full router replica per GPU with gradient synchronization; inference tensor parallelism and training data parallelism have different memory and execution behavior.

## Corrections carried into v2

1. Start with decision-model transfer learning, retaining a plain classifier baseline.
2. Make long-context retention an explicit model-selection gate.
3. Predict independent tier sufficiency, not a mutually exclusive tier softmax.
4. Separate teacher belief, observed local success, and observed downstream success.
5. Preserve untested tiers as missing; three successful trials cannot certify 95% reliability.
6. Add cache-aware measured costs and on-policy trajectory evaluation.
7. Treat Ray inference as established repository evidence and Ray training as work to implement and validate.
