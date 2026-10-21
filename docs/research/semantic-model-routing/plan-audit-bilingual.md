# 研究方案审核记录 / Research Plan Audit

日期 / Date：2026-10-10。审核方式 / Review method：同一助手分别进行方法、数据和可行性检查；不是独立同行评审 / Separate methods, data, and feasibility passes by one assistant; not independent peer review.

结论：可以开始公开数据收集和 pilot 审核。当前材料不满足正式训练或企业有效性结论的条件。
Decision: proceed with public-source intake and pilot review. Current material is not ready for formal training or enterprise-effectiveness claims.

后续审核已发现并修正抽样简单化、pilot 缺少内部开发划分和长元数据截断问题。
现有 240 条平衡审核包、审核导出验证器及 embedding 训练脚本；真实可训练样本仍为零。
具体证据及执行步骤见[最新审核与训练准备记录](pilot-readiness-bilingual.md)。

The follow-up audit corrected simple-question sampling bias, missing internal pilot development splits, and long-metadata truncation.
A balanced 240-episode package, review/export validator, and embedding training script now exist. Source-data training eligibility remains zero.
See the [current readiness audit and runbook](pilot-readiness-bilingual.md) for evidence and commands.

| 审核问题 / Finding | 处理 / Resolution | 剩余工作 / Remaining work |
| --- | --- | --- |
| 研究贡献易退化为普通 schema 检索 / Contribution could reduce to ordinary schema retrieval | 主指标改为完整且一致的业务上下文，并保留强 hybrid 对照 / Prioritize complete, consistent context against tuned hybrid | 语义子集与企业验证 / Semantic subset and enterprise validation |
| SQL 不能唯一确定业务口径 / SQL does not uniquely establish business semantics | 区分结构转换与独立语义扩充 / Separate structural conversion and semantic enrichment | 审核指标、粒度和时间规则 / Review metrics, grain, and time |
| 从测试 SQL 生成目录会泄漏答案 / Catalogs authored from test SQL leak answers | 冻结目录后再标注问题，分离作者与审核角色 / Freeze catalogs before annotation; separate roles | 记录目录冻结时间及 authoring 输入 / Log freeze time and authoring inputs |
| 原始数据隐含已知数据库 / Source questions assume a known database | oracle database ID 不进入模型输入；增加全目录歧义审核 / Exclude oracle IDs and review pooled-catalog ambiguity | 人工确认合法解释 / Confirm valid interpretations |
| 多个表不是多个互斥类别 / Multiple tables are not mutually exclusive classes | 多正例召回、独立候选评分、集合完整性检查 / Multipositive retrieval, candidate scoring, set checks | 合法替代集合标注 / Annotate alternative sets |
| pilot 可能消耗评估域 / Pilot could expose evaluation domains | 分组预留后只抽训练域 / Sample only training-reserved groups | 人工别名合并，最终冻结 / Semantic alias review and final freeze |
| 未审核和不相关混为一谈 / Unknown confused with negative | 标签保持 null，training_eligible=false / Keep labels null and ineligible | 正负例双向审核 / Review positive and negative judgments |
| 格式合法被当作业务正确 / Schema validity mistaken for correctness | 分开 JSON Schema、引用、执行、业务审核 / Separate schema, references, execution, semantic review | 物理 DDL 与 SQL 执行 / Physical DDL and SQL execution |
| 把所有血缘当作可连接关系 / Lineage mistaken for valid joins | 不生成未知 PK/FK；复合键不拆成错误单列关系 / No invented keys or invalid composite-key decomposition | 检查连接基数与聚合重复 / Check cardinality and fanout |
| 500 ms 被误作整体回答时间 / 500 ms mistaken for total response time | 检索上下文与整体时延分别计量 / Separate context preparation from total response | 生产负载和各阶段实测 / Measure actual serving load and stages |
| 公开数据被假定无许可差异 / Public sources treated as uniformly licensed | 每源记录许可；发现 LiveSQLBench 声明冲突 / Record per-source terms and the LiveSQLBench conflict | 发布前整合派生条款 / Reconcile derivative terms before release |
| 万表规模或零污染被提前宣称 / Premature scale or contamination claims | 当前 1,259 对象仅为转换统计；预训练暴露未知 / Conversion counts only; pretraining exposure unknown | 真实规模与新写问题 / Real scale and newly authored questions |

实施证据：已准备固定版本下载与构建工具、来源注册表和审核模板。
当前批次导入 13,601 个来源问题，生成 209 个结构草稿，准备 240 条待审核记录。
一个缺失列名的 BIRD 字段被隔离；没有为其虚构列名。

Implementation evidence: pinned acquisition/build tooling, a source registry, and a review template are prepared.
The current batch imports 13,601 source questions, generates 209 structural drafts, and queues 240 records for review.
One BIRD field with a missing column name was quarantined rather than repaired with an invented name.

首个验收点：审核 80 条问题，并提交错误类型、实际审核工时、可确认的语义定义和歧义比例。
若目录缺失语义是主要原因，优先补数据；若强 hybrid 已满足要求，保留简单部署方案。

First gate: review 80 episodes and report error types, actual review effort, supported definitions, and ambiguity rates.
Improve the data when missing semantics dominate; retain the simpler deployment when tuned hybrid already meets requirements.
