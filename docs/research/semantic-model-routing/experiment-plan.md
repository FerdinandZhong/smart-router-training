# Experiment plan: sufficient semantic context under a fixed budget

Status: proposed. All dataset sizes, thresholds, and latency budgets below are planning values, not measured results.

Scope update, 10 October 2026: the [current execution proposal](research-plan-zh.md) prioritizes no-graph Ossie retrieval and low total latency.
Its schedule, decision gates, and latency protocol take precedence over earlier planning values here.
Graph methods are related work or optional later comparisons, not required training components.

Updated after the [focused literature review](focused-literature-review.md) on 9 October 2026.
The primary catalog-change protocol now covers table additions, following the user's deployment description.
Standard training objectives remain sufficient for the initial study; a new cost-aware loss is outside scope.

The [Chinese execution plan](training-and-experiments-zh.md) specifies the training stages and the roles of GLiNER2.5-Decide and Laya.
Its [model evidence](model-evidence.json) distinguishes pinned upstream behavior from our current routing adapters.

## Research questions

1. Does candidate-conditioned learning improve complete semantic coverage beyond strong lexical, dense, and hybrid retrieval?
2. Does it distinguish similar definitions that differ in filters, grain, units, time rules, or release applicability?
3. Does it generalize to unseen models and reduce unnecessary clarification while preserving answer correctness?
4. Does any gain survive equal token budgets and the full cost of retrieval, expansion, and clarification?

The primary comparison isolates selection quality.
Every comparable system receives the same approved catalog, permissions, relationship evidence, compiler, and downstream generator.
Scorer comparisons hold dependency assembly constant; separate ablations vary declared-dependency lookup explicitly.
The final generator remains fixed throughout a comparison.

## System and training contract

### Input and output

Each decision starts with the question and its recorded, confirmed conversation prefix.
Available inputs also include the catalog snapshot, release hashes, and descriptions the caller can access.
Authorization produces the eligible candidate set before learned scoring.
The model never predicts whether the caller deserves access.

A candidate descriptor contains its scoped ID, description, aliases, applicability, and material semantic constraints.
Include explicit inclusions and exclusions when the approved model supplies them.
Use stable references for expressions and declared dependency lists that remain server-side.
Do not silently truncate a defining exclusion or time rule to fit the encoder.
Record descriptor omissions and route unsupported cases to clarification or abstention.

The output contains ranked candidate references, selected definition references, release hashes, and a decision.
The decision is `proceed`, `clarify`, or `abstain`.
Deterministic checks validate dependency closure, release compatibility, permissions, and the context budget before proceeding.
Multiple relevant candidates and multiple acceptable complete bundles are allowed.
Relevance alone does not imply that a candidate can support execution.

Start with selection inside one compilable release, after retrieval across model releases.
Multiple selected models may represent alternatives requiring clarification.
They do not authorize unsupported cross-model joins.

### Index and scorer

```text
Offline: approved releases -> typed descriptors -> lexical / dense index
Online:  question + history + caller
                    |
            permitted candidates, K
                    |
        question-candidate scoring, batched
                    |
        select definitions and dependencies
                    |
        check sufficiency / budget / policy
                    |
       clarify <-> confirmed user choice
                    |
        typed request -> compile -> execute
```

Start candidate retrieval with BM25, a dense retriever, and reciprocal-rank fusion.
Tune the hybrid baseline on development data and add a generic reranker.
Include corpus-adaptive embedding training and a documented REaR-style retrieval/refinement comparison from the focused review.
Do not infer valid joins from lineage or similarity; the main method uses approved declared references.
Benchmark model summaries and individual metric or dataset descriptors.
Retrieve both granularities so an inaccurate model summary cannot always hide a relevant metric.
Candidate recall sets the ceiling for reranking quality.
Report this ceiling separately rather than blaming the scorer for missing candidates.

Evaluate Laya and GLiNER2.5-Decide as candidate scoring backbones alongside a conventional cross-encoder.
Use an indexable dual encoder for first-stage retrieval; no independent vector-index interface was verified for the current decision-model adapters.
Prototype `score(question, confirmed_history, candidate_descriptor)` with shared weights across candidate IDs.
Avoid one fixed output class per catalog model.
New approved models should become searchable through indexing without mandatory classifier-head expansion.
This interface property does not establish accuracy on new business definitions.

The main reranker comparison uses independent question-candidate pairs from the same frozen candidate pool.
Place material business definitions in the candidate body, not long option labels.
Pinned Laya source caps individual option descriptions at 48 tokens and separately truncates the instruction block.
Audit the actual token view and test essential clauses at different positions.
Use the same evidence across models; report a separate condition when longer supported views change evidence access.
A GLiNER candidate-group mode is an optional ablation with group-size and candidate-order tests.

Start with masked binary relevance labels and standard ranking comparisons.
Treat conflict and completeness annotations as evaluation labels first.
Independent relevance scores cannot certify that a set of candidates is jointly sufficient.
Consider a set-level verifier only after measuring residual errors from candidate scoring plus dependency expansion.

Candidate-conditioned records and collation require a new adapter.
Reuse provenance, grouped splits, masks, training telemetry, and distributed execution where their contracts match.
The existing pre-call projection principle still applies; add an explicit projection for this task.
Gold SQL, answers, reviewer reasons, and post-execution evidence remain outside model inputs.

Existing routing targets do not provide semantic-retrieval supervision.
Start primary comparisons from the original checkpoints; old routing-tuned weights are an optional transfer ablation.
The inspected Laya adapter freezes its encoder; the GLiNER adapter trains only its classifier.
Compare original models, frozen-encoder adaptation, and encoder-updating adaptation before making backbone claims.
The existing adapters block encoder gradients and therefore require implementation changes for the last condition.
Report trainable parameter counts because the two output modules have different capacities.
If a decision model wins, add a matched base-encoder/task-head control to investigate the source of the gain.

The branch base contains the committed Laya implementation.
The current GLiNER comparison code remains unfinished work in the original checkout.
Integrate a reviewed commit later; do not assume those uncommitted files exist on this branch.

### State and authorization

Index only approved releases and retain each source hash.
Use caller scope and policy revision to partition or filter retrieval.
Revalidate expanded dependencies before exposing context to a model or browser.
Reject expired or revoked releases and permissions on every new turn.
Scope caches by authorization context, policy revision, catalog snapshot, and selected releases.
Do not expose restricted candidate names through scores, clarification choices, logs, or cached responses.

Store conversation-local choices separately from shared business definitions.
A confirmation such as “use net revenue” applies to its recorded context.
It does not silently change the organization's canonical revenue definition.
Use one catalog snapshot per decision and record any explicit migration between releases.

The UOB identity and retrieval milestones remain prerequisite integration work.
Offline policy fixtures can test application behavior before that work completes.
They cannot establish live Trino row or column enforcement.

## Dataset plan

### Small reviewed pilot

Begin with **240 independent question episodes across at least six semantic families**.
This size supports rubric development and initial learning curves, not a strong generalization claim.
Use at least three independently designed domain catalogs before making cross-domain claims.
Allocate whole families or catalogs to development, calibration, and final evaluation according to available independent groups.
Do not force a percentage split that leaves too few groups for meaningful evaluation.

The UOB financial fixture supplies useful deterministic examples and result checks.
Its six tables alone cannot establish performance on enterprise catalogs.
Add other independently reviewed domains before presenting a general retrieval result.

| Question family | Required distinction |
| --- | --- |
| Direct metric lookup | Correct published metric and required filters |
| Business synonyms | Familiar business words versus physical schema names |
| Similar but incompatible definitions | Gross versus net; booked versus settled; UTC versus local reporting date |
| Composition within an approved model | Required dimensions, join keys, relationship direction, and aggregation grain |
| Ambiguous request | Two legitimate interpretations and the discriminating clarification |
| Unsupported or incomplete semantics | No approved definition, missing dependency, or unavailable release |

Do not treat permission denial as an ordinary relevance negative.
Test denied resources separately through deterministic policy fixtures.
Use those fixtures to confirm restricted metadata never enters the scorer or prompt.

Keep a natural question set and a deliberately difficult challenge set separate.
Do not present performance on balanced synthetic examples as production prevalence.
After the pilot, expand toward **1,000–2,000 reviewed episodes** only when the rubric and baseline errors justify the expense.
Retain a fresh test set that was not used to author the semantic models.

### Annotation and evidence

1. Freeze approved definitions before annotating final evaluation questions.
2. Ask an independent reviewer to specify intent, required definitions, and acceptable alternative bundles.
3. Record ambiguity branches, required user choices, and unsupported cases.
4. Validate typed semantic plans and results against independent reference logic where execution is available.
5. Adjudicate disagreements; preserve unresolved labels as unknown.
6. Record reviewer identity, provenance, source rights, versions, and checksums in the manifest.

SQL dependency extraction can supply weak labels for table and column relevance.
It cannot establish whether the business interpretation is correct.
A reference query generated by the same compiler is insufficient independent truth.
Use separate reference logic and data cases that expose returns, fanout, date boundaries, nulls, and currency conversion.
Compilation success and one matching result table do not prove semantic correctness.

Generate training negatives from actual retrieval candidates, including highly similar business definitions.
Only reviewed irrelevant or conflicting candidates receive negative labels.
Unjudged candidates remain masked.
Distinguish organic retrieval errors from injected challenge negatives in reports.
Keep question paraphrases, derived templates, duplicate descriptors, and related issue episodes in one split.

### Generalization and scale

Use separate evaluation protocols for unseen model families and temporal release changes.
For the unseen-family protocol, group all related releases and templates together.
For the temporal protocol, train on earlier releases and evaluate later changes explicitly.
Do not describe temporal reuse of a known family as unseen-family generalization.

Test catalog scale at approximately **100, 1,000, and 10,000 tables**, when real catalog diversity supports those sizes.
Separately report model, definition, column, and relationship counts.
Add realistic confusable distractors as well as irrelevant distractors.
Duplicated or renamed fixtures can support load tests but cannot establish semantic diversity.
Measure indexing time, storage, update cost, and old-query regression after additions.
Deletion and revocation tests remain integration checks outside the primary append-only research protocol.

Evaluate known-database and pooled-catalog retrieval separately.
Do not supply an oracle database ID in the main enterprise comparison.
Freeze weights after training on snapshot C0, then index new tables from C1 and C2.
Keep new-table synthetic training questions and future query logs outside C0 training.
Measure questions requiring new tables and existing questions that gain confusing alternatives.
Report retraining on the expanded catalog as a separate adaptation condition.
If historical snapshots are unavailable, label staged arrivals as simulated rather than prospective evidence.

Give all comparable methods the same metadata and row-sample access.
CORE-T and several other methods use value evidence; label metadata-only versions as adaptations.
Separate local summarization from retrieval so summary omissions do not become hidden selection failures.
Preserve exact expressions and mandatory rules alongside a generated summary.

## Experiment sequence

| Stage | Comparison | Decision it supports |
| --- | --- | --- |
| E0: truth and oracle | Gold sufficient context versus retrieved context; full permitted context only when feasible | Whether catalog quality and generator capability support the task |
| E1: retrieval | Existing Helios lexical behavior, BM25, dense, hybrid, query expansion, and a RASL-style baseline | Whether simple indexing already resolves the problem |
| E2: learned selection | Generic reranker, corpus-adaptive embeddings, Bi-SR-style retrieval, ExSL-style scoring, Laya, and GLiNER2.5-Decide | Whether training and backbone choice improve selection |
| E3: completeness | No assembly versus declared-dependency assembly; flat table documents versus typed semantic units; a clearly labeled REaR-style adaptation | Whether learning adds value beyond metadata representation and deterministic assembly |
| E4: context policy | Fixed top-K, token-budgeted selection, compression, and calibrated proceed/clarify/abstain | Whether selection improves the useful-context versus cost trade-off |
| E5: transfer | Unseen catalog families, chronological table additions with frozen weights, natural paraphrases, and larger distractor pools | Whether gains survive realistic changes |

Label simplified implementations as adaptations, not exact paper reproductions.
Use authors' code where compatible and record differences in metadata, training data, and retrieval budgets.
Include governed validation for every comparable baseline, following the concern exposed by GROUND.
Its benefits must not be attributed to our learned selector.

For trained comparisons, start with standard masked BCE and a conventional ranking objective.
Choose hyperparameters using development data and thresholds using calibration data.
Freeze the test set until the comparison is selected.
Use at least three seeds for shortlisted learned systems and report grouped uncertainty intervals.
Do not repeatedly inspect the test set to choose epochs.

Report both training-epoch counts and optimization steps.
Use validation-based stopping rather than assuming that ten epochs is optimal for this new task.
Separate selector training expense from offline indexing and per-request serving expense.

## Metrics and decision criteria

| Layer | Required measurements |
| --- | --- |
| Retrieval | Recall@K for required definitions; fraction of answerable questions with a complete acceptable bundle available |
| Selection | Required-definition precision and recall; complete-bundle accuracy; incompatible-definition rate |
| Decision | Proceed/clarify/abstain confusion matrix; unnecessary clarification; unsafe proceeding on ambiguous questions; risk versus coverage |
| Probability | Calibration on reviewed labels; Brier score or log loss; threshold sensitivity |
| End-to-end | Correct business interpretation and checked results; execution success reported separately |
| Efficiency | Context tokens; warm and cold p50/p95 latency; request throughput; total model calls and cost |
| Integrity | Restricted-context leakage, stale-release use, unauthorized execution attempts, and revocation behavior |

**Complete-bundle accuracy** applies to answerable, disambiguated questions.
A selected bundle passes when it contains a reviewed sufficient set, includes required dependencies, and introduces no incompatible definition.
Extra permitted, compatible context affects precision and cost rather than automatically invalidating the bundle.
Unanswerable and ambiguous questions use the decision metrics instead.

Publish both micro results and macro results across independent families.
Report denominators and uncertainty, especially for rare ambiguity and permission cases.
Bootstrap whole episodes or families as appropriate; candidate pairs are not independent experimental units.

Compare systems at fixed **2K, 4K, and 8K semantic-context token budgets**, subject to the selected generator's capacity.
Keep encoder descriptor length and generator context budget separate.
Count closure expansion inside the semantic budget and report the complete prompt size separately.
If required context exceeds the budget, record an unsupported case or an explicit additional retrieval step.
Never trim mandatory definitions merely to meet the budget.

The UOB plan's warm p95 below 500 ms and 95% definition recall are engineering targets, not current measurements.
Evaluate them alongside complete-bundle recall; average definition recall can hide one missing dependency per question.
Include query-expansion calls, reranking, dependency assembly, and clarification in the appropriate latency and cost totals.

Continue the learning research only if the shortlisted model improves complete-bundle accuracy at a matched budget.
Require consistent gains across independent families and no unexplained decline in end-to-end semantic correctness.
Alternatively, demonstrate lower serving cost or latency at comparable quality.
Predeclare a practical improvement threshold after the pilot estimates baseline variance and deployment needs.

Zero observed policy violations is a release gate for tested cases, not a universal security guarantee.
Any observed leak blocks integration until fixed.
Permissions remain hard constraints in every experiment.

## Standard objectives and error analysis

First classify the residual errors: retrieval omission, missing semantics, ranking confusion, incomplete assembly, calibration, or generation.
A new loss cannot repair missing business definitions or an unenforced execution identity.

Use standard multi-positive ranking and masked relevance objectives for the first comparisons.
If relevant candidates remain jointly insufficient, evaluate dependency assembly and set-level selection.
Keep a new cost-aware loss outside the current research scope.
Keep access rules and mandatory semantic dependencies as hard checks.
Report gains at equal budgets, with ablations and independent test questions.

## Deliverables and integration boundary

1. Produce a versioned catalog export, descriptor schema, annotation rubric, and source-use manifest.
2. Release an offline retrieval harness with oracle and deterministic baselines.
3. Add candidate-conditioned adapters and train shortlisted models on the existing cluster when this phase is authorized.
4. Produce a comparative report with semantic accuracy, calibration, latency, cost, and failure cases.
5. Integrate the selected method into UOB's existing hardening milestones after their identity boundary is verified.

This side plan does not change the active router dataset, launch training, or modify either sibling implementation.
General analytics and prediction remain downstream work after reliable semantic selection and authorized execution.
