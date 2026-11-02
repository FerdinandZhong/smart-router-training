# Training workspace plan — 1 November 2026

## Decision and purpose

Build a general-purpose training workspace on the existing CAI Ray infrastructure.
Every training job is an independent task. Users configure and launch jobs through the UI.
Users can inspect active jobs, completed jobs, failures, checkpoints and saved configurations.
The product has no required model family or SFT-to-GRPO sequence.
Selecting an earlier checkpoint establishes lineage; it does not schedule another stage automatically.

This plan supersedes the [initial sequential demonstration proposal](INITIAL-DEMO-20261030.md).
The historical proposal remains useful for source references and the research handoff.
Branch: `training-demo`, based on semantic research commit `9e9a2a0`.
The original main checkout and its unfinished router work remain separate.

## Method and configuration model

Training objective and parameter updates are separate choices.

| Setting | Initial scope | Validation required |
| --- | --- | --- |
| Training method | SFT or reinforcement learning with GRPO | Trainer and dataset compatibility |
| Parameter updates | PEFT with LoRA or full fine-tuning | Model module support and GPU memory |
| Starting weights | Model repository or shared checkpoint | Exact revision, readable files and supported loader |
| Existing adapter | Optional adapter path | Base-model identity and adapter compatibility |
| Dataset | Shared JSONL/Parquet or dataset repository | Schema, revision, splits and permissions |
| Column mapping | Prompt plus completion for SFT; prompt plus reward answer for numeric GRPO | Answers stay outside policy inputs |
| Compute | GPU workers and resources per worker | Actual available capacity and worker readiness |
| Schedule | Steps, learning rate and micro batch size | Valid optimizer settings and effective batch |
| GRPO reward | Initial numeric exact-match function | Parser tests, generation grouping and reward variance |

PEFT is not an alternative objective to SFT or GRPO.
Numeric rewards constitute RL with verifiable rewards (RLVR), not human-preference RLHF.
Do not advertise preference-based RLHF until preference data, reward models and the chosen trainer are implemented.
Model-specific examples may prefill a configuration, but must not determine the application architecture.

## User experience

1. Open Training jobs to inspect active runs and history.
2. Select New training job and configure weights, method, dataset and compute.
3. Validate the configuration and review resource requirements.
4. Launch one job through the authenticated backend.
5. Inspect its status, metrics, logs, evaluation and checkpoints.
6. Optionally use its configuration or checkpoint when creating another independent job.

```text
Training jobs / history <---------- Job details
          |                            ^
          v                            |
New job -> Validate -> Submit -> Persistent job record
                                    |
                                    v
                          Ray Job -> Ray Train workers
                                    |
                                    v
                          Metrics and checkpoints
```

Use the UOB workspace's light background, white panels, system typography and compact blue actions.
The inspected reference is `../uob-ai-data-operations-workspace`; `../uob_ai_data_platform` was not found.
Keep model geometry editors and topology diagrams out of the default view.
Expose technical settings through focused fields or disclosures.
Show missing, stale and disconnected telemetry explicitly.
Never substitute sample training curves for live data.

## Implemented now

The UI preview provides job history for local drafts, search and method filtering.
The form separates SFT/GRPO from LoRA/full fine-tuning and shows method-specific fields.
Users can select weight and dataset locations, column mappings, compute counts and schedule settings.
The summary updates while editing. Drafts persist in browser localStorage.
Job details display the saved configuration and empty metrics/artifact states.
Users can duplicate a draft and download its JSON configuration.
Launch is enabled only when `/api/cluster` accepts that kind: the cluster smoke needs two Ray-alive GPU nodes; SFT/GRPO also need the smoke gate and an implemented trainer, so they stay disabled with a stated reason.

The preview server binds to loopback on port 8096, or the configured CAI application port.
It is not a deployed Ray Serve application.
The legacy `/api/status` snapshot endpoint was removed; nothing used it. The backend API is `GET /api/cluster`, `GET /api/jobs`, `GET /api/jobs/<id>`, `GET /api/jobs/<id>/logs`, `POST /api/jobs` and `POST /api/jobs/<id>/stop`.
Records live in `training-jobs/<id>/job.json` (immutable) and `events.jsonl`. Status is always Ray-observed. See the [design](../superpowers/specs/2026-11-01-amp-training-dashboard-design.md).
Browser drafts are local convenience storage, not an authoritative run database.
The preview validates basic fields only; model, data and GPU compatibility checks remain pending.

The existing GSM8K preparation and numeric reward function remain usable demonstration assets.
Frozen subsets contain 1,024 SFT, 512 GRPO, 128 validation and 256 test examples.
The subsets do not require sequential training. Each job chooses its own dataset and starting weights.
See [the dataset manifest](data-manifest.json) for revision, hashes and licensing.

## Backend implementation plan

1. [Done locally] Define a server-side job schema and immutable submitted-configuration record.
2. [Partly done] Persist jobs, events and Ray submission IDs; ownership and artifact references remain.
3. Add validation that resolves model/data revisions and checks dataset columns before GPU allocation.
4. [Done for the cluster smoke only] Add authenticated submission with idempotency and explicit failure reporting.
5. Add SFT and GRPO adapters behind a shared job contract.
6. Add metrics, checkpoint and evaluation collection per job.
7. Connect the UI to live history and enable submission only after validation succeeds.
8. [Implemented, not yet deployed live] Deploy the dashboard as a CAI application (`amp/training_dashboard_app.py`), not through Ray Serve.

Proposed states: draft, validating, queued, running, succeeded, failed, cancel_requested and cancelled.
Keep validation failures visible with corrective messages.
Do not mark a job running because a worker application was created.
Do not infer success from a process disappearing or a checkpoint file appearing.
Use observed Ray state and trainer completion artifacts together.
Cancellation must target the recorded submission ID and preserve its history.

Treat paths and downloaded model identifiers as untrusted inputs.
Apply server-side path restrictions, ownership checks and safe argument construction before adding executable endpoints.
Do not enable arbitrary remote model code automatically.
Keep gateway tokens and CAI credentials out of browser storage, job configurations, logs and runtime payloads.

## Training framework and compute

Start with TRL SFTTrainer/GRPOTrainer and PEFT, orchestrated by Ray Train TorchTrainer.
Use verl later if rollout throughput or distributed RL orchestration requires it.
The source-backed comparison is preserved in the historical proposal.
Pin the training stack in an isolated environment; keep head and worker Ray versions compatible.
The repository Ray pin is 2.58.0; the inspected official example used 2.59.0.
Do not upgrade the shared cluster or existing router environment implicitly.

Begin with one-worker model loading, one gradient update, checkpoint saving and fresh reload.
Verify changed trainable weights and unchanged frozen weights for LoRA.
Validate GRPO group sizes, reward correctness, zero-variance groups and reference-policy identity.
Only then test multi-worker networking, synchronized training and interrupted-run resume.
No live resource availability or GPU training success has been established for this branch.

## Acceptance and verification

| Area | Current evidence | Remaining gate |
| --- | --- | --- |
| UI | Browser checks cover forms, persistence, filtering, duplication and download | Connect real backend and test submission failures |
| Responsive layout | Checks passed at 1440, 980 and 390 pixels | Repeat after backend-driven content changes |
| Data | Pinned sources, hashes and disjoint subsets verified | Dataset inspection and tokenization for each selected model |
| Reward | Five unit tests passed | Real generation outputs and reward distribution audit |
| Training | No demo trainer execution | SFT and GRPO update/reload tests on GPU |
| Deployment | Local loopback preview | Authenticated CAI/Ray Serve deployment |

Do not claim quality improvement from a successful training launch.
Compare selected checkpoints on the same held-out questions and report regressions as well as improvements.
Keep training reward separate from held-out accuracy.

## Research return point

Semantic research remains at `research/semantic-model-routing`, commit `9e9a2a0`.
Its scoped inventory contains 13,601 questions, 209 provisional customer catalogs and a 240-question pilot.
No scoped examples are training-approved. The scoped annotation runner remains pending.
Resume the metadata-only annotation contract on 20 pilot cases before expanding to the remaining cases.
Do not reuse pooled judgments as customer-scoped labels.
See [semantic preparation](../research/semantic-model-routing/scoped-selector-data-20261021.md).

## Mistral Small demo jobs (2 × L40S)

Two independent jobs: **A** SFT with LoRA on the frozen SFT subset, **B** GRPO with the numeric reward and LoRA on the GRPO subset. Job B is RL with verifiable rewards, not preference RLHF.
If the model is about 24B parameters, bf16 weights alone are about 48 GB, a full L40S. Feasibility needs 4-bit QLoRA, sharding across both GPUs, or a smaller model, and is not yet evidenced.
The UI presets prefill these jobs and show an unverified memory estimate. Confirm the exact model repository and revision before any run.
