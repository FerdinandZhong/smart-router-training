# Architecture and data flow

## Training workspace architecture — 1 November 2026

The current branch adds independent-job UI preparation alongside the existing router components.
The browser stores local drafts and downloads configuration JSON. No submission endpoint is implemented.

```text
Browser form -> Local draft -> Job detail / configuration download

Planned production path:
Browser -> Authenticated job API -> Persistent job store
                       |                    ^
                       v                    |
                    Ray Job -> Trainer -> Events / metrics / checkpoints
```

Starting weights are an explicit input for each job. Checkpoint lineage does not imply a pipeline.
The loopback preview is not the planned Ray Serve deployment.
See [the job lifecycle and implementation plan](docs/training-demo/PLAN.md).


## Components

```text
Customer records / recorded agent trajectories
                    |
           task + column mappings
                    v
    schemas + data import / audit / grouped splits
                    |
         +----------+-------------------+
         |                              |
  customer labels                 agent candidates
         |                       FAST / GENERAL / REASONING
         |                              |
         |                   checks + independent LLM judge
         |                              |
         |                   silver observations + unknowns
         |                              |
         |                   explicit pilot export / validation
         +------------------------------+
                    |
           versioned data bundle
                    |
     Laya typed-binary head pilot training
     + future adapter/calibration/routing work
```

`src/smart_router/schemas.py` owns task semantics and model-input projection.
`data/prepare.py` imports and splits customer records; `data/swe_gym.py` extracts
recorded pre-call prefixes. `annotation/` performs candidate/judge evaluation,
without executing candidate tools or downstream continuations.

Canonical imported records contain `input`, structured `targets`, metadata,
evidence and provenance. The AMP pilot exporter deliberately creates a separate
smoke format with flat class targets and explicit observation masks. Treat the
formats as distinct contracts; see [component-api.md](component-api.md).

## CAI deployment and training

```text
AMP setup in one CAI project / shared /home/cdsw
  |
  +-- .venv: Ray 2.58.0 + cluster management
  |      -> CPU head -> authenticated management API + Ray Dashboard/Jobs
  |                          |
  |                    manual POST /resources/nodes (twice)
  |                          |
  |                    GPU worker A + GPU worker B
  |
  +-- .venv-router-train: Ray 2.58.0 + Torch 2.8.0 + TensorBoard 2.20.0
  |      -> TensorBoard CPU application -> shared training-runs/ events
  |
  +-- data/pilot/pilot-smoke-v1: repository-included pilot
  |
  +-- manual pod networking setup and collective probes
         -> amp/jobs.py -> authenticated Ray Jobs API
              -> CPU driver -> TorchTrainer -> two GPU workers
                   -> controlled optimization + checkpoint + resume
                   -> shared training-runs/<submission-id>/
```

The head and workers use a pinned snapshot of `ray-serve-cai` included in this
repository. They do not rely on the sibling checkout at runtime. Only the head
and TensorBoard are automatically launched by AMP; worker creation and network
preparation remain explicit operational stages.

Ray jobs use the existing shared filesystem and the training Python through
`runtime_env.py_executable`. There is no dataset upload or working-directory
bundle in the current submission path. This assumes every application belongs
to the same CAI project; a separate-project/object-storage design is future work.

The infrastructure smoke validates data visibility and hashes, distinct Ray nodes,
synchronized weights and checkpoint restoration. Its fixed per-rank `y=2x` inputs
are independent of the routing labels. Rank zero writes TensorBoard events;
all workers participate in loss reduction. TensorBoard reads these files and
binds to loopback behind CAI's authenticated ingress.

## Failure and reproducibility boundaries

- Transport/provider errors and uncertain judgments remain unknown observations.
  Annotation caches and run hashes bind evidence to inputs/configuration.
- Grouped splits prevent episode leakage; input validation rejects structured
  future-evidence fields. Semantic leakage still requires review.
- AMP setup verifies dependencies and dataset/vendor hashes. CAI-injected Python
  add-ons are excluded from virtualenv child processes.
- Network probes are required for each new worker-pod pair. Ray node readiness
  alone does not establish NCCL connectivity.
- Submission IDs and output directories are unique. The smoke uses no automatic
  trainer retries; its explicit second stage tests checkpoint resume.
- Run manifests, worker identities, metrics, events and checkpoints remain on
  shared storage when the TensorBoard application is stopped.

See [deployment details](docs/amp-deployment.md), [annotation design](docs/annotation-pipeline.md),
and [proposed adapter contract](docs/decision-models-and-customer-training.md).

## Laya pilot extension

`amp/setup_laya_environment.py` extends the idle training environment with pinned
Laya/Transformers packages and downloads one revision of checkpoint, encoder
configuration and tokenizer into shared `model-cache/`. The setup lock, installed
source commit and artifact hashes are recorded under `.amp-state/`.

`amp/laya_jobs.py` submits `smart_router.training.laya_trial` through Ray Jobs.
Two GPU workers run one full model replica each: encoder and action head frozen,
26.2 million decision-head parameters trainable. Independent per-class questions
use raw binary logits and global observed-target normalization. The bounded
512-token view records omitted context; full-state labels remain unchanged.
Validation is sharded without padding and compared to training-prior constants.
A CPU driver freshly loads the head checkpoint before a two-step GPU resume.
Calibration/test labels do not contribute to optimization or model selection.
See [Laya recipe and limitations](docs/laya-first-trial.md).

## Full Laya pilot

The [full pilot recipe](docs/laya-pilot-training.md) supports shuffled complete
training epochs, validation checkpoint selection, audited 2,048-token views and
selected-head export. It remains a frozen-encoder, independent-binary adapter.
See the [dated GPU results](docs/status/2026-10-01-laya-pilot.md); calibration and
production routing remain unimplemented.

## Semantic research branch — 21 October 2026

See the [branch record](docs/research/semantic-model-routing/branch-record-20261021.md) for the current implementation, tests, artifact locations, and partial diagnostic status.
The [structural review contract](docs/research/semantic-model-routing/structural-review-v2.md) defines the automated label schema and execution commands.
