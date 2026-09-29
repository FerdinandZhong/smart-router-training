# Ray training smoke implementation: first-trial

> Deployment architecture update (2026-09-29): option 2 is implemented as a
> self-contained AMP. Use [AMP deployment](amp-deployment.md) for current setup,
> data paths, cluster ownership and launch commands. The existing-cluster reuse,
> local-upload workflow and serving handoff below describe the earlier design.
> The model-specific Laya experiment and its acceptance criteria remain planned;
> the AMP's implemented `cluster-smoke` is a separate infrastructure diagnostic.

Prepared 2026-09-29. This is a concrete implementation plan; no training job was submitted and no live deployment was changed during the review.

## Objective and verified starting point

Implement a reusable training operation in this project, submitted as a Ray Job named `first-trial` to the existing `ray-serve-cai` cluster. Ray Train's `TorchTrainer` owns the two training workers; PyTorch owns optimization and DDP. Prove data loading, forward/backward, synchronized updates, checkpointing, reload and job operations before claiming routing quality.

Live authenticated GET checks confirmed:

- Ray 2.58.0; `/dashboard/api/version` and `/dashboard/api/jobs/` return HTTP 200.
- One healthy head and two healthy `gpu-worker` nodes, each exposing one L40S GPU and 16 CPUs.
- Two total GPUs and **zero currently available GPUs**; the Qwen Serve application is running.
- The public Dashboard/Jobs API root is `https://ray-cluster-head.ml-16e5d8cb-7c9.qzhong-a.a465-9q4k.cloudera.site/dashboard/`. The browser fragment `#/cluster` is not part of an API address.

Read-only evidence: `data/inspection/training-cluster-2026-09-29.json`. Ray GPU reservations are verified; GPU memory availability, installed Torch/CUDA versions, training environment and checkpoint-path write access still need preflight. A successful GET does not yet validate package upload or job submission through the proxy.

The annotation campaign completed all 300 states: 210 train, 30 validation, 30 calibration, 30 test. There are 846 observed state/class labels and 54 unknowns. The original ten-state recovery view and 290-state campaign are the two authoritative label sources.

| Class | Pass | Fail | Unknown |
|---|---:|---:|---:|
| FAST | 27 | 219 | 54 |
| GENERAL | 291 | 9 | 0 |
| REASONING | 296 | 4 | 0 |

These are single-trial, local-step silver observations. Formatting dominates many FAST failures, and GENERAL/REASONING have few negatives. The first run measures the implementation; it cannot establish useful calibrated routing or downstream success.

## Text-format architecture

The following components are proposed implementation, built around the existing cluster. One sample is one decision state with its recorded history prefix; candidate outputs from earlier pilot steps are not substituted into that history.

```text
DATA AND TASK CONTRACT
  Current pilot: 300 recorded decision states + authoritative silver labels
  Future customer data: decision states + configured class IDs + labels
                 |                         |
                 +------------+------------+
                              v
  Export / validate / freeze
    - example IDs, issue-group splits, source hashes, class schema
    - independent per-class targets + observation masks
    - unknown -> mask 0; observed fail -> target 0, mask 1
                              |
                              v
  Prepared dataset + TaskSpec + immutable manifest
    train 210 | validation 30 | calibration 30 | test 30
    Smoke uses train/validation; calibration/test remain held out
                              |
                              v
  Model adapter: versioned state view + tokenizer + trainable logits
    First: Laya typed pass/fail question for each configured class
    Later: CLM / GLiNER-decide adapters after compatibility checks

SUBMISSION AND EXECUTION
  Local submission CLI + first-trial configuration + prepared dataset
    Authentication: ~/tokens/cdp_sandbox -> local request header only
                              |
                              v
  Existing authenticated nginx /dashboard/ -> Ray Jobs API
                              |
                              v
  Job first-trial: CPU-only driver, isolated training environment
                              |
                              v
  Ray Train TorchTrainer: 2 workers, SPREAD, NCCL / PyTorch DDP
             +----------------+----------------+
             v                                 v
  GPU worker on Ray node A          GPU worker on Ray node B
    1 L40S, 2 CPUs                     1 L40S, 2 CPUs
    full model replica                full model replica
    frozen encoder + head             frozen encoder + head
             |                                 |
             +<--- synchronized gradients ---->+
                              |
                              v
  Shared NFS: data/cache + isolated environment + run artifacts
    manifests | metrics | checkpoints | reload/resume evidence
                              |
                              v
  Reloaded model -> {configured class ID: success probability}
```

The class probabilities are independent; they do not need to sum to one. The current 0/1 labels are single observed outcomes used to learn these probabilities, not measured probability estimates. Customer-provided soft targets can use the same contract, with their estimation method recorded in the manifest.

## Text-format execution flow

```text
Freeze pilot export and TaskSpec
             |
             v
Check masks / split integrity / objective / checkpoint contracts
             |
             v
CPU smoke + pin adapter revisions and training dependencies
             |
             v
Provision isolated NFS environment; verify both GPU nodes
             |
             v
Check Jobs authentication/upload and shared storage access
             |
             v
Training window: snapshot Qwen config -> managed serving shutdown
             |
             v
Verify 2 available GPUs + released GPU memory + collective paths
             |
             v
Submit Ray Job first-trial
             |
             v
Two-GPU controlled diagnostic: backward + parameter synchronization
             |
             v
Release diagnostic workers -> real Laya head fit, up to 100 steps
             |
             v
Validation metrics + checkpoint -> fresh reload -> short resume job
             |
             v
Save evidence -> release training resources -> serving restoration

Failure at any runtime stage
  -> save failed-stage logs and evidence
  -> release that job's resources
  -> follow recorded serving-restoration policy
  -> fix the failed gate before repeating the experiment
```

The Qwen service currently reserves both GPUs. The training window must release those reservations before a two-worker job can run. The resource handoff is an execution step; preparing this plan does not change the service.

## Reuse boundary

Reuse the sibling project's existing CAI Applications, Ray head/worker topology, authenticated nginx routing, managed Serve lifecycle, NFS-mounted environment convention, and scoped collective-network runbook. Implement training entry points here; the sibling checkout has no working training implementation to call. Keep inference serving and training as separate workloads on the same cluster.

Relevant reusable sources:

- `../ray-serve-cai/cai_integration/templates/ray_head_launcher.py.j2`: established head startup and internal Dashboard.
- `../ray-serve-cai/ray_serve_cai/configs/nginx/conf.d/server.conf.j2`: `/dashboard/` proxy, including the Ray Jobs API.
- `../ray-serve-cai/ray_serve_cai/engines/venv_utils.py` and `docs/ISOLATED_ENV_DESIGN.md`: shared-NFS named environment and interpreter handling.
- `../ray-serve-cai/docs/CROSS_NODE_GPU_DEPLOYMENT.md`: current TCPStore/Gloo/NCCL diagnostics and scoped network workaround, superseding older cross-pod limitations.
- Management resource and application APIs: inspect GPU allocation and release the Qwen deployment through its normal lifecycle for a training window.

Do not reuse inference TP placement groups as a trainer layout. Each DDP worker needs its own full model replica; the two GPU memories are not pooled. No nested `torchrun`, upstream notebook DDP launcher, or independent process-group initialization inside Ray Train.

## Implementation sequence

### 1. Freeze the smoke data

Create `scripts/export_smoke_training_data.py` and `data/training/pilot-smoke-v1/`.

- Join labels to original inputs by `example_id`, verify exact coverage, immutable hashes, class identity, and original issue-group/split assignments.
- Use the original pilot's unknown-only recovery view; do not replace observed failures or count serving retries as repeated trials.
- Materialize `targets` plus an observation mask. Unknown FAST values get mask zero, never a negative label. Keep annotation/evidence metadata outside model input.
- Retain the 210/30/30/30 splits. Train on train only and use validation for smoke metrics. Do not fit calibration or select on test.
- Export a configurable TaskSpec and label-source manifest, not hard-coded positional FAST/GENERAL/REASONING columns. Support future customer class sets through the same contracts.
- Record `purpose=engineering_smoke` and explicit opt-in to these unreviewed silver labels. Original source eligibility/evidence flags remain intact; this is not automatic promotion to a production training dataset.

### 2. Build the shared training interfaces

Add `src/smart_router/training/` with configuration, dataset/collation, objectives, metrics, checkpoint and Ray entry-point modules. Add `src/smart_router/models/` with a registry and model-adapter interface.

Proposed implementation files:

```text
configs/training/first-trial.json        # Data, classes, adapter, resources
scripts/export_smoke_training_data.py   # Canonical pilot/customer export
scripts/setup_training_env.py           # Isolated, NFS-safe provisioning
scripts/check_training_cluster.py       # Resources, runtime, storage, network
scripts/submit_training_job.py          # Plan/submit/status/logs/stop/resume
src/smart_router/training/
  config.py                            # Validated run and task contracts
  dataset.py                           # Input rows, targets, masks, collation
  objectives.py                        # Masked objectives and DDP normalization
  metrics.py                           # Support, loss, Brier, prior baseline
  checkpoint.py                        # Save/reload/resume and provenance
  ray_entrypoint.py                    # TorchTrainer and worker training loop
src/smart_router/models/
  base.py                              # Adapter contract
  registry.py                          # Configurable adapter selection
  laya_typed_binary.py                  # First real model adapter
data/training/pilot-smoke-v1/            # Frozen export and manifest
```

The adapter owns tokenizer/serialization, tensor preparation, model construction, trainable parameters and probability extraction. The core owns masks, grouped splits, optimization, distributed normalization, artifacts and metrics. Configuration owns customer classes, model/recipe selection, data path and versions; Ray owns execution resources. Swapping the dataset must not require edits to the trainer.

For independent route sufficiency, compute one binary success probability per configured class. Multiple classes may pass simultaneously. For a shared-logit adapter use masked BCE; for the first typed Laya adapter use one pass/fail question per route and masked soft cross-entropy, with target distribution `[1-p, p]`. Do not apply a three-way softmax across model tiers. Declare objective compatibility explicitly for future customer single-label and multilabel tasks.

DDP must normalize loss by the globally observed target weight, not average rank-local means with different masks. Report global counts and losses. All workers execute compatible backward/report schedules; zero-observation batches are handled collectively. Validation must exclude sampler padding from metrics. Test masking, distributed normalization and checkpoint restoration with small controlled fixtures.

### 3. First real adapter and context policy

Implement a pinned `laya_typed_binary` adapter for `convaiinnovations/laya`, beginning with the encoder frozen and the decision head trainable. Freeze the unused action head. Load trainable logits directly, not the inference `predict()` API. Pin upstream package/source, checkpoint and tokenizer revisions; record encoder/head token budgets and disable inherited inference temperature overrides for raw training logits.

The [checkpoint configuration](https://huggingface.co/convaiinnovations/laya/raw/main/rl_agent_config.json) specifies ModernBERT-large and a default encoder budget of 512 tokens. It does not solve the full-history context limit. For this first smoke use a deterministic, versioned bounded view built from the prior user task and selected recent observations, with actual tokenizer accounting including question/options. Log selected/omitted spans and original/retained token counts. Labels still describe the full recorded state, so bounded-view training introduces information loss; the smoke checks engineering behavior, not validity of this context policy. Long-context experiments and better decision views are later gates.

A tiny controlled PyTorch model is a separate infrastructure diagnostic before the actual Laya stage. Passing that diagnostic alone does not count as completing Laya fine-tuning. If Laya cannot load or train in the pinned environment, report that failed stage rather than silently substituting a model.

### 4. Environment and cluster preflight

Create `scripts/check_training_cluster.py` and `scripts/setup_training_env.py` (idempotent, NFS-safe provisioning). Proposed environment: `/home/cdsw/.venv-router-train`; proposed storage: `/home/cdsw/training-runs/smart-router/`. Verify those paths on the actual cluster.

- Pin Ray 2.58.0 in client, driver and workers. Verify Python, Torch/CUDA, BF16 support and adapter dependency compatibility on both nodes; isolate training packages from `.venv-vllm`.
- Use explicit interpreter/runtime environment handling and the sibling's PATH lesson; ensure the driver and workers actually use the intended environment.
- Verify both workers can read the dataset and model cache and write/read shared checkpoints. Install/download once on NFS with a lock; never race package installs in workers.
- Check two exclusive GPU resources before submitting training. With zero available GPUs, fail resource preflight instead of leaving an unexplained pending trainer.
- For the training window, snapshot the Qwen deployment's existing configuration, release it via the managed application lifecycle, wait for placement-group/GPU memory release, and recheck capacity. Keep the head, GPU host pods and management API running. Restore the serving configuration after the smoke if requested by the operations policy.
- Recheck current pod labels and the actual rendezvous/collective paths; reuse the scoped network recipe. Prior TP inference success is evidence, not proof of training backward or Ray Train rendezvous.

### 5. Ray Jobs submission and trainer

Implement `scripts/submit_training_job.py` with `plan`, `submit`, `status`, `logs`, `stop` and `resume` operations. Use [Ray Jobs](https://docs.ray.io/en/latest/cluster/running-applications/job-submission/sdk.html), rather than a laptop-side persistent Ray Client session.

Local submission reads `~/tokens/cdp_sandbox` and adds the bearer header to the Jobs client; do not package the token file or inject the CAI credential into training workers. Package only source, training configuration and prepared smoke data, excluding raw datasets, annotation runs, credentials, model caches and sibling worktrees. Test runtime-env package upload through the authenticated proxy; an in-project/head-local submission is the fallback if upload is blocked.

Use `submission_id=first-trial` for the initial job and refuse collisions. Keep a separate immutable experiment manifest/run ID; follow-up jobs use explicit suffixes such as `first-trial-resume-001` and link to the original checkpoint.

Proposed operation interface (not yet implemented):

```bash
python scripts/export_smoke_training_data.py --config configs/training/first-trial.json
python scripts/submit_training_job.py plan --config configs/training/first-trial.json
python scripts/submit_training_job.py submit --config configs/training/first-trial.json --submission-id first-trial
python scripts/submit_training_job.py logs --submission-id first-trial
python scripts/submit_training_job.py status --submission-id first-trial
```

The Ray job driver reserves CPU only, zero GPUs. Inside the cluster, `ray.init(address="auto")` and `TorchTrainer` request two workers with one GPU and two CPUs each, NCCL backend and SPREAD placement. With one GPU per GPU node, verify distinct live Ray node IDs and exposed GPU identity; distinguish pod/node identity from physical Kubernetes-host identity if that metadata is unavailable. Do not claim separate physical machines merely from separate pod IPs.

Start with one question row per worker, BF16 if verified, head-only AdamW and a configurable 100 optimizer-step cap. Run a small controlled two-GPU synchronization diagnostic first, release its trainer workers, then the real pilot stage. Expand to a full epoch/full encoder tuning after profiling. No speedup claim is required for 300 samples.

### 6. Checkpoints, metrics and acceptance

Write immutable manifests, environment/version records, worker identity evidence, train/validation metrics and checkpoints to shared storage. Checkpoints include trainable weights, frozen encoder reference, optimizer/scheduler, step/epoch, data/sampler position, RNG state, task/class schema, tokenizer/view policy and dataset hashes. All ranks participate in report cadence; checkpoint ownership follows the pinned Ray API.

Acceptance for `first-trial`:

1. Ray Jobs submission reaches RUNNING/SUCCEEDED with inspectable logs.
2. Two exclusive GPU workers are on distinct Ray nodes; NCCL and backward complete.
3. Controlled diagnostic loss decreases and synchronized trainable parameters agree across ranks.
4. Real Laya head receives finite gradients and its weights change; train/validation masked losses and per-class support are saved. A falling real-pilot loss is informative but does not prove useful routing.
5. A fresh model reload returns finite per-class probabilities with the correct configured schema; frozen encoder/head provenance is complete.
6. A short checkpoint-resume run restores optimizer and step/data position and performs further updates.
7. GPU resources are released at completion/failure and serving restoration follows the recorded operations policy.

Compare validation loss/Brier scores to constant per-class training-prior predictions. Accuracy alone can be misleading for nearly all-positive Terra/Sol labels. Report unknown coverage and both positive/negative support; do not claim calibrated performance from this smoke.

## Confidence and unresolved items

These are subjective engineering estimates, not measured success probabilities.

| Area | Confidence | Evidence / remaining gate |
|---|---|---|
| Data export and customer-configurable masks/classes | High, ~95% | Existing canonical importer, frozen splits and completed labels; export still to implement/test |
| Reuse existing cluster and Ray Jobs route | High, ~90% | Live nodes and authenticated GET APIs verified; upload/POST not exercised |
| Two-node TorchTrainer scheduling and DDP | Medium-high, ~80% | Two one-GPU nodes and validated collective runbook; training process-group/backward still untested |
| Laya head tuning in isolated environment | Medium-high, ~80% | Upstream model/training source exists; pinned package/runtime compatibility and memory still untested |
| Full operation including checkpoint resume | Medium-high, ~80% | Standard Ray/PyTorch path and shared-NFS precedent; fresh restore must be proven |
| Useful router quality from this pilot | Low | Label imbalance, formatting failures, limited trials and bounded-view information loss |

Implement in order: export/contracts → model/objective/checkpoint unit checks → CPU smoke → isolated environment and Jobs preflight → managed GPU handoff → `first-trial` diagnostic and real Laya head fit → reload/resume evidence. The first milestone is a repeatable training operation on the current cluster; richer datasets and model comparison follow through the same interfaces.
