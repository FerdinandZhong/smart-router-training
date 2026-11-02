# AMP setup with a training dashboard application — design, 1 November 2026

## Goal

The demo needs two training jobs on Mistral Small: PEFT with SFT + LoRA, and GRPO with a numeric reward + LoRA.
They run one after the other, and each job uses both L40S GPUs.
The AMP should bring up all the infrastructure.
The training dashboard submits training jobs; the Ray cluster management app manages resources only.

## Agreed decisions

- Each job spans 2 workers × 1 L40S, so cross-node NCCL is a hard prerequisite for training.
- The dashboard submits directly to the Ray Jobs API, reusing `amp/jobs.py` (approach A).
  It does not forward to the management app's `/api/v1/jobs`.
- Launching the workers is configuration, not new code. `cai_integration/launch_ray_cluster.py` already supports
  `worker_groups` with `count`, `cpu`, `memory`, `gpus`, `accelerator_type` and `input_template`.

## AMP flow

```text
validate_pilot -> configure_project_resources -> setup_cluster_environment -> setup_training_environment
-> launch_training_cluster     CPU head + management app; worker group: 2 × (1 L40S, 12 CPU, 80 GiB)
-> launch_training_dashboard   new authenticated CPU app; serves 127.0.0.1:$CDSW_APP_PORT
-> launch_tensorboard          unchanged
-> check_cluster_ready         new; passes only when Ray reports >= 2 alive nodes with GPU resources
Manual: administrator runs scripts/setup_cross_node_gpu.fish (TCPStore/Gloo/NCCL probes must pass)
Dashboard: launch "Cluster smoke" (existing 2-worker NCCL smoke) -> SUCCESS.json is the training gate
Dashboard: launch SFT / GRPO jobs once their trainers exist (next milestone)
```

A created CAI application does not count as a ready worker. `check_cluster_ready` polls with a timeout.
On failure it prints each node's observed state.

## Dashboard backend

- It extends `amp/training_demo/monitor.py` and keeps that one small stdlib server.
- It runs under `.venv-router-train`, behind `isolated_environment()`.
- It binds only `127.0.0.1`. CAI ingress provides authentication and TLS.
- Job records live under `training-jobs/<submission_id>/` in the project:
  - `job.json` holds the immutable submitted configuration, schema version, created time and Ray submission ID.
  - `events.jsonl` is an append-only list of state transitions.
- The browser's local drafts stay as drafts. Server records are authoritative for submitted jobs.
- API:
  - `GET /api/cluster` returns head URL presence, alive GPU nodes, and whether the smoke gate passed.
  - `GET /api/jobs` lists records merged with observed Ray status.
  - `GET /api/jobs/<id>` returns one record.
  - `GET /api/jobs/<id>/logs` returns the Ray Job logs.
  - `POST /api/jobs` submits a job.
  - `POST /api/jobs/<id>/stop` stops a job.
- Job kinds:
  - `cluster_smoke` is launchable now.
  - `sft` and `grpo` are validated and recorded. Submission returns `409 trainer not implemented` until the trainers exist.
  - `sft` and `grpo` also require the smoke gate.
- Status comes from observed Ray Job status. It never comes from app creation or from a checkpoint appearing.
- Security:
  - State-changing requests require same-origin and a JSON content type.
  - Submission IDs are validated with the existing regex.
  - Dataset and model paths must resolve under the project root.
  - Arguments are built with `shlex`.
  - The API key is read from the app environment and never returned, logged or stored.
  - A missing key gives an explicit error.

## UI

- The existing page keeps its look.
- Launch is enabled only when `/api/cluster` reports the gate as satisfied.
- Job history shows server jobs alongside browser drafts.
- Details show Ray status and logs.
- Missing or stale telemetry is shown explicitly.

## Verification

- Local CPU:
  - Unit tests with a fake Ray client cover submit, duplicate IDs, the gate, path rejection, stop and the missing-key error.
  - Browser tests run against a stubbed backend.
  - Existing tests still pass.
- Live (separate, dated status note): AMP import, readiness, networking probe, dashboard-launched smoke.
  No live evidence exists yet.
