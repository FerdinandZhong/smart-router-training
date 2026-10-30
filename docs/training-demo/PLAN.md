# Small Mistral training demo — 30 October 2026

## Purpose and current state

Demonstrate LoRA supervised fine-tuning, then GRPO post-training, using the existing CAI Ray infrastructure.
The read-only dashboard explains progress and compares model outputs. Job submission stays in the CLI.
This branch contains preparation tooling and a dashboard prototype, not a verified trainer or deployed Ray Serve application.
No training job, worker allocation, cluster upgrade or model download occurred during preparation.

## Research handoff

Semantic research is preserved on `research/semantic-model-routing` at `9e9a2a0`.
That commit includes the 21 October literature review, scoped preparation implementation and research records.
The original main checkout retains its unrelated uncommitted router experiments.
Both old research worktrees expired; branch commits and main-checkout dataset artifacts survive.
Recover with `git worktree add --ignore-other-worktrees /tmp/semantic-research-return research/semantic-model-routing` if necessary.

The semantic package remains at the original project's `data/semantic-research/scoped-selector-20261021-v1/`.
It contains 13,601 questions, 209 provisional customer catalogs and a 240-question pilot.
The new scoped annotation runner was discussed but has not been implemented or launched.
No scoped training labels are approved. Prior pooled review labels are not equivalent.
Resume by adapting scoped annotation, testing 20 cases, then processing the remaining pilot under the validated contract.
See [semantic preparation](../research/semantic-model-routing/scoped-selector-data-20261021.md).

## Model and framework decision

Primary candidate: `mistralai/Ministral-3-3B-Instruct-2512-BF16`, Apache-2.0.
Use text-only examples. Pin the exact model revision before downloading or training.
This model contains vision capability; verify its Transformers loader, chat template, PEFT module paths and TRL support explicitly.
The published inference memory estimate is not a training memory guarantee.
Do not substitute a different model silently if the compatibility check fails.

Use TRL `SFTTrainer` and `GRPOTrainer` with PEFT LoRA, orchestrated by Ray Train `TorchTrainer`.
Ray's official GRPO example provides a direct integration starting point.
The repository pins Ray 2.58.0; the inspected online example documents 2.59.0.
Keep head and worker Ray versions aligned. Resolve a compatible training stack in a separate `.venv-training-demo`.
Pin Torch, Transformers, TRL, PEFT, Accelerate and datasets after the compatibility smoke.
Do not replace the current `.venv-router-train` dependencies.

| Framework | Decision | Reason |
|---|---|---|
| TRL + PEFT + Ray Train | Primary | Shared SFT/GRPO interfaces; direct Ray example; smallest new integration surface |
| verl | Later option | Ray-based actor/rollout orchestration and GRPO; useful when rollout throughput or sharding becomes central |
| Custom GRPO implementation | Excluded | Existing frameworks already implement the optimizer and generation lifecycle |

GRPO with numeric correctness rewards is RL with verifiable rewards (RLVR).
It is not human-preference RLHF. PEFT is a parameter-update technique and can be used in both training stages.

## Data already prepared

The official GSM8K repository is pinned at `3101c7d5072418e28b9008a6636bde82a006892c`.
The MIT license, source checksums, output checksums and deterministic subset recipe are retained.
Artifacts: original project `data/training-demo/gsm8k-v1/`.

| Subset | Examples | Use |
|---|---:|---|
| SFT | 1,024 | Prompt plus supplied solution; loss on completion tokens only |
| GRPO | 512 | Disjoint prompts plus separate reward answers |
| Validation | 128 | Disjoint official-train questions for monitoring and checkpoint selection |
| Test | 256 | Official-test questions; final comparison only |

Question hashes separate subsets. Exact normalized train/test question overlap is rejected.
Do not pass `answer` fields into prompts or the SFT text formatter.
These are demo subsets, not an unbiased research benchmark; model pretraining contamination is unknown.

Reward: 1 for a correct numeric answer following a final `####` marker, otherwise 0.
The parser requires a complete final answer and uses Decimal comparisons, not eval or an LLM judge.
Log malformed outputs and zero-variance reward groups. A group of all correct or all wrong answers provides no relative learning signal.
Start with correctness-only rewards. Avoid rewarding format alone at the expense of correctness.
Keep generation length and temperature fixed across controlled comparisons.

## Training sequence and compute

```text
Frozen data + pinned model
           |
           v
Original-model evaluation
           |
           v
LoRA SFT -> save/reload adapter -> validation
           |
           v
GRPO with LoRA -> save/reload adapter -> validation
           |
           v
Original / SFT / SFT+GRPO held-out comparison
           |
           v
Shared run artifacts -> read-only dashboard
```

1. Inspect live cluster resources, GPU types, free memory, Ray versions and active allocations.
2. Use one existing L40S worker for model loading, one update, saving and fresh reload.
3. Verify finite loss, nonzero adapter gradients, changed adapter weights and unchanged frozen parameters.
4. Run LoRA SFT with rank 16, alpha 32, 1,024-token examples and an initial 100-step limit.
5. Continue from the SFT adapter using GRPO, four generations per prompt and an initial 50-step limit.
6. Start with native Transformers generation; add vLLM only after correctness and memory validation.
7. Verify global generation-batch divisibility by four against the pinned TRL API.
8. Scale to two workers only after cross-node networking/NCCL and one-worker correctness pass.
9. Evaluate original, SFT and SFT+GRPO with the same greedy decoding and held-out questions.

The recipe's hyperparameters are starting proposals, not measured performance claims.
Keep 256 generated tokens initially; record truncation because incomplete solutions can distort rewards.
Use explicit shared `/home/cdsw` paths and unique Ray submission IDs.
Avoid resource claims that double-reserve GPUs in the Ray driver and training workers.
Do not silently reduce requested training workers when resources are unavailable.
For GRPO reference policy, verify that the KL reference remains the intended SFT policy when continuing its adapter.
Resume must restore adapter, optimizer, scheduler, RNG and trainer step. Test interrupted recovery before claiming support.

## UI and telemetry

Design reference found: `../uob-ai-data-operations-workspace/demo/static/styles.css` and `DESIGN.md`.
The requested `../uob_ai_data_platform` path does not exist in this workspace.
Reuse its white panels, system font, light background, blue actions and restrained red brand accent.
No step confirmation wizard, architecture editor or default infrastructure graph.

The initial page has four stages, current status, step count, GPU allocation, validation accuracy and recent activity.
Keep detailed configuration collapsed. Add optional topology only after reliable per-rank telemetry exists.
Loss/reward charts and output comparisons must use recorded metrics, with separate axes and stage labels.
The current prototype displays empty chart/comparison states; the live telemetry writer and chart renderer remain pending.
No fabricated training curves or cluster status are included.

Target deployment: a CPU Ray Serve monitor behind existing authenticated CAI ingress.
Reuse the current Serve proxy instead of starting a conflicting proxy on the head.
Until that adapter is implemented, `amp/training_demo/monitor.py` serves a loopback local/CAI preview.
Do not expose the Python preview server directly to the public internet.
Telemetry must include run ID, stage, timestamp, heartbeat, actual worker count, steps, metrics and checkpoint identity.
Use atomic snapshot replacement; mark stale or disconnected telemetry visibly.
Sanitize logs and do not expose credentials, arbitrary files or Ray administrative actions to the browser.

## Commands and acceptance

```bash
# From the training-demo worktree; choose a fresh output directory.
PYTHONPATH=src python -m smart_router.training_demo.data --output data/training-demo/gsm8k-v1
python amp/training_demo/monitor.py --port 8096
PYTHONPATH=src python -m unittest discover -s tests -p test_training_demo.py -q
```

- Prepared: isolated branch, research handoff, source-backed framework decision, frozen demo data, reward function and UI prototype.
- Verified locally: reward contract tests and dataset hash/split audit; browser evidence recorded separately.
- Pending: model/package pins, live cluster preflight, trainer adapters, telemetry bridge, Ray Serve deployment and GPU SFT/GRPO runs.
- Demo acceptance: both stages update adapters, reload successfully, report actual metrics and produce a held-out comparison.
- Quality acceptance: report improvement or regression honestly; a successful short run does not guarantee improvement.

## Primary references checked 30 October 2026

- [Ray TRL GRPO example](https://docs.ray.io/en/latest/train/examples/transformers/transformer_reinforcement_learning/README.html)
- [TRL GRPOTrainer](https://huggingface.co/docs/trl/grpo_trainer)
- [TRL SFTTrainer source documentation](https://github.com/huggingface/trl/blob/main/docs/source/sft_trainer.md)
- [verl GRPO](https://verl.readthedocs.io/en/latest/algo/grpo.html)
- [Ministral 3 3B BF16 model card](https://huggingface.co/mistralai/Ministral-3-3B-Instruct-2512-BF16)
- [Official GSM8K repository](https://github.com/openai/grade-school-math)

The hosted SFT documentation challenged the browser; the official repository documentation provided the fallback.
