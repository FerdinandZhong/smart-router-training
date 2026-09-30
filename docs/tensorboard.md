# TensorBoard on CAI

TensorBoard runs as a separate authenticated CAI Application (1 CPU, 2 GiB, no
GPU), using the configured head CPU runtime and `.venv-router-train`. It reads
`/home/cdsw/training-runs` from the same shared project filesystem as the Ray
workers. No event upload, GPU allocation, or head restart is needed.

```text
Ray TorchTrainer
  +-- worker rank 0 -> training-runs/<submission-id>/tensorboard/<stage>/events.*
  +-- worker rank 1 -> participates in global loss reduction
                              |
                      shared project filesystem
                              |
                 TensorBoard CAI Application
                              |
                    authenticated CAI HTTPS URL
```

New AMP imports install TensorBoard 2.20.0 with the training dependencies and
run the `launch_tensorboard` job. The subdomain defaults to
`smart-router-tensorboard`; change `TENSORBOARD_SUBDOMAIN` before launch if that
subdomain is already used. Deployment reuses a matching application without
restarting it and rejects conflicting script/authentication settings.

For an existing project, run these in its terminal, with no training job active
while updating the shared environment:

```bash
git pull --ff-only
python amp/setup_training_environment.py
python amp/launch_tensorboard.py
```

The deployment writes the application ID, status and URL to
`.amp-state/tensorboard-application.json`. Application creation is asynchronous;
use CAI Applications to confirm readiness and inspect startup logs. If an existing
matching application is stopped or failed, restart it through CAI Applications.
There is no need to redeploy the Ray cluster. A manually created CAI Application
can instead use `amp/serve_tensorboard.py` as its script, Python 3.11 Standard,
1 CPU / 2 GiB / 0 GPU, with unauthenticated access disabled.

The launcher binds to `CDSW_APP_PORT` and uses the isolated training Python.
It ignores notebook kernel arguments, preserves the CAI kernel, propagates
server failures, and reloads event files every five seconds. CAI ingress provides
TLS and authentication. The normal Python event loader is used (`--load_fast
false`) to avoid requiring the optional native data server.

The updated infrastructure smoke writes these scalar series from rank zero:

- `diagnostic/loss`: global mean loss, before training and after every update.
- `train/learning_rate`: optimizer learning rate for each update.
- `perf/step_seconds`: rank-zero wall time for an update plus global loss reduction.

The initial and resumed stages appear as separate runs; resumed step numbers
continue from the checkpoint. Writers flush every five seconds and on close.
The smoke is intentionally tiny, so most charts may appear after it finishes.
These are controlled linear-model diagnostics, not router quality metrics or
GPU utilization. Older runs without event files will not acquire curves retroactively.

Submit a fresh smoke after worker networking is ready:

```bash
python amp/jobs.py submit --submission-id cluster-smoke-tb-001 --wait
```

TensorBoard may initially show no dashboards until this run writes events.
Select `<submission-id>/tensorboard/initial` and `.../resume` in the Scalars UI.
Ray's own result logging may also produce separate event runs under `ray/`.
Event files persist when TensorBoard stops or restarts. Model/operator profiling
and CPU/CUDA traces are not enabled by this change.

Implementation follows the official [TensorBoard server usage](https://www.tensorflow.org/tensorboard/get_started)
and [PyTorch SummaryWriter API](https://docs.pytorch.org/docs/stable/tensorboard.html).
