# provincial-control-line Specification

## Purpose
TBD - created by archiving change provincial-score-data. Update Purpose after archive.
## Requirements
### Requirement: 省控线数据模型定义

系统 SHALL 定义 `ProvincialControlLine` 数据模型，承载各省份各批次录取控制分数线。字段 MUST 包含：省份、年份、科类（track 自由字符串，支持"文科"/"理科"/"物理类"/"历史类"）、批次控制线集合（special_line 特殊类型招生控制线、first_batch 一本线、second_batch 二本线、undergrad_batch 本科批[新高考合并批次]、junior_college 专科线）。各省仅需填其适用的批次线（如广东新高考无一本/二本，用本科批）。

模型 SHALL 继承来源追溯基类（source/as_of/confidence/note）。省控线为官方公开数据，confidence 建议 ≥ 0.8。

#### Scenario: 构造河南传统文理科控线

- **WHEN** 构造 ProvincialControlLine（省份河南、年份2024、科类理科、一本线514、二本线400）
- **THEN** 实例化成功，各批次线可读取，来源字段存在

#### Scenario: 构造广东新高考省控线

- **WHEN** 构造 ProvincialControlLine（省份广东、年份2024、科类物理类、特殊类型招生线539、本科批442）
- **THEN** 实例化成功，本科批存在，一本/二本字段可为空

#### Scenario: 缺省份或年份被拒绝

- **WHEN** 构造省控线时省略省份或年份
- **THEN** 校验失败并报错

#### Scenario: 分数为负被拒绝

- **WHEN** 某批次线填负数（如 -1）
- **THEN** 校验失败

### Requirement: 省控线种子数据覆盖两省三年

系统 MUST 提供河南与广东两省近 3 年（如 2022-2024）的省控线种子数据，覆盖河南文科/理科与广东物理类/历史类。每条 MUST 标注来源（数据集名/官方发布）、as_of（数据所属年份）、confidence（官方数据≥0.8）。

#### Scenario: 种子省控线可查询

- **WHEN** 加载种子后查询河南2024理科省控线
- **THEN** 返回完整批次线（一本/二本/专科等），含来源字段

#### Scenario: 两省批次结构差异体现

- **WHEN** 查询河南2024 vs 广东2024 省控线
- **THEN** 河南有一本/二本线，广东有本科批（无一本二本），结构差异正确反映

