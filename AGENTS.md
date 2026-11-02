# Working in this repository

## Active branch: training-demo — 2 November 2026

Read [the current training workspace plan](docs/training-demo/PLAN.md) before changing this branch.
Build a model-independent UI for standalone training jobs, not a fixed training pipeline.
Keep training method (SFT or GRPO) separate from parameter updates (LoRA/PEFT or full fine-tuning).
Selecting an earlier checkpoint records lineage; it must not trigger automatic training stages.
Numeric-reward GRPO is RLVR. Do not label it human-preference RLHF.

The current UI supports browser-local drafts, filtering, details, duplication and configuration download.
The dashboard backend submits infrastructure smoke jobs through Ray and stores records under `training-jobs/<id>/`.
The UI displays server jobs, Ray-observed status, logs and a Stop action alongside browser-local drafts.
It explicitly uses UNKNOWN or NOT_SUBMITTED when Ray supplies no status.
SFT and GRPO trainers remain unimplemented. Before a smoke passes, their requests are blocked.
After the current smoke gate passes, requests are recorded and rejected with "trainer not implemented".
Keep their Launch controls disabled until the trainers and validation are implemented.
Training curves and checkpoint reporting remain pending. Never show fabricated training metrics.
The dashboard is a loopback CAI application, not a deployed Ray Serve application.
POST requests require JSON and the page's custom header; this is a cross-origin guard, not user authentication.
Browser drafts are not submitted jobs. Model and dataset text fields are not compatibility verification.
Keep existing router environments and vendor code unchanged unless the task explicitly requires changes.
Use the UOB workspace design reference recorded in the plan.
Run `python tests/browser_training_demo.py` with the preview active for UI changes.
Keep the plan, verification evidence and root guides aligned with implemented behavior.

Semantic research remains on `research/semantic-model-routing` at `9e9a2a0`.
Preserve its data and original main-checkout work. Do not present pooled annotations as scoped training labels.


Smart Router Training is a Cloudera AI (CAI) AMP for configurable decision-model
training. Read [project-overview.md](project-overview.md), [TODO.md](TODO.md), and
[architecture.md](architecture.md) before changing behavior. Use
[development.md](development.md) for commands and verification, and
[component-api.md](component-api.md) for implemented contracts.

## Implementation boundaries

- Customer data import, agent-step annotation, the frozen pilot, AMP provisioning,
  TensorBoard, and a Ray infrastructure smoke trainer are implemented.
- A pinned Laya head trial supports masked independent-binary pilot training,
  validation and reload/resume. CLM-8B and GLiNER2.5-Decide adapters, calibration
  and production routing remain proposed. Do not generalize the Laya trial to
  unsupported task kinds or claim routing quality from its short bounded view.
- The smoke validates distributed execution using a controlled linear model. It
  reads and validates pilot data but does not learn routing labels.
- Deployment observations belong in dated status notes. A created CAI application
  is not proof that its Ray worker is alive or that NCCL works.

## Data and evaluation invariants

One agent sample is a full pre-call state for one routing decision. Preserve the
recorded history prefix; do not insert candidate-generated prior steps into this
pilot. Keep future actions, outcomes and judge evidence outside model inputs.
Use `model_input()` for canonical input projection.

Routing targets are independent per-class success observations: several or all
routes can pass or fail. Unknowns remain null and masked, never zero. Judge
confidence is not a candidate success probability. Keep episode/issue groups and
connected duplicate inputs in one split. Preserve dataset manifests, checksums,
annotation provenance and the recorded source-use limitations. Customer classes
must come from task configuration, not hardcoded tier names.

## CAI and Ray conventions

- On this branch, AMP import configures a CPU head and one group of two GPU workers.
  Each worker defaults to one L40S, 12 CPUs and 80 GiB RAM.
  `RAY_WORKER_CPU`, `RAY_WORKER_MEMORY`, `RAY_WORKER_GPUS` and
  `RAY_WORKER_ACCELERATOR_TYPE` override the marked worker group's shape.
- Import runs cluster launch, dashboard launch, TensorBoard launch, then readiness checking.
  The cluster-smoke CAI job is created but not automatically run.
- `amp/cluster_ready.py` polls the head's authenticated node endpoint for up to 20 minutes by default.
  It counts alive Ray nodes with GPUs, not CAI applications marked running.
  Node readiness does not establish free capacity or working cross-node NCCL.
- Import-time provisioning and the new dashboard integration remain unverified live.
  Check GPU quota, memory limits, credentials, endpoint authentication and launch timeouts during the first import.
- Use the existing `.venv` for the cluster and `.venv-router-train` for training
  and TensorBoard. Preserve `isolated_environment()` at process boundaries so
  CAI add-ons do not leak in through `PYTHONPATH` or `PYTHONHOME`.
- CAI/PBJ scripts may run without `__file__` and with ipykernel arguments. Use
  argument-free wrappers and explicit child arguments; do not parse kernel argv.
- TensorBoard and the training dashboard bind to `127.0.0.1:$CDSW_APP_PORT`.
  TensorBoard uses the built training venv,
  and retains CAI ingress authentication. Do not switch it to `0.0.0.0`.
- Project applications share `/home/cdsw`. The current job submission uses shared
  files rather than a Ray `working_dir` upload. Use new submission IDs for reruns.
- Do not print credentials or put them in configs, receipts, documentation, or
  Ray runtime-env payloads. Use injected variables or configured credential paths.

## Dashboard review findings — resolved 2 November 2026

The five review findings are fixed with local CPU evidence (172 unit tests and the browser test passed):

- The smoke's resolved `output_dir/<id>` must stay inside the project root.
- Dashboard smoke entrypoints run under `timeout --kill-after=60 <job_timeout_seconds>`; coreutils `timeout` on the head runtime is unverified live.
- The smoke gate parses `SUCCESS.json` and requires initial worker identities on distinct Ray nodes currently alive with GPUs.
- Submission failures return and record only the exception type.
- A failed job list is shown as stale or unavailable, never as zero jobs.

The dashboard currently reads credentials only from `CDSW_APIV2_KEY` or `CML_API_KEY`.
Credential-file fallback is not implemented. CAI application credential injection and head ingress authentication require live verification.
`GET /api/v1/resources/nodes` has no application-level admin dependency; access relies on CAI ingress authentication.
No live cluster calls or GPU runs have been performed.

## Changes and verification

Keep project-specific entrypoints in `amp/` and training/data logic in
`src/smart_router/`. Included Ray code has provenance in
[vendor/ray-serve-cai/SNAPSHOT.json](vendor/ray-serve-cai/SNAPSHOT.json). If a tracked
snapshot file changes, update its local-modification reason and effective hash;
retain the upstream hash. Do not silently refresh the vendor snapshot.

Run checks appropriate to the change; see the verification matrix in
[development.md](development.md). Report local CPU evidence separately from live
GPU/NCCL evidence. Update the relevant guide and `TODO.md` when capabilities or
verified milestones change. Historical reports remain dated evidence, not the
current status source. Include these root documentation files in the AMP bundle.
