# Search record — 21 October 2026

Scope: metadata-only semantic-context retrieval within one customer domain, with cross-domain training and evaluation.
This is a targeted literature review, not an exhaustive systematic review.
The main period is 2025 onward. Older datasets remain relevant training sources.

## Search workflow

1. Read the nature-academic-search multi-source workflow and tool guidance.
2. Check available tools. The dedicated academic-search MCP was unavailable.
3. Run endpoint preflight. Sandbox DNS failed; the authorized retry passed PubMed, CrossRef and arXiv checks.
4. Run the academic_search.py fallback for `schema retrieval text to SQL`, year-from 2025, limit 8. OpenAlex returned HTTP 429.
5. Continue through web search and primary publisher, author, repository and dataset pages.
6. Deduplicate conference and preprint versions by title and identifier.
7. Verify selected repository HEAD commits through GitHub API. Read Wren architecture at its recorded commit.

## Executed query families

- `2025 2026 schema retrieval text to SQL REaR CORE-T JoinGR`
- `2025 2026 semantic layer benchmark GROUND text SQL business metadata retrieval`
- `2025 enterprise text SQL schema retrieval benchmark Spider 2.0 BIRD schema linking`
- `"Finding the Right Tables and Columns" github`
- `"REaR" "Retrieve" "Expand" github`
- `"REaR" "2511.00805" code`
- `"REaR: Retrieve, Expand" code repository`
- `"GROUND" "semantic" benchmark SQL 2026 github`
- `"GROUND" "Text-to-SQL" benchmark semantic layer`
- `"BEAVER" text sql benchmark dataset github 2025`
- `"LiveSQLBench" dataset license`
- `"AutoLink" "schema" github`
- `WrenAI schema retrieval semantic layer MDL github pipeline`
- `Snowflake Cortex Analyst semantic views semantic model retrieval metadata documentation`
- `2025 Qwen3 embedding reranker technical report github`
- `"Text-to-SQL Benchmarks are Broken" CIDR 2026 github`
- `"BIRD-Ent" "Spider-Ent" github`
- `2025 2026 text SQL ambiguous clarification benchmark metadata AmbiSQL CLARITY`
- `EntSQL benchmark dataset GitHub 2026`
- `2025 schema retrieval late interaction ColBERT text SQL`

## Evidence rules and limitations

Use primary papers, official proceedings, author repositories, official dataset cards and product documentation.
Exclude social posts and secondary summaries from technical evidence.
Separate released code, documented architecture and reproduced results. No implementation was run for this review.
No dataset was acquired and no access-request email was sent.
No citation-count ranking or formal screening count was produced.
The DRAG OpenReview page presented a browser challenge. Its artifact and publication status remain unverified.
A pinned raw Wren web fetch failed; the GitHub API returned the architecture document at the recorded commit.
Repository names alone do not establish conference acceptance.
LiveSQLBench license statements conflict; GROUND reuse terms remain unresolved.

See [review](domain-scoped-review-20261021.md) and [source manifest](domain-scoped-sources-20261021.json).
