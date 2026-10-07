# Ray distributed training practice on CAI Workbench

## Verified scope

A CPU Ray head and two GPU workers, each hosted by a separate CAI application
and each using one NVIDIA L40S GPU. The workers ran on different nodes. Project
applications shared code, configurations, model cache and data under `/home/cdsw`.
The training environment was separate from the cluster environment.

An authenticated Ray Jobs API request submitted the Python entrypoint and
configuration. Ray started the driver; Ray Train `TorchTrainer` scheduled two GPU
training workers. Each GPU held a full model replica and processed a different
mini-batch. PyTorch DDP synchronized gradients through NCCL before updates.
With two class questions per GPU, the global batch was four questions per update.
Several class questions can come from one agent state; this is not four distinct
full conversations per update.

The model was a pinned Laya backbone with a **trainable decision head and frozen
encoder**, not full language-model pretraining or an all-parameter fine-tune.
Targets were independent binary route-success observations. Unknowns were masked.
The audited model view was limited to 2,048 tokens, so long history was truncated.

## Ten-epoch pilot evidence

| Item | Observed result |
|---|---|
| Run | `longer-pilot`, succeeded |
| Frozen bundle | 300 states: 210 train, 30 validation, 30 calibration, 30 test |
| Training | 10 epochs, 1,580 optimizer updates |
| Distributed checks | Complete training-question coverage and matching changed weights across ranks |
| Best validation macro log loss | 0.6690, epoch 1 |
| Epoch 10 train / validation loss | 0.5192 / 0.8092 |
| Artifact | Selected head checkpoint and reload verification |

Validation selected the best trained checkpoint. Calibration and test were held
out. Longer training did not improve validation performance; successful distributed
execution alone does not establish production routing quality.

Workers reduced training statistics and gathered validation predictions. Rank 0
wrote the aggregated metrics to shared TensorBoard event files, avoiding duplicate
writes. The TensorBoard application read those files; Ray collected console logs
separately.

A subsequent local labeling campaign produced 1,000 fresh states with 2,968
observed silver labels and 32 masked unknowns. Its split is 702 train, 100 validation,
99 calibration and 99 test. This larger bundle has not been trained in the results
above. Judge labels are single-trial local-step assessments, without executable
replay or calibrated probabilities; source-use limitations remain applicable.

## Larger-model work

The Ray worker architecture can be adapted to PyTorch FSDP or DeepSpeed ZeRO-3,
which shard weights, gradients and optimizer state across GPUs. Ray coordinates
workers; the training framework implements sharding and communication. This
requires changes to model/optimizer initialization and checkpoint handling and
has **not been implemented or verified in this project**.

Project: https://github.com/FerdinandZhong/smart-router-training

Local evidence: `docs/laya-pilot-training.md`, the recorded `longer-pilot` job logs,
and `docs/status/2026-10-03-gateway-labeling-complete.md`. Reference runbooks are
engineering observations, not a customer production certification.
