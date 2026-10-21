# Semantic research branch record — 21 October 2026

This record preserves the semantic-context research separately from the original routing experiments.
The implementation and research documents belong to `research/semantic-model-routing`.
The original checkout remains on `main`, with its unfinished router changes intact.

## Branch and checkout

- Branch: `research/semantic-model-routing`.
- Previous branch commit: `42ef2e4`.
- Original routing base: `2b7eecf`.
- Restored worktree: `/tmp/smart-router-semantic-research-20261021`.
- Main checkout: `/Users/zhongqishuai/Projects/cldr_projects/smart_router_training`.

The old worktree `/tmp/smart-router-semantic-research-20261009` is missing.
Its branch and committed history survived. The restored worktree continues that branch.
Git commits preserve code and documentation if temporary worktree files disappear again.
No remote push is part of this update.

This update copies research-specific files into the branch and commits them there.
It excludes unfinished Laya/GLiNER routing experiments, their datasets, and customer-share material.
Shared root guides receive research links without importing unrelated main-checkout edits.
Research copies remain in the main checkout because the live review and local UI use those paths.
The main branch history is unchanged. Its working directory is therefore not a clean isolation boundary.

## Research objective and constraints

Select complete, consistent semantic context from a changing Ossie catalog within fixed context and latency budgets.
Use keyword and embedding retrieval as established baselines.
Use declared Ossie dependencies for context assembly; no learned graph model is required.
GLiNER or Laya remains an optional later reranker comparison.
A new cost-aware loss is outside this research direction.

```text
Question and confirmed context
             |
Keyword / dense candidate retrieval
             |
Declared Ossie dependency expansion
             |
Candidate relevance and context sufficiency
             |
Proceed / clarify / request missing metadata
```

## Implementation preserved

| Area | Files and behavior |
|---|---|
| Intake and pilot | `semantic_intake.py`, `semantic_pilot.py`; pinned sources, structural Ossie units, grouped pilot preparation |
| Retrieval | `semantic_baselines.py`, `models/semantic_embedding.py`; BM25, dense and fusion diagnostics |
| Training preparation | `training/semantic_retriever.py`; embedding training entrypoint, tested with an invented fixture |
| Review UI | `semantic_review_ui.py`, `review_ui/index.html`; persistent review events and metadata inspection |
| Initial judges | `semantic_review_judge.py`, `semantic_delegated_review.py`; cached Sonnet proposals and delegated Opus adjudication |
| Structural diagnostic | `semantic_structural_review.py`; complete inspected definitions, bounded dependency expansion and separate relevance/context judgments |
| Entrypoints | Research preparation, baseline, review, cluster verification and training scripts under `scripts/` |
| Configuration | `configs/semantic_retrieval/`, including `structural-reviewer-v2.json` |

The v2 evidence view prioritizes 24 candidates and examines up to 96 original candidates for one dependency expansion.
It resolves relationship field IDs to parent tables.
The final evidence has at most 96 tables and a 240,000-byte metadata-item budget.
Whole tables can be omitted; field descriptions are not clipped.
Coverage logs retain added tables and omitted catalog units.
These are offline annotation bounds, not measured serving latency or tokenizer-specific token limits.

The judge returns table relevance separately from complete-context sufficiency.
A positive relevance label does not establish a unique intended table or complete context.
Unknown relevance remains null. Complete contexts must contain their declared dependencies.
Multi-table contexts require declared connecting relationships.
Physical-schema, execution, and business-definition certification remain unknown.
The original human training exporter remains separate.

## Dataset and previous review evidence

The immutable pilot is `data/semantic-research/pilot-20261010-v3`:

- 240 questions and 702 tables from 112 catalogs.
- Internal grouped split: 197 training questions and 43 validation questions.
- First review batch: 80 questions.
- 38 BIRD catalogs have zero imported relationship units.
- 74 Spider catalogs have 280 imported relationship units.

The completed original Opus campaign reviewed 72 questions and failed on eight.
It produced 38 clarification dispositions, 33 metadata deferrals, and one approval.
The approval is in training; no validation sample received approval.
These are automated results, not human approval or SQL execution evidence.

The [ten-case audit](deferral-audit-20261020.md) found genuine catalog ambiguity, description clipping, candidate misses, missing joins, and inconsistent review standards.
It additionally inspected the sole approved control.
Its purposive sample does not estimate error rates across the dataset.

## Live diagnostic snapshot

The diagnostic directory is `data/semantic-research/structural-diagnostic-20261020-v2c`.
Its preparation date remains in the directory name; execution continued on 21 October.
At this branch-record snapshot, the run has five reviewed cases and one failure out of eleven.
Five cases have not yet produced final receipts.

| Source record | Recorded result |
|---|---|
| BIRD 5165: female employees | Transport failure; no label decision |
| BIRD 6392: cryptocurrency circulation | Needs metadata |
| BIRD 4779: disappeared coins | Sufficient within supplied evidence |
| BIRD 5506: absence over six months | Sufficient within supplied evidence |
| BIRD 4064: counties without Bakers Square | Needs metadata |
| BIRD 2750: unsalable black products | Sufficient within supplied evidence |

These results remain provisional model judgments.
In particular, the product-definition and absence-unit decisions require inspection against the audit findings.
A higher sufficiency count alone does not demonstrate better labels.
The diagnostic uses direct Opus reviews under one rubric, without prior judge proposals or reference SQL as inputs.
It does not establish agreement between independent model families.

The original live process runs from the main checkout.
Do not launch a concurrent resume against the same output directory.
Check `status.json` and process liveness before resuming.
Revalidate all final receipts with the current validator before any downstream export.
A final accuracy comparison or training-readiness claim is not available yet.

## Tests and verification

The local CPU suite passed 46 tests:

```bash
PYTHONPATH=src python -m unittest \
  tests.test_semantic_structural_review \
  tests.test_semantic_delegated_review \
  tests.test_semantic_review_judge \
  tests.test_semantic_review_ui \
  tests.test_semantic_pilot \
  tests.test_semantic_intake
```

Actual evidence checks recovered `program` and its declared join for the missing-program case.
They also confirmed that the full coins status description includes the `extinct` definition.
Source artifact hashes remained unchanged after implementation.
`git diff --check` passed in the implementation checkout.
No new GPU training or serving-latency verification occurred.

## Artifact retention and resume

Large source datasets, requests, credentials, and raw review receipts are not committed.
Their existing location is the main checkout's ignored `data/semantic-research/` directory.
The restored worktree has a local ignored symlink to that directory.
A fresh clone needs the source data restored or regenerated before these commands can run.
Git preserves the implementation and evidence reports, not a backup of ignored datasets.
`docs/status/2026-10-21-semantic-branch-copy.json` records copied-file hashes.
Gateway configuration refers to a credential file; no credential value is stored in Git.

```bash
# Prepare evidence only. Do not run concurrently with the active campaign.
python scripts/review_semantic_diagnostic.py --dry-run

# Resume after confirming the prior process has stopped.
python scripts/review_semantic_diagnostic.py
```

The updated runner reuses valid successful receipts and archives failed receipts before retrying.
It writes a final comparison file after completion.
The already-running process may predate that completion-report addition; a cached resume can produce the report afterward.
Changed frozen configuration, prompt, or evidence requires a new output directory.

## Remaining work

1. Finish the eleven-case diagnostic and retry transport failures with pacing.
2. Validate all receipts and inspect disagreements with the audit, including the product-definition case.
3. Verify BIRD join metadata independently of reference SQL.
4. Define a separate automated training export with explicit label semantics and evidence scope.
5. Preserve grouped splits and require usable train and validation support.
6. Re-run matched retrieval baselines before task-specific training.

See [structural review v2](structural-review-v2.md) for the contract and [bilingual research plan](research-plan-bilingual.md) for the wider study.
