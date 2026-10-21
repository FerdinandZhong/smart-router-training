# Research side plan: selecting semantic context for lakehouse questions

Current implementation and review status: [21 October branch record](branch-record-20261021.md).
The dated sections below retain earlier research milestones.

Reviewed: 10 October 2026. Status: balanced pilot review package, review/export tools,
CPU retrieval diagnostics and an embedding training script; no reviewed semantic training results.

The current execution proposal is the [bilingual research plan](research-plan-bilingual.md).
Read the [plan audit](plan-audit-bilingual.md), [collection protocol](data-collection-bilingual.md),
and [data availability plan](data-availability-bilingual.md) before collecting or approving semantic labels.
The [earlier Chinese plan](research-plan-zh.md) remains as background for the initial design.
It prioritizes Ossie document retrieval without graph retrieval, trained embeddings, optional reranking, and low total latency.
Its staged schedule and evaluation boundaries supersede earlier requirements to train graph scorers.

Public-source intake is now implemented in this research branch.
It prepares 13,601 unreviewed source records, 209 structural Ossie drafts, and a 240-record review queue.
The 1,259 dataset objects have passed pinned JSON Schema validation, not semantic or SQL execution validation.
No reviewed semantic training release or semantic model training result exists yet.

The [pilot readiness audit and runbook](pilot-readiness-bilingual.md) records the
latest changes. Use `pilot-20261010-v3`, with 240 balanced episodes and a 197/43
grouped internal train/development reservation. It searches 702 tables from 112
training-reserved catalogs. All labels remain pending. `baselines-20261010-v3`
contains current BM25/dense/untuned-hybrid diagnostics with complete token-window
encoding. Training optimization has only been tested on an invented CPU fixture.

Branch: `research/semantic-model-routing`.
Base: `2b7eecf37d0053951576bca654f6efd204e07950`.
The original checkout remains on `main`, with its unfinished router work preserved.

## Recommendation

The [2026-10-10 hybrid retrieval verification](hybrid-retrieval-verification-20261010.md)
defines the established BM25/dense baseline, primary sources and cluster audit scope.

Explore this direction through a bounded benchmark first.
The engineering need is concrete, and the existing router training infrastructure can support the experiment.
However, generic learned schema retrieval already has substantial prior work.
Research novelty remains conditional on a more specific result.

**Working question:** Can learned retrieval select complete, consistent business context from a growing Ossie catalog within fixed token and latency budgets?

A **semantic bundle** means selected definitions plus their required dependencies.
These include metric expressions, filters, aggregation grain, units, time rules, and approved relationships.
The term describes our retrieval output, not a new Apache Ossie document format.

The proposed distinction is between *relevant* context and *sufficient* context.
Finding a payments table can be relevant while omitting settlement rules, currency conversion, or the correct reporting date.
A useful selector must support clarification or abstention when the available definitions cannot determine the intended calculation.

This is a proposed contribution, not a claim of priority.
The [focused literature review](focused-literature-review.md) identifies close prior work in trained retrieval and graph traversal.
JoinGR already learns query-conditioned traversal; REaR and CORE-T already select relationally coherent table sets.
GROUND already addresses governed business definitions.
The hypothesis now requires business-definition completeness, equal-budget comparisons, and chronological new-table evaluation.
The earlier [literature and implementation review](literature-review.md) retains the local source assessment.

## What the code inspection changed

The current Helios checkout already implements model-scoped lexical search, authorization checks, and delegated Impala execution.
Its search path does not establish a persistent, learned index across many approved model releases.
Code presence also does not establish live database enforcement.

The UOB banking path has a more immediate gap.
It loads one approved release and serializes the complete document into the planning context.
It rejects context above 40,000 characters.
Its direct Trino connection uses configured shared credentials without verified caller delegation.
Its existing hardening plan already proposes authorization, bounded retrieval, and scoped conversations.

Yan's concerns therefore motivate useful tests, but several claims need different attribution for Helios and the UOB integration.
Root-level database grants were not inspected.
The supplied citation placeholders do not establish independently verified meeting quotations.
See the [implementation assessment](literature-review.md#implementation-assessment) and [source manifest](source-audit.json).

## Proposed flow

```text
Approved Ossie releases + catalog metadata
                    |
       versioned lexical / vector indexes
                    |
Question + confirmed history + verified caller
                    |
       permission-filtered candidate retrieval
                    |
          optional learned candidate scorer
                    |
       declared-dependency lookup + budget checks
                    |
          proceed / clarify / abstain
                    |
       typed plan -> Helios compilation
                    |
      database authorization -> results -> analysis
```

Authorization remains deterministic at retrieval and execution boundaries.
Model confidence cannot grant access.
Conversation state references immutable releases and explicit user choices.
It does not merge unreviewed definitions from unrelated sessions.

## Relationship to the current router

| Aspect | Current LLM router | Proposed semantic selector |
| --- | --- | --- |
| Decision | Which execution model can handle this state? | Which definitions can support this question? |
| Candidate | Configured model or route | Model release, metric, or semantic bundle descriptor |
| Structure | Encoder plus independent decision scores | Reuse encoders; score question–candidate pairs |
| Trade-off | Response quality versus execution cost | Semantic sufficiency versus retrieval cost and context size |
| Main failure | Choosing an unsuitable or expensive route | Missing a required definition or selecting incompatible definitions |
| Unknown target | Masked observation | Unreviewed candidate suitability remains masked |

Laya and GLiNER2.5-Decide are candidate backbones, not proven winners for this task.
Their existing routing labels do not transfer to semantic retrieval.
A dynamic catalog requires candidate-conditioned scoring rather than a fixed output class for every model ID.
The [experiment plan](experiment-plan.md) describes the required adapter and controls.
The [Chinese training and experiment brief](training-and-experiments-zh.md) explains their role as rerankers after hybrid retrieval.
It also separates frozen-encoder trials from encoder adaptation and records the required input-budget checks.

## First decision gate

1. Define the semantic bundle contract and an independent annotation rubric.
2. Build a small reviewed benchmark with realistic ambiguity and conflicting definitions.
3. Measure tuned hybrid search, trained embeddings, and deterministic dependency assembly with shared source evidence.
4. Compare optional candidate scorers, using standard objectives and frozen-weight evaluation after table additions.
5. Continue only if learning improves completeness or latency beyond strong retrieval and better metadata.

Graph methods remain related work rather than mandatory implementation for this phase.
Measure context preparation separately from SQL generation, execution, and the final answer.
The initial 500 ms context p95 target is unmeasured and subject to a declared serving load.

A new cost-aware loss is outside this study's current scope.
If the strongest baseline already meets the requirements, retain the engineering improvement and revise the research claim.

Read the [experiment plan](experiment-plan.md), [search record](search-record.md), and [return handoff](return-to-main.md) for execution details.
