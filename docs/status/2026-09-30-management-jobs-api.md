# Management Jobs API deployment — 2026-09-30

The training head's management API was redeployed in place through Ray Job
`management-jobs-api-20260930-001` (SUCCEEDED). The Ray head was not restarted.
Existing management resource settings were preserved: 2 CPUs, 8 GiB,
one replica pinned to the head, loopback Serve port 5000.

Live OpenAPI confirms submission/list, status, logs and stop routes under
`/api/v1/jobs`. An authenticated POST submitted CPU-only diagnostic
`management-jobs-api-check-20260930-001`; polling through the management routes
returned SUCCEEDED and logs contained `JOBS_API_CHECK_OK`. No GPU training was
started by this diagnostic. Stop authorization/forwarding was tested locally;
no live training job was stopped.

Local verification: 26 focused tests passed (management jobs, AMP, environment
isolation and notebook execution contexts); pilot/vendor validation and AMP
archive construction passed. The snapshot retains the upstream management app
hash and records the effective local hash. Remote pre-update app bytes are saved
under `/home/cdsw/.amp-state/jobs-api-backup/`.

The training dependency extra was corrected to `ray[default,train]==2.58.0`;
setup now checks the SDK dependency gate. Source fixes do not install packages
into an already-built remote virtualenv. Existing environments need the
installation command in the deployment guide or a rerun of AMP training setup.
These checks do not establish GPU worker readiness or NCCL training success.
