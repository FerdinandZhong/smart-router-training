# Development and verification

## Setup

Core dataset tooling supports Python 3.10+. CAI deployment requires Python 3.11
to match the configured runtimes. Use a separate local development environment;
AMP owns `.venv` and `.venv-router-train` inside `/home/cdsw`.

```bash
python3.11 -m venv .venv-dev
. .venv-dev/bin/activate
python -m pip install -e '.[annotation,parquet]'
```

For the complete cluster/training test environment, install the additional extras
in a compatible development environment:

```bash
python -m pip install -e '.[cluster,training]'
```

This installs substantial Ray/Torch dependencies; basic data construction does
not require a GPU or these extras. TensorBoard is part of the training extra.
Use the AMP setup wrappers on CAI so installation and runtime processes exclude
inherited add-on Python paths and retain mandatory dependency checks.

## Useful commands

```bash
PYTHONPATH=src python -m smart_router.cli audit --config configs/examples/customer-support.json
python scripts/annotate.py plan --config configs/annotation/mock.json
python amp/validate_pilot.py
python amp/jobs.py plan
python amp/tensorboard_app.py plan
python scripts/build_amp_bundle.py
git diff --check
```

Plan/validation commands do not launch resources or invoke candidate models.
The archive builder validates the pilot and vendor hashes, then writes an
allowlisted archive and checksum manifest under ignored `dist/`. It excludes
credentials, raw/private data, environments and training outputs. Source checkout
annotation tools are broader than the curated AMP archive.

## Regression matrix

| Change | Appropriate verification |
|---|---|
| Documentation only | Check file links, commands and factual status; rebuild archive if its allowlist changes |
| Data/task semantics | Dataset tests; pilot validation if the frozen bundle or validator changes |
| Annotation behavior | Annotation/campaign tests and offline fixtures; distinguish these from live calls |
| AMP setup or launchers | AMP environment and PBJ execution-context tests; relevant subprocess smoke |
| Training loop or checkpoints | Unit suite and two-process CPU smoke; live GPU run after network probes |
| TensorBoard launcher/events | Application tests, HTTP smoke, and distributed event validation if the writer changes |
| Included Ray source | Review snapshot changes, update effective hashes, AMP validation and relevant cluster checks |

Full unit suite:

```bash
PYTHONPATH=src:. python -m unittest discover -s tests -q
```

Separate integration checks:

```bash
PYTHONPATH=src:. python tests/run_distributed_amp_smoke.py
PYTHONPATH=src:. python tests/run_tensorboard_smoke.py
```

The first uses two real CPU/Gloo processes with mocked Ray I/O: it verifies the
worker loop, synchronization, checkpoint resume and event contents, not actual
Ray scheduling or GPU networking. The second starts real TensorBoard and queries
its UI/scalar API. Both require local socket access; a restricted sandbox can
block them. Report the tested Python/package versions when they differ from CAI.

## Repository layout and changes

| Path | Purpose |
|---|---|
| `src/smart_router/` | Data, annotation and training logic |
| `amp/` | CAI entrypoints, isolated environments, Ray submission, TensorBoard |
| `configs/` | Customer examples, annotation runs and infrastructure config |
| `data/pilot/pilot-smoke-v1/` | Frozen repository-included engineering pilot |
| `ray_serve_cai/`, `cai_integration/` | Included cluster implementation and local adaptations |
| `vendor/ray-serve-cai/` | Upstream provenance, source hashes and network runbook |
| `tests/`, `scripts/` | Regression checks and operational helpers |
| `docs/` | Detailed runbooks and dated research/experiment reports |

Keep proposed adapters separate from working infrastructure diagnostics. Update
`TODO.md` when evidence changes and the relevant contract/guide when behavior
changes. Preserve historical reports with explicit date/scope notices. Never
commit local secrets, generated run output or private customer data.

For deployment commands, recovery and shutdown, follow [user-guide.md](user-guide.md)
and [the AMP runbook](docs/amp-deployment.md). For presentation changes, follow
[DESIGN.md](DESIGN.md).
