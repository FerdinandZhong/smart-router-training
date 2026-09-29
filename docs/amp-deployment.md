# Self-contained training AMP

Option 2 is the deployment architecture as of 2026-09-29. This project owns its
CAI Ray Applications, cluster/training environments, data and job entry points.
The previous plan to submit into the Qwen serving project is superseded.

## Included implementation

```text
Import this project into CAI as an AMP
  |
  +-- code: src/smart_router + amp + included Ray cluster implementation
  +-- data: data/pilot/pilot-smoke-v1 (300 states, about 7.6 MiB)
  |
  v
Sequential AMP jobs
  validate_pilot -> configure_project_resources
    -> setup_cluster_environment (.venv; Ray 2.58.0 + management dependencies)
    -> setup_training_environment (.venv-router-train; Ray 2.58.0 + Torch 2.8.0)
    -> launch_training_cluster
         +-- CPU head only: 8 CPUs / 32 GiB (zero GPU workers)
  |
  v
Manual setup through head Swagger UI
  POST /api/v1/resources/nodes twice
    +-- GPU worker A: for example 16 CPUs / 64 GiB / 1 L40S
    +-- GPU worker B: for example 16 CPUs / 64 GiB / 1 L40S
  |
  v
Run scripts/setup_cross_node_gpu.fish on an administrator workstation
  -> select the new GPU pods -> configure scoped traffic exception
  -> verify TCPStore, Gloo and NCCL using the training environment
  |
  v
Manually run cluster-smoke (CPU-only CAI submission job)
  -> discover this project's head URL from ray_cluster_info.json
  -> authenticate to /dashboard/ with CAI-injected credentials
  -> submit Ray Job cluster-smoke
       -> CPU driver -> TorchTrainer -> two GPU workers / NCCL
       -> each worker verifies the included dataset and shared storage
       -> controlled model forward/backward and gradient synchronization
       -> checkpoint -> fresh trainer restores optimizer/RNG/step -> two updates
  |
  v
training-runs/cluster-smoke/
  run-manifest.json, worker identities, metrics, checkpoints, SUCCESS.json
```

The smoke model is a controlled one-weight regression, not a Laya adapter. It
reads and checks the real pilot bundle, but does not fit routing labels. The
Laya `first-trial` experiment remains the next model-specific implementation.
This distinction prevents a successful infrastructure test being reported as
successful decision-model training.

## Import and launch

1. Import [FerdinandZhong/smart-router-training](https://github.com/FerdinandZhong/smart-router-training)
   as an AMP using its `main` branch. Repository credentials may be required
   according to its visibility and your Workbench access.
   The root `.project-metadata.yaml` declares the setup jobs using the
   [Cloudera AMP specification](https://docs.cloudera.com/machine-learning/cloud/applied-ml-prototypes/topics/ml-amp-project-spec.html).
2. Select a Python 3.11 runtime. Confirm the CPU/CUDA runtime identifiers in
   `configs/ray_cluster_config.yaml` are available in the target Workbench.
   Set a unique `RAY_HEAD_SUBDOMAIN` for additional installations. The default is
   `smart-router-ray-head`, distinct from the old serving cluster's head.
3. Import runs validation, provisions environments, and starts **only the CPU
   head**. Worker pools and worker groups are empty. GPU resource choices are
   made later through the API. When redeploying an older installation, remove any
   previously set `RAY_INITIAL_WORKER_POOLS` or set it to `[]` first; existing
   Applications/pool state are not deleted by changing the YAML.
4. Open `https://<RAY_HEAD_SUBDOMAIN>.<CDSW_DOMAIN>/docs` and call
   `POST /api/v1/resources/nodes` twice, selecting one GPU per worker. An example
   request is shown below. Then wait for both workers to join in the head's
   `/dashboard/#/cluster` page.
   GPU capacity must be available in the workspace. The existing Qwen cluster
   does not relinquish its CAI allocations automatically.
5. From an administrator workstation, run the included setup script against the
   **new** GPU pods, then require its TCPStore/Gloo/NCCL probes to pass. The
   [included upstream runbook](../vendor/ray-serve-cai/docs/CROSS_NODE_GPU_DEPLOYMENT.md)
   describes the tested, scoped Istio workaround. Labels applied to previous
   Qwen worker pods do not automatically apply to these pods. The script uses
   `/home/cdsw/.venv-router-train/bin/python`. AMP import itself does not modify
   Kubernetes networking; that is the explicit manual setup step.
6. Run the created `cluster-smoke` CAI Job. It submits a Ray Job, waits up to
   15 minutes, prints logs and fails the CAI Job if the Ray Job fails or times out.
   A timeout requests Ray Job termination. The smoke is created but not run
   automatically during import, so collective-network readiness can be checked.

Example Swagger request (submit twice; select an available CUDA runtime):

```json
{
  "node_type": "gpu-worker",
  "cpu": 16,
  "memory": 64,
  "gpus": 1,
  "accelerator_type": "L40S",
  "runtime_identifier": "docker.repository.cloudera.com/cloudera/cdsw/ml-runtime-pbj-jupyterlab-python3.11-cuda:2026.04.1-b7"
}
```

Get the current worker pod identities from `GET /api/v1/resources/nodes` and
confirm them with Kubernetes. On the administrator workstation, from this checkout:

```bash
fish scripts/setup_cross_node_gpu.fish <GPU_POD_A> <GPU_POD_B> <NAMESPACE>
```

This applies the scoped Istio exception and records a rollback baseline. It
requires `kubectl`, `jq`, Fish and access to the selected pods and namespace.
The recipe checks the tested ephemeral port range and PERMISSIVE namespace
policy; review the included runbook for environment-specific prerequisites.
Rerun it for replacement pods. The training job uses the same TCP interface
settings as the probe (`eth0`, InfiniBand disabled), configured in
`configs/training/cluster-smoke.json`; adjust both if the network differs.

From a terminal **inside the imported CAI project**, equivalent operations are:

```bash
python amp/jobs.py plan
python amp/jobs.py submit --submission-id cluster-smoke --wait
python amp/jobs.py status --submission-id cluster-smoke
python amp/jobs.py logs --submission-id cluster-smoke
python amp/jobs.py stop --submission-id cluster-smoke
```

Use a new ID such as `cluster-smoke-002` for a second run. Existing IDs and output
directories are not overwritten. Credentials are read from `CDSW_APIV2_KEY` or
`CML_API_KEY` at runtime and are not placed in the submission payload.

## Data and storage

AMP import brings `data/pilot/pilot-smoke-v1/` into this project's filesystem.
The head and workers belong to the same CAI project and use the same NFS project
mount. There is no second dataset upload through Ray Jobs: job commands refer
to absolute paths in `/home/cdsw`, and the installed package points to this
checkout. Worker preflight verifies checksums and shared read/write visibility.

The data includes 210 train, 30 validation, 30 calibration and 30 test states;
846 observed labels and 54 unknowns. Labels are single-trial local-step silver
observations. Original eligibility and replay flags remain unchanged. Future
evidence and judge rationales are excluded from the model-input export.

This trial bundle is intended for the requested private AMP experiment. Its
manifest retains the upstream source revision and the unresolved source-term
note; no blanket license for the underlying trajectories is asserted. See the
[dataset README](../data/pilot/pilot-smoke-v1/README.md).

Virtual environments and outputs are excluded from version control. Model
weights will be downloaded/cache-pinned separately when the Laya adapter is
implemented. The AMP currently provisions the **core** PyTorch training
environment, not the eventual model-specific dependency lock.

## Cluster code ownership and lifecycle

`ray_serve_cai/` and the required `cai_integration/` files are included from a
clean sibling checkout at commit `14486d8e95947edbcdee79cc348b9547f036d0b1`.
`vendor/ray-serve-cai/SNAPSHOT.json` records source hashes and local changes.
There is no runtime dependency on `../ray-serve-cai` or a moving Git branch.
The head's nginx repair fallback uses this AMP's environment provisioner.
Optional inference code is retained as part of the existing management library;
AMP setup does not install or deploy inference engines.

GPU workers are created manually through Swagger; there is no managed pool or
minimum worker count in the default AMP configuration.
Finishing a training job releases Ray reservations but leaves CAI Applications
allocated. To release capacity, first stop active training jobs, then remove
the manually created worker Applications through
`DELETE /api/v1/resources/nodes/{app_id}` in Swagger. If managed pools were added
separately, disable those policies before removing their workers so they are not
recreated. Stop the head Application
when the cluster is no longer needed. Checkpoints remain in project storage.

## Local validation and artifacts

```bash
python amp/bootstrap.py validate
PYTHONPATH=src:. python -m unittest discover -s tests -v
PYTHONPATH=src:. python tests/run_distributed_amp_smoke.py
python scripts/build_amp_bundle.py
```

The distributed local check uses two CPU/Gloo processes and mocks Ray's context
and checkpoint-report transport. It exercises the worker loop, synchronization,
shared data and optimizer/RNG/step recovery. Live Ray scheduling, CUDA/NCCL,
runtime-image compatibility and CAI import still require the remote smoke.

`dist/smart-router-training-amp.tar.gz` is an allowlisted project source/data
archive for review or staging. It is not a substitute for the Git URL in the
standard AMP importer. A wheel alone does not include the AMP metadata and
pilot dataset; import the project source tree.
