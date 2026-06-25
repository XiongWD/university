# Brainstorm Summary

- Change: provincial-score-data
- Date: 2026-06-25

## 确认的技术方案

技术栈：复用 data-foundation（Python 3.13 + FastAPI + Pydantic v2 + SQLModel + SQLite + YAML）。本 change 在其架构上新增省级分数数据。

架构：复用 data-foundation 的双模型（Domain Pydantic 嵌套 + Table SQLModel 拍平）+ Repository 映射 + SourcedRecord 来源基类。

## brainstorming 已确认的设计决策

1. **数据源分工**（已确认）
   - 一分一段表：从 GitHub 公开数据集 CSV 导入（`sdgedfegw/Gaokao-score-distribution`，含 1996-2024 全国高考分段表，覆盖河南/广东/文理/物理历史）
   - 省控线：手编 YAML 种子（数据量小、官方可查，每省每年每科类 1 条）
   - 各取所长：大数据量走 CSV 导入，小数据量走手编

2. **导入时机：运行时导入**（已确认）
   - CSV 作为依赖随项目分发（`data/datasets/` 目录）
   - FastAPI 启动时若一分一段表数据缺失，触发导入器从 CSV 加载
   - 导入器需健壮：CSV 缺失/格式异常时降级为空数据集（不阻断启动）

3. **一分一段表存储：分段记录**（design D1）
   - 多条 ScoreRankEntry（score/count_at/cumulative_rank），非单条 JSON
   - 可索引、支持双向查询（分数↔位次）

4. **Open Questions 默认决策**（合理默认，无需用户确认）
   - 广东新高考合并批次：支持 undergrad_batch（本科批），按省差异存在
   - 一分一段表双字段：count_at（该分人数）+ cumulative_rank（累计位次）都含
   - 特殊类型招生线：统一 special_line 字段，各省命名差异在 note 标注

## 关键取舍与风险

| 取舍/风险 | 决策/缓解 |
|-----------|-----------|
| 运行时依赖外部 CSV | CSV 随项目分发（data/datasets/）；导入器降级处理（CSV 缺失→空集不阻断） |
| 一分一段表数据量大（数千条） | 分段记录+索引，SQLite 承载；按省/年/科类分区查询 |
| 公开数据集质量/时效 | 每条带 source/as_of/confidence≥0.8；导入器做位次单调性校验拦截脏数据 |
| 两种高考模式字段差异 | 科类 track 自由字符串（文/理 vs 物理/历史类）；批次线可选 |
| 合规（数据时效） | as_of 记录数据年份；标注"历史数据，非当年实时" |

## 测试策略

分层测试（复用 data-foundation 模式）：
- models：省控线（批次可选/分数非负）、一分一段表（位次单调性校验）、双字段完整
- 查询逻辑：分数→位次精确匹配、位次→分数就近匹配
- 导入器：CSV 解析、清洗（去重/类型转换）、幂等、脏数据拒绝、CSV 缺失降级
- API：省控线查询、分数查位次、位次查分数、空结果不报错、来源字段返回
- 来源追溯链路：CSV/种子→Domain→DB→API 来源不丢

## Spec Patch

无（design 阶段未发现 delta spec 需修改，spec 已覆盖确认的决策）。
