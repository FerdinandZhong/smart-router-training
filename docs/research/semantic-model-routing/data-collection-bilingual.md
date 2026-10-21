# 训练数据收集与审核协议 / Training Data Collection and Review Protocol

日期 / Date：2026-10-10。当前阶段 / Current stage：平衡 pilot 审核准备 / Balanced pilot review preparation。
主方案 / Master plan：[研究计划 / Research plan](research-plan-bilingual.md)。

## 1. 当前已有材料 / Material prepared

| 产物 / Artifact | 已核验数量 / Verified count | 含义 / Meaning |
| --- | --- | --- |
| Spider upstream train | 7,000 问题，140 数据库 / questions, databases | 固定官方代码库快照中的训练注释 / Training annotations from a pinned official repository snapshot |
| BIRD filtered train | 6,601 问题，69 数据库 / questions, databases | 官方筛选训练集 / Publisher-filtered training set |
| Ossie 草稿 / Drafts | 209 文档，1,259 数据集对象 / documents, dataset objects | schema／字段说明转换；不是人工批准的语义模型 / Schema or column-description conversion, not approved semantic models |
| Pilot 审核队列 / Review queue | 240；每来源 120 / 120 per source | 已按结构平衡重采样；见 pilot-v3 / Resampled with structural balance; see pilot-v3 |
| 已审核／可训练 / Reviewed / trainable | 0 / 0 | 不能将导入成功称为训练数据完成 / Successful import is not training readiness |
| 隔离字段 / Quarantined fields | 1 | BIRD 的一个字段标识缺少列名 / One BIRD column identifier has an empty column name |

来源导入入口为 `data/semantic-research/intake-20261010-v3/`。
实际审核使用 `data/semantic-research/pilot-20261010-v3/`，详见[审核与训练准备协议](pilot-readiness-bilingual.md)。
早期本地 v1/v2 仅为构建中间产物，不使用其审核队列。
上述材料未下载物理数据库行，也未执行 SQL。

Use `data/semantic-research/intake-20261010-v3/` as the current source intake.
Use `data/semantic-research/pilot-20261010-v3/` for actual review; see the [pilot protocol](pilot-readiness-bilingual.md).
The earlier local v1/v2 directories are intermediate builds; do not use their review queues.
No physical database rows were downloaded and no SQL was executed.

## 2. 获取与复现 / Acquisition and reproduction

来源清单：[sources.json](../../../configs/semantic_retrieval/sources.json)。所有下载文件均固定版本、字节数和 SHA-256。
工具拒绝哈希不符的内容，并要求为每次构建使用新目录。
需要 Python 3.10+ 和 `jsonschema`；可使用项目的 `annotation` 依赖组。

The [registry](../../../configs/semantic_retrieval/sources.json) pins source revisions, byte counts, and SHA-256 hashes.
The tool rejects mismatched files and requires a new directory for each build.
Use Python 3.10+ and `jsonschema`, available through the project's `annotation` extra.

```bash
python scripts/prepare_semantic_intake.py fetch \
  --registry configs/semantic_retrieval/sources.json \
  --raw-dir data/semantic-research/raw-20261010

python scripts/prepare_semantic_intake.py build \
  --registry configs/semantic_retrieval/sources.json \
  --raw-dir data/semantic-research/raw-20261010 \
  --output data/semantic-research/intake-reproduction-v1

env PYTHONPATH=src python -m unittest discover -s tests -p test_semantic_intake.py -v
```

原始数据和生成目录被 Git 忽略。代码、来源注册表和不含原始问题的状态报告进入研究分支。
正式发布前再确定派生数据许可、署名和长期存储位置。

Raw files and generated directories are ignored by Git. Code, the source registry, and aggregate status evidence are tracked on the research branch.
Confirm derivative-data terms, attribution, and archival location before publication.

## 3. 三种证据轨道 / Three evidence tracks

| 轨道 / Track | 生成方式 / Construction | 可支持的结论 / Supported conclusions |
| --- | --- | --- |
| A：结构转换 / Structural conversion | schema、键、独立字段说明 → Ossie；原始 SQL → 弱监督 / Schemas, keys, independent descriptions to Ossie; SQL to weak labels | 结构召回与表集合覆盖 / Structural retrieval and table coverage |
| B：语义扩充 / Semantic enrichment | 先定义并审核指标口径，再写问题与参考计算 / Review definitions before authoring questions and reference calculations | 在已审核扩充场景下的业务语义完整性 / Business completeness in explicitly enriched scenarios |
| C：外部验证 / External validation | 后续企业样本或保留的复杂语义基准 / Later enterprise examples or held-out semantic benchmarks | 外部有效性；不能用 A/B 结果代替 / External validity not established by A/B alone |

Track A 不自动生成净收入、退款规则或业务指标。名称展开和字段说明仅保留其来源证据等级。
Track B 的假设规则标记为 `synthetic_defined`；来源文档支持的规则标记为 `source_documented`。
LLM 草稿标记为 `generated_unreviewed`，人工批准后仍保留生成来源。

Track A does not invent net-revenue definitions, refund policies, or business metrics. Name expansion and descriptions retain their source evidence level.
Label stipulated Track B rules `synthetic_defined` and documented rules `source_documented`.
Label LLM drafts `generated_unreviewed`; preserve generation provenance after human approval.

## 4. 转换与泄漏边界 / Conversion and leakage boundaries

1. 固定原始文件和来源许可记录。/ Pin source files and record their declared terms.
2. 先建立数据库、schema 别名及重复输入分组。/ Group databases, schema aliases, and duplicate inputs first.
3. 从 schema 和独立文档生成 Ossie 草稿。/ Generate Ossie drafts from schemas and independent documentation.
4. 隔离无效字段和无法确认的关系。/ Quarantine malformed fields and unresolved relationships.
5. 由目录作者补充并审核业务语义。/ Have catalog authors add and review business semantics.
6. 冻结目录，再标注原始问题或编写新增问题。/ Freeze catalogs before query annotation or new query authoring.
7. 审核完整上下文集合及合法替代方案。/ Review complete context sets and valid alternatives.
8. 通过质量门槛后导出正式训练或评估版本。/ Export reviewed releases only after quality gates pass.

当前 Spider 转换器仅将目标列明确对应单列主键的关系写入 Ossie。
复合键和无法确认唯一性的关系保留为未解决项，不能拆成未经证明的独立连接。
BIRD 字段说明导入不建立 PK/FK，必须补充实际 DDL 核验。
不得将 SQL 的 FROM/JOIN 关系误记为完整 ETL 血缘。

The Spider converter emits a relationship only when the target is a declared single-column primary key.
Composite-key or unverified uniqueness cases remain unresolved, rather than becoming unsupported independent joins.
BIRD description import creates no PK/FK claims; physical DDL verification remains required.
SQL FROM/JOIN references do not establish full ETL lineage.

问题级 `evidence`、SQL、执行结果、gold database ID 和审核理由只存在于监督或来源记录。
`model_input()` 仅输出 question、confirmed_history 和 catalog_snapshot。
目录中的正常限定名可以作为候选信息；当前问题的答案数据库 ID 不得作为预过滤条件。
候选描述不得包含直接从该测试问题改写的 `ai_context.examples`。

Question-specific evidence, SQL, execution results, gold database IDs, and reviewer reasons remain in supervision or provenance records.
`model_input()` projects only question, confirmed history, and catalog snapshot.
Catalog-qualified names are candidate information; the answer database ID cannot prefilter the current query.
Candidate descriptions cannot contain `ai_context.examples` rewritten from the evaluation question.

## 5. 文件契约 / File contracts

| 文件 / File | 用途 / Purpose | 模型可见 / Model-visible |
| --- | --- | --- |
| `catalogs/*.json` | 固定 JSON Schema 通过的 Ossie 草稿 / Schema-valid Ossie drafts | 人工批准及快照筛选后才进入检索 / Only after approval and snapshot filtering |
| `catalog_index.jsonl` | 来源、哈希、缺失项和关系审核记录 / Provenance, hashes, missing items, and relation audit | 不整体传入 / Not passed wholesale |
| `records.jsonl` | 问题、来源、待审标签与初步分组 / Questions, provenance, pending labels, provisional groups | 仅白名单 input / Whitelisted input only |
| `supervision_only.jsonl` | SQL、原始 evidence、SQL 表集合弱标签 / SQL, original evidence, weak table labels | 否 / No |
| `pilot_review_queue.jsonl` | 待审核记录引用 / Review record references | 否 / No |
| `source_issues.jsonl` | 隔离原因 / Quarantine reasons | 否 / No |
| `manifest.json` | 数量、状态、来源与产物哈希 / Counts, state, source and artifact hashes | 否 / No |

`null` 表示未审核或未知，不代表负例。空集合只用于已确认没有适用对象的情形。
`observed_sql_tables` 只覆盖当前 SQL 实现，不等于完整业务标签。
`proposed_split` 是预留建议，`assigned_split` 仍为空，直到最终审核冻结。
当前 intake snapshot 只是全来源盘点，不是训练 C0。正式训练索引只能包含协议允许的训练时目录，不能直接使用整个导入目录挖掘未来域负例。

`null` means unknown or unreviewed, not negative. An empty set requires a reviewed absence of applicable objects.
`observed_sql_tables` describes the supplied SQL implementation, not complete business labels.
`proposed_split` is a reservation proposal. `assigned_split` remains null until final review and freezing.
The intake snapshot inventories all sources; it is not training snapshot C0. Build training indexes from the permitted training-time catalog, rather than mining future-domain negatives from the entire intake.

早期[审核模板](../../../configs/semantic_retrieval/review-template.json)保留为完整语义研究的设计表。
当前结构训练导出器使用 pilot 包中生成的 `reviews.template.jsonl` 与 `catalog_reviews.template.jsonl`。
验证器现已检查审批、哈希、字段引用、显式依赖、正负标签及划分隔离。

The earlier [review template](../../../configs/semantic_retrieval/review-template.json) remains a worksheet for the broader semantic study.
The structural exporter uses generated `reviews.template.jsonl` and `catalog_reviews.template.jsonl` from the pilot package.
The implemented validator checks approval, hashes, references, declared dependencies, observed labels, and split isolation.

## 6. Pilot 的具体审核 / Pilot review procedure

原始多样性队列被结构平衡队列替代，全部替换均已记录。
当前覆盖 45 个 Spider 与 34 个 BIRD 数据库，合并为 73 个分组。
首批每来源 40 题，每类结构各 10 题。197/43 内部训练／开发预留全部来自正式训练域。

The structurally balanced queue replaces the initial diversity queue, with every replacement recorded.
It covers 45 Spider and 34 BIRD databases, joined into 73 groups.
Review 40 episodes per source first, ten per structural stratum. The 197/43 internal split remains within formal-training-reserved domains.

对每题检查：原始数据库范围是否隐含、问题是否歧义、SQL 是否可信、所需字段是否齐全、是否需要值检索。
无法从纯 metadata 回答的值依赖问题单独分层；主实验不额外给某个方法提供行样本。
至少安排多表、聚合／子查询、口径冲突、缺失定义与澄清样本。
结构配额现已满足，但不能当作业务语义覆盖配额。

Check implicit database scope, ambiguity, SQL correctness, field coverage, and dependence on database values.
Stratify value-dependent tasks separately; do not give row samples only to the proposed method.
Include multitable, aggregation/subquery, conflicting-definition, missing-definition, and clarification cases.
Structural sampling quotas are now met; they do not establish coverage of business-semantic conditions.

## 7. 正式版本的进入条件 / Formal release gates

1. 每个来源有固定版本、许可证据、引用和 SHA-256。/ Every source has a revision, terms evidence, citation, and checksum.
2. 每个训练正例或负例有审核依据，未知标签保留掩码。/ Every positive or negative is reviewed; unknowns remain masked.
3. 目录先于评估问题冻结，禁止问题到目录的泄漏。/ Catalogs predate evaluation questions; no query-to-catalog leakage.
4. 分组、别名、重复输入和派生变体不跨划分。/ Groups, aliases, duplicate inputs, and derived variants stay within splits.
5. 所选上下文的字段、公式及必要依赖引用均可解析。/ Selected fields, expressions, and dependencies resolve.
6. 有数据库的样本在隔离、只读环境验证 SQL；记录超时与失败。/ Execute eligible SQL only in isolated read-only databases; record failures and timeouts.
7. 人工语义审核与执行结果核验分开记录。/ Record semantic review separately from execution checks.
8. 测试集冻结后不再用于调参或改写元数据。/ Frozen tests cannot tune models or rewrite metadata.

当前已实现来源导入、草稿转换、平衡 pilot、审核验证、结构训练导出及训练脚本。
全部真实标签仍待审；尚无实际训练导出。物理数据库、业务语义、困难负例及正式划分仍需完成。
结构工程 pilot 与正式语义发布分开：前者只训练已审核的 metadata 检索标签，后者仍需上述全部门槛。

Intake, conversion, balanced pilot preparation, review validation, structural export, and a training script are implemented.
All source labels remain pending, so no actual training release exists. Physical databases, business semantics, reviewed negatives and formal splits remain outstanding.
The structural engineering pilot uses reviewed metadata-retrieval labels only. A formal semantic release still requires all gates above.
