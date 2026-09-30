# Component and API reference

This documents implemented interfaces. Model-adapter and production-router APIs
remain proposals in [the framework contract](docs/decision-models-and-customer-training.md).
Internal Python helpers are not a versioned public compatibility guarantee.

## Task and dataset components

| Component | Interface | Result / invariant |
|---|---|---|
| `smart_router.schemas.TaskSpec` | `from_dict(spec)` | Validates task kind, class IDs/descriptions, aliases and sample unit |
| `TaskSpec` | `targets(raw, encoding, completeness)` | Canonical target encoding plus per-class values; null remains unknown |
| `smart_router.schemas` | `model_input(record)` | Returns validated `record['input']`; excludes evidence/labels |
| `smart_router.data.prepare` | `load_config(path)` | Loads dataset configuration |
| `smart_router.data.prepare` | `import_records(config, project_root)` | Returns canonical records and source provenance |
| `smart_router.data.prepare` | `assign_splits(records, settings)` | Assigns/validates grouped splits with duplicate-connected groups |
| `smart_router.data.prepare` | `audit(records, task)` | Reports dataset coverage and validation statistics |
| `smart_router.data.prepare` | `write_bundle(config, records, source, output)` | Creates a new bundle directory with audit, splits and checksums |
| `smart_router.data.pilot_bundle` | `validate_bundle(directory)` | Verifies the engineering-smoke pilot and returns its manifest |

Importer mappings require `example_id`, `group_id`, and exactly one of `text` or
`state`. At most one of `label`, `labels`, `probabilities` is mapped. Agent-step
inputs additionally map `episode_id`, `step_id`, and `step_index`. Optional split,
metadata and evidence mappings are supported. See
[prepare.py](src/smart_router/data/prepare.py) for the exact validation contract.

Two record formats are intentionally distinct:

```text
Imported canonical record
  input: {text: ...} or {state: ...}
  targets: {encoding: ..., values: {class_id: probability_or_null}}
  customer_id / dataset_id / task_id / example_id / group_id / split
  metadata / label_evidence / provenance

Frozen AMP pilot record
  input: {state: ...}
  targets: {class_id: probability_or_null}
  observation_mask: {class_id: 0_or_1}
  example_id / group_id / split / metadata / provenance
```

The explicit conversion is [export_smoke_training_data.py](scripts/export_smoke_training_data.py).
The frozen format is validated against `task.json` and `manifest.json`. It is not
a general customer-training adapter. CLI data validation failures return exit 2.

## Annotation interfaces

`smart_router.annotation.pipeline.prepare(config_path)` freezes/validates inputs;
`plan(frozen)` reports planned calls; `run(frozen, output, live=False,
retry_errors=False, candidates_only=False)` executes or resumes the pipeline.

The CLI supports `plan`, `candidates`, and `run`, with `--config`, `--output`,
`--live` and `--retry-errors`. Candidate/judge identities, contracts, generation
settings and budgets are configuration-driven. Backends cover mock responses,
external request-bound receipts, Responses HTTP and text-based Chat Completions.

Outputs include frozen run inputs, call evidence, silver labels, annotated records
and review artifacts. Original targets are not silently replaced by local-step
labels. Pass/fail frequencies use valid trials only; transport errors and
unresolved verdicts remain unknown. See [the detailed contract](docs/annotation-pipeline.md).

## Ray and CAI operations

| Entry point | Supported operations |
|---|---|
| `amp/bootstrap.py` | `validate`, `resources`, `cluster-env`, `training-env`, `launch` |
| Dedicated AMP wrappers | Argument-free scripts referenced by [.project-metadata.yaml](.project-metadata.yaml) |
| `amp/jobs.py` | `plan`, `submit`, `status`, `logs`, `stop`; `--config`, `--submission-id`, `--wait` |
| `amp/tensorboard_app.py` | `plan`, `deploy`, `serve` |
| `amp/launch_tensorboard.py` | CAI job wrapper for authenticated dashboard creation/reuse |
| `amp/serve_tensorboard.py` | Notebook-safe application entrypoint using the training virtualenv |

`amp.jobs.build_submission(root, config_path, run_id, collective_env=None)` returns
Ray Jobs arguments with one CPU/no GPU for the driver, the training Python,
explicit project paths and permitted collective settings. Credentials are used
by the submitter and excluded from the runtime payload. The current config must
have purpose `infrastructure_smoke` and exactly two workers. Submission and output
collisions are rejected; `--wait` raises on failure and requests stop on timeout.

The worker function is `smart_router.training.cluster_smoke.train_worker(config)`;
`run(config, root, run_id)` orchestrates initial and resumed TorchTrainer stages.
Persistent results include run manifest, per-worker identities, stage metrics,
Ray checkpoints, a reload checkpoint, TensorBoard events and `SUCCESS.json`.

## Management HTTP API

Use the training head's authenticated `/docs` Swagger UI. Source contracts live
in [resource routes](ray_serve_cai/management/api/resources.py) and
[request models](ray_serve_cai/management/models/requests.py).

| Method and path | Purpose |
|---|---|
| `POST /api/v1/resources/nodes` | Create a worker CAI application; admin authorization required |
| `GET /api/v1/resources/nodes` | Ray node state enriched with worker/application/pod identities |
| `GET /api/v1/resources/capacity` | Live Ray resource totals and availability |
| `GET /api/v1/resources/allocation` | Management API's tracked allocations; distinct from live capacity |
| `DELETE /api/v1/resources/nodes/{app_id}` | Remove the selected worker; admin authorization required |

Worker creation accepts `name`, `node_type`, `cpu`, `memory` (GiB), `gpus`,
`accelerator_type`, `runtime_identifier`, and optional `node_label`, `ray_labels`
and descriptive `labels`. Supplying CPU and memory permits direct creation without
a registered node-type template. `accelerator_type` is a Ray label; `node_label`
controls Kubernetes placement. The creation response supplies application and
worker IDs; pending readiness is not a successful Ray join.

Ray Jobs and Dashboard are exposed under `/dashboard/`. TensorBoard is a separate
CAI application: it reads shared event files, binds to `127.0.0.1:$CDSW_APP_PORT`,
and relies on CAI ingress for authentication/TLS. See [TensorBoard operations](docs/tensorboard.md).
