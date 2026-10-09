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
