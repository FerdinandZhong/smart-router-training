# Search record and evidence limits

Search date: 9 October 2026. Language: English.
Workflow: `nature-academic-search` / `multi-source-search`.
Scope: 2025 onward, with older papers retained only as explicit background.

## Sources and method

Discovery used web search and the skill's OpenAlex fallback.
Claim verification used arXiv, ACL Anthology, ICLR proceedings, author repositories, and official Apache documentation.
Generic vendor articles and search-generated summaries were not used as technical evidence.
Academic MCP search tools were unavailable in this session.

Representative query families:

```text
schema retrieval text to SQL
semantic model retrieval semantic layer 2025 2026 paper
semantic layer retrieval benchmark 2026
large scale database schema routing trained retriever
AmbigSQL ICLR 2025 clarification paper
BIRD Interact 2025 benchmark clarification business intelligence text SQL
semantic routing Ossie paper
```

The final screening also used exact-title searches for RASL, ExSL, LinkAlign, Bi-SR, SchemaRAG, and GROUND.
The OpenAlex query returned 12 records before screening.
That is a discovery batch size, not a count of all literature screened.
Artifact versions and duplicate publisher records were not counted as separate research contributions.

Reproduction command for the OpenAlex discovery batch:

```sh
python /Users/zhongqishuai/.codex/skills/nature-academic-search/scripts/academic_search.py 'schema retrieval text to SQL' --year-from 2025 --limit 12 --compact
```

The first attempt failed because sandbox networking could not resolve the service.
The approved network retry succeeded.
OpenAlex ranking and coverage can change; rerunning this command need not return the same records.

## Verification depth

| Source | Review depth | Publication handling |
| --- | --- | --- |
| RASL, arXiv 2507.23104 | Full HTML methods and evaluation inspected | 2025 arXiv version; workshop acceptance stated in the paper |
| Extractive Schema Linking, arXiv 2501.17174 | Full HTML methods inspected | 2025 preprint; no peer-reviewed venue asserted |
| LinkAlign, ACL 2025.emnlp-main.51 | Anthology record and conference PDF inspected | EMNLP 2025 |
| Gen-SQL, ACL 2025.coling-main.256 | Anthology metadata and abstract inspected | COLING 2025 |
| Bi-SR, ACL 2026.findings-acl.369 | Anthology metadata and abstract inspected | Findings ACL 2026; PDF retrieval failed, so detailed reproduction choices remain open |
| Learning to Clarify | Official ICLR abstract and relevant PDF appendix inspected | ICLR 2025; AmbigSQL is a task within this paper |
| BIRD-INTERACT | Official ICLR abstract, arXiv record, and project page inspected | ICLR 2026; first arXiv version in 2025 |
| Semantic-Layer-Mediated Agent, arXiv 2606.31041 | Full HTML architecture and limitations inspected | 2026 preprint |
| GROUND, arXiv 2608.26157 | Full HTML framework and evaluation sections inspected; SSRN metadata checked | 2026 preprint; exact first-publication date is unresolved |
| Database Context Compression, arXiv 2606.28601 | Abstract and metadata inspected | 2026 preprint; no independent reproduction |
| Semantic Layers benchmark, arXiv 2604.25149 | Abstract and metadata inspected | 2026 preprint; HTML full text unavailable during the review |
| SchemaRAG, DOI 10.1145/3786696 | OpenAlex discovery and author repository inspected | Discovery reports PACMMOD 2026; publisher access returned HTTP 403 |
| TYTAN, arXiv 2608.06331 | Abstract and metadata inspected | 2026 preprint; contextual authoring work |

GROUND's arXiv identifier indicates an August series, while the displayed submission date says July.
SSRN reports an August posting and a July written date.
The review therefore cites only the year and does not resolve publication priority from those inconsistent day-level records.

The papers' numerical results were not reproduced.
Different generators, catalogs, annotations, and benchmark versions prevent direct ranking by their headline scores.
The proposed experiments control these factors instead.

## Local evidence and unresolved items

Source hashes are in [source-audit.json](source-audit.json).
Sibling source files were inspected read-only.
No runtime configuration, credentials, database grants, or live service enforcement were verified.
The current main router checkout was preserved rather than included in the research branch.

The supplied critique contains citation placeholders without source links.
It is treated as a set of hypotheses and requirements, not as authenticated quotations.
Atlas vector-search availability remains deployment-specific and unverified.
Apache Ossie's mutable development specification must be pinned before implementation.

Dataset licenses, access routes, and permitted redistribution must be checked before importing any external benchmark.
This task downloaded no training dataset and made no claim that a public benchmark contains approved Ossie models.
Any conversion would require separate semantic annotation and provenance.

This search establishes substantial prior overlap.
It does not establish the absence of other work on complete-context selection, semantic constraints, or catalog evolution.

## Focused review addendum

Date: 9 October 2026. Requested skill: `nature-academic-search`.
Workflow: `multi-source-search`, using the skill's OpenAlex fallback and primary-source web verification.
Output: [focused review](focused-literature-review.md) and [selected source inventory](focused-sources.json).

This pass focuses on the user's revised problem: Ossie-aligned retrieval across a large, append-only enterprise catalog.
Its main comparison is keyword plus embedding search, with strong trained and graph baselines added after discovery.
A new cost-aware loss is outside the revised study scope.

### Sources and query families

The skill preflight succeeded for PubMed, CrossRef, and arXiv.
Academic MCP search tools were unavailable in this session.
PubMed was not queried because the topic concerns computer science.
OpenAlex discovery used:

```text
python /Users/zhongqishuai/.codex/skills/nature-academic-search/scripts/academic_search.py \
  'schema retrieval text to SQL' --year-from 2025 --limit 12 --compact
```

The command returned 12 records.
They included SchemaRAG, RASL, Rethinking Schema Linking, and two distinct GRASP-named works.
Discovery also returned an artifact record, a talk record, and uncertain duplicate publication records.
Those records were not treated as independent validated method papers.
The 23-work selected inventory is not a search-hit count or a PRISMA screening total.

Web discovery and citation following covered these topic families:

```text
schema retrieval / schema linking / corpus-adaptive embeddings
table retrieval / join-aware retrieval / learned graph traversal
semantic data lakes / enterprise metadata search / large catalogs
ambiguous and unanswerable questions / robust schema linking
semantic-layer retrieval / context compression / changing schemas
```

Additional exact verification queries included:

```text
"Can We Retrieve Everything All at Once" ARM 2025 ACL
"REaR" "Retrieve, Expand and Refine" 2026 venue
"Ossie" "semantic" retrieval paper
"semantic layer" "retrieval" "benchmark" 2025 2026
"schema retrieval" "evolution" "2025"
"table retrieval" "incremental" "2026"
```

JoinGR's bibliography led to REaR, ARM, CORE-T, and the human-guided schema-graph paper.
Primary verification used arXiv, ACL Anthology, PMLR, OpenProceedings, CIDR proceedings, and author project pages.
Ossie structure was checked against its official Apache repository.
Vendor blogs and secondary summaries were not used to establish algorithmic claims or numerical results.
Generic GraphRAG and document-memory results were excluded when their retrieval unit or task did not match.

### Deduplication and dates

Merge preprints and conference papers as one work.
Prefer DOI or arXiv identifiers, then normalized title and author identity.
REaR is one work: November 2025 preprint and ACL 2026 publication.
SchemaGraphSQL is one work: May 2025 preprint and Findings EACL 2026 publication.
BenchPress is one work: October 2025 preprint and CIDR 2026 publication.
CORE-T remains labeled a preprint; an author repository name does not verify conference acceptance.
BEAVER is explicitly marked as an older benchmark, first posted in 2024.
DBCopilot is included by its EDBT 2025 publication, without claiming its first public release occurred in 2025.

Do not mix benchmark versions when interpreting scale.
For example, JoinGR's BEAVER-DW subset contains 97 tables and 121 questions.
Other reviewed papers use a larger multi-database BEAVER subset.
The current BEAVER project describes a further expanded corpus.
These are different evaluation pools, not contradictory scores on one frozen dataset.

### Reading depth and access limits

The source inventory distinguishes inspected methods from abstract-only screening.
The deepest additional reading covered JoinGR, corpus-adaptive schema embeddings, REaR, CORE-T, Guided Table Retrieval, and Graph-Link.
DBCopilot and the human-guided graph paper received targeted method and limitation checks.
Supporting robustness works were screened at abstract level; this is not described as full-paper review.

Local PDF extraction for DBCopilot and the human-guided graph paper returned mostly page numbers.
Web PDF extraction supplied the relevant primary text instead.
Graph-Link's author PDF provided readable methods and limitations through local extraction.
An ARM metadata-page open and a CORE-T citation-link click failed; the official ARM PDF and author repository supplied the evidence.
A CIDR BenchPress landing page failed; the official conference PDF and arXiv record were available.
Earlier publisher access restrictions for SchemaRAG and full-text limits for Bi-SR remain documented above.

No verified Ossie-specific retrieval benchmark was identified in this targeted pass.
That result does not establish that such work is absent.
The reviewed methods already cover coherent table sets, cross-domain transfer, and incremental index design.
Our proposed contribution therefore requires measured business-semantic completeness and temporal evaluation, not merely a new format or graph component.
