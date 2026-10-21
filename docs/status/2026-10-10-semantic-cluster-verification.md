# Semantic pilot cluster verification — 2026-10-10

## Outcome

The existing cluster completed the pilot audit and three retrieval diagnostics on one NVIDIA L40S.
Ray submission `semantic-pilot-audit-20261010-02` succeeded with exit code zero.
Both L40S workers remained alive. Both GPUs were available after completion.
The run performed no training and approved no labels.

Full machine-readable evidence: [verification JSON](2026-10-10-semantic-cluster-verification.json).
Method and primary literature: [hybrid retrieval protocol](../research/semantic-model-routing/hybrid-retrieval-verification-20261010.md).

## Data audit

| Item | Verified result |
|---|---:|
| Questions | 240 |
| Ossie catalogs | 112 |
| Tables in the shared search universe | 702 |
| Metadata units | 5,205 |
| Connected groups | 73 |
| Internal train / development reservations | 197 / 43 |
| Pending reviews | 240 |
| Training-eligible records | 0 |

Checksums, pinned Ossie JSON Schema validation and exact metadata reconstruction passed.
Dependency references, unique identifiers, input whitelisting and group/duplicate split isolation passed.
The schema hash matches the pinned source registry.
The review audit reported no malformed approved reviews; all reviews remain pending.
This audit establishes structural integrity. It does not establish correct business definitions or executable SQL.

The first submission failed because the verifier used catalog filenames as IDs.
The corrected verifier reads catalog IDs from the catalog-review manifest.
No pilot records or labels changed during this correction.

## Retrieval diagnostics

All methods searched the same 702-table universe and returned K=32 candidates.
The encoder was unadapted `all-MiniLM-L6-v2`, pinned to revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`.
BM25 used k1=1.2 and b=0.75. RRF used c=60 and full rankings, without tuning.

These measures use reference-SQL table evidence for 120 Spider questions only.
They are weak structural coverage diagnostics, not reviewed semantic accuracy.
No BIRD coverage, business-semantic completeness or SQL execution metric is available from this run.

| Method | Mean reference-table recall@32 | All reference tables present@32 |
|---|---:|---:|
| BM25 | 68.06% | 57.50% |
| Dense | 93.06% | 87.50% |
| Untuned RRF hybrid | 88.26% | 83.33% |

The aggregate results match the earlier local CPU diagnostic to reported precision.
Matching aggregates do not prove identical rankings for every tied candidate.
Untuned RRF trails dense retrieval on this evidence. Retain dense as a baseline and tune fusion using reviewed development labels.
Published fusion studies support comparing normalized score fusion as well as RRF.

## Timing and runtime

Offline index encoding took 0.870 seconds after model loading.
The warm serial loop took 9.21 ms p50 and 11.87 ms p95 across 240 questions.
Each loop included query encoding, exact dense scanning, BM25 ranking and RRF.
The measurement excludes model loading, queues, network transport, reranking, context assembly and concurrent serving.
The 702-table exact scan does not establish a large-catalog latency SLA.

162 table descriptions exceeded the 256-token encoder window.
Overflow chunking created 998 chunks for 702 tables, with at most 12 chunks per table.
The encoder discarded zero tokens. Normalized mean chunk pooling remains a representation choice requiring ablation.

The run used Torch 2.8.0, Transformers 4.57.6 and Sentence Transformers 5.2.3.
Missing packages were installed only under this run's `dependencies` directory.
The job used an immutable Ray working-directory package, one GPU and four worker CPUs.
Artifacts remain at `/home/cdsw/semantic-runs/semantic-pilot-audit-20261010-02/`.
The `baselines` subdirectory contains rankings, per-question diagnostics and a checksummed manifest.

## Next gate

1. Review the first 80 questions and referenced Ossie definitions.
2. Resolve questionable source descriptions, ambiguity and acceptable alternative context sets.
3. Freeze reviewed pilot labels and preserve unknown masks.
4. Tune candidate windows and fusion using development data.
5. Compare a reference search engine and optional single reranker at equal budgets.
6. Measure complete semantic context, catalog additions and concurrent end-to-end latency.

Local validation also passed 20 semantic unit tests, the corrected verifier audit, compilation and `git diff --check`.
This is live single-GPU retrieval evidence. It is not distributed training or NCCL evidence.
