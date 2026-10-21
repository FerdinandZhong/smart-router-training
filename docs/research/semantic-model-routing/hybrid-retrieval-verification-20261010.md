# Pilot verification and established hybrid retrieval / Pilot 核验与成熟混合检索方法

Date: 2026-10-10. Scope: semantic-context research, separate from the original model-routing experiments.

## Decision / 结论

Use BM25 plus a pinned dense encoder as the first retrieval baseline. Fuse the rankings before selecting multiple tables.
This method has published evidence and maintained search-engine implementations. Its quality on our Ossie catalogs still requires evaluation.
The research contribution should concern complete, consistent context under a fixed budget and catalog additions.
Hybrid retrieval itself is an established baseline, not the novelty claim.

采用 BM25 与固定版本 embedding 模型作为首个检索基线，再融合排序，输出多个候选表。
混合检索有公开论文和成熟搜索引擎实现，但仍需验证其在本项目 Ossie 数据上的效果。
研究重点应是固定预算下的上下文完整性、一致性，以及新增目录的适应能力。

## Verified sources / 已核验文献

Search routes: primary author repository, arXiv, ICLR/OpenReview search results, and official Elasticsearch documentation.
The academic MCP tools were unavailable. Browser search and primary-source retrieval provided the fallback.
The ACM page returned HTTP 403; the authors' publicly accessible RRF paper supplied its method and publication details.
No citation counts or publication-impact claims were collected.

| Source | Evidence | Use in this project |
|---|---|---|
| Cormack, Clarke and Büttcher, SIGIR 2009, [Reciprocal Rank Fusion](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf), DOI 10.1145/1571941.1572114 | Combines ranks using the sum of `1 / (c + rank)`; evaluates TREC and LETOR experiments. | Transparent initial fusion with `c=60`; no raw BM25/cosine addition. |
| Bruch, Gai and Ingber, [An Analysis of Fusion Functions for Hybrid Retrieval](https://arxiv.org/abs/2210.11934v2), revised 2023, journal DOI 10.1145/3596512 | Finds parameter sensitivity in RRF and advantages for tuned convex score combination in studied settings. | Compare RRF with normalized score fusion. Tune only on reviewed development data. |
| Thakur et al., NeurIPS Datasets and Benchmarks 2021, [BEIR](https://arxiv.org/abs/2104.08663v4) | Studies retrieval generalization; identifies BM25 as robust and reranking as computationally expensive. | Retain lexical and dense standalone baselines. Measure reranker latency separately. |
| Enevoldsen et al., ICLR 2025, [MMTEB](https://arxiv.org/abs/2502.13595v4) | Evaluates embeddings across languages, tasks and domains. Model scale alone does not settle model choice. | Add Chinese and bilingual business questions before choosing the production encoder. |
| [Official Elasticsearch RRF documentation](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion) | Defines RRF retrievers, rank constants, candidate windows and result size. | Use an established search-engine implementation for the later large-catalog baseline. |

These sources do not establish Ossie semantic correctness or our latency SLA.
Older foundational papers remain necessary to define the method. MMTEB supplies relevant evidence from 2025.

## Current pilot / 当前 pilot

The current bundle is `data/semantic-research/pilot-20261010-v3`.
It contains 240 questions, 112 Ossie catalogs, 702 tables and 5,205 addressable metadata units.
Spider and BIRD each contribute 120 questions. The first review batch contains 80 questions.
The internal reservations contain 197 training questions and 43 development questions across 73 connected groups.
All domains remain reserved for eventual formal training. This is a known-catalog question split, not an unseen-catalog test.

All 240 reviews remain pending. Zero records qualify for training.
Schema validity and checksums establish structural integrity. They do not establish correct business definitions or executable SQL.
BIRD reference table sets remain unavailable in this diagnostic. Physical database execution has not been checked.

当前数据包可以进行结构核验和检索诊断，但不能作为已审核训练集。
240 条样本均未完成审核，训练可用样本为零。
JSON Schema 合法并不代表业务含义正确，也不代表 SQL 可执行。

One review priority is source-description quality. For example, the `address.CBSA` draft describes officers while its examples resemble geographic classifications.
Treat this as a possible description inconsistency requiring source and domain review. Do not silently rewrite source evidence.
Human reviewers must also check SQL-dependent values, synonyms, alternative valid tables and required relationship definitions.

## Pipeline / 流程

```text
Versioned Ossie catalog + independently verified metadata
                  |
        Search documents + stable IDs
                  |
Query + confirmed history + access scope
                  |
        +---------+---------+
        |                   |
      BM25              Dense retrieval
        |                   |
        +------ RRF --------+
                  |
       Optional single reranker
                  |
    Multiple tables + exact Ossie units
                  |
  Declared dependency and conflict checks
                  |
       Token-budgeted LLM context
```

1. Generate search text from table names, descriptions, columns and reviewed business aliases.
2. Keep exact Ossie definitions outside the searchable summary; retrieve them by stable IDs after selection.
3. Apply user access and catalog-version constraints to both retrieval branches before fusion.
4. Run BM25 and dense retrieval on the same allowed catalog and query context.
5. Start with up to 100 candidates per branch and RRF `c=60` for the planned search-engine baseline.
6. Return the top 32 fused candidates for pilot review; do not force a single-table result.
7. Add one reranker only if measured quality gains justify its latency.
8. Assemble selected fields, relationships and definitions within the explicit token budget.
9. Reject incompatible definitions or ask for clarification when the catalog cannot resolve ambiguity.

Candidate window 100 and final K=32 are starting configurations, not tuned recommendations.
The current diagnostic fuses full rankings across all 702 tables. It does not yet implement the proposed windowed serving pipeline.
The existing BM25 code is a deterministic project implementation. A reference-engine comparison must check tokenization, ranking and zero-score handling.
No permission-filter, ANN index, conflict assembler or semantic reranker is verified by this diagnostic.

元数据分别承担检索文本、精确定义和约束三种作用。
检索文本用于召回；精确定义用于构建最终上下文；版本与权限用于限制可见范围。
Ossie 声明的依赖关系可以直接使用，不需要训练图模型。
数据血缘只能用于其声明的依赖含义，不能自动视为可执行 join。

## Evaluation and next experiments / 评估与下一步

Run BM25, dense, RRF and tuned normalized score fusion against the same catalog, allowed scope, K and context budget.
Use reviewed development labels for encoder and fusion selection. Freeze settings before a separate formal evaluation.
Keep pending judgments masked. Do not convert missing labels into negatives.

Report table recall and complete-table coverage separately. Add reviewed semantic-unit completeness, definition consistency and budget adherence.
Measure SQL execution success only after acquiring and verifying the physical databases.
Report query encoding, lexical retrieval, vector retrieval, fusion, reranking and context assembly separately.
Measure p50/p95 end-to-end latency under concurrency; exclude offline indexing from online latency but report update time.

The 702-table exact scan verifies a bounded pilot. It cannot establish performance on tens of thousands of tables.
For scale, compare a reference lexical engine plus ANN against exact dense search and measure ANN recall loss.
For catalog arrivals, freeze model weights and index new independently authored Ossie documents. Test new-table recall and old-table regressions.
For Chinese queries, compare small multilingual encoders under the same measured latency budget.

First complete the 80-question review batch and its referenced catalog reviews.
Then freeze a reviewed pilot, tune fusion, and compare optional embedding adaptation or one reranker.
GLiNER/Laya remain candidate rerankers; they are not required to demonstrate this baseline.

## Cluster evidence / 集群证据

The supplied cluster has a live CPU head and two live L40S workers.
The bounded audit uses one GPU and four worker CPUs. It performs no model optimization or label approval.
Dependencies missing from the training environment are installed into this run's directory.
The immutable Ray package contains the current pilot, review forms, pinned Ossie schema and verification code.
Results persist under `/home/cdsw/semantic-runs/<run-id>` on the cluster.
See the dated project status report for the completed job, audit and measured retrieval results.
The [completed cluster report](../../status/2026-10-10-semantic-cluster-verification.md)
records 93.06% weak mean table recall for dense retrieval and 88.26% for untuned RRF at K=32.
Warm serial p95 was 11.87 ms across all three methods together. This is not an end-to-end serving measurement.
