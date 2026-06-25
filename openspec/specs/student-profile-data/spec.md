# student-profile-data Specification

## Purpose
TBD - created by archiving change data-foundation. Update Purpose after archive.
## Requirements
### Requirement: 考生画像数据模型定义

系统 SHALL 定义 `StudentProfile` 数据模型，承载"根据考生情况模拟填报志愿"的完整输入结构。模型 MUST 包含以下字段：总分（数值）、省份（决定分数线基准）、偏科科目真实分数（`subject_scores: dict[str,int]`，键为科目名如"数学"/"英语"/"理综"，值为该科高考真实分数）、小语种能力（语种 + 等级如日语 N2/N1）、家庭体制资源（6 个布尔位）、性别、个人兴趣（标签列表）、强项（标签列表）、风险偏好（稳/中/冲三档枚举）。

家庭体制资源 MUST 用 6 个布尔字段表达：`has_govt_resource`（体制内/公务员/事业编）、`has_medical_resource`（医生/医疗系统）、`has_education_resource`（教师/教育系统）、`has_finance_resource`（银行/金融/证券）、`has_law_resource`（法律/司法系统）、`has_business_resource`（企业主/商业/外贸）。

模型 SHALL 继承来源追溯基类，包含 `source`/`as_of`/`confidence` 字段，因为画像输入本身也是需要记录的"数据"。

#### Scenario: 构造完整考生画像

- **WHEN** 用合法字段构造一个 StudentProfile（如总分 450、省份河南、subject_scores={数学:120,英语:75}、has_education_resource=true）
- **THEN** 模型实例化成功，所有必填字段已填充，来源字段存在

#### Scenario: 缺失必填字段被拒绝

- **WHEN** 构造 StudentProfile 时省略省份或总分
- **THEN** 校验失败并抛出明确错误，指出缺失字段

#### Scenario: 风险偏好取值约束

- **WHEN** 风险偏好传入非法值（如 "unknown"）
- **THEN** 校验失败，仅接受稳/中/冲三档之一

### Requirement: 偏科分数支持文理两种模式

系统 MUST 支持两种偏科结构：传统文理分科（语文/数学/英语/文综 或 语文/数学/英语/理综）与新高考选科。模型 SHALL 用足够灵活的结构承载，不丢失任何一科分数。

#### Scenario: 传统理科考生

- **WHEN** 录入语文/数学/英语/理综四科分数
- **THEN** 模型正确存储并可按单科查询

#### Scenario: 新高考选科考生

- **WHEN** 录入语文/数学/英语 + 三门选科分数
- **THEN** 模型正确存储三门选科及其分数

