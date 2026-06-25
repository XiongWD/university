## Why

产品的核心价值是"真实志愿填报流程"——用户打开产品第一件事就是输入分数筛选可报学校。而高考录取本质是**按位次录取**，不是按分数：同一分数在不同年份含金量不同（试卷难度波动），但位次相对稳定。因此做"位次法志愿筛选"必须先有**省控线**（决定能否报对应批次）和**一分一段表**（分数↔位次映射）这两组省级基础数据。

当前 `admission-data-schema`（已归档）只定义了院校录取记录的 schema 与示例，**缺少这两组决定位次法能否成立的核心数据**。本 change 建立省级分数数据底座，是后续志愿筛选引擎（change⑤）的硬前置依赖。

## What Changes

- 新增**省控线** `ProvincialControlLine` 数据模型：省份、年份、科类（河南=文/理，广东=物理类/历史类）、各批次线（特殊类型招生线、一本线、二本线、专科线）。决定"分数能否报对应批次"。
- 新增**一分一段表** `ScoreRankTable` 数据模型：省份、年份、科类、分数→累计位次的映射（1 分一档，官方精度）。位次法核心数据，用于"今年分数→今年位次"换算。
- 新增**公开数据集导入器**：从公开高考数据集（GitHub 结构化数据集 / 省考试院公开 PDF 转结构化）导入河南、广东两省近 3 年省控线与一分一段表。
- 扩展**查询 API**：按省份/年份/科类查询省控线与一分一段表，支持"给定分数查位次"与"给定位次查分数"双向查询。
- 复用 data-foundation 的 **SourcedRecord 来源追溯基类**，所有数据带来源（数据集名/发布年）、采集时间、置信度。
- 覆盖**两种高考模式**：河南传统文理分科 + 广东新高考 3+1+2（物理类/历史类）。

## Capabilities

### New Capabilities

- `provincial-control-line`: 省控线数据模型与查询（各批次分数线，决定批次门槛）
- `score-rank-table`: 一分一段表数据模型与查询（分数↔位次双向映射，位次法基础）
- `provincial-data-import`: 公开数据集导入器（河南/广东近3年，含来源追溯）

### Modified Capabilities

- `data-foundation-api`: 扩展 FastAPI 访问层，新增省控线与一分一段表查询端点（复用已归档的 data-foundation-api 能力的查询机制）

## Impact

- **代码**：在 `app/models/` 新增 provincial.py（省控线+一分一段表 Domain/Table）；在 `app/repositories/mappers.py` 扩展映射；在 `app/api/routers/` 新增 provincial.py router；在 `app/loader/` 扩展种子/导入器
- **数据**：新增 `data/seed/provincial/*.yaml` 种子（河南/广东近3年省控线+一分一段表）+ 公开数据集导入脚本
- **依赖**：复用现有 pydantic/sqlmodel/fastapi；导入器可能新增数据处理依赖（如 PDF 解析，若数据源为 PDF）
- **后续依赖**：change ④b（院校录取数据）需对照省控线定批次；change⑤（志愿引擎）依赖一分一段表做位次换算
- **合规**：数据标注"基于历史数据模拟"，省控线/一分一段表为官方公开数据，confidence 可较高（≥0.8）
