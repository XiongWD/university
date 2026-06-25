# admission-data-schema Specification

## Purpose
TBD - created by archiving change data-foundation. Update Purpose after archive.
## Requirements
### Requirement: 录取数据 Schema 定义（仅结构，不批量入库）

系统 SHALL 定义 `AdmissionRecord` 数据模型，描述高校历年录取数据结构，用于后续"根据考生分数筛选可报考大学"。字段 MUST 包含：学校、专业、省份、年份、科类（文/理/新高考选科组合）、最低录取分、最低录取位次、平均分、批次（一本/二本/提前批）。

本 change 仅定义 schema 与少量手编示例（3–5 校 × 2 省），不批量入库。批量历年分数线/位次数据归属后续独立 change（爬虫或公开数据集导入）。

模型 SHALL 继承来源追溯基类。

#### Scenario: 构造录取记录示例

- **WHEN** 用合法字段构造一条 AdmissionRecord
- **THEN** 实例化成功，含学校/专业/省份/年份/分数/位次

#### Scenario: 缺关键字段被拒绝

- **WHEN** 构造 AdmissionRecord 时省略省份或年份
- **THEN** 校验失败

### Requirement: 录取数据原始查询接口

系统 MUST 提供录取数据的**原始查询**接口：`GET /api/v1/admissions?province={省}&track={科类}&school={学校}`，仅返回匹配的原始录取记录，不做任何"按考生分数筛选可报考学校"的决策性计算。

**边界**：本层只提供原始数据存取。"根据考生分数筛选可报考大学、计算录取概率"属于决策逻辑，归属 decision-engine（change②）。本层接口 SHALL 只做字段匹配查询（省份/科类/学校等过滤），不做分数区间推断或院校推荐。

#### Scenario: 按省份科类原始查询

- **WHEN** GET /api/v1/admissions?province=河南&track=理科
- **THEN** 返回该省理科的原始录取记录列表（示例数据或空），每条含来源字段，不做分数筛选

#### Scenario: 空数据集查询不报错

- **WHEN** 录取数据表仅有示例数据，用户按某省查询
- **THEN** 接口正常返回（示例匹配或空列表），不抛异常

#### Scenario: schema 验证可用

- **WHEN** 后续 change 批量导入真实录取数据
- **THEN** 本 change 定义的 schema 可直接承接，无需重新建模

