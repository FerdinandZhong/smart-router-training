# Included engineering pilot

This directory is deliberately included in the project repository and AMP source
archive. It contains 300 pre-call agent states from 100 SWE-Gym issues, preserving
210/30/30/30 train/validation/calibration/test splits and independent FAST,
GENERAL and REASONING targets. Unknowns are `null` with observation mask zero.

The labels are single-trial local-step silver judgments. There are 846 observed
targets and 54 unknowns. They are suitable for engineering smoke tests, not a
claim of calibrated routing or executed task success. The original
`eligible_for_training=false` and `runtime_replayed=false` metadata are retained.

`manifest.json` records source revision, source/annotation hashes, class support
and file checksums. Source: SWE-Gym/OpenHands-Sampled-Trajectories at
`baf3a4e4bff514d48ddc08a93a2ade5c126212c7`. The source dataset card did not declare
a dataset license; its upstream code license is not asserted to cover every
trajectory/code excerpt. This export is for the requested private AMP trial;
source terms remain unresolved for public redistribution or a training release.

Rebuild from the original local data and annotation runs with
`python scripts/export_smoke_training_data.py`. AMP users do not need those raw
inputs or annotation run directories: validate the included export with
`python amp/bootstrap.py validate`.
