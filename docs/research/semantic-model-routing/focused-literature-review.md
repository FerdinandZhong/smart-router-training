# Literature review: retrieving sufficient Ossie semantic context

Review date: 9 October 2026. Main publication window: 2025–2026.
Status: targeted literature review and proposed experiments; no method has been reproduced here.

## Assessment

The research problem is useful, but the proposed retrieval architecture has close prior work.
Training a schema retriever, expanding through joins, and selecting a coherent table set are already active research directions.
In particular, JoinGR directly overlaps with a small learned model that traverses a schema graph.
REaR and CORE-T also closely match the proposed retrieve–expand–select pipeline.

The most credible hypothesis concerns **complete business definitions under a fixed context budget as an enterprise catalog grows**.
This means retrieving the required metric expressions, filters, grain, time rules, and approved relationships alongside tables.
Ossie supplies a useful representation for that task.
Using Ossie alone does not establish algorithmic novelty.

This review selects 23 works, including one explicitly older benchmark, across five related areas.
The [source inventory](focused-sources.json) records publication status and reading depth.
The [search record](search-record.md#focused-review-addendum) records discovery routes and limitations.
The earlier [implementation assessment](literature-review.md#implementation-assessment) remains separate from these literature findings.

## 1. Trained schema retrieval

| Work | Verified method or evidence | Consequence for our study |
| --- | --- | --- |
| **[JoinGR: Learning to Traverse Join Graphs for Table Retrieval](https://arxiv.org/abs/2610.01064)**, De et al., 1 October 2026 preprint | Frozen embeddings feed a lightweight, query-conditioned edge scorer. A pairwise margin loss uses gold table sets. It evaluates cross-domain transfer and perfect table recall. | This is the nearest learned traversal baseline. A small graph scorer and transfer to unseen schemas are established ideas. |
| **[Finding the Right Tables and Columns](https://arxiv.org/abs/2607.13311)**, Zeng et al., July 2026 preprint | Corpus-grounded synthetic questions and granularity-aware hard negatives train a 305M embedding model contrastively. The study also evaluates held-out corpora. | A trained embedding model is essential. Comparing only with an untuned general embedding model would be weak. |
| **[Bi-SR](https://aclanthology.org/2026.findings-acl.369/)**, Wu et al., Findings ACL 2026 | Schema and query enrichment support contrastive dense retrieval. This review inspected its abstract and metadata. | Include enrichment and trained retrieval as separate factors. Detailed reproduction requires further full-text inspection. |
| **[DBCopilot](https://www.openproceedings.org/2025/conf/edbt/paper-209.pdf)**, EDBT 2025 | A generative schema router uses graph serialization, constrained decoding, and synthetic schema-to-question training. Its method discussion identifies unseen-schema limitations of parameterized retrieval. | Contrast catalog-specific training with candidate-conditioned scoring. Do not assume a fixed output vocabulary supports new tables through indexing alone. |
| **[Extractive Schema Linking for Text-to-SQL](https://arxiv.org/html/2501.17174)**, Glass et al., 2025 preprint | Decoder representations predict schema-item relevance and roles. | Independent decision heads are a credible baseline, but their general structure is not new. |

Two findings deserve particular attention.

JoinGR's BEAVER-DW experiment contains 97 tables and 121 questions, with five-fold evaluation.
Its graph combines column nodes, within-table edges, and foreign-key edges.
The authors also compare fixed graph propagation with learned propagation.
These tests do not establish behavior on 10,000 tables or chronological arrivals of new semantic definitions.
Its acknowledged limitations include missing foreign keys and English-only evaluation. [Methods and limitations](https://arxiv.org/html/2610.01064).

The corpus-adaptive embedding paper reports average Recall@10 increasing from 60.4 to 75.6.
These are author-reported benchmark results, not expected gains for our system.
Training uses one positive and six hard negatives per question.
Retrieval is scoped to each database group, and its metadata representation includes sampled rows.
The main adaptation condition sees the target catalog; held-out-corpus evaluation is a separate condition. [Methods](https://arxiv.org/html/2607.13311).

## 2. Graph expansion and coherent table selection

| Work | Verified method or evidence | Consequence for our study |
| --- | --- | --- |
| **[REaR: Retrieve, Expand and Refine](https://aclanthology.org/2026.acl-long.1826/)**, Agarwal et al., ACL 2026; preprint November 2025 | Retrieves seed tables, expands through column similarity, and refines using relevance and joinability. Online retrieval avoids LLM calls; offline descriptions use an LLM. | This closely matches the proposed three-stage pipeline. Include it as an efficiency baseline. |
| **[CORE-T](https://arxiv.org/abs/2601.13111)**, Soliman et al., 2026 preprint; inspected v3 | Dense retrieval, cached compatibility, one LLM selection call, and additive recovery produce a coherent table set. Experiments pool tables without database IDs. | A strong comparison for whole-catalog selection. Its value-based compatibility evidence needs an equal-access comparison track. |
| **[Guided Table Retrieval for Structured Data Search](https://arxiv.org/abs/2608.11644)**, Jindal et al., August 2026 preprint | Combines token matching, directed join reachability, LLM disambiguation, and compact join trees. Semantic fallback supplements lexical matching. | Keyword search with relational reasoning is a stronger baseline than isolated BM25. Its rooted left-join assumptions require adaptation. |
| **[Graph-Link](https://proceedings.mlr.press/v306/zhong26s.html)**, Zhong et al., ICML 2026 | Hierarchical schema communities and Steiner-tree optimization recover connecting tables. An LLM refines the resulting context. | Connectivity-preserving context selection already has a direct precedent. Count community summaries and refinement calls in cost. |
| **[SchemaGraphSQL](https://aclanthology.org/2026.findings-eacl.134/)**, Safdarian et al., Findings EACL 2026; preprint May 2025 | Training-free schema linking combines LLM grounding with graph pathfinding. The published abstract also describes discovering missing join relationships. | Compare deterministic path completion with learned traversal. Inferred join candidates require separate validation before execution. |
| **[ARM](https://aclanthology.org/2025.acl-long.1463.pdf)**, Chen et al., ACL 2025 | Aligns questions with available data and its relationships, then verifies selected evidence. | Query decomposition and relationship-aware selection are established. Include an LLM-assisted baseline if serving budgets permit. |
| **[Plugging Schema Graph into Multi-Table QA](https://aclanthology.org/2025.findings-emnlp.311/)**, Wang et al., Findings EMNLP 2025 | Human-curated relations, pruning, and subpath merging support multi-table QA. Evaluation includes the CISS vehicle-safety corpus. | Domain expertise and real industrial data already appear in related work. Our contribution must exceed having a real deployment. |

CORE-T is especially relevant to the catalog boundary.
Its appendix discusses lazy compatibility caching and updating entries associated with a newly added table.
That is an incremental maintenance design, not a reported longitudinal test of business-definition completeness.
Its main representation includes five sampled rows, and inferred compatibility uses value evidence.
A metadata-only adaptation must be named and evaluated as an adaptation. [Methods and Appendix C](https://arxiv.org/html/2601.13111).

Graph-Link explicitly leaves frequent schema changes and underspecified questions for future work.
Its graph may include similarity-based edges in addition to declared foreign keys.
The retrieved path therefore needs independent business validation in our application. [Paper](https://raw.githubusercontent.com/mlresearch/v306/main/assets/zhong26s/zhong26s.pdf).

**Our inference:** graph connectivity is necessary for some queries, but it does not certify business consistency.
The same connected tables can support gross revenue, net revenue, or settled revenue.
Each answer can require different expressions, filters, dates, and aggregation rules.
This distinction should become an annotation target and an evaluation condition.

## 3. Noisy questions, ambiguity, and clarification

| Work | Relevant finding | Consequence for our study |
| --- | --- | --- |
| **[RASL](https://arxiv.org/html/2507.23104)**, Eben et al., 2025; paper reports KDD SKnowLLM workshop acceptance | Retrieves typed schema units with question and keyword queries, then selects tables. | Compare query expansion and semantic-unit indexing with direct question retrieval. |
| **[Solid-SQL](https://aclanthology.org/2025.coling-main.654/)**, Liu et al., COLING 2025 | Trains a robust schema linker with LLM augmentation; evaluates perturbed benchmarks. | Robustness to paraphrases and schema wording is already studied. Use it to design controlled perturbations. |
| **[SQUAB](https://aclanthology.org/2025.emnlp-main.906/)**, Papicchio et al., EMNLP 2025 | Generates annotated ambiguous and unanswerable semantic-parsing questions using SQL and LLMs. | Distinguish ambiguity from ordinary retrieval errors. Synthetic challenge cases need review and separate reporting. |
| **[Learning to Clarify](https://proceedings.iclr.cc/paper_files/paper/2025/hash/4ffd05ca3cf3985f4572af015b4cfc1e-Abstract-Conference.html)**, Chen et al., ICLR 2025 | Learns clarification behavior; AmbigSQL is a task within the paper. | Predicting whether clarification is useful is not a new task by itself. |
| **[BIRD-INTERACT](https://proceedings.iclr.cc/paper_files/paper/2026/hash/496b549556509bbb9770bf9d335c5800-Abstract-Conference.html)**, Huo et al., ICLR 2026; preprint 2025 | Evaluates interactive database work with user clarification and executable checks. | Measure downstream behavior after clarification, while keeping our initial scope read-only. |

Our dataset should separate three phenomena.
Typos and paraphrases preserve one intended answer.
Ambiguous business terms permit multiple answers until the user clarifies.
Unanswerable questions lack a required approved definition or data source.
Training every example to select one table set would mislabel the latter two conditions.

An embedding model may tolerate some wording errors, but this review establishes no universal advantage over a tuned hybrid retriever.
That advantage must be measured on natural company questions and a separately labeled perturbation set.

## 4. Business semantics and compact context

| Work | Relevant method and boundary | Consequence for our study |
| --- | --- | --- |
| **[A Semantic-Layer-Mediated Agent](https://arxiv.org/html/2606.31041)**, Kim et al., June 2026 preprint | Semantic models support an intermediate request and deterministic compilation. Curated per-database context limits claims about retrieval scale. | Semantic compilation is prior work. Hold the compiler fixed when evaluating retrieval. |
| **[GROUND](https://arxiv.org/html/2608.26157)**, Pillai, 2026 preprint | Validates governed metric, join, grain, filter, and policy definitions. Section 4.1 supplies the full semantic layer. | Business-semantic validation already has close overlap. Giving only our method better definitions would confound the comparison. |
| **[Database Context Compression](https://arxiv.org/abs/2606.28601)**, Liu et al., June 2026 preprint | Describes shared structural and semantic compression with query-time evidence. This review inspected the abstract. | Compare selection with compression. Further methods inspection is needed before reproduction. |

The inspected [Ossie core specification](https://github.com/apache/ossie/blob/main/core-spec/spec.md) is a mutable development specification.
It represents one model per document, with datasets, relationships, fields, and metrics.
Its core does not define cross-model references or a bundle format.
Pin a specification commit before implementation.
Keep retrieval identifiers and catalog links outside the core format unless an approved extension defines them.

The proposed representation has three levels:

```text
Approved Ossie model documents + reviewed catalog relationships
                              |
              model / dataset / definition descriptors
                              |
Question -> hybrid seed retrieval -> query-guided dependency selection
                              |
          exact expressions + required filters + approved joins
                              |
              budget and consistency checks -> local summary
                              |
                        fixed SQL generator
```

This is our proposed experimental representation, not a claim that Ossie defines every field in the diagram.
Record grain, units, and applicability only where their meaning is explicit or independently reviewed.
Keep formulas and mandatory rules in an exact structured payload beside any generated summary.
Evaluate summarization as a separate factor because omission can occur after successful retrieval.
Do not create cross-model execution joins merely because two descriptors contain similar column names.

## 5. Data and benchmark construction

| Work | Useful evidence | Boundary |
| --- | --- | --- |
| **[BenchPress](https://www.vldb.org/cidrdb/papers/2026/p16-wenz.pdf)**, Wenz et al., CIDR 2026; preprint 2025 | SQL logs generate draft natural-language questions that experts select, rank, or edit. | Useful for weak supervision and annotation tooling. Reconstructed questions do not replace naturally expressed user questions. |
| **[BEAVER](https://arxiv.org/abs/2409.02038)**, first preprint 2024; [current project](https://beaverbench.github.io/) | Enterprise questions, schemas, and retrieval annotations support realistic evaluation. | Explicit older-work exception. Published subsets and the evolving project have different sizes; pin the version and retrieval pool. |
| **[Fantastic Tables and Where to Find Them](https://www.openproceedings.org/2025/conf/edbt/paper-108.pdf)**, Christensen et al., EDBT 2025 | Searches semantic data lakes using entity tuples and knowledge-graph semantics. | Adjacent task: its query form and content evidence differ from natural-language retrieval of Ossie definitions. |

Public SQL benchmarks can supply table and column supervision.
They do not automatically supply validated Ossie models or gold business interpretations.
SQL parsing also misses acceptable alternatives, such as a materialized view that implements the same approved calculation.
Our labels should permit multiple sufficient bundles and preserve unreviewed candidates as unknown.

Create two data tracks.
The first uses existing benchmarks for reproducible table retrieval comparisons.
The second uses approved company semantics and independently reviewed business questions.
Keep an access-controlled internal test set if redistribution is unavailable.
Any public artifact should state its source rights, transformation rules, and limitations.

## 6. What remains defensible

| Proposed contribution | Literature assessment | Required evidence |
| --- | --- | --- |
| Small trained schema embedding | Direct overlap with corpus-adaptive embeddings and Bi-SR | Baseline, not primary novelty |
| Retrieve, traverse, then refine | Direct overlap with REaR, JoinGR, CORE-T, and Guided Table Retrieval | Show a specific unresolved failure |
| Connected, complete table sets | Existing full/perfect recall and coherent-set methods | Do not rename table completeness as a new task |
| Index new tables without retraining | Existing nonparametric retrieval and CORE-T maintenance design | Measure temporal performance; indexability alone is insufficient |
| Ossie representation and a real company deployment | Valuable engineering and external-validity choices | Format and deployment alone do not establish method novelty |
| Complete, nonconflicting business definitions under a budget | Closely related to semantic governance, with a narrower retrieval question | Controlled comparisons with shared semantics, validation, and downstream generation |
| Temporal benchmark with natural questions and semantic hard negatives | Plausible dataset and evaluation contribution | Independently labeled snapshots, credible diversity, and no future-catalog leakage |

**Recommended question:** Can a learned selector improve complete, consistent Ossie-context retrieval over strong hybrid and graph baselines at equal budgets, including newly added tables?

This is a testable hypothesis.
The reviewed studies do not establish that our exact combined condition is solved.
They also do not establish that nobody has studied it.
Avoid a priority claim until the benchmark and method are concrete.

## 7. Experiments that answer the question

1. Freeze catalog snapshot C0 and independent question groups.
2. Establish BM25, dense, and tuned hybrid retrieval with identical available descriptions.
3. Add a generic reranker and corpus-adaptive embedding training with reviewed hard negatives.
4. Compare fixed dependency expansion, REaR, learned JoinGR-style traversal, and CORE-T-style set selection.
5. Add business-definition supervision while holding candidate access and deterministic validation constant.
6. Evaluate C1 and C2 after indexing newly added tables, with model weights frozen.
7. Report natural questions, ambiguity, linguistic perturbations, and complex joins separately.

These are proposed experiments, not implementation commitments or measured results.
Start with standard contrastive, ranking, or masked relevance objectives.
A new cost-aware loss is outside this study's current scope.
Laya and GLiNER remain candidate backbones; neither receives preferential training data or metadata.

Use three explicit catalog protocols: known database, pooled catalog, and chronological table additions.
The main enterprise result should use the entire eligible catalog without an oracle database ID.
In the temporal protocol, new-table descriptors may enter the index at evaluation time.
Their synthetic training questions, labels, and future query logs must not enter C0 training.
Report retraining on the expanded catalog as a separate adaptation condition.
If historical snapshots are unavailable, label staged table arrivals as simulated rather than prospective enterprise evidence.

Test increasing real catalog sizes, targeting approximately 100, 1,000, and 10,000 tables when available.
Renamed copies can measure index throughput, but cannot establish semantic generalization.
Report table, model, definition, column, and relationship counts separately.
Measure new-table indexing time and old-query regression after additions.
Deleted tables are outside the primary append-only protocol requested for this study.

Use fixed 2K, 4K, and 8K semantic-context budgets as initial planning values.
Count dependency expansion and summaries inside the budget.
Also report offline enrichment expense, online calls, total prompt tokens, and warm/cold p95 latency.
For value-dependent methods, provide equal data access or label a metadata-only adaptation explicitly.

| Outcome | Measurement |
| --- | --- |
| Table retrieval | Recall@K and fraction of questions with all required tables retrieved |
| Semantic completeness | Fraction containing at least one independently approved sufficient definition bundle |
| Semantic consistency | Incompatible formula, filter, grain, time, or relationship selections |
| Ambiguity handling | Missed ambiguity, unnecessary clarification, and correctness after clarification |
| New-table transfer | Quality on questions needing new tables, with weights frozen |
| End-to-end utility | Business-correct answers with one fixed generator; execution success reported separately |
| Serving behavior | Token budgets, p50/p95 latency, throughput, and indexing/update expense |

Run a factorial ablation over scorer, graph expansion, semantic descriptor richness, and summarization.
This prevents attributing gains from better metadata or deterministic dependency closure to the learned model.
Group paraphrases, duplicated inputs, and related query templates in one split.
Use grouped uncertainty intervals and multiple seeds for shortlisted trained systems.
Choose stopping criteria on validation data, then freeze the final test evaluation.

The immediate deliverable should be a benchmark and baseline report.
Proceed to a method contribution only when the error analysis identifies a repeatable gap in existing approaches.

## Reading order and evidence limits

Read JoinGR, the corpus-adaptive embedding paper, REaR, and CORE-T first.
Then read Graph-Link, Guided Table Retrieval, and the semantic-layer papers for structural and business constraints.
Use BenchPress and SQUAB when writing the annotation protocol.

Publication status is deliberately mixed: official conference papers and clearly labeled preprints.
Some supporting works were screened only at abstract level, as recorded in the source inventory.
The search did not reproduce results or audit every released codebase.
It found no verified Ossie-specific retrieval benchmark within this targeted search; that is not evidence of absence.
Performance numbers from different papers must not be combined into a shared leaderboard.
