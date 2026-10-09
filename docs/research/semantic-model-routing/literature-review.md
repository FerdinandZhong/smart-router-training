# Literature and implementation review

Review date: 9 October 2026.
Scope: 2025–2026 literature on schema retrieval, semantic layers, clarification, and context selection.
This is a targeted review, not a systematic review or an exhaustive novelty determination.

The later [focused review](focused-literature-review.md) extends this search to trained graph traversal and whole-catalog table selection.
It identifies JoinGR, REaR, CORE-T, and corpus-adaptive schema embeddings as additional close baselines.
Use that review for the current novelty assessment and this document for the source implementation assessment.

## Finding

Training a small model to retrieve metadata is already an established research direction.
The strongest opportunity here concerns selecting sufficient semantic context under catalog change and a bounded context budget.
That opportunity needs direct comparison with recent retrieval and governance systems.

### Closest research

| Work and publication status | Relevant contribution | Implication for this project |
| --- | --- | --- |
| Eben, Ahmad, and Lau. **[RASL](https://arxiv.org/html/2507.23104)**, 2025. The paper reports acceptance at KDD's SKnowLLM workshop. | Indexes schema metadata as semantic units; combines question and keyword retrieval with table selection. | A close baseline for scalable metadata retrieval. “Retrieve semantics before SQL” cannot be our novelty claim. |
| Glass et al. **[Extractive Schema Linking for Text-to-SQL](https://arxiv.org/html/2501.17174)**, 2025 preprint. | Adapts decoder hidden states to predict schema-item relevance and column roles. It controls the precision–recall trade-off. | Encoder features with independent decision scores are a credible baseline, but the general architecture is established. |
| Wang, Liu, and Yang. **[LinkAlign](https://aclanthology.org/2025.emnlp-main.51/)**, EMNLP 2025. | Separates database retrieval from schema grounding; uses iterative retrieval and filtering. Introduces the synthetic AmbiDB benchmark. | Test catalog confusion and separate retrieval failures from downstream generation failures. |
| Shi et al. **[Gen-SQL](https://aclanthology.org/2025.coling-main.256/)**, COLING 2025. | Generates a pseudo-schema to bridge questions and embedding retrieval. | Compare direct question retrieval with query expansion; include expansion latency and model cost. |
| Wu, Wang, and Nguyen. **[Bi-SR](https://aclanthology.org/2026.findings-acl.369/)**, Findings ACL 2026. | Enriches schemas and queries, then trains a dense retriever with a contrastive objective. | A particularly close learned retrieval baseline. Training on richer descriptions is insufficient novelty by itself. |
| Chen, Sun, Pfister, and Arik. **[Learning to Clarify](https://proceedings.iclr.cc/paper_files/paper/2025/hash/4ffd05ca3cf3985f4572af015b4cfc1e-Abstract-Conference.html)**, ICLR 2025. | Learns dialogue actions through contrastive self-training; includes the AmbigSQL task. | Asking a clarification question is an established decision-learning task. Measure unnecessary questions as well as missed ambiguity. |
| Huo et al. **[BIRD-INTERACT](https://proceedings.iclr.cc/paper_files/paper/2026/hash/496b549556509bbb9770bf9d335c5800-Abstract-Conference.html)**, ICLR 2026; preprint in 2025. | Evaluates interactive database tasks with knowledge, user clarification, and executable checks. | Use interactive evaluation principles. A read-only subset cannot establish performance on the benchmark's full CRUD scope. |
| Kim, Khoeurn, and Yoon. **[A Semantic-Layer-Mediated Agent](https://arxiv.org/html/2606.31041)**, 2026 preprint. | Uses semantic models and a structured intermediate request with deterministic compilation. | Helios-style semantic compilation already has close research precedent. The paper also identifies semantic-layer overfitting as a concern. |
| Pillai. **[GROUND](https://arxiv.org/html/2608.26157)**, 2026 preprint. | Retrieves approved definitions and validates metrics, joins, grain, filters, access policy, and cost. | This is the closest governance overlap. Sufficient context plus validation alone is not a defensible novelty claim. |
| Liu et al. **[Database Context Compression](https://arxiv.org/abs/2606.28601)**, 2026 preprint. | Compresses schema and documentation through shared structural and semantic components. | Include a compression baseline. Smaller prompts do not necessarily require a learned selector. |
| Rumiantsau and Fokeev. **[Semantic Layers for Reliable LLM-Powered Data Analytics](https://arxiv.org/abs/2604.25149)**, 2026 preprint. | Compares schema-only and schema-plus-semantics conditions on 100 retail questions. | Supports testing business definitions directly. Its small, fixed semantic document does not establish large-catalog retrieval performance. |

GROUND's implementation supplies the full semantic layer in its prompt, according to Section 4.1.
Our assessment is that this leaves catalog-scale context selection unresolved.
Its comparison also changes policy information and retry access, which our selector comparison must hold constant. [Methods](https://arxiv.org/html/2608.26157).

SchemaRAG is an additional baseline lead from OpenAlex.
Its [author repository](https://github.com/chelsea2002/SchemaRAG) documents a trained SchemaLinker and schema-aware retrieval of SQL examples.
Example retrieval and semantic-definition retrieval must remain separate comparison dimensions.
The publisher endpoint returned HTTP 403, so this review does not rely on an inspected publisher full text.

TYTAN concerns constructing analytic semantic schemas with user clarification.
It is relevant to Helios authoring, but it addresses a different main task from catalog selection.
See the [2026 preprint](https://arxiv.org/abs/2608.06331).

Older systems such as [CHESS](https://arxiv.org/abs/2405.16755) provide background rather than new 2025-first-release evidence.
Publication dates, source access, and review depth are recorded in the [search record](search-record.md).

### What would and would not distinguish the work

| Proposed claim | Assessment | Evidence needed |
| --- | --- | --- |
| Search metadata before constructing an LLM prompt | Established by schema retrieval work | Engineering acceptance only |
| Train an encoder to score tables or models | Established by learned schema linking | Compare established retrieval objectives and strong backbones |
| Ground SQL in approved semantics with validation | Strong overlap with GROUND and semantic-layer-mediated agents | Keep the same validation layer across compared selectors |
| Use Ossie as the model representation | Useful interoperability choice | Format compatibility is not evidence of algorithmic novelty |
| Learn which compact context is sufficient across unseen models and changing releases | Plausible, narrower hypothesis | Generalization tests, equal budgets, independent semantic truth, and meaningful gains over close baselines |
| Build a benchmark exposing semantically similar but incompatible definitions | Potential dataset contribution | Independent expert labels, realistic domains, clear source rights, and tests that resist template memorization |

The most defensible initial story is a benchmark and empirical study.
A new objective or architecture should follow a measured failure that existing methods cannot resolve.
Any eventual priority claim requires another focused review after the method is concrete.

## Implementation assessment

The inspection used Helios revision `316f5d89926f96d366afaee641bd923af4ca6bf3` plus its local working tree.
The UOB folder was not a standalone Git repository.
The [source manifest](source-audit.json) records file hashes for both inspections.
These are source findings, not deployment or database acceptance results.

| Concern | Current Helios evidence | Current UOB banking path | Research or integration consequence |
| --- | --- | --- | --- |
| Full semantic context in every prompt | The documented conversation loop searches within a locked model before compilation. | `demo/app/planner.py:44` serializes the complete supplied model; line 46 enforces a 40,000-character limit. | Add retrieval across approved releases and bound the selected context. Do not attribute the demo behavior to every Helios path. |
| No metadata search | `apps/helios/mcp/server.py:197` scores lexical token overlap over one model. `search_semantics` enforces model-level semantic access. | `load_model()` loads a configured model ID and release; the banking planner lacks catalog retrieval. | Build a persistent candidate index and evaluate ranking quality. Existing model-level access does not prove field-level metadata filtering. |
| No indexing | The inspected search loops over in-memory definitions; other graph indexes serve different purposes. | `semantic_registry.sql` already defines a JSONB GIN index. | A registry index exists, but it does not establish semantic retrieval or ranking. Avoid a blanket “no indexes” claim. |
| Root credentials and absent permissions | `_authorize()` checks principal grants. `run_query()` checks physical resources. Impala delegation verifies the effective user. | `execute_trino()` uses the configured shared user. Verified caller identity is absent from this function. | Root/admin privileges remain unverified. Reuse policy concepts, then validate Trino identity enforcement separately. |
| Fragmented sessions | The conversation architecture specifies durable, model-scoped histories and revision traces. | The inspected orchestration builds request-local state; scoped conversation work remains planned. | Pin approved releases and explicit user choices. Do not mix conversation-local assumptions into global definitions. |
| Only data retrieval | Query compilation and execution form the structured-data foundation. | Computed observability analysis exists; a general analytics sandbox remains planned. | Keep prediction and general analytics as downstream extensions, outside the initial selector experiment. |

One additional boundary needs explicit handling.
Helios `ModelStore.sources()` can expose an unreviewed proposal when no published artifact exists.
The research catalog and serving adapter must accept approved releases only.
Do not inherit this fallback into the selector's publication contract.

The UOB `demo/HELIOS_HARDENING_PLAN.md` already proposes the required authorization and retrieval work.
Its older assessment paragraph references revision `83ac412`, while its update notes the later sync.
This review uses current source hashes and revision `316f5d8` rather than treating that historical paragraph as current evidence.

## Ossie and Atlas boundaries

The inspected Apache Ossie specification represents one semantic model per document.
It does not define core cross-model references or a bundle exchange format.
Its current development shape is flat and differs from earlier wrapped documents.
Pin the specification and compiler versions before implementing an adapter. [Official specification](https://github.com/apache/ossie/blob/main/core-spec/spec.md).

Store retrieval descriptors, dependency references, and catalog mappings beside approved Ossie documents.
Do not invent joins between separate models because their embeddings are similar.
Initially require one compilable approved model per execution.
Treat cross-model execution as a later capability requiring reviewed mappings and compiler support.

Atlas documents structured DSL, attribute filtering, and wildcard matching.
Its API also exposes full-text search.
The inspected documentation does not establish native embedding retrieval in the user's deployment.
Verify that capability separately instead of treating approximate text matching as vector search. [Advanced search](https://atlas.apache.org/2.0.0/Search-Advanced.html), [Discovery API](https://atlas.apache.org/api/v2/resource_DiscoveryREST.html).

Atlas can supply authoritative metadata and identifiers.
The approved semantic registry supplies business definitions and release identity.
A retrieval index connects these sources while preserving their provenance.
Database policy remains responsible for execution access.

## Review verdict

Proceed with a small benchmark and baseline study.
The integration need is supported by the source inspection.
The algorithmic contribution remains unproven.
The strongest test asks whether learned selection improves semantic sufficiency under equal budgets, across unseen catalogs and releases.
It must outperform the same deterministic dependency and policy checks attached to strong retrieval baselines.
