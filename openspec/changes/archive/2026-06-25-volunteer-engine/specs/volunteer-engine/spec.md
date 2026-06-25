# volunteer-engine Specification

## Purpose
志愿填报引擎：根据考生分数用位次法筛选可报学校，生成冲稳保三档完整志愿表。承接 data-foundation + provincial-score-data 底座，是三层架构第②层 decision-engine 的志愿筛选核心子能力，直接服务高考志愿填报。
## Requirements
### Requirement: 分数位次换算（含缺失插值）

引擎 SHALL 提供 `convert_score_to_rank`：给定一分一段表与考生分数，返回今年累计位次。表中存在精确分数时返回精确位次；不存在时按相邻分数线性插值返回近似位次（不返回 None，除非表为空）。

复用 rank_query.score_to_rank 做精确匹配，避免重复实现位次逻辑。

#### Scenario: 精确分数查位次

- **WHEN** 一分一段表含 582分→累计位次37744，查询582分
- **THEN** 返回 37744

#### Scenario: 缺失分数线性插值

- **WHEN** 一分一段表含 605分→19000 和 582分→37744，查询 590分（表中无）
- **THEN** 返回 19000 与 37744 之间的插值位次

#### Scenario: 空表返回 None

- **WHEN** 一分一段表为空，查询任意分数
- **THEN** 返回 None

### Requirement: 等效位次跨年折算

引擎 SHALL 提供 `equivalent_rank`：给定今年位次与今年/历史考生总量，返回折算到历史年份的等效位次。公式：`历史等效位次 = 今年位次 × (历史考生总量 / 今年考生总量)`。无历史考生数据时返回原位次（降级，不阻断）。

解决不同年份考生总量不同导致的位次不可直接比较。

#### Scenario: 按考生总量比例折算

- **WHEN** 今年位次30000、今年40万考生、历史50万考生
- **THEN** 等效位次 = 30000 × 500000/400000 = 37500

#### Scenario: 无历史数据降级

- **WHEN** 历史考生总量为 None
- **THEN** 返回原位次 30000

### Requirement: 冲稳保三档分档

引擎 SHALL 提供 `classify_strategy`：根据考生位次与学校录取位次的比值分冲稳保。
- ratio = school_rank / student_rank
- ratio < 0.95（学校位次显著优于考生，更难录）→ 冲
- 0.95 ≤ ratio ≤ 1.05（接近）→ 稳
- ratio > 1.05（学校位次显著低于考生，更容易录）→ 保

位次比是位次法的天然度量，不受试卷难度/总分波动影响。

#### Scenario: 学校更难录→冲

- **WHEN** 考生位次30000、学校录取位次25000（ratio 0.83 < 0.95）
- **THEN** 分档为 冲

#### Scenario: 位次接近→稳

- **WHEN** 考生位次30000、学校录取位次29500（ratio 0.98）
- **THEN** 分档为 稳

#### Scenario: 学校更容易录→保

- **WHEN** 考生位次30000、学校录取位次40000（ratio 1.33 > 1.05）
- **THEN** 分档为 保

### Requirement: 录取概率估算

引擎 SHALL 提供 `estimate_probability`：基于位次比估算录取概率（0-1）。ratio=1（完全匹配）→ 高概率（约0.9）；ratio 越小（越难）概率越低；ratio 越大（越容易）趋近 0.99。每条估算 SHALL 含 `basis` 字段说明估算依据（如"位次比 0.46"），透明化不误导用户。

#### Scenario: 完全匹配高概率

- **WHEN** 考生位次30000、学校录取位次30000（ratio 1.0）
- **THEN** 概率 ≥ 0.85

#### Scenario: 冲的志愿低概率

- **WHEN** 考生位次30000、学校录取位次20000（ratio 0.67，冲）
- **THEN** 概率 < 0.5

### Requirement: 志愿表生成（冲稳保完整表）

引擎 SHALL 提供 `generate_volunteer_table`：输入考生画像 + 录取数据 + 一分一段表 + 科类 + 数据年份，生成完整志愿表。

表 SHALL 含：考生分数、今年位次、等效位次、科类、数据年份、冲/稳/保三档学校列表、数据来源说明（标注"基于历史数据预测"）。

生成逻辑：
1. 过滤 track/年份/省份匹配的录取数据（剔除不匹配的）
2. 逐校分档（classify_strategy）；冲的志愿若位次低于考生 40%（SPRINT_FLOOR）则不列入（几乎录不到）
3. 按风险偏好（StudentProfile.risk_preference）配额裁剪各档：冲型=6冲3稳2保、稳型=2冲3稳5保、中型=3冲4稳3保
4. 各档内按录取概率降序排列

#### Scenario: 端到端分档

- **WHEN** 河南543分理科考生，6 校2024录取数据
- **THEN** 河南大学（位次37744）→冲，河南师范大学（78624）→稳，河南农业大学（114271）→保

#### Scenario: track 不匹配的数据被剔除

- **WHEN** 混入文科录取数据，考生为理科
- **THEN** 文科数据不出现在任何档

#### Scenario: 风险偏好改变各档数量

- **WHEN** 同一考生分别用"稳"和"冲"偏好
- **THEN** 稳型保档数量 ≥ 冲型保档数量

#### Scenario: 无录取数据返回空表

- **WHEN** 录取数据为空
- **THEN** 三档均为空列表，不报错

### Requirement: 录取数据 schema 支持新高考

AdmissionRecord SHALL 支持新高考院校专业组：新增可选字段 `major_group`（专业组代码）与 `subject_requirement`（选科要求如"物理+化学"）。老高考数据这两个字段为空，兼容并存。Batch 枚举 SHALL 包含"本科批"（新高考合并批次）与"专科"。

#### Scenario: 新高考专业组数据

- **WHEN** 构造 AdmissionRecord 含 major_group="205"、subject_requirement="物理"
- **THEN** 实例化成功，字段可读写

#### Scenario: 老高考数据兼容

- **WHEN** 构造老高考 AdmissionRecord（major_group=None）
- **THEN** 实例化成功

### Requirement: 志愿填报 API 端点

系统 SHALL 提供：
- `POST /api/v1/volunteer/recommend`：输入考生画像（分数/科类/风险偏好/省份/数据年份）→ 返回冲稳保志愿表
- `GET /api/v1/volunteer/admissions`：录取数据查询，支持 province/track/year/school 过滤 + min_score/max_score 分数范围筛选（用于按分数筛选可报学校）

#### Scenario: 推荐志愿表

- **WHEN** POST recommend 河南理科543分
- **THEN** 返回含 sprint/stable/safe 三档的志愿表，含数据来源说明

#### Scenario: 按分数范围筛选学校

- **WHEN** GET admissions min_score=530&max_score=600
- **THEN** 仅返回 min_score 在 [530,600] 区间的学校

#### Scenario: 无数据返回空

- **WHEN** 查询不存在的省份/学校
- **THEN** 返回空列表，HTTP 200
