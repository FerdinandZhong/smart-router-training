# Ossie 语义上下文检索研究计划 / Ossie Semantic Context Retrieval Research Plan

版本 / Version：2026-10-10 public-data revision。状态 / Status：方案及未审核数据收集工具已准备；语义训练尚未开始 / Proposal and unreviewed intake tooling prepared; semantic training has not started.

本文件是当前主计划。它更新了早期中文计划的数据来源、样本口径和评估隔离安排。
This is the current master plan. It updates the earlier Chinese plan's data sources, sample accounting, and evaluation isolation.

## 1. 研究目标 / Research objective

在持续增长的 Ossie 目录中，在固定延迟和上下文预算内选择完整、一致的业务语义。
初始召回采用 keyword + embedding。可选的 GLiNER 或 Laya 同时承担重排与候选适用性判断。
最终选择允许多个语义对象和多个表，确定性装配负责补齐已声明的必要依赖。

Select complete, consistent business context from a growing Ossie catalog under fixed latency and context budgets.
Use keyword plus embedding retrieval for candidate generation. An optional GLiNER or Laya stage provides reranking and suitability scores.
The output may contain several semantic objects and tables. Deterministic assembly adds declared dependencies.

| 假设 / Hypothesis | 验证 / Test | 否定条件 / Falsification |
| --- | --- | --- |
| H1：语义对象表示和依赖装配提高完整性 / Semantic units and dependency assembly improve completeness | 相同来源信息下比较表文档、语义对象和装配 / Compare representations and assembly with identical source information | 收益仅来自增加说明文字 / Gains arise solely from extra metadata |
| H2：领域训练改善口径区分 / Domain adaptation improves business distinctions | 同一骨干训练前后，与调优 hybrid 比较 / Compare adapted and original encoders against tuned hybrid | 无稳定质量或效率收益 / No stable quality or efficiency gain |
| H3：新增表可通过索引更新获得支持 / Index updates support new tables | 冻结权重，评估 C0/C1/C2 / Freeze weights and evaluate catalog arrivals | 新表失败或旧问题明显退化 / New-table failures or material regression on existing queries |

领域 schema 检索与多表精筛已有研究。Ossie 格式、无图架构或更换模型本身不构成创新。
贡献要由业务语义完整性、目录新增和质量—延迟实验支持。
Corpus-adaptive schema retrieval and multitable refinement are established research directions. Format choice, a graph-free architecture, or a different backbone alone is not a contribution.
Claims require evidence on business-semantic completeness, catalog growth, and quality–latency trade-offs.
Sources: [corpus-adaptive retrieval](https://arxiv.org/abs/2607.13311), [REaR](https://aclanthology.org/2026.acl-long.1826/).

## 2. 审核后的范围 / Reviewed scope

主方法不使用图检索、GNN 或新的成本感知损失。使用标准对比学习和候选排序目标。
第一阶段从全目录检索，先限制为同一可执行模型版本内的组合。
跨模型结果可以是替代解释，不能自动推断跨模型连接。

The main method uses no graph retrieval, GNN, or new cost-aware loss. Use standard contrastive and ranking objectives.
Search across the catalog, while initially composing context within one executable model release.
Cross-model results can represent alternative interpretations; they do not authorize inferred cross-model joins.

Ossie 结构合法不等于业务定义正确，也不等于 SQL 可执行。
固定研究用规范提交；与 Helios 实际版本的兼容性另行验证。
来源映射、计算依赖、分析连接与完整 ETL 血缘分别记录。

A valid Ossie document does not establish business correctness or SQL executability.
Pin the research schema revision and validate compatibility with the actual Helios version separately.
Distinguish source mappings, calculation dependencies, analytical joins, and full ETL lineage.
Specification: [pinned Ossie core](https://github.com/apache/ossie/blob/28a91f59e0d7fc51d808608b626627be79ef8128/core-spec/spec.md).

## 3. 数据来源与证据等级 / Sources and evidence levels

| 来源 / Source | 用途 / Role | 边界 / Boundary |
| --- | --- | --- |
| Spider 1.0 upstream train | 结构检索、关联与多表问题的起点 / Structural retrieval and multitable starting point | 仅使用固定训练快照；规范化名称不是业务说明 / Pinned training snapshot; normalized names are not business definitions |
| BIRD official filtered train | 主要训练候选；字段说明辅助建模 / Main candidate source with column descriptions | 问题级 evidence 默认仅作监督；补查真实 schema 和键 / Question-specific evidence is supervision-only; verify schemas and keys |
| 经独立审核的语义扩充 / Independently reviewed semantic enrichment | 指标、口径、时间、粒度、歧义与难负例 / Metrics, definitions, time, grain, ambiguity, and hard negatives | 标记为生成或审核扩充，不冒充原数据事实 / Label generated or reviewed additions explicitly |
| Spider 2.0 | 后续外部评测 / Later external evaluation | 不用于本项目微调；访问与资产许可另核验 / Excluded from our fine-tuning; verify asset access and terms |
| LiveSQLBench-Large-v1 | 条件性复杂语义评测 / Conditional complex-semantic evaluation | 许可声明冲突；完整答案需申请 / Conflicting license declarations; gold data require a request |

来源版本、链接、校验和和访问状态见[来源注册表](../../../configs/semantic_retrieval/sources.json)。
即使公开训练集，也要审核其 SQL 与自然语言是否一致。
公众数据上的结果不能直接证明企业语义层效果。

See the [source registry](../../../configs/semantic_retrieval/sources.json) for revisions, URLs, checksums, and access status.
Public training examples still require question–SQL consistency checks.
Results on public data do not establish effectiveness on an enterprise semantic layer.

## 4. 数据构建与推理流程 / Data construction and inference

```text
OFFLINE DATA
public schemas + catalog documentation
                 |
     source grouping and split reservation
                 |
  Ossie structural conversion + provenance
                 |
 independent semantic authoring and review
                 |
          freeze catalog version
                 |
 original NL-SQL annotation / new query authoring
                 |
   multi-object labels + dependency review

ONLINE INFERENCE
query + confirmed history
                 |
  keyword + query embedding -> candidate pool
                 |
 optional generic reranker / GLiNER / Laya
                 |
      select multiple semantic objects
                 |
 exact definitions + declared dependency lookup
                 |
       budget and consistency checks
                 |
      SQL generation / clarify / abstain
```

目录作者不能看到正式评估问题、答案 SQL 或问题专用 evidence。
先从 schema 和独立文档建立并冻结目录，再由另一审核角色标注问题。
新增语义任务应先定义口径，再编写问题和参考计算。
训练 SQL 可以帮助提出训练域的指标草稿，但必须单列该条件，并独立审核。

Catalog authors must not see final evaluation questions, answer SQL, or question-specific evidence.
Build and freeze the catalog from schemas and independent documentation before another reviewer annotates queries.
For new semantic tasks, define the semantics before writing questions and reference calculations.
Training SQL may suggest metric drafts for training domains, but this condition requires separate reporting and independent review.

同一问题可能需要多个表。SQL 中出现的表只是某个实现的弱证据，并不是唯一合法答案集合。
移除原始 database ID 后，问题可能变得歧义。此时要澄清、记录多个合法解释，或另测用户提供业务域的条件。
不能把原始 database ID 当成用户已经提供的上下文。

A query may require multiple tables. Tables observed in SQL provide weak evidence for one implementation, not the only valid answer set.
Removing the original database ID can make a question ambiguous. Require clarification, record valid alternatives, or separately test user-supplied domain context.
Do not present the oracle database ID as context supplied by the user.

## 5. Pilot 与正式数据 / Pilot and formal data

| 阶段 / Stage | 独立问题目标 / Target episodes | 内容 / Content |
| --- | --- | --- |
| 首轮审核 / First review | 80，来自 pilot / 80 from the pilot | 测量审核工时和公开数据适配问题 / Measure review effort and adaptation failures |
| Pilot | 240；Spider 与 BIRD 各 120 / 240; 120 per source | 训练预留域中的原始问题；补充语义、难例和歧义审核 / Original questions from training-reserved domains with semantic and ambiguity review |
| 正式训练 / Formal training | 1,200 | 审核后的锚点、多正例、困难负例 / Reviewed anchors, multiple positives, and hard negatives |
| 验证 / Validation | 300 | checkpoint 和超参数选择 / Checkpoint and hyperparameter selection |
| 校准 / Calibration | 100 | 阈值选择与初步校准 / Threshold selection and initial calibration |
| 锁定测试 / Locked test | 400 | 语义完整性、泛化与质量—延迟主结果 / Main completeness, generalization, and quality–latency results |

正式目标共 2,000 个 episode，替代早期模糊的总量范围。
通过统一审核的 pilot 可以计入正式训练集，不能重复计数，也不能进入正式测试。
改写、翻译和口径变体仍属于同一来源组，不增加独立问题数。
比例和数量是规划值；分组边界、审核吞吐和统计精度优先。

The formal target is 2,000 episodes, replacing the earlier approximate total range.
Pilot episodes may count toward formal training after re-review, without double counting or entering final tests.
Paraphrases, translations, and semantic variants remain in their source group and do not increase the independent episode count.
Counts are planning values; group integrity, review capacity, and statistical precision take precedence.

先按数据库及其别名、重复 schema 和重复输入组成分组，再保留训练、验证、校准与测试域。
pilot 只从训练预留组抽取。当前工具只提供初步分组，最终还需人工识别跨来源语义别名。
语义完整性子集应包含指标、时间、过滤、粒度、必要关系和歧义任务；实际比例由试点确定。

Group database aliases, duplicate schemas, and duplicate inputs before reserving training, validation, calibration, and test domains.
Draw pilot examples only from training-reserved groups. Current tooling provides provisional grouping; cross-source semantic aliases require review.
The semantic-completeness subset must include metrics, time, filters, grain, required relationships, and ambiguity. Set proportions after the pilot.

对于基于公开旧数据的测试，记录预训练污染未知的限制。
另外准备目录冻结后新写的问题，并将企业小规模验证列为外部有效性阶段。
无法取得企业样本时，将结论限定在公开及人工扩充数据。

For older public benchmarks, report unknown pretraining exposure.
Add newly authored questions after catalog freezing, and plan a small enterprise validation for external validity.
If enterprise data are unavailable, limit conclusions to public and deliberately enriched data.

## 6. 训练与对照 / Training and controls

| 顺序 / Order | 方法 / Method | 监督 / Supervision |
| --- | --- | --- |
| T0 | BM25、原始 dense、调优 hybrid、hybrid+通用重排 / BM25, original dense, tuned hybrid, hybrid+generic reranker | 不训练或使用原始 checkpoint / No adaptation or original checkpoints |
| T1 | 一个语言适配的双编码器 / One language-appropriate dual encoder | 多正例对比学习与审核难负例 / Standard multipositive contrastive learning and reviewed hard negatives |
| T2 | 通用 cross-encoder / Generic cross-encoder | BCE 或标准排序 / BCE or standard ranking |
| T3 | GLiNER2.5-Decide 与 Laya / GLiNER2.5-Decide and Laya | 相同候选池和证据的 masked BCE / Masked BCE with matched pools and evidence |

T2/T3 是替代重排路径，不串联执行。先比较零适配，再比较冻结编码器和允许编码器更新。
中英文条件要匹配模型的语言支持；不能把语言不适配误判为结构缺陷。
旧路由标签不转作语义检索标签；训练用输入必须经过新的白名单投影。

T2/T3 are alternative reranking paths, not a cascade. Compare unadapted checkpoints, frozen encoders, and encoder adaptation.
Match model language support to the evaluation condition; language mismatch is not an architectural conclusion.
Old routing labels do not become retrieval labels. Training inputs require the new whitelist projection.

同一描述、元数据、候选池和装配器用于可比实验。不要只给新方法增加业务定义。
在开发集选 checkpoint；在校准集选阈值；测试集不用于补正例或改写目录。
采用验证集早停。每个骨干先限制四个开发配置，再对入选方法运行三个随机种子。

Comparable experiments use the same descriptions, metadata, candidate pools, and assembler. Do not enrich only the proposed method.
Use development data for checkpoints and calibration data for thresholds. Never inject test positives or rewrite catalogs from test errors.
Use validation-based stopping. Begin with at most four development configurations per backbone, then run three seeds for shortlisted methods.

## 7. 实验、指标与延迟 / Experiments, metrics, and latency

| 实验 / Experiment | 内容 / Comparison |
| --- | --- |
| E0 | 专家完整上下文与检索上下文，固定 SQL 生成器 / Oracle versus retrieved context with a fixed generator |
| E1 | 强 keyword/dense/hybrid 对照 / Strong keyword, dense, and hybrid baselines |
| E2 | 同来源的表级与语义对象表示；必要依赖装配消融 / Matched-source representations and assembly ablations |
| E3 | embedding 微调、通用重排、GLiNER、Laya / Encoder adaptation and alternative rerankers |
| E4 | 2K/4K/8K token、候选数量、并发和重排开关 / Context budgets, candidate counts, serving load, and reranking |
| E5 | 冻结权重，只更新 C1/C2 索引；新表和旧问题回归 / Index-only arrivals, new-table queries, and old-query regression |

主指标为完整上下文成功率：包含一个审核通过的充分集合、不含冲突、满足预算。
可回答问题上的拒答计为失败。歧义和不可回答问题单列决策指标。
报告候选完整覆盖率、冲突率、下游业务正确率，以及问题组级置信区间。

The primary metric is complete-context success: a reviewed sufficient set, no incompatible definitions, and compliance with the budget.
Abstention on an answerable question counts as failure. Evaluate ambiguity and unanswerability decisions separately.
Report complete candidate coverage, conflict rate, downstream business correctness, and group-level uncertainty.

暂定上下文准备 p95 ≤ 500 ms，预热服务、常驻索引、关闭最终查询缓存，暂以 5 QPS 测试。
另测 1/5/10 QPS、冷启动和目录更新。计入排队、编码、检索、重排与装配。
整体响应还包括 SQL 生成、执行及答案解释，单独报告。
这些目标尚未验证，正式测试前根据业务需要固定。

Provisionally target context-preparation p95 ≤ 500 ms at 5 QPS, with warm services, resident indexes, and result caching disabled.
Also measure 1/5/10 QPS, cold starts, and catalog updates. Include queueing, encoding, retrieval, reranking, and assembly.
Measure total response latency separately, including SQL generation, execution, and explanation.
These are unverified targets to finalize against deployment needs before formal testing.

新增表必须连同必要依赖形成可用快照，不能让未来字段描述进入 C0。
将留出目录分批加入只能称为模拟到达实验。
约千表的公开转换结果不等于真实万表验证；重复表只用于容量测试。

New tables and required dependencies must form a usable snapshot. Future descriptions cannot enter C0.
Staged arrival of held-out catalogs is a simulated arrival experiment.
A roughly thousand-table public conversion is not evidence at ten thousand real tables; duplicates support load tests only.

## 8. 排期与交付 / Schedule and deliverables

| 周 / Week | 工作及决策 / Work and decision |
| --- | --- |
| 1–2 | 固定来源，导入、转换，审核 80 题，建立 E0/E1 / Pin sources, import, convert, review 80 episodes, establish E0/E1 |
| 3 | 完成 240 题 pilot，冻结标注和正式评估协议 / Complete the pilot and freeze annotation and evaluation protocols |
| 4–5 | 扩充审核数据并训练 embedding / Expand reviewed data and adapt the encoder |
| 6 | 比较重排器，决定是否进入线上路径 / Compare rerankers and decide whether to retain one |
| 7–8 | 增量目录、规模、延迟与下游评估 / Catalog-growth, scale, latency, and downstream evaluation |
| 9–10 | 必要补样、多种子结果、集成原型和写作 / Necessary additional samples, repeated runs, integration prototype, and writing |

需要一名研究工程师、兼职集成支持，以及两名业务审核者，每人每周约 10–12 小时。
先测首批审核吞吐，再调整排期。240 题若每题主审 10–15 分钟，需约 40–60 人时，复核另计。
单 GPU 优先；已有集群容量在执行前核实。本次没有启动 GPU 训练或付费 LLM 标注。

Plan for one research engineer, part-time integration support, and two reviewers contributing about 10–12 hours each per week.
Measure initial review throughput before fixing dates. A 10–15 minute primary review per pilot episode implies 40–60 person-hours, excluding second review.
Prefer one GPU initially and verify cluster availability before execution. This preparation launched no GPU training or paid LLM annotation.

目录缺失语义时先修数据；专家上下文仍失败时先检查生成器；强 hybrid 已满足要求时保留简单方案。
论文方法贡献必须由实测增益支持，基准与错误分析可作为另一类成果。

Repair missing semantics before training. Diagnose the generator when oracle context fails. Retain the simpler system when tuned hybrid already meets requirements.
A method contribution requires measured gains; the benchmark and failure analysis can support a different contribution.

数据收集细则见[双语收集协议](data-collection-bilingual.md)，来源与共享边界见[数据可用性计划](data-availability-bilingual.md)。
See the [bilingual collection protocol](data-collection-bilingual.md) and [data availability plan](data-availability-bilingual.md) for execution and sharing details.
