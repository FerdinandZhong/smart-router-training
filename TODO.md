# Current work and priorities

Updated: 2026-09-30. This is the current milestone record. Older batch reports and
[implementation history](docs/IMPLEMENTATION_STATUS.md) retain historical evidence.
Live application states must be rechecked before operating the cluster.

## Completed

- [x] Configurable customer classes; JSONL/CSV/optional Parquet ingestion,
  hard/soft/partial labels, audits and grouped splits.
- [x] Candidate/judge annotation with deterministic action checks, resumable
  receipts, bounded retries, unknown handling and review artifacts.
- [x] Frozen 300-state pilot: 100 issue groups, 846 observed targets, 54 unknowns;
  split sizes 210/30/30/30. See the [manifest](data/pilot/pilot-smoke-v1/manifest.json).
- [x] Self-contained AMP with pinned Ray code, isolated environments and
  notebook-safe setup wrappers.
- [x] CPU Ray head running in the training CAI project.
- [x] TensorBoard CAI application running, confirmed by application API and user;
  loopback binding, built training venv and AMP launch job implemented.
- [x] TorchTrainer infrastructure diagnostic, checkpoint resume and per-step
  TensorBoard events implemented. Local two-process CPU/Gloo validation passed.
- [x] Latest implementation verification: 75 unit tests and a real local
  TensorBoard HTTP/scalar test passed.
- [x] Two GPU worker applications created, each requesting 16 CPUs, 64 GiB and
  one GPU. Creation alone does not establish worker readiness.

## P0 — finish live distributed infrastructure validation

- [ ] Confirm both workers join Ray and expose one GPU each. Latest checked state
  at this documentation update: both CAI applications were `APPLICATION_STARTING`;
  Ray still reported zero GPUs. Stable identities:

  | Worker | CAI application ID |
  |---|---|
  | training-gpu-01 | ls0w-mxik-9si3-8g18 |
  | training-gpu-02 | a2pu-asoj-xk2w-yaey |

- [ ] Record current worker pod names and the correct Kubernetes namespace/context.
- [ ] Run the scoped networking setup against those pods; require TCPStore,
  Gloo and NCCL probes to pass. See [AMP deployment](docs/amp-deployment.md).
- [ ] Submit a fresh `cluster-smoke` Ray Job. Acceptance: workers on distinct Ray
  nodes, identical dataset hashes, synchronized finite updates, checkpoint resume
  from step 20 to 22, and `SUCCESS.json`.
- [ ] Confirm the actual smoke's initial/resume curves appear in TensorBoard.
  The `tensorboard-setup-check` event is synthetic deployment evidence only.

## P1 — first decision-model training trial

- [ ] Implement and verify a differentiable Laya adapter against a pinned checkpoint;
  check actual context handling, memory use and two-worker training compatibility.
- [ ] Add task-driven heads/losses and class-order metadata. Acceptance: changing
  customer classes requires configuration, not editing a fixed three-tier head.
- [ ] Train a small pilot baseline with observed-label masks; preserve holdouts
  and report this as a smoke experiment, not a quality benchmark.
- [ ] Expand independent task diversity and audit annotation quality, especially
  GENERAL/REASONING separation and unknown missingness.
- [ ] Add executable replay and human-reviewed evaluation evidence before claiming
  downstream success. Resolve the source-use gate recorded in the pilot manifest
  before model release or dataset redistribution.

## P2 — comparative quality and operations

- [ ] Implement CLM-8B and GLiNER2.5-Decide adapters behind a common contract.
- [ ] Add learning curves, calibration, abstention and routing-cost evaluation.
- [ ] Add configurable metric cadence and sampled per-rank CPU/CUDA profiling.
- [ ] Evaluate Prometheus/Grafana integration for sustained resource monitoring;
  the training AMP does not currently provision those applications.
- [ ] Exercise failure recovery beyond the controlled checkpoint-resume diagnostic.

Update this file with the date, evidence and remaining limitation whenever an item
is completed. Do not mark a live GPU gate complete based on a local CPU test.
