# Customer-scoped selector data preparation — 21 October 2026

The central research model is a trained Laya/GLiNER semantic selector.
Keyword and embedding retrieval provide candidates and comparison baselines.
This preparation creates annotation inputs, not approved training labels.

## Prepared artifacts

`data/semantic-research/scoped-selector-20261021-v1/` contains 13,601 questions across 209 source catalogs.
Each source database approximates one customer deployment. This assumption does not establish a verified business domain.
A deployed customer may span several databases; that case needs a later customer mapping.
High-level domain remains null because the source does not supply a verified domain label.

The 240-question pilot contains 197 development-training and 43 development-validation questions across 79 catalogs.
Both pilot partitions use formal-training-reserved groups. No pilot episode uses a single-table catalog.
The full inventory preserves 7,576 train, 1,610 validation, 294 calibration and 4,121 test reservations.
These remain provisional until semantic aliases and source families are reviewed.

```text
Pinned source metadata -> customer catalog -> BM25 candidate tables
                                                   |
Source question ---------------------------------->| selector input
                                                   |
Source SQL -> separate supervision evidence -> annotation -> audited labels
```

- `episodes.pending.jsonl`: common Laya/GLiNER episode contract, including model inputs and null targets.
- `pilot.pending.jsonl`: the selected development pilot with the same contract.
- `supervision_only.jsonl`: SQL, source provenance, weak table references and pending judgment forms.
- `catalogs/`, `catalog_index.jsonl`, `metadata_units.jsonl`: unchanged Ossie drafts and addressable metadata.
- `manifest.json`: source hashes, generated file hashes, counts and limitations.
- `excluded.jsonl`: missing-catalog exclusions; empty for this build.

Only the nested `input` object belongs in model prompts.
Record IDs, source IDs, customer routing IDs, labels and supervision are not prompt features.
Candidate content comes only from catalog metadata. Selection does not use reference SQL.
All labels remain null, observation masks remain zero, and training eligibility remains false.
SQL table references provide structural evidence, not complete-context labels.
Absence from reference SQL does not establish a negative label.
Existing pooled judgments are not copied into this new task.

## Difficulty audit

There are 110,951 question/candidate pairs in the full inventory.
207 of 209 catalogs have at most 32 tables; the largest has 65.
13,007 episodes therefore expose their entire catalog at candidate-k 32.
All 7,000 questions with existing SQL table references retain those references among candidates.
This weak diagnostic is not a retrieval accuracy result or a large-scale search result.
Small catalogs can test learned selection, but cannot establish enterprise-scale retrieval performance.
Do not inflate scale by mixing unrelated customer databases.

## Training-data completion sequence

1. Add scoped dense/hybrid rankings under the same catalog and snapshot contract.
2. Annotate the 240-question pilot using question and metadata first; retain SQL as separate structural checking evidence.
3. Record answerability, multiple acceptable context sets, supported positives, hard negatives and unknowns.
4. Review catalog descriptions, reference consistency and unresolved source evidence before approving examples.
5. Implement an audited exporter for this new contract, with explicit automated-review provenance and observed-label masks.
6. Prepare common model views for both selector families and audit token truncation before training.
7. Expand annotation only after pilot error analysis. Reserve held-out groups for evaluation.
8. Add larger coherent customer catalogs and independent semantic definitions for the full research benchmark.

Existing review tools assume pooled scope and are not automatically compatible.
No new judge calls or GPU jobs were launched by this preparation.
The current package starts with table candidates; semantic-object labels and dependency completion require further annotation work.
No synthetic business definitions, domain labels, execution results or reviewer approvals were invented.

## Reproduction and verification

```bash
python scripts/prepare_semantic_scoped_data.py \
  --intake data/semantic-research/intake-20261010-v3 \
  --output data/semantic-research/scoped-selector-20261021-v1
PYTHONPATH=src:tests python -m unittest test_semantic_scoped_data test_semantic_pilot test_semantic_intake -q
```

Use a new output directory for each build. Existing output is rejected.
The build verifies intake checksums and rejects duplicate questions or connected groups crossing reserved splits.
22 local CPU tests passed. No training or GPU quality claim follows.
See the [preparation receipt](../../status/2026-10-21-semantic-scoped-preparation.json).
Source-use restrictions and schema limitations remain inherited from the pinned intake.
