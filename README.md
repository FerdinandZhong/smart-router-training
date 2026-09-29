# Smart router training

Train configurable decision models for customer-defined classification tasks and step-level model selection in agent workflows.

Current direction: compare Laya, CLM-8B, and GLiNER2.5-Decide through interchangeable model adapters. Accept customer datasets and target classes through configuration. LLM annotation is optional for customer-labeled data; agent routing additionally uses executable outcomes. Ray supports distributed preparation and training.

This project is now a self-contained **Cloudera AMP**: it includes a pinned Ray
cluster implementation, setup/launch jobs, an isolated PyTorch environment, the
300-state pilot dataset, and a two-worker infrastructure smoke job. AMP import
starts only the head. Add GPU workers through Swagger, configure their
collective networking, then launch the smoke job. Follow the
[AMP deployment guide](docs/amp-deployment.md) for import, resource requirements,
job commands, data flow and cluster shutdown. The AMP metadata is
[.project-metadata.yaml](.project-metadata.yaml).

- [Implementation plan v2.1](docs/agent-step-router-implementation-plan.md) — current design, annotation protocol, training gates, and build order.
- [Model comparison and customer framework contract](docs/decision-models-and-customer-training.md) — adapter boundaries, class semantics, ingestion, calibration, and acceptance gates.
- [Dataset construction guide](docs/data-pilot.md) — sample definition, pilot sizes, working audit/preparation commands, and remaining real-data requirements.
- [Annotation pipeline](docs/annotation-pipeline.md) — runnable candidate/judge script, model configuration, resumable evidence and local-step silver labels.
- [First live annotation batch](docs/annotation-batch-001.md) — GPT-5.6 Sol/Terra candidates with Astra judging; two synthetic-source samples, eight model executions and a contract review finding.
- [Three-candidate batch](docs/annotation-batch-002.md) — Qwen FAST, Terra GENERAL, Sol REASONING and Astra judge; completed on two synthetic states after Qwen recovery, with all six judgments saved.
- [Real-data pilot](docs/real-data-pilot-001.md) — 300 recorded pre-call states from 100 SWE-Gym issues; first ten-state annotation batch and source limitations.
- [Pilot continuation](docs/real-data-pilot-002.md) — recovery of initial unknowns and a resumable 29-batch campaign for the other 290 states, using fresh CLI model sessions.
- [Customer task configuration](configs/examples/customer-support.json) and [JSONL fixture](data/examples/customer-support.jsonl) — runnable import/audit example; its model/training settings are still design-only. Three rows are too small for four-way evaluation splits.
- [Agent-step fixture](configs/examples/agent-steps.json) — runnable construction example with 24 synthetic unlabeled steps in 12 episodes; not real training data.
- [Jev/Laya/Ray evidence review](docs/jev-laya-ray-review-2026-09-27.md) — paper review, upstream source findings, and sibling-project readiness.
- [Original implementation plan v1](docs/agent-step-router-implementation-plan-v1.md) — archived ModernBERT-first proposal.
- [Original research report](docs/deep-research-report.md) — background research; implementation decisions are superseded by v2.1 where they differ.

Status as of 2026-09-29: all 300 pilot states have completed annotation, with 846 observed state/model labels and 54 unknowns. The frozen bundle is included under `data/pilot/pilot-smoke-v1/`. AMP and cluster-smoke code are implemented locally; live CAI import and GPU/NCCL validation remain. The smoke trains a controlled diagnostic model and validates pilot data access. Laya fine-tuning, executable replay and routing-quality evaluation remain separate milestones.

Run `PYTHONPATH=src python -m smart_router.cli audit --config configs/examples/customer-support.json` from this directory. See the construction guide for preparation and test commands.
