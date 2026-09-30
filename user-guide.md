# User guide

Start with [project-overview.md](project-overview.md) for scope and [TODO.md](TODO.md)
for current progress. Commands below run from the repository root. Offline data
and annotation examples assume a full repository checkout; the AMP archive is a
curated deployment bundle.

## Bring customer data

Use JSONL, CSV or Parquet with stable example and group identifiers, one text or
structured-state input, and optional labels. Define the customer's classes and
map column names in a JSON configuration. See the working
[customer configuration](configs/examples/customer-support.json) and
[three-row example](data/examples/customer-support.jsonl).

```json
{"ticket_id":"ticket-001","conversation_id":"conversation-001","message":"Please refund the duplicate charge.","intent":"billing"}
```

Supported target mappings are `label`, `labels`, or `probabilities`, with at most
one encoding per dataset. For probability labels, map a field containing a class
ID to probability/null object. Single-label distributions must cover all classes
and sum to one; independent routing probabilities do not need to sum to one.
Null means unknown. For positive-only multilabel data, omitted classes remain
unknown instead of becoming negatives.

Agent-step records also require episode ID, step ID and nonnegative step index.
Each input is the complete available history before one model call. Keep later
outcomes and judge evidence in separate fields.

Audit before preparing splits:

```bash
PYTHONPATH=src python -m smart_router.cli audit --config configs/examples/customer-support.json
```

The three-row customer fixture is an import example, too small for meaningful
four-way evaluation. Use the larger synthetic agent fixture to exercise export:

```bash
PYTHONPATH=src python -m smart_router.cli prepare --config configs/examples/agent-steps.json --output data/prepared/agent-fixture-v1
```

Choose a new output directory for a new bundle. Inspect its audit, grouped split
manifest, missing-label queue and checksums. Customer dataset construction is
implemented; configurable model fine-tuning is still planned.

## Run annotation

Try the offline demonstration first:

```bash
python scripts/annotate.py plan --config configs/annotation/mock.json
python scripts/annotate.py run --config configs/annotation/mock.json --output runs/annotation-demo-v1
```

For real annotation, configure actual candidate endpoints and a separate judge,
with credentials supplied through environment variables or credential-file paths.
Review the call/token caps in the plan, then use the same commands with your
configuration and `--live`. Use the same run directory to resume unchanged inputs;
`--retry-errors` retries eligible errors within the configured attempt limits.
Do not retry evaluated failures until they pass. Inspect unknowns and the review
queue before treating silver observations as training evidence.

See [annotation pipeline](docs/annotation-pipeline.md) for configuration, receipts,
artifacts and the distinction between local-step evidence and downstream success.

## Launch and operate the training AMP

1. Import the repository as a CAI AMP with Python 3.11 and available CPU/CUDA
   runtimes. Setup launches the CPU Ray head and TensorBoard.
2. Add two one-GPU workers through the head Swagger API, following the exact
   payload in [AMP deployment](docs/amp-deployment.md). Reuse existing workers
   instead of creating duplicates.
3. Confirm both workers are alive in Ray. Identify their current pod names and
   run the documented networking setup from the correct administrator context.
   Require TCPStore/Gloo/NCCL probes to pass before training.
4. From the CAI project terminal, submit and monitor a new run:

```bash
python amp/jobs.py plan
python amp/jobs.py submit --submission-id cluster-smoke-001 --wait
python amp/jobs.py status --submission-id cluster-smoke-001
python amp/jobs.py logs --submission-id cluster-smoke-001
```

Use a fresh submission ID for each rerun. The job reads shared project files,
validates the pilot, runs a controlled optimization diagnostic and reloads its
checkpoint. `training-runs/<submission-id>/SUCCESS.json` marks successful completion.

## View results and stop work

Use Ray Dashboard for job/worker status and logs. Open the TensorBoard application
from CAI Applications and select `<submission-id>/tensorboard/initial` and `resume`.
The setup-check run is synthetic. Actual smoke curves measure diagnostic loss,
learning rate and step time; they are not router-quality results.

```bash
python amp/jobs.py stop --submission-id cluster-smoke-001
```

Stopping a Ray job does not release CAI worker allocations. Remove unneeded workers
with the management API procedure in the deployment runbook. TensorBoard can be
stopped independently; events persist on shared storage.

For an existing project without TensorBoard, see [TensorBoard setup](docs/tensorboard.md).
Startup logs, loopback binding, environment isolation and notebook argument errors
are covered there and in [AMP troubleshooting](docs/amp-deployment.md).
