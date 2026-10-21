# Pilot 审核与训练准备 / Pilot Review and Training Readiness

Date / 日期: 2026-10-10. Branch: `research/semantic-model-routing`.
Scope: data/methods audit by one assistant, not independent peer review or business-owner approval.
范围：同一助手进行数据与方法检查，不是独立同行评议或业务负责人审批。

## Decision / 结论

Proceed with the structural pilot review and training-script preparation.
The 240 episodes are review-ready; none is approved for training.
The richer business-semantic experiment still requires reviewed definitions, ambiguity cases, and physical database checks.

可以开展结构 pilot 审核，并准备训练脚本。240 个样本已整理成审核包，目前可训练数量为零。
完整业务语义实验仍需补齐经审核的业务定义、歧义样本及物理数据库核验。

## Audit findings and repairs / 审核发现与修正

| Finding / 发现 | Action / 处理 | Remaining boundary / 边界 |
| --- | --- | --- |
| Original Spider queue had only 13 multitable episodes out of 120 / 原队列多表样本仅 13/120 | Resample four structural strata; log all replacements / 按四类结构重采样，保存替换记录 | SQL complexity is not semantic difficulty / SQL 复杂度不等于业务语义难度 |
| All pilot examples were reserved for formal training / pilot 全部来自正式训练预留组 | Grouped internal development split: 197 train, 43 development / 内部组级划分为 197/43 | This is not the formal validation set / 不能替代正式验证集 |
| Inventory snapshot contained future evaluation catalogs / 导入盘点包含未来评估目录 | Build a pilot snapshot with only 112 train-reserved catalogs / 仅使用 112 个训练预留目录 | Cross-source semantic aliases still need review / 跨来源语义别名仍需审核 |
| Names and SQL tables could be mistaken for business semantics / 名称或 SQL 表集合可能被误作业务定义 | Keep structural and semantic evidence tracks separate / 分开结构与语义证据轨道 | No approved metrics or business rules yet / 尚无已批准的业务指标或口径 |
| Weak labels and unknowns could become training labels / 弱标签与未知值可能进入训练 | Export requires explicit review; null remains masked / 导出强制审核，null 保持掩码 | Software checks do not verify reviewer competence / 软件检查不证明审核质量 |
| 162 metadata descriptions exceeded the encoder window / 162 个元数据描述超出编码器窗口 | Encode all token windows and pool chunk vectors / 完整分块编码并聚合向量 | Pooling can dilute a specific field; ablate this choice / 聚合可能稀释关键字段，需消融 |
| Model validation could be confused with task success / 模型验证指标可能被误作任务成功率 | Report pair accuracy and reviewed-pool ranking separately / 单列候选对准确率与池内排序 | Context completeness and downstream SQL remain separate / 完整性和下游 SQL 另行评测 |

The balanced queue retains 10 old records and replaces 230 before any human review.
No adverse result was removed after evaluation. `sampling-audit.json` records every ID.
The original intake and the first pilot build remain immutable historical artifacts.

平衡队列保留 10 条旧记录，替换 230 条。重采样发生在人工审核之前，并非根据模型表现删除困难样本。
`sampling-audit.json` 保存全部记录 ID。旧导入包与首个 pilot 构建保留为历史产物。

## Current artifacts / 当前产物

Use `data/semantic-research/pilot-20261010-v3/` for review.
Use `data/semantic-research/baselines-20261010-v3/` for current diagnostics.
The editable forms and readable first-80 packet are prepared in `data/semantic-research/review-work-20261010-v2/`.
Earlier baseline v1 used truncation and emitted numerical warnings; it is superseded, not evidence for model selection.
Pilot v3 also fixes keyword accumulation order, so independent package rebuilds have identical hashes.

审核使用 `pilot-20261010-v3`。诊断使用 `baselines-20261010-v3`。
可编辑表单与首批 80 条阅读材料位于 `review-work-20261010-v2`。
早期 baseline v1 存在截断和数值警告，已被替代，不用于模型选择。
Pilot v3 同时固定关键词累加顺序，独立重建得到相同哈希。

| Artifact / 产物 | Content / 内容 |
| --- | --- |
| `catalogs/` | 112 training-reserved structural Ossie documents / 112 个训练预留结构文档 |
| `metadata_units.jsonl` | 5,205 addressable table/field/relationship units, including 702 tables / 5,205 个可引用对象，其中 702 个表 |
| `episodes.supervision.jsonl` | 240 questions, independent retrieved pools, isolated SQL evidence / 240 个问题、独立召回池及隔离 SQL 证据 |
| `reviews.template.jsonl` | Pending judgments with null labels / 标签为 null 的待审模板 |
| `catalog_reviews.template.jsonl` | Catalog checks bound to exact document hashes / 与文档哈希绑定的目录审核 |
| `first80.jsonl` | 40 episodes per source; ten per structural stratum / 每来源 40 条，每类结构 10 条 |
| `sampling-audit.json` | Inclusion, replacement and stratum accounting / 抽样、替换与结构统计 |
| `rankings.jsonl` in baseline output | BM25, dense and untuned RRF rankings over identical 702 tables / 相同 702 表上的三种排序 |
| `review-work-20261010-v2/first80.md` | Readable question/SQL packet and top candidates / 可读问题、监督 SQL 及主要候选 |
| `review-work-20261010-v2/reviews.jsonl` | Editable union of baseline candidates; every label remains null / 三种基线候选的可编辑并集，标签均为 null |

The balanced pilot spans 45 Spider and 34 BIRD source databases, grouped into 73 connected groups.
Source databases, groups, semantic objects, and independent episodes are different counting units.
All selected records remain within the original formal-training reservation.
The whole pilot catalog is available for both internal splits. This is a known-catalog, held-out-query diagnostic, not unseen-catalog generalization.

平衡 pilot 覆盖 45 个 Spider 数据库和 34 个 BIRD 数据库，合并为 73 个连接分组。
数据库、分组、语义对象和独立问题分别计数。全部样本仍位于正式训练预留范围内。
内部训练与开发共享 pilot 目录。这属于已知目录上的问题泛化，不代表未见目录泛化。

| Source / 来源 | Structural sampling strata, 30 each / 结构抽样分层，每类 30 条 |
| --- | --- |
| Spider | Single simple; single aggregate/subquery hint; two tables; three or more tables / 单表简单、单表聚合或子查询提示、两表、三表及以上 |
| BIRD | Simple hint; aggregation hint; JOIN hint; nested SELECT hint / 简单、聚合、JOIN、嵌套 SELECT 提示 |

Spider table counts come from its supplied structured SQL AST. BIRD tags are lexical sampling hints, not parsed gold table sets.
Missing definitions, conflicts and clarification cases still require semantic review and later Track B authoring.

Spider 表数量来自原始 SQL AST。BIRD 分类仅为词法抽样提示，不是解析后的标准表标签。
缺失定义、口径冲突和澄清任务仍需语义审核及后续 Track B 构建。

## Reviewer workflow / 审核流程

```text
schema / independent descriptions
               |
catalog review and frozen document hashes
               |
query + candidate pool + isolated SQL evidence
               |
two reviewers: labels, ambiguity, complete sets
               |
audit -> reviewed export -> training preflight
               |
embedding training -> internal development checks
```

1. Give catalog reviewers only the catalogs, metadata units, and catalog-review template.
   目录审核者只接收目录、元数据对象与目录审核模板。
2. Copy review templates outside the immutable package before editing.
   将模板复制到包外再编辑，不能直接修改不可变审核包。
3. Check field meaning, source schema evidence, and declared references. Physical verification is recorded separately.
   检查字段含义、来源 schema 证据和声明引用。物理数据库核验单独记录。
4. Review the first 80 queries against the pooled catalog, without assuming the oracle database is user context.
   先审核 80 条问题，不能将答案数据库 ID 当作用户提供的上下文。
5. Use baseline rankings to find missed positives and potential negatives. Keep uncertain judgments null.
   使用三种排序发现漏召正例及候选负例。不确定标签保留 null。
6. Record each known table label with a reason. Record complete context sets using stable unit IDs.
   每个已知表标签必须有理由，完整上下文集合使用稳定对象 ID。
7. Include required fields, relationships, and connecting tables in those sets. Software verifies explicit dependency closure only.
   集合需要包含必要字段、关系及连接表。软件仅验证已声明依赖，不证明语义充分性。
8. Record two distinct query reviewers, timezone-aware timestamps, ambiguity checks, and alias review.
   记录两位不同的问题审核者、含时区时间戳、歧义及别名审核。
9. Mark ambiguous, metadata-missing, or value-dependent tasks with reasons. Retain them for later task-specific evaluation.
   对歧义、缺失元数据或依赖行值的任务记录原因，并保留用于后续专项评估。
10. Audit before export. Only approved answerable structural tasks enter the current ranking trainer.
    先审核后导出。当前排序训练器只接收已批准且可回答的结构任务。

Do not certify guessed labels as human review. An automated review draft remains a draft.
Human-added positives may expand a training review pool; never insert them into recorded baseline rankings.
This prevents training-pool curation from masquerading as retrieval recall.

The editable union contains 13,699 candidate judgment slots. Reviewers need not label all slots.
Review required positives and a useful set of hard negatives; leave other slots unknown.
Measure first-80 review effort before retaining the earlier 10–15 minute-per-episode planning assumption.

不能将自动猜测标签标记为人工审核。人工可以扩充训练审核池，但不能向已记录的 baseline 排序中注入正例。
训练候选整理与实际召回率必须分开。
可编辑并集包含 13,699 个候选判断位置，不要求全部标注。
优先审核必要正例及有效困难负例，其余保持未知。先测首批工时，再确认原有每题 10–15 分钟的估算。

## Commands / 命令

Run from the research worktree. Generated artifacts remain outside Git.
从研究工作树执行。生成数据不进入 Git。

```bash
python scripts/prepare_semantic_pilot.py build \
  --intake data/semantic-research/intake-20261010-v3 \
  --output data/semantic-research/pilot-REPRODUCTION

python scripts/evaluate_semantic_baselines.py \
  --pilot data/semantic-research/pilot-20261010-v3 \
  --config configs/semantic_retrieval/embedding-pilot.json \
  --output data/semantic-research/baselines-NEW-RUN

# An editable workspace already exists as review-work-20261010-v2.
# This command creates a new one and refuses to overwrite reviewer edits.
python scripts/prepare_semantic_pilot.py workspace \
  --pilot data/semantic-research/pilot-20261010-v3 \
  --baselines data/semantic-research/baselines-20261010-v3 \
  --output data/semantic-research/review-work-NEW

python scripts/prepare_semantic_pilot.py audit \
  --pilot data/semantic-research/pilot-20261010-v3 \
  --reviews data/semantic-research/review-work-20261010-v2/reviews.jsonl \
  --catalog-reviews data/semantic-research/review-work-20261010-v2/catalog-reviews.jsonl

# These commands require completed reviews; pending templates are rejected.
python scripts/prepare_semantic_pilot.py export \
  --pilot data/semantic-research/pilot-20261010-v3 \
  --reviews data/semantic-research/review-work-20261010-v2/reviews.jsonl \
  --catalog-reviews data/semantic-research/review-work-20261010-v2/catalog-reviews.jsonl \
  --output data/semantic-research/reviewed-structural-pilot-v1

python scripts/train_semantic_retriever.py preflight \
  --data data/semantic-research/reviewed-structural-pilot-v1 \
  --config configs/semantic_retrieval/embedding-pilot.json

python scripts/train_semantic_retriever.py train \
  --data data/semantic-research/reviewed-structural-pilot-v1 \
  --config configs/semantic_retrieval/embedding-pilot.json \
  --output data/semantic-research/training-NEW-RUN
```

`audit` exits nonzero for malformed approvals. A valid pending package returns `ready_for_training: false`.
`export` and training `preflight` enforce readiness. A partial reviewed release lists remaining pending and deferred records.
Keep the original pilot denominator when reporting exclusions and task mix.

`audit` 对格式错误审批返回非零状态。合法待审包返回 `ready_for_training: false`。
`export` 与训练 `preflight` 强制检查就绪状态。部分审核发布必须保留待审、延期记录及原始分母。

## Training implementation / 训练实现

The first recipe uses the pinned English `sentence-transformers/all-MiniLM-L6-v2` model.
It is an engineering baseline, not the final backbone selection.
Reference: [model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/tree/1110a243fdf4706b3f48f1d95db1a4f5529b4d41).
The adapter follows the [SentenceTransformer API](https://www.sbert.net/docs/package_reference/sentence_transformer/model.html).

第一套配置使用固定版本的英文 MiniLM 模型，仅作为工程起点，不代表最终骨干选择。

- One shared encoder processes query and candidate descriptions. Catalog IDs and SQL are excluded from encoder text.
  查询与候选描述共享编码器，目录 ID 与 SQL 不进入编码文本。
- Every token enters an overflow window. Normalized chunk vectors are averaged and normalized again.
  所有 token 都进入分块窗口，块向量归一化后取均值，再次归一化。
- Each positive uses a standard softmax contrastive objective against explicitly reviewed negatives.
  每个正例使用标准 softmax 对比目标，仅与明确审核的负例比较。
- Other positives and unknowns are excluded from that negative set. There are no automatic in-batch negatives.
  其他正例及未知对象不作为负例，不自动使用 batch 内负例。
- The default cap is ten epochs, with development-loss stopping after two non-improving epochs.
  默认最多十轮，开发损失连续两轮无改善时停止。
- Epoch zero is eligible for checkpoint selection. Keep the original encoder if adaptation does not improve development loss.
  初始模型也参与 checkpoint 选择，适配无改善时保留原模型。
- Logs include loss, reviewed-pair accuracy, and reviewed-pool MRR. These are not whole-catalog recall or context completeness.
  日志包含损失、审核候选对准确率和候选池 MRR，不代表全目录召回或上下文完整率。
- Save the selected encoder, artifact hashes, configuration, package versions, and reload checks.
  保存选定编码器、哈希、配置、软件版本和重载检查。

The script is single-device and defaults to CPU. CUDA requires an explicit config change and an available device.
No Ray submission, GLiNER/Laya task adapter, semantic metric trainer, threshold calibration, or resume support is claimed.
Install `.[semantic]` in a dedicated compatible environment. Local evidence used Python 3.13.9 and Torch 2.9.1;
the project's optional environment retains Torch 2.8.0 for cluster compatibility, which was not newly validated here.

脚本使用单设备，默认 CPU。CUDA 需要显式配置及可用设备。
尚未提供 Ray 提交、GLiNER/Laya 新任务适配、业务指标训练、阈值校准或断点续训。
当前本地证据不等于集群 Torch 2.8.0 或 GPU 验证。

## Claim–evidence map / 主张与证据

Current checks: 20 semantic unit tests passed. The offline training smoke passed weight-update,
multiple-positive gradient, unknown-mask, chunk-coverage and checkpoint-reload checks.
An independent pilot rebuild matched every artifact hash. Pending source data failed both export and training preflight as intended.
Aggregate evidence: [dated preparation status](../../status/2026-10-10-semantic-pilot-preparation.json).

当前检查：20 项语义数据单元测试通过。离线训练 smoke 通过权重更新、多正例梯度、未知掩码、分块覆盖及 checkpoint 重载检查。
独立重建得到相同产物哈希。待审数据按预期无法通过导出及训练预检。

The following baseline numbers concern 120 unreviewed Spider episodes at K=32, with 702 candidate tables.
They measure coverage of the supplied SQL's table set, not business-semantic correctness.
Do not select a final method from these diagnostics; tune the hybrid using reviewed development data.

以下数字来自 120 条未审核 Spider 问题，候选目录为 702 个表，K=32。
它们仅衡量原始 SQL 表集合覆盖，不代表业务语义正确率。最终方法选择需使用审核后的开发数据。

| Method / 方法 | Mean weak table recall / 平均弱标签表召回 | Complete SQL-table coverage / SQL 表集合完整覆盖 |
| --- | --- | --- |
| BM25 | 68.06% | 57.50% |
| Unadapted dense / 未微调 dense | 93.06% | 87.50% |
| Untuned hybrid RRF / 未调优 hybrid | 88.26% | 83.33% |

| Claim / 主张 | Evidence / 证据 | Status / 状态 |
| --- | --- | --- |
| Preparation is reproducible / 构建可复现 | Pinned intake, checksums, deterministic grouping and sampling / 来源、哈希及确定性抽样 | Implemented and locally checked / 已实现并本地检查 |
| The training loop updates weights and reloads / 训练循环能更新和重载权重 | Offline tiny-BERT fixture, multiple-positive gradients, unknown masking / 离线微型模型测试 | CPU engineering evidence only / 仅 CPU 工程证据 |
| Learned retrieval improves semantic completeness / 学习检索改善语义完整性 | No reviewed task-specific training result / 尚无审核后的任务训练结果 | Needs evidence / 待验证 |
| The system meets 500 ms under load / 系统在负载下满足 500 ms | No serving-load test / 尚无服务负载测试 | Needs evidence / 待验证 |
| New tables work through index updates / 新增表仅更新索引即可支持 | C0/C1/C2 experiment not run / 尚未运行增量实验 | Needs evidence / 待验证 |

Terminology is fixed across documents:

| Canonical term / 术语 | Definition / 定义 | Usage decision / 使用边界 |
| --- | --- | --- |
| Ossie | Pinned semantic metadata format / 固定语义元数据格式 | Format validity is separate from semantic correctness / 格式合法不等于语义正确 |
| Metadata unit / 元数据对象 | Addressable table, field or declared relationship / 可引用的表、字段或声明关系 | Do not count units as independent episodes / 不与独立问题数混用 |
| Structural pilot / 结构 pilot | Reviewed metadata retrieval experiment / 经审核的元数据检索试验 | Does not establish business-semantic performance / 不证明业务语义效果 |
| Complete context set / 完整上下文集合 | Reviewer-approved sufficient objects and dependencies / 经审核的充分对象及依赖 | SQL table sets alone are weak evidence / 单独 SQL 表集合仅为弱证据 |
| Pilot development split / pilot 内部开发集 | Grouped checkpoint-selection examples within training-reserved domains / 训练预留域内的组级模型选择样本 | Separate from formal validation and locked test / 与正式验证及锁定测试分开 |

Do not use “semantic training ready” for a structural conversion or an unreviewed packet.
术语统一：Ossie、元数据对象、结构 pilot、完整上下文集合、pilot 内部开发集。

## Data and code availability / 数据与代码可用性

The local pilot derives from the pinned Spider and BIRD sources in `sources.json`.
Review packets, model diagnostics, and scripts now exist locally on the research branch.
No reviewed label release, research-trained checkpoint, archive record, or DOI has been issued.
Source terms and publication actions remain in the [availability plan](data-availability-bilingual.md).

本地 pilot 使用来源注册表中的固定公开数据。当前已有审核包、模型诊断和脚本。
尚无审核标签发布、研究训练 checkpoint、公开归档记录或 DOI。
待确认内容包括业务审核者、独立业务定义、物理数据库核验及未来发布责任人。

The BIRD publisher links an 8,919,543,554-byte database archive. A read-only availability check succeeded on 2026-10-10.
No database rows were downloaded or SQL executed. Schema checks based on source metadata do not replace that work.
Source: [pinned BIRD dataset card](https://huggingface.co/datasets/birdsql/bird23-train-filtered/blob/4068469807b255fcfc0816bdd520946fe460d256/README.md).
