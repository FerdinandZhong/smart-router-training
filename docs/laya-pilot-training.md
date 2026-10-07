# Full Laya pilot training

This recipe trains the pinned Laya decision head on the complete frozen training
split. The encoder remains frozen. Only `independent_binary` tasks are supported;
class questions, masks and order derive from `task.json`.

## Submit inside CAI

After the verified environment and two GPU workers are available:

```bash
.venv-router-train/bin/python amp/laya_jobs.py plan \
  --config configs/training/laya-pilot.json --submission-id laya-pilot-example-001
.venv-router-train/bin/python amp/laya_jobs.py submit \
  --config configs/training/laya-pilot.json --submission-id laya-pilot-example-001 --wait
```

Use a new submission ID. Shared source/config files must be deployed before
submission. The plan is also the body accepted by the authenticated management
`POST /api/v1/jobs` endpoint. No credentials belong in that body.

## Recipe and selection

- Two GPU workers, four Ray CPUs each, two questions per worker per step.
- Every epoch shuffles all training questions exactly once; the final batch has
  masked padding. Unknown labels remain null in records and masked in loss.
- BF16 forward, FP32 head parameters, AdamW at 1e-4, weight decay 0.01,
  10% warmup/cosine schedule and gradient norm cap 1.
- At most five epochs; at least three, with two stale validation epochs stopping
  training. Select the lowest macro per-class validation log loss among trained
  epochs. Epoch zero is a diagnostic baseline, not a selectable trained model.
- Canonical `model_input()` only, using the audited prefix/tail token view at
  2,048 tokens. Omitted tokens are reported; this is not a full-state model view.
- Calibration/test are excluded from optimization and selection. Bundle integrity
  validation checks all splits. Probabilities are independent and uncalibrated.

Before optimization, each GPU runs the longest observed batch through forward
and backward, checks finite gradients, and restores RNG without updating weights.
Each epoch verifies complete coverage, observed counts and identical changed head
hashes across ranks on distinct nodes.

## Artifacts and monitoring

Under `/home/cdsw/training-runs/<submission-id>/`:

| File | Evidence |
|---|---|
| `run-manifest.json` | Recipe, pins, package versions, data manifest, executed source hashes |
| `worker-*.json`, `preflight-worker-*.json` | Node identity, matching recipe/data and GPU preflight |
| `*-view-audit.jsonl` | Canonical input hashes, retained/omitted spans |
| `epoch-*-metrics.json`, `epoch-*-validation.json` | Full coverage, losses, priors and validation predictions |
| `best-epoch-*.pt` | Head, optimizer, scheduler, rank RNG and resume metadata |
| `artifact/decision-head.pt`, `artifact/manifest.json` | Selected head and required pinned backbone/task metadata |
| `reload-predictions.json`, `SUCCESS.json` | Fresh CPU reload and finite predictions |

The head artifact requires the pinned Laya backbone; it is not a standalone
encoder. In TensorBoard Scalars select `<submission-id>/tensorboard/pilot`, then
`train/epoch_log_loss`, `validation/macro_log_loss` and per-class validation tags.

To resume an epoch checkpoint into a new run, add `--resume-checkpoint` with its
absolute shared path. Task, dataset, world size and training recipe must match;
output paths and job timeout may differ. Full-pilot resume is implemented, but
its live recovery path has not yet been exercised. The earlier short trial did
verify live reload/resume separately.

See [2026-10-01 results](status/2026-10-01-laya-pilot.md). Source-use limitations
in the frozen dataset manifest remain applicable to model release.

## Ten-epoch comparison run

`configs/training/longer-pilot.json` uses the same frozen 300-state bundle and model pins. Its 210-state training split is optimized for exactly 10 epochs (`min_epochs=max_epochs=10`); validation still selects the best trained checkpoint and calibration/test remain held out. This is a fresh run, not a resume of the earlier optimizer. Submit with `amp/laya_jobs.py submit --config configs/training/longer-pilot.json --submission-id longer-pilot`. TensorBoard run: `longer-pilot/tensorboard/pilot`.
