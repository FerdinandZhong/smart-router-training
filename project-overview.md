# Project overview

Smart Router Training builds the data and infrastructure needed to train small
decision models for customer-defined classes and step-level agent routing.
The intended router estimates whether each candidate model can handle the next
agent call, supporting later quality/cost tradeoffs.

## Users and scope

| User | Current workflow |
|---|---|
| Dataset owner | Map customer columns and class definitions, audit inputs, create grouped splits |
| Annotation operator | Run candidates and separate judges, inspect failures and unknowns, retain evidence |
| Training operator | Launch the AMP, add GPU workers, prepare networking, run the distributed smoke |
| Experiment reviewer | Inspect manifests, checkpoints, diagnostic metrics and TensorBoard curves |

Customer tasks support `single_label`, `multi_label`, and `independent_binary`
contracts. FAST/GENERAL/REASONING are the pilot's classes, not a framework-wide
restriction. Customer labels can bypass LLM annotation; the current candidate
runner specifically evaluates routing candidates against local-step contracts.

## Current capability

The repository includes import/audit/preparation tools, resumable annotation,
a pinned Ray cluster implementation, CAI setup and application launchers, and a
Ray TorchTrainer diagnostic with checkpoint resume and TensorBoard logging.

The frozen [pilot manifest](data/pilot/pilot-smoke-v1/manifest.json) records 300
pre-call states from 100 SWE-Gym issues: 210 train and 30 each validation,
calibration and test. Of 900 state/class targets, 846 are observed and 54 are
unknown. These are single-trial local-step silver observations, not calibrated
success probabilities or verified downstream task outcomes.

The current trainer fits a controlled one-weight regression to test the
infrastructure. It validates pilot access but does not fit a decision model.
Laya, CLM-8B and GLiNER2.5-Decide adapters, larger datasets, executable replay,
calibration, and production routing remain planned. ModernBERT-first material is
historical background, not the current implementation direction.

## Documentation map

| File | Responsibility |
|---|---|
| [AGENTS.md](AGENTS.md) | Repository context, invariants and agent working conventions |
| [DESIGN.md](DESIGN.md) | Visual and information-presentation rules |
| [TODO.md](TODO.md) | Current priorities, progress and acceptance criteria |
| [architecture.md](architecture.md) | Components, deployment and data flow |
| [user-guide.md](user-guide.md) | Operator and dataset-owner workflows |
| [development.md](development.md) | Setup, commands and regression checks |
| [component-api.md](component-api.md) | Implemented Python, CLI and HTTP contracts |

[README.md](README.md) is the entry point. Detailed runbooks and research evidence
remain under `docs/`; they are linked rather than copied into each overview.
See [TODO.md](TODO.md) for dated deployment evidence and remaining work.
