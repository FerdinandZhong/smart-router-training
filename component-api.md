# Component and API reference

## Training workspace contracts — 1 November 2026

`amp/training_demo/monitor.py` serves the page and the dashboard API on `127.0.0.1` (`--port` or `CDSW_APP_PORT`).
The legacy `/api/status` endpoint was removed.

- `GET /api/cluster`: Ray-observed alive GPU nodes, smoke gate and per-kind `launch` reason (`null` = launchable).
- `GET /api/jobs`, `GET /api/jobs/<id>`, `GET /api/jobs/<id>/logs`: records merged with observed Ray status
  (`NOT_SUBMITTED` for a recorded rejection, `UNKNOWN` when Ray does not report the job).
- `POST /api/jobs` with `{kind, submission_id, config}`; kinds `cluster_smoke`, `sft`, `grpo`. `201` with the job.
  `409` for duplicate ID, unmet gate or `trainer not implemented`; `400` for bad ID or paths outside the project root,
  including the smoke's resolved `output_dir/<id>`. `502` on submission failure reports only the exception type.
  Smoke entrypoints run under `timeout --kill-after=60 <job_timeout_seconds>`.
- Smoke gate: parsed `SUCCESS.json` with `initial` and `resume` objects, a GPU `infrastructure_smoke` manifest, and
  `initial-worker-<rank>.json` identities on distinct Ray node IDs that are currently alive with GPUs.
- `POST /api/jobs/<id>/stop`.
- State-changing requests need `Content-Type: application/json` and the `X-Training-Dashboard: 1` header (`415`/`403` otherwise).
- `503` with an explicit message when the CAI API key (`CDSW_APIV2_KEY` or `CML_API_KEY`) or `ray_cluster_info.json` is missing. The dashboard does not return, log or store the key, and client exception text is not echoed.
- Records: `training-jobs/<id>/job.json` (schema 1, written once) and append-only `events.jsonl`.

`amp/cluster_ready.py` (`--timeout-minutes`, default 20; `--min-gpu-nodes`, default 2) writes `.amp-state/cluster-ready.json`.

Browser draft storage key: `training-workspace-drafts-v2`.
Draft envelopes contain `id`, `name`, `created_at` and `config`.
Configuration schema version 1 contains weights, method, parameter_updates, lora, dataset, compute, training and reward.
Method is `sft` or `grpo`; parameter_updates is `lora` or `full`.
These are preview contracts, not a versioned executable trainer API.
Dataset target columns must remain outside GRPO policy inputs.
See [the current plan](docs/training-demo/PLAN.md) before adding executable endpoints.


This documents implemented interfaces. The broader interchangeable-adapter and
production-router APIs remain proposals in
[the framework contract](docs/decision-models-and-customer-training.md).
Internal Python helpers are not a versioned public compatibility guarantee.

## Isolated semantic research intake

`smart_router.semantic_intake` prepares unreviewed public-source research material.
`checked_assets()` verifies source hashes; `build()` emits structural Ossie drafts,
provisional database/duplicate groups, and a pilot queue restricted to proposed training groups.
`model_input()` projects only question, confirmed history, and catalog snapshot.
SQL, source evidence, oracle database IDs, and weak labels remain outside that projection.
All generated records remain `training_eligible=false` with unreviewed labels.
This is not an approved semantic-training exporter or a production retrieval API.
See the [collection contract](docs/research/semantic-model-routing/data-collection-bilingual.md).

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

Chat Completions generation settings accept `thinking: {"type": "disabled"}`
for explicit Anthropic gateway control. Other `thinking` settings are rejected.
They also accept the fixed strict `JUDGE_RESPONSE_FORMAT` schema for native
JSON judgments. Arbitrary JSON schemas remain unsupported. The pipeline still
validates confidence, exact fields and the pass/fail/abstain verdict.
See [original pilot gateway reannotation](docs/pilot-300-gateway-sonnet.md) for
the Sonnet-judged rebuild commands and evidence paths.

## Ray and CAI operations

| Entry point | Supported operations |
|---|---|
| `amp/bootstrap.py` | `validate`, `resources`, `cluster-env`, `training-env`, `launch` |
| Dedicated AMP wrappers | Argument-free scripts referenced by [.project-metadata.yaml](.project-metadata.yaml) |
| `amp/jobs.py` | `plan`, `submit`, `status`, `logs`, `stop`; `--config`, `--submission-id`, `--wait` |
| `amp/laya_jobs.py` | Separate Laya pilot `plan`, `submit`, `status`, `logs`, `stop`; fresh `--submission-id` required |
| `amp/setup_laya_environment.py` | Install pinned Laya dependencies and cache/checksum the model snapshot; run while training jobs are idle |
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

`smart_router.models.laya` supplies the typed-binary trainable head and versioned
token view; it currently accepts only `independent_binary`. Customer classes come
from `task.json`. `smart_router.training.laya_trial` runs the real model through
two-GPU DDP, global mask normalization, per-class validation/prior metrics, fresh
head reload and optimizer/step/data-position/RNG resume. Its separate config has
purpose `laya_pilot_smoke`; calibration/test labels are not used for training or
selection. See [the recipe and limitations](docs/laya-first-trial.md).

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
| `POST /api/v1/jobs` | Submit a Ray job using the Ray Jobs payload; admin authorization required |
| `GET /api/v1/jobs` | List Ray jobs |
| `GET /api/v1/jobs/{submission_id}` | Job status and details |
| `GET /api/v1/jobs/{submission_id}/logs` | Captured job output |
| `POST /api/v1/jobs/{submission_id}/stop` | Request termination; admin authorization required |

Worker creation accepts `name`, `node_type`, `cpu`, `memory` (GiB), `gpus`,
`accelerator_type`, `runtime_identifier`, and optional `node_label`, `ray_labels`
and descriptive `labels`. Supplying CPU and memory permits direct creation without
a registered node-type template. `accelerator_type` is a Ray label; `node_label`
controls Kubernetes placement. The creation response supplies application and
worker IDs; pending readiness is not a successful Ray join.

The management Jobs routes forward to the head's local Ray Dashboard, without
forwarding caller credentials. Submission accepts `submission_id`, `entrypoint`,
`entrypoint_num_cpus`, `entrypoint_num_gpus`, and `runtime_env`; it returns
immediately. The Swagger example runs the infrastructure smoke. These routes
are separate from `/api/v1/applications`, which deploys Ray Serve applications.
Use a fresh submission ID and matching smoke `--run-id` for each run.

Ray Jobs and Dashboard are also exposed under `/dashboard/`. TensorBoard is a separate
CAI application: it reads shared event files, binds to `127.0.0.1:$CDSW_APP_PORT`,
and relies on CAI ingress for authentication/TLS. See [TensorBoard operations](docs/tensorboard.md).

## Full Laya pilot

The [full pilot recipe](docs/laya-pilot-training.md) supports shuffled complete
training epochs, validation checkpoint selection, audited 2,048-token views and
selected-head export. It remains a frozen-encoder, independent-binary adapter.
See the [dated GPU results](docs/status/2026-10-01-laya-pilot.md); calibration and
production routing remain unimplemented.

## Gateway annotation campaign

- `scripts/list_gateway_models.py`: credential-file/environment model discovery.
- `scripts/gateway_candidate_stage.py`: paced, cached candidate phases with
  bounded transient retries and estimated monetary reservations.
- `scripts/gateway_annotation_campaign.py`: approved Flash Lite/Luna/Sol mapping,
  separate Terra judging, cached label assembly and separate dataset export.
- Annotation generation accepts JSON-object or the fixed strict judgment-schema
  `response_format` for Chat Completions, and JSON-object `text.format` for Responses.
- `validate_bundle()` accepts `engineering_smoke` and `pilot_training` manifests.
  Both require task/split checksums, valid targets and explicit unknown masks.

A launched campaign is not evidence that annotation has finished or that labels
are sufficient for training. Current progress is recorded in its run directory.

## Semantic research branch — 21 October 2026

See the [branch record](docs/research/semantic-model-routing/branch-record-20261021.md) for the current implementation, tests, artifact locations, and partial diagnostic status.
The [structural review contract](docs/research/semantic-model-routing/structural-review-v2.md) defines the automated label schema and execution commands.

## Customer-scoped selector preparation — 21 October 2026

`smart_router.semantic_scoped_data.prepare()` builds metadata-only, customer-scoped annotation episodes for Laya/GLiNER selector training.
The CLI is `scripts/prepare_semantic_scoped_data.py`. Existing output is never overwritten.
The generated labels remain unknown and cannot enter training. See [contract, results and commands](docs/research/semantic-model-routing/scoped-selector-data-20261021.md).
