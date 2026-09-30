# Dataset construction pilot

> Initial construction guidance and dated pilot snapshots. The completed frozen
> 300-state bundle is `data/pilot/pilot-smoke-v1/`; see [current progress](../TODO.md)
> for annotation completion and deployment status.

Updated 2026-09-28. Offline construction and a [local-step annotation runner](annotation-pipeline.md) are implemented. The [real-data pilot](real-data-pilot-001.md) contains 300 recorded SWE-Gym pre-call states from 100 independent issues, with the first ten selected for annotation debugging.

## What counts as one sample?

One routing sample is the state **immediately before one routable LLM call**, including the earlier context needed to decide which model to call. It is not the entire episode, and it is not just the newest message. Tool operations without a model-selection decision do not create a routing row.

```text
Episode A
  user request → [state A:0] → first LLM call
  tool result  → [state A:1] → second LLM call
  observation  → [state A:2] → final LLM call → episode outcome
```

This episode produces three states. It can produce nine state/tier training pairs if all three tiers are observed at every state. Repeated candidate trials add evidence to those targets; they do not create additional unique states. Future responses/outcomes are evidence only. Counterfactual replay restores the environment at the decision point.

All states and branches from the same episode remain in one split. Broader customer/template/task-family grouping should be used when those relationships cause leakage. The importer also merges groups connected by duplicate inputs; current duplicate detection is exact structured JSON or whitespace-normalized text, not semantic near-duplicate detection.

## Sample size milestones

These are starting budgets, not claims that a fixed sample count guarantees model quality:

| Stage | Approximate size | What it can establish |
|---|---|---|
| Construction fixture | 24 synthetic unlabeled states / 12 fictional episodes | Import, masks, split and export behavior only |
| Annotation debugging | 10 real states | Snapshot fidelity, contracts, judge schema, execution and costing |
| Data-quality pilot | 300 real states from roughly 50–100 diverse episodes | Annotation feasibility and a first head-training/overfit smoke experiment |
| First comparative training pilot | Roughly 2,000–5,000 real states, with more independent tasks | Learning curves and preliminary comparisons between adapters |
| Expansion | Determined by learning curves, class coverage and confidence intervals | Progress toward task-specific quality and calibration gates |

With 70/10/10/10 allocation, 300 states gives approximately 210 training and 30 each validation/calibration/test; grouped splits can deviate. These holdouts contain even fewer independent episodes. They cannot justify precise per-language, per-class or 95% reliability claims. More repeated steps or seeds in the same few episodes are not substitutes for task diversity.

Use learning-curve subsets drawn from the training split (for example 300, 1K, 2K, 5K when available), and keep validation/calibration/test tasks fixed. To expand a released pilot, preserve assignments through source split columns with `strategy=provided`; do not rerun grouped splitting over appended data and assume old test tasks remain held out. Automated append-to-manifest reconciliation is not implemented yet.

## Run the implemented constructor

From the project root, with Python 3.10+:

```bash
# Read-only audit of the three-row customer fixture. No model/teacher calls.
PYTHONPATH=src python -m smart_router.cli audit \
  --config configs/examples/customer-support.json

# Construct a synthetic agent-step bundle and annotation queue.
PYTHONPATH=src python -m smart_router.cli prepare \
  --config configs/examples/agent-steps.json \
  --output data/prepared/agent-fixture-v1

# Run the offline correctness suite.
PYTHONPATH=src python -m unittest discover -s tests -v
```

The output directory must be new. The three-row customer fixture can be audited but intentionally fails four-way preparation because it lacks enough groups. JSONL and CSV use the standard library; Parquet requires the optional `pyarrow` dependency (`pip install '.[parquet]'`). An installed package also exposes `smart-router-data` with the same arguments.

The importer reads a whole dataset into memory; this first implementation is sized for pilots. It has no network access or teacher backend. `annotation.mode=queue_missing` writes work items, not paid requests. `disabled` writes no annotation tasks even if labels are missing. Missing values are always preserved.

## Customer and agent mappings

Configure task IDs, class IDs/descriptions/aliases, and column mappings. Exactly one of `text` or `state` supplies model input; targets may use `label`, `labels`, or `probabilities`. Dot paths support nested JSON. CSV structured values must be JSON strings, not Python reprs or comma-separated guesses. IDs must be explicit strings.

- `single_label`: one class or a full probability distribution summing to one.
- `multi_label`: complete label lists imply negatives; `positive_only` leaves unlisted classes unknown. An empty complete list means no labels; null means unannotated.
- `independent_binary`: probability maps can be sparse and do not sum to one. Missing/null classes remain unknown.
- Agent tasks set `unit=agent_step` and map episode, step ID and nonnegative step index. These remain metadata, outside model input.
- `metadata` and `label_evidence` can retain source revisions, capture timestamps, snapshot references, contracts and trial/judge references. The model projection excludes them. This importer does not infer executable-success labels from raw rollouts.

Use `dataset.split.strategy=provided` with a mapped `split` column to preserve official/customer assignments. Allowed names are `train`, `validation`, `calibration`, `test`. Group/duplicate leakage is rejected. Grouped splitting is deterministic under source row reordering; ratios are approximate, and class stratification is not yet implemented. Audits report missing class coverage rather than silently deleting classes.

The synthetic example uses unassigned model-pool/continuation-policy versions and has no observed targets. It is not suitable for training. Before actual routing annotation, supply concrete model versions, generation parameters, candidate context, restorable snapshots and success checks.

## Exported bundle

Each new output contains four split JSONL files, `task.json`, `audit.json`, `annotation_queue.jsonl`, `split_manifest.json`, and `manifest.json`. The manifest records source SHA-256, task/data specification hashes, split settings, and output checksums. It is written last; an export missing its manifest is incomplete. Customer/task identity travels with every canonical record. Output files contain customer data and should stay in the intended project storage.

`model_input(record)` is the only supported input projection. It excludes labels/evidence/metadata and rejects known future-evidence structural keys nested inside input. This is a structural check: it cannot detect a future answer pasted into an ordinary text field. Captured timestamps and semantic review are still required for real traces. Token counts are not yet available; the audit explicitly reports character lengths only.

## Real-data milestone

The active bundle is `data/prepared/swe-gym-pilot-v2`: 210/30/30/30 states across train/validation/calibration/test, grouped by issue. These are recorded model trajectories on real GitHub issues, not customer production traces. Source extraction preserves complete prefixes and excludes the historical next action and future results from model inputs. See the [source and annotation report](real-data-pilot-001.md) for reproducible commands and restrictions.

Complete the first ten-state annotation audit before expanding to all 300. After Qwen recovery, 27 state/model pairs are observed and three remain unknown. Investigate its response-format and timeout/incomplete cases, review semantic failures, then add fixed-count repeated trials and executable checks. Local next-action judgments remain silver evidence; they do not establish downstream success or calibrated probabilities. Customer traces, replay, model adapters and training remain subsequent work.
