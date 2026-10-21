# Domain-scoped Ossie retrieval: literature and implementation review

Reviewed: 21 October 2026. Focus: 2025–2026 methods, with older foundational datasets retained where needed.
This is a targeted review, not a systematic review or a reproduced benchmark.

## Decision and revised scope

The clarified deployment is well supported by existing research and implementations.
One deployed system serves one customer-specific business domain and catalog.
The retrieval method must generalize across customers and domains.
Its available inputs are the question, high-level domain description, and that customer's metadata and semantic definitions.
A customer catalog can span several schemas or databases; it is not necessarily one physical database.

The former pooled, unrelated-catalog experiment is no longer the primary task.
Its ambiguity labels and retrieval scores cannot be reused unchanged under the new scope.
They remain historical evidence for an open-catalog diagnostic.

Our proposed research question is:

> Can a compact learned retriever select sufficient, consistent Ossie context within a customer catalog, under fixed token and latency budgets, while transferring to unseen customer domains and newly added tables?

This is a proposed research position, not an established novelty claim.
Generic schema retrieval, semantic-layer grounding, dependency expansion, and clarification already have close predecessors.

## Closest research

| Work and publication status | Verified contribution | Relevance and boundary for our study |
|---|---|---|
| **Zeng et al., Finding the Right Tables and Columns**, July 2026 preprint | Table and column retrieval evaluated per database; corpus-adaptive synthetic queries, hard negatives, and contrastive training. | Closest training precedent. Its metadata representation includes sampled rows for several datasets, so we need a strict metadata-only reproduction. Code release was not confirmed. [Paper](https://arxiv.org/html/2607.13311) |
| **Agarwal et al., REaR**, 2025 preprint; ACL 2026 | Retrieve, expand through estimated joinability, then refine. Online retrieval avoids LLM calls; offline enrichment is distinct. | Strong low-latency comparator. Replace inferred joins with declared Ossie relationships in a separately labeled adaptation. A standalone author repository was not confirmed. [Proceedings](https://aclanthology.org/2026.acl-long.1826/), [methods](https://arxiv.org/html/2511.00805) |
| **Soliman et al., CORE-T**, 2026 preprint | Training-free retrieval, one LLM selection stage, and compatibility-based adjustment; published code pools multiple benchmark databases. | Useful complete-table-set comparator. Its pooled scope and sampled-value signals differ from our deployment. Measure a metadata-only, customer-scoped adaptation separately. [Paper](https://arxiv.org/html/2601.13111), [code](https://github.com/UKPLab/emnlp2026-core-t) |
| **Wang et al., AutoLink**, 2025 preprint; AAAI 2026 | Iterative agent-guided schema exploration and expansion without supplying the entire schema. | Useful accuracy-oriented comparator. Repeated LLM calls make it a different latency operating point, not a default serving design. [Official paper](https://ojs.aaai.org/index.php/AAAI/article/download/40672/44633), [code](https://github.com/wzy416/AutoLink) |
| **De et al., JoinGR**, October 2026 preprint | Query-conditioned traversal over join structure, using a lightweight scorer on frozen embeddings; evaluates cross-benchmark transfer. | Shows that retrieving implicit bridge tables and transferable traversal are prior work. A graph model remains optional, not required for our implementation. [Paper](https://arxiv.org/html/2610.01064) |
| **Pillai, GROUND**, 2026 preprint | Governed metrics, dimensions, joins, filters, validation and abstention, with released benchmark artifacts. | Close semantic-completeness precedent. The evaluated grounding packet contains the full semantic layer; policy inputs and retry budgets differ across conditions. It does not isolate budgeted retrieval gains. [Paper](https://arxiv.org/html/2608.26157), [artifacts](https://github.com/aravindsp/ground-benchmark) |
| **Zhang et al., Qwen3 Embedding**, 2025 technical report | Instruction-aware embedding and reranking families, including 0.6B variants. | Practical modern baselines beyond MiniLM. General retrieval rankings do not establish Ossie accuracy or our latency. [Report](https://arxiv.org/abs/2506.05176), [implementation](https://github.com/QwenLM/Qwen3-Embedding) |
| **CLEAR**, ICDE 2025; **Ding et al., AmbiSQL**, 2025 preprint | Schema-grounded ambiguity detection, interactive choices and query reformulation. | Relevant ambiguities can remain inside one domain. Reuse their task taxonomy rather than treating every low score as a clarification need. [CLEAR](https://ieeexplore.ieee.org/document/11113237/), [AmbiSQL](https://arxiv.org/abs/2508.15276) |
| **Sarwar et al., CLARITY**, April 2026 preprint | Multi-faceted ambiguity and unanswerability, including conversational continuations and schema annotations. | A useful evaluation design for locating the actual ambiguity and handling incomplete clarification. Public artifact access was not verified in this pass. [Paper](https://arxiv.org/abs/2604.22313) |

The corpus-adaptive paper explicitly retrieves within each database group.
This supports the revised experimental scope without claiming that every real customer has exactly one database.
Its target-corpus adaptation and leave-one-corpus-out experiments also motivate separate transfer and adaptation settings.
[Source](https://arxiv.org/html/2607.13311)

## Prior implementations worth inspecting or adapting

These are implementation precedents, not evidence that we reproduced their performance.
Repository documentation and public file trees were inspected; WrenAI's architecture document was additionally retrieved at its recorded commit.

| Implementation | Reusable mechanism | What we must change or control |
|---|---|---|
| **WrenAI** | Explicit MDL business context, schema-item retrieval, separate query-history retrieval, semantic planning and validation. | Replace or map MDL representation to Ossie. Disable query-history examples in the primary metadata-only comparison. This is a strong architecture precedent, not an apples-to-apples retrieval benchmark. [Pinned architecture](https://github.com/Canner/WrenAI/blob/aa9432ec42e93519b23b86bb47e48d6e360d3a30/docs/core/reference/architecture.md) |
| **BEAVER retrieval pipeline** | Dense retrieval with optional reranking; separate table, join, column, domain-knowledge and decomposition evaluation. | Reuse evaluation boundaries and a retrieve/rerank comparator. Inspect serialized evidence before claiming metadata-only operation. The data downloader requires gated access. [Repository](https://github.com/beaverbench/beaver), [retrieval entrypoint](https://github.com/beaverbench/beaver/blob/main/retrieve/retrieve.py) |
| **CORE-T** | Offline compatibility cache and online table-set selection. | Restrict candidate catalog and remove sampled rows in our adaptation. Label this modified configuration rather than reporting its published scores. [Code](https://github.com/UKPLab/emnlp2026-core-t) |
| **AutoLink** | Incremental evidence exploration and schema-linking evaluation. | Use as an optional quality ceiling with measured calls and latency. [Code](https://github.com/wzy416/AutoLink) |
| **dbt semantic-layer benchmark** | Compares SQL generation, semantic-layer querying and MCP access on common business questions. | Reuse execution evaluation concepts. These strategies change interfaces and information, so they do not independently measure retrieval quality. [Repository](https://github.com/dbt-labs/dbt-llm-sl-bench) |
| **Snowflake Cortex Analyst / Semantic Views** | Domain definitions, metrics, relationships and verified examples in a customer deployment. | A product reference, not open retrieval code. Disable examples in the metadata-only condition; do not infer its private ranking algorithm. [Official documentation](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst) |
| **CLEAR / AmbiSQL** | User-facing clarification interfaces and ambiguity handling. | Adapt choices to supported business definitions. Do not introduce cross-customer ambiguity into a customer-scoped evaluation. [CLEAR code](https://github.com/mengzhang18/CLEAR), [AmbiSQL code](https://github.com/JustinzjDing/AmbiSQL) |

Repository HEAD identifiers for six key projects are recorded in the accompanying source manifest.
A recorded HEAD is a version anchor, not proof that every file or experiment was audited.
No third-party implementation was installed or executed during this review.

## Dataset availability and recommended roles

Access to a paper, dataset card, schema, gold SQL, and executable database are separate facts.
The table distinguishes them. No new dataset was downloaded or imported during this review.

| Dataset | Available evidence and access | Recommended role / restriction |
|---|---|---|
| **Spider 1.0** | Official questions, SQL and database/schema assets; established database-disjoint evaluation. Older foundational dataset. | Structural training and converter checks. Usually too small to establish enterprise-scale retrieval. Keep each database as an explicit customer proxy. [Official site](https://yale-lily.github.io/spider) |
| **BIRD** | Official train/dev downloads include realistic databases and question-SQL data; descriptions and question-specific evidence need separate treatment. | Main initial structural training source. Acquire real schema/key evidence; the current description-only import is incomplete. Question-specific evidence is not automatically shared catalog metadata. [Official site](https://bird-bench.github.io/) |
| **Corrected BIRD subsets / Arcwise-Plat** | Authors release corrected subsets and audit tooling; SQL-only fixes and ambiguity-resolving fixes are distinct variants. | Hold out as label-quality diagnostics. Preserve variant identities and underlying database groups. Do not treat reviewed benchmark subsets as fresh training data. [Author repository](https://github.com/uiuc-kang-lab/text_to_sql_benchmarks) |
| **BEAVER** | Current project reports 9,128 queries, 812 tables, 19 domains, with 7,978 queries publicly released. Its downloader requires authenticated gated access. | Enterprise retrieval and multi-table evaluation after access is confirmed. Do not mix these current counts with older 209-question paper subsets. Confirm dataset terms separately from code access. [Project](https://beaverbench.github.io/), [access instructions](https://github.com/beaverbench/beaver) |
| **LiveSQLBench** | Public schemas, column meanings and hierarchical knowledge bases. The inspected Base-Lite card describes 18 databases and 270 tasks. Full solution SQL/test cases require the documented access route. | Strong metadata-plus-business-knowledge evaluation. Use SELECT tasks for our initial retrieval study. Dataset release growth is not automatically a within-customer schema-evolution benchmark. [Repository](https://github.com/bird-bench/livesqlbench/blob/main/README.md), [card](https://huggingface.co/datasets/birdsql/livesqlbench-base-lite) |
| **EntSQL** | 2026 paper describes 1,066 aligned bilingual semantic examples across five business domains. Public SQLite archives and long documents exist. The card states that ground-truth answers are withheld. | Particularly relevant to business-definition retrieval. Start as held-out evidence-grounding evaluation; assess whether document knowledge can become reusable Ossie definitions. Do not assume supervised gold context sets are available. [Paper](https://arxiv.org/html/2606.03363), [dataset](https://huggingface.co/datasets/XuWave/Rethinking_Enterprise_Text_to_SQL) |
| **GROUND** | Repository contains 100 synthetic questions, semantic definitions, SQL and a small star schema; NHTSA question sets and source-build instructions are also present. | Semantic-rule and abstention diagnostics, not evidence of retrieval at thousands of tables. Root listing did not establish a dataset license; verify reuse terms. [Artifacts](https://github.com/aravindsp/ground-benchmark) |
| **Spider 2.0** | Enterprise workflow evaluation, local/cloud environments and partial gold-SQL availability. Authors explicitly discourage using released gold SQL for SFT. | Held-out scale and downstream evaluation; not our default training source. Budget cloud setup separately. [Official site](https://spider2-sql.github.io/) |
| **dbt benchmark assets** | Open evaluation framework and links to its modeled business workload. | Small controlled semantic-layer comparisons. Verify component dataset terms; a repository license does not necessarily cover upstream data. [Repository](https://github.com/dbt-labs/dbt-llm-sl-bench) |

Two access findings deserve explicit records:

- The EntSQL card states CC BY 4.0, while withholding ground-truth answers. Public availability does not imply ready supervised retrieval labels.
- The inspected LiveSQLBench Base-Lite card lists CC BY 4.0 in metadata but CC BY-SA 4.0 in its body. Resolve this discrepancy before redistribution.

These observations come from the [EntSQL card](https://huggingface.co/datasets/XuWave/Rethinking_Enterprise_Text_to_SQL) and [LiveSQLBench card](https://huggingface.co/datasets/birdsql/livesqlbench-base-lite).
They are access findings, not a legal interpretation.

The Ent-series/DRAG manuscript was discovered, but OpenReview presented a browser verification challenge.
Its publication status, stable release, and reuse terms were not established from primary evidence.
It is excluded from the executable dataset shortlist.

## What advanced beyond keyword plus embedding search

The following synthesis is our interpretation of the cited work.

1. **Retrieve at several granularities.** Index tables, fields and semantic definitions separately, retaining parent and dependency identifiers.
   A whole-table vector can obscure a rare field or a business metric.
2. **Adapt representations to schema language.** Document-anchored synthetic questions and within-domain hard negatives can train compact retrievers.
   SQL reference sets provide structural supervision, not proof of complete business semantics.
3. **Select a coherent set.** Independent top-k ranking can miss bridge tables or introduce incompatible definitions.
   Compare deterministic declared-dependency completion before proposing a learned set selector.
4. **Retrieve more evidence only when needed.** Agentic exploration can improve coverage, but its calls and latency must be measured.
   Use it offline for labeling or as a separately budgeted online fallback.
5. **Make ambiguity an explicit output.** Distinguish uncertain relevance, missing metadata, conflicting definitions, and unanswerability.
   Domain restriction removes unrelated-customer ambiguity but not these local problems.
6. **Evaluate data quality independently.** Published annotation audits demonstrate why executable reference SQL alone is not trustworthy semantic ground truth.
   Corrections can change model rankings. [Audit and corrected assets](https://github.com/uiuc-kang-lab/text_to_sql_benchmarks)

## Ossie alignment

The inspected core specification is the mutable draft `0.2.0.dev0`.
It defines datasets, fields, relationships, metrics and additional AI context.
Each document describes one model; the core does not define a cross-model bundle or cross-model references.
Pin the actual schema commit and preserve provenance during conversion.
[Official specification](https://github.com/apache/ossie/blob/main/core-spec/spec.md)

For this project, a customer-level manifest can list the permitted Ossie documents.
That manifest is our application contract, not a new field asserted to exist in the Ossie core.
Retrieve stable unit IDs and assemble necessary definitions without summarizing away formulas, units, grain, filters or approved joins.
Keep unsupported cross-model joins unresolved.

A single customer domain may still contain thousands of tables and several semantic models.
Domain restriction changes the admissible corpus; it does not imply a tiny catalog or one selected target table.

## Revised experiments and training recommendation

These are proposed experiments, not completed results.

```text
Customer/domain metadata and pinned Ossie catalog
                       |
BM25 + dense retrieval, fused within that catalog
                       |
Optional compact reranker + declared dependency completion
                       |
Budgeted context / clarification / missing-evidence decision
                       |
Fixed downstream generator and independent evaluation
```

1. **Rebuild the task boundary first.** Add an explicit customer-environment ID and high-level domain description supplied before retrieval.
   Initially map a source database to a customer proxy; document that simplification.
   Do not manufacture a large catalog by mixing unrelated databases.
2. **Separate three settings.** Evaluate unseen customer/domain transfer, optional customer-corpus adaptation, and index-only handling of new tables.
   Adaptation may use that customer's metadata and synthetic questions, but never held-out queries or answers.
   Keep bilingual versions, paraphrases, source queries, and duplicate schemas within their assigned evaluation groups.
3. **Build two label layers.** Structural labels identify necessary tables, fields, and declared joins.
   Semantic labels identify required definitions, valid alternatives, and clarification needs.
   Preserve unknowns. Record relevant candidates separately from sufficient context sets.
4. **Use same-domain hard negatives.** Include nearby facts, confusing metrics, wrong aggregation grain, and tables lacking required relationships.
   Mask alternate valid answers instead of automatically making them negatives.
5. **Run matched baselines.** Compare BM25, modern dense retrieval, development-tuned fusion, then fusion with a compact reranker.
   Add declared-dependency completion as a separate ablation.
   Test a REaR-style adaptation and optionally CORE-T/AutoLink under reported latency budgets.
6. **Train a compact retriever first.** Use standard contrastive learning with multiple positives and audited hard negatives.
   Compare a compact encoder with Qwen3-Embedding-0.6B before investing in larger models.
   GLiNER/Laya should earn their place through equal-candidate-pool reranker comparisons, not architecture preference.
7. **Measure completeness and latency together.** Report table and field recall, all-required-context coverage, conflict rate, clarification quality, context tokens and p50/p95 latency.
   Keep index construction, query serving and downstream SQL execution timings separate.
   Evaluate on a fixed machine and declared concurrency; report quality-versus-budget curves rather than one top-k score.
8. **Measure additions with frozen weights.** Introduce new tables or definitions within the same customer catalog, then update only the index.
   Use real version histories where available. Label constructed addition sequences as simulations.
   Track retrieval coverage, update time, stale-definition errors and context completeness.

The primary condition allows metadata and declared semantics only.
Sample rows, value probing, query-history examples, execution feedback and gold evidence belong in separately labeled conditions.
All compared systems receive the same information allowance and downstream generator budget.

## What remains potentially distinctive

A defensible contribution would combine metadata-only Ossie context sufficiency, transfer across customer domains, and controlled within-customer catalog growth at measured latency.
Neither using Ossie nor adding embeddings is sufficient novelty by itself.
The corpus-adaptive paper already covers trained retrieval; REaR/CORE-T/JoinGR cover complementary multi-table structure.
GROUND, EntSQL and existing semantic platforms cover business meaning.

Our study should demonstrate a specific improvement over those relevant mechanisms under matched information and resource budgets.
If a tuned hybrid baseline with better metadata solves the task, retain that engineering result and narrow the research claim.

## Search and verification limits

The academic-search MCP was unavailable. Endpoint preflight succeeded after retrying outside the network sandbox.
The OpenAlex fallback returned HTTP 429. Primary arXiv, proceedings, author repositories, official dataset cards and product documentation were used instead.
Searches covered schema retrieval, enterprise semantic context, implementations, data access and within-domain ambiguity.
Conference and preprint versions were deduplicated by identifier/title.
Social posts, secondary summaries and unverified leaderboard claims were excluded from evidence.

No citation-count ranking was used. No claim of exhaustive coverage or research priority follows.
REaR's conference status is verified through ACL Anthology; a repository name alone is not used to assign CORE-T a conference status.
GROUND has conflicting day-level date metadata, so this review cites only its verified 2026 preprint status.
Exact dataset versions, licenses and benchmark-access terms must be pinned before acquisition.

See [source manifest and repository anchors](domain-scoped-sources-20261021.json) and [search record](domain-scoped-search-log-20261021.md).
