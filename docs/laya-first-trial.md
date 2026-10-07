# Laya head verification and short pilot trial

This is an engineering trial of the pinned English Laya checkpoint. It supports
`independent_binary` tasks with configured class IDs/descriptions. It does not
implement single-label/multilabel adapter recipes, calibration or production routing.

## Recipe

- Laya source: `4066d5d5fbf08b66c6757ddeedbd797bd7655bc0` (package 0.3.20).
- Checkpoint/tokenizer/encoder config: `convaiinnovations/laya` revision
  `55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851`.
- Transformers 4.57.6, Torch 2.8.0, Ray 2.58.0; setup records full package inventory
  and snapshot file hashes on shared storage.
- Freeze encoder and unused action head; train the typed decision head using raw
  logits and binary soft cross entropy. No inference temperature correction.
- Two GPU workers, one question row per rank per optimizer step, BF16 autocast,
  20 scheduled optimizer steps and 2 resume steps. This is not a full epoch over
  the 210 training states. The data position is deterministic and saved.
- Null labels remain null in prepared rows; masks exclude them from gradients.
  DDP loss is normalized by the global observed-target count. All ranks run the
  same collective schedule, including zero-observation batches.
- Validation reads all 30 validation states, sharded without sampler padding.
  Report per-class log loss/Brier, observed/unknown and positive/negative support,
  compared with constant probabilities estimated only from training labels.
- Calibration/test records are not used for optimization or model selection.
  Dataset integrity validation checks their recorded file hashes.

## Context boundary

The default input budget is 512 tokens, including question/options. A deterministic
`canonical_input_prefix_tail_tokens_v1` view serializes `model_input(record)`,
keeps the first half and last half of the available state-token budget, and never
inserts candidate-generated history or future judge evidence. Per-question audits
record original/retained/omitted counts, selected token spans and input hash.
This can omit essential state information. Labels describe the full recorded
state; this view is a compatibility experiment, not a validated context policy.

## Remote commands

Run environment setup only when shared training jobs are idle; it changes the
training environment, downloads once into `/home/cdsw/model-cache`, and verifies
source revision, snapshot revision and package dependencies under a setup lock.
Use the existing cluster to submit setup; it requires no GPU.

```bash
/home/cdsw/.venv-router-train/bin/python amp/setup_laya_environment.py
python amp/laya_jobs.py plan --submission-id laya-first-trial-NEW
python amp/laya_jobs.py submit --submission-id laya-first-trial-NEW --wait
python amp/laya_jobs.py status --submission-id laya-first-trial-NEW
python amp/laya_jobs.py logs --submission-id laya-first-trial-NEW
```

Alternatively POST the plan payload to `/api/v1/jobs` in management Swagger.
Choose a fresh submission/run ID on every attempt. Ray uses the built training
Python and shared files; the CPU driver does not reserve a GPU. Existing worker
pods must retain the verified networking patch. No automatic worker retry or
resource provisioning is performed by this trial.

## Verification artifacts

Under `training-runs/<run-id>/`: run manifest, initial/resume worker identities,
view audits, stage metrics, per-class validation predictions/metrics, Ray
checkpoints, a reload checkpoint, fresh reload predictions, TensorBoard events
and `SUCCESS.json`. The gates require distinct nodes, matching data hashes,
finite nonzero head gradients, changed/synchronized head hashes, fresh checkpoint
reload, finite class-aligned probabilities and resumed optimizer/step/data/RNG
state. Falling loss or beating the prior baseline is reported, not assumed.

TensorBoard runs are `<run-id>/tensorboard/initial` and `/resume`, with
`train/masked_loss`, per-class `validation/<class>/log_loss` and `/brier`.
The training curve uses changing samples, so adjacent values need not decrease.
