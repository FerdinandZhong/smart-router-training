# 数据与代码可用性计划 / Data and Code Availability Plan

日期 / Date：2026-10-10。目标期刊与文章类型尚未指定，当前采用期刊无关的研究准备方案。
No journal or article type is specified. This is a journal-neutral preparation plan, not a submission-ready availability statement.

## 1. 数据清单与访问路线 / Inventory and access routes

| 数据 / Data | 访问路线 / Access route | 当前映射 / Current mapping |
| --- | --- | --- |
| Spider 训练注释及 schema / Training annotations and schema | reused public source | [官方入口 / Official page](https://yale-lily.github.io/spider)，固定提交及文件哈希见 sources.json / Pinned commit and hashes in registry |
| BIRD 筛选训练注释及字段说明 / Filtered training annotations and column meanings | reused public source | [官方数据记录 / Dataset record](https://huggingface.co/datasets/birdsql/bird23-train-filtered)，固定 revision / Pinned revision |
| Ossie JSON Schema | reused public source | [固定官方 schema / Pinned schema](https://github.com/apache/ossie/blob/28a91f59e0d7fc51d808608b626627be79ef8128/core-spec/ossie-schema.json) |
| 派生 Ossie 草稿、审核队列和弱监督 / Derived drafts, review queue, weak supervision | public repository，计划路线 / planned route | 当前为本地、未审核产物；尚无公开存储记录 / Local unreviewed artifacts; no deposited record yet |
| 审核标签、划分与生成记录 / Reviewed labels, splits, generation logs | public repository，计划路线 / planned route | 尚未生成；许可核验后以版本化记录发布 / Not yet generated; release after rights review |
| 模型 checkpoint、指标和图表源数据 / Checkpoints, metrics, figure source data | public repository，计划路线 / planned route | 尚无本任务实验结果 / No task-specific results yet |
| Spider 2.0 资产 / Assets | reused public source | 仅作为候选外部评测；未取得和训练 / Optional external evaluation; not acquired for training |
| LiveSQLBench 公开 schema/知识库 / Public schemas and knowledge | reused public source | 许可冲突待澄清；未纳入派生发布 / Terms conflict unresolved; excluded from derived release |
| LiveSQLBench gold SQL、知识 ID、测试用例 / Gold SQL, knowledge IDs, tests | third-party restricted | 数据卡指明向维护方申请；本次未发送邮件 / Maintainer request route documented; no email sent |
| 企业验证数据 / Enterprise validation data | not applicable，当前阶段 / current phase | 当前收集未包含企业数据；后续来源加入时重新分类 / No enterprise data in current intake; classify when added |

公开原始数据、派生标注、软件及模型权重分别记录许可。
Ossie 的 Apache 许可不覆盖所转换数据的内容。
Spider 和 BIRD 数据源声明 CC BY-SA 4.0；派生发布应保留来源、版本及变更说明，并核实适用条款。
当前不对全部产物统一贴上新的开放许可。

Record terms separately for source data, derived annotations, code, and model weights.
Ossie's Apache license does not license the content converted into its format.
Spider and BIRD declare CC BY-SA 4.0 for the relevant datasets. Preserve attribution, versions, and modification notices, and verify applicable terms for a derivative release.
No blanket new license is assigned to all outputs.

LiveSQLBench 的固定数据卡 YAML 声明 `cc-by-4.0`，正文 License 部分声明 `cc-by-sa-4.0`。
来源记录保留两种声明，不自动选择更宽松的许可。
Its pinned card declares `cc-by-4.0` in YAML and `cc-by-sa-4.0` in the License section.
The registry preserves both declarations rather than choosing the less restrictive one.
Evidence: [pinned dataset card](https://huggingface.co/datasets/birdsql/livesqlbench-large-v1/blob/a418e108d5cbb4cf9b783a928eff5e924ad2460d/README.md).

## 2. 仓库与标识符策略 / Repository and identifier strategy

开发阶段保存 Git 提交、固定来源 revision、JSON/JSONL 文件、说明文档和 SHA-256。
原始数据库不进入代码仓库。优先发布可重建脚本和明确的上游获取步骤。
派生数据达到发布条件后，选择支持版本化 DOI 的长期仓库，例如 Zenodo 或机构仓库。
这只是存储建议；尚未创建记录、分配 DOI 或上传数据。

During development, preserve Git commits, source revisions, JSON/JSONL artifacts, documentation, and SHA-256 hashes.
Keep raw databases outside the code repository. Prefer reproducible scripts and explicit upstream acquisition routes.
When derivatives are ready, select a durable archive with versioned identifiers, such as Zenodo or an institutional repository.
This is a proposed route; no record, DOI, or upload has been created.

每个正式版本须包含创建者、标题、版本、发布日期、语言、许可、来源和处理脚本版本。
每个图表还需对应可重建的数据文件和参数。
如后续加入企业数据，另行记录其数据所有者、实际限制和可访问路线。

Each release needs creators, title, version, date, language, terms, provenance, and processing-code version.
Each figure or table must map to reconstructible source files and parameters.
If enterprise data are added, document the actual owner, restrictions, and access route separately.

## 3. 当前可使用的状态说明 / Current-status wording

### Data Availability — preparation-stage wording

This study is in data preparation. The current source pool uses Spider 1.0 training annotations and schemas from the official project repository, and BIRD-SQL Train (Filtered) annotations and column descriptions from the BIRD Team's dataset repository. Exact revisions, download locations, declared licenses, and checksums are recorded in `configs/semantic_retrieval/sources.json`. Derived Ossie documents and review queues are unreviewed local preparation artifacts. No reviewed training release or public archive identifier has yet been issued. Optional external evaluation sources are listed separately, together with unresolved access and licensing conditions.

### 数据可用性 — 研究准备阶段表述

本研究处于数据准备阶段。当前来源池使用 Spider 官方项目仓库中的训练注释和 schema，以及 BIRD 官方筛选训练集的注释与字段说明。来源注册表记录了准确版本、下载地址、声明许可和校验和。派生 Ossie 文档及审核队列目前属于本地未审核产物。尚未发布审核后的训练集，也未取得公开归档标识符。候选外部评测来源及其访问、许可待解决项单独记录。

### Code Availability — preparation-stage wording

Preparation code is maintained on the `research/semantic-model-routing` branch of the project repository. It provides pinned-source retrieval, structural Ossie conversion, grouped pilot sampling, review validation, structural training export, retrieval diagnostics, and a single-device embedding training script. All source pilot labels remain pending. Training optimization has only been verified on an invented CPU fixture, not the public pilot. A public code release and persistent archive identifier remain to be selected before publication.

### 代码可用性 — 研究准备阶段表述

准备代码保存在独立研究分支，支持来源获取、Ossie 转换、分组抽样、审核验证、结构训练导出、检索诊断和单设备 embedding 训练。全部来源标签仍待审。优化过程仅在虚构 CPU fixture 上验证，尚未训练公开 pilot。正式发表前仍需确定公开代码版本和长期归档标识符。

## 4. 数据引用 / Dataset citations

以下为目前可追溯的数据记录引用，尚不包含不存在的 DOI。
These references identify the available dataset records without inventing identifiers.

- Spider dataset authors / Yale LILY. *Spider 1.0*. [Official dataset landing page](https://yale-lily.github.io/spider). Acquired training/schema snapshot: repository commit `b7b5b8c890cd30e35427348bb9eb8c6d1350ca7c`; accessed 2026-10-10. Dataset paper: [Spider, EMNLP 2018](https://aclanthology.org/D18-1425/).
- BIRD Team. *BIRD-SQL Train (Filtered)* (2025 release). [Hugging Face dataset record](https://huggingface.co/datasets/birdsql/bird23-train-filtered). Revision `4068469807b255fcfc0816bdd520946fe460d256`; accessed 2026-10-10. This record cites the original BIRD benchmark; paper metadata should be finalized from the proceedings when preparing the manuscript.
- Apache Ossie contributors. *Apache Ossie Core Metadata Specification and JSON Schema*. [Official source](https://github.com/apache/ossie/tree/28a91f59e0d7fc51d808608b626627be79ef8128/core-spec). Revision `28a91f59e0d7fc51d808608b626627be79ef8128`; accessed 2026-10-10.

## 5. FAIR 审核及待确认事项 / FAIR audit and unresolved fields

| 维度 / Dimension | 已完成 / Prepared | 正式发布前仍需 / Still required |
| --- | --- | --- |
| Findable | 来源注册表、稳定内部 ID / Source registry and stable internal IDs | 派生数据标题、创建者和持久标识符 / Derivative title, creators, persistent identifier |
| Accessible | 已取得公开训练注释和字段材料 / Public training annotations and descriptions acquired | 物理数据库、可公开派生记录和实际访问验证 / Physical databases, published derivatives, access checks |
| Interoperable | JSON/JSONL、固定 Ossie schema、双语说明 / Open formats, pinned schema, bilingual documentation | 引用解析、Helios 兼容性和规范迁移策略 / Reference resolution, compatibility, migration policy |
| Reusable | 文件哈希、来源、转换限制和未知标签规则 / Hashes, provenance, conversion limits, unknown-label rules | 人工审核、最终划分、引用和许可整合 / Review, frozen splits, citations, rights reconciliation |

中文核对：当前不需要为了收集公开训练数据确定期刊。正式投稿前需要确定目标期刊、署名、存储库和标识符。
LiveSQLBench 的许可与完整答案访问仍未解决，但不阻塞 Spider/BIRD 的当前准备。
没有向数据维护者发送邮件，没有对外上传数据，也没有把未审核草稿标记为可训练。

Chinese author check: the journal is not needed for current public-source intake. Confirm the journal, authorship, archive, and identifiers before submission.
LiveSQLBench terms and gold-data access remain unresolved, without blocking current Spider/BIRD preparation.
No maintainer email or external upload was performed, and unreviewed drafts remain ineligible for training.
