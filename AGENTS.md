# Working in this repository

Smart Router Training is a Cloudera AI (CAI) AMP for configurable decision-model
training. Read [project-overview.md](project-overview.md), [TODO.md](TODO.md), and
[architecture.md](architecture.md) before changing behavior. Use
[development.md](development.md) for commands and verification, and
[component-api.md](component-api.md) for implemented contracts.

## Implementation boundaries

- Customer data import, agent-step annotation, the frozen pilot, AMP provisioning,
  TensorBoard, and a Ray infrastructure smoke trainer are implemented.
- Laya, CLM-8B and GLiNER2.5-Decide are proposed interchangeable adapters. Their
  fine-tuning, calibration and production routing are not implemented.
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

- AMP launches the CPU head and TensorBoard. GPU workers are created separately
  through the management API; networking probes precede GPU training.
- Use the existing `.venv` for the cluster and `.venv-router-train` for training
  and TensorBoard. Preserve `isolated_environment()` at process boundaries so
  CAI add-ons do not leak in through `PYTHONPATH` or `PYTHONHOME`.
- CAI/PBJ scripts may run without `__file__` and with ipykernel arguments. Use
  argument-free wrappers and explicit child arguments; do not parse kernel argv.
- TensorBoard binds to `127.0.0.1:$CDSW_APP_PORT`, uses the built training venv,
  and retains CAI ingress authentication. Do not switch it to `0.0.0.0`.
- Project applications share `/home/cdsw`. The current job submission uses shared
  files rather than a Ray `working_dir` upload. Use new submission IDs for reruns.
- Do not print credentials or put them in configs, receipts, documentation, or
  Ray runtime-env payloads. Use injected variables or configured credential paths.

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
