# major-data Specification

## Purpose
TBD - created by archiving change data-foundation. Update Purpose after archive.
## Requirements
### Requirement: 专业实力数据模型

系统 SHALL 定义 `Major` 模型，承载文档的"专业评分"输入数据：
- **就业密度**：岗位数量、招聘频率、城市覆盖度
- **薪资分布**：MUST 用 P25（低）/P50（中位）/P75（高）三分位，而非平均值
- **门槛难度**：是否要求英语/数学/证书/考研
- **上升空间**：能否转管理岗/自由职业/跨行业

模型 SHALL 继承来源追溯基类。

#### Scenario: 查询专业薪资分布

- **WHEN** 查询"日语"专业
- **THEN** 返回 P25/P50/P75 三个薪资分位，而非单一平均值

#### Scenario: 门槛要求结构化

- **WHEN** 查询某专业的门槛难度
- **THEN** 返回各门槛项的布尔/枚举（如 requires_english: true）

### Requirement: 专业种子数据

系统 MUST 提供至少 15 个专业种子数据，覆盖文科（含日语/国际经济与贸易/历史等文档重点方向）与理工科。薪资分布 SHALL 标注来源（BOSS/智联等公开报告量级）、采集时间、置信度，附"待爬虫校准"。

#### Scenario: 种子专业含薪资三分位

- **WHEN** 加载专业种子后查询任一专业
- **THEN** 返回完整 P25/P50/P75 与就业密度、门槛、上升空间字段

#### Scenario: 用平均值代替三分位被拒绝

- **WHEN** 某专业种子只填了平均薪资而无 P25/P50/P75
- **THEN** 校验失败（强制三分位分布）

