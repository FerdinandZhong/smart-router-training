# Architecture and data flow

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
     future model adapters and router training
       (not implemented by the smoke trainer)
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
