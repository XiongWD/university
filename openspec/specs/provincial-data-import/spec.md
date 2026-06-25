# provincial-data-import Specification

## Purpose
TBD - created by archiving change provincial-score-data. Update Purpose after archive.
## Requirements
### Requirement: 公开数据集导入器

系统 MUST 提供数据导入器 `dataset_importer`，从公开高考数据集（CSV/JSON 结构化格式）解析并入库省控线与一分一段表。导入 SHALL 复用 Repository 的幂等 upsert 机制（重复导入不产生重复记录）。

导入器 MUST 对导入数据做合理性校验：
- 省控线：分数非负、必填字段（省/年/科类）存在
- 一分一段表：累计位次单调性（高分位次小）
- 校验失败的记录 SHALL 被拒绝并报告（文件、记录标识、原因），不静默跳过

#### Scenario: 导入 CSV 省控线

- **WHEN** 用合法 CSV 数据集导入河南2024省控线
- **THEN** 数据入库，幂等（再次导入数量不变），每条带来源字段

#### Scenario: 导入失败数据被拒绝

- **WHEN** 导入的一分一段表数据存在位次单调性违反
- **THEN** 导入器拒绝并报告具体记录，不静默跳过

#### Scenario: 增量更新

- **WHEN** 数据集新增 2025 年数据后再次导入
- **THEN** 仅新增 2025 年记录，历史记录不变

### Requirement: 数据清洗与来源标注

导入器 MUST 对原始数据集做清洗：类型转换（字符串→数值）、去重（按省/年/科类主键）、缺失关键字段剔除。每条导入记录 MUST 标注来源（数据集名称/版本）、as_of（数据所属年份）、confidence（公开数据集建议 0.7-0.9）。

#### Scenario: 脏数据清洗

- **WHEN** 原始数据集含重复行或类型错误（如分数为字符串"514"）
- **THEN** 导入器清洗后入库（重复去重、类型转换），数据合法

#### Scenario: 来源标注完整

- **WHEN** 导入任意省控线/一分一段表记录
- **THEN** 入库记录含 source（数据集名）、as_of（年份）、confidence 字段

