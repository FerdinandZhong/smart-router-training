# 2026-10-01 — full Laya pilot

Live CAI job `laya-pilot-20261001-001` **SUCCEEDED** on the two previously verified
L40S nodes. This is decision-head training on actual frozen pilot labels, with
the encoder frozen. It establishes execution and artifact integrity; quality
remains below the training-prior baseline.

## Configuration and execution

Pinned source/model revisions and environment match the
[first trial](2026-10-01-laya-first-trial.md). Recipe:
`configs/training/laya-pilot.json`; two workers, four Ray CPUs each, batch two
questions each, BF16, AdamW 1e-4, 2,048-token audited prefix/tail view, maximum five
epochs, minimum three and patience two. Validation macro log loss selects among
trained epochs; epoch zero is diagnostic.

- GPU preflight: both ranks ran a 2,048-token batch of two, with finite gradients
  and about 2.17 GiB peak allocated memory. Epoch peak was about 2.37 GiB.
- Three epochs, 474 optimizer updates; early stopping selected epoch 1.
- Every epoch covered 210 states / 630 class questions exactly once, including
  all 591 observed targets. The 39 unknown targets remained masked.
- Distinct nodes `0a7fec928ac8894b64a642054a328782fd25a9d31c42a61e08c47684`
  and `51cd2c8b7ddf8e652f39fb7ff4d1609311ac343aaafa45b957141e4c` had matching
  data/recipe hashes and changed, identical head hashes after each epoch.
- Selected head hash:
  `7eeb96f5169ab53eaad43c8ad382662053d0c18f48b8e40994997d64725544f7`.
- Fresh CPU model reload verified the selected hash and finite predictions.
  Exported head size: 105,003,108 bytes. `SUCCESS.json` and evidence job
  `laya-pilot-evidence-20261001-001` both verified.
- Calibration and test were excluded from training and checkpoint selection.
  Both GPUs were available again after completion.

## Loss and quality

| Epoch | Training observed-label log loss | Validation macro log loss |
|---|---:|---:|
| 0, before training | — | 0.678270 |
| 1, selected | 0.663666 | 0.661898 |
| 2 | 0.607326 | 0.852236 |
| 3 | 0.612599 | 0.817558 |

The observed-label training objective gives each observed question equal weight.
Selection averages per-class validation log losses equally.

| Class | Observed validation labels | Selected log loss | Training-prior log loss |
|---|---:|---:|---:|
| FAST | 24 (3 positive) | 0.837169 | 0.377077 |
| GENERAL | 30 (26 positive) | 0.575340 | 0.519240 |
| REASONING | 30 (29 positive) | 0.573185 | 0.155526 |

Lower is better. All selected-class Brier scores also underperformed priors.
GENERAL and REASONING improved relative to the untrained checkpoint, while FAST
worsened. Overall validation improved slightly at epoch 1, then deteriorated.
The small, imbalanced validation support limits interpretation. This run does
not justify production routing or calibration on the remaining holdout yet.

All train/validation views were truncated. Median retained state-token fraction
was 21.916% / 25.670%, versus about 5–6% in the short 512-token trial. No outcomes,
future actions or judge evidence entered the canonical input projection.

## Inspect

Artifacts live under
`/home/cdsw/training-runs/laya-pilot-20261001-001/`:
selected checkpoint `best-epoch-001.pt`, exported `artifact/decision-head.pt` and
`artifact/manifest.json`, per-epoch predictions/metrics, worker receipts, context
audits and run source/config/data provenance.

Authenticated TensorBoard Scalars run:
`laya-pilot-20261001-001/tensorboard/pilot`. HTTP checks confirmed three epoch
training-loss points, four validation macro points including epoch zero, and
474 step-loss points. Compare epoch losses; consecutive step losses use different
samples and cannot alone establish learning quality.

Local verification: 90 pytest tests and 36 subtests passed (Python 3.13 local).
This is separate from live Ray 2.58.0, Torch 2.8.0+cu128 / Python 3.11 GPU evidence.
Full-pilot epoch resume has implementation checks but has not been run live;
the prior bounded trial verified its own reload/resume path. Source-use gates in
the dataset manifest still apply. Next work is to investigate FAST degradation,
class/question conditioning and annotation support before expanding experiments.
