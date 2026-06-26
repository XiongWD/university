---
status: draft
role: technical-design
topic: henan-2026-advisory-upgrade
created: 2026-06-26
---

# Design Doc: henan-2026-advisory-upgrade

本设计用于把当前「专业推荐」从规则样机升级为以河南 2026 为主的真实志愿辅助能力。目标不是给出绝对录取承诺，而是在 2026 一分一段、2026 省控线、2025 同制度录取数据、招生章程和院校专业组规则的约束下，输出可解释、可核验、可回归测试的推荐结果。

## 1. 目标

- 补齐河南 2026 志愿推荐所需的数据结构和数据导入链路。
- 严格执行 3+1+2 选科资格，尤其是理工农医类常见的物理+化学要求。
- 让 `data_year` 和 `risk_preference` 成为真实推荐策略输入，而不是仅影响展示。
- 增加本科线/专科线判断，低分段输出本科冲刺与专科稳妥方案。
- 输出每条推荐的证据链：位次、批次线、资格原因、录取档位、数据粒度、数据来源和置信度。

## 2. 非目标

- 不爬取或承诺覆盖全国所有省份；本阶段以河南为主。
- 不输出伪精确录取概率；用档位和区间解释风险。
- 不绕过官方数据缺失；缺 2026 录取结果时必须标注使用 2025 同制度数据作为基准。
- 不重新引入回本、ROI、人生路径等 narrative-policy 禁止表达。

## 3. 外部依据与数据来源

开发必须只把可追溯数据写入种子或数据集。优先级：

1. 河南省教育考试院：省控线、一分一段、志愿填报与录取规则。
   - 官方入口：https://www.haeea.cn/
2. 阳光高考平台：院校招生章程、院校信息、专业信息。
   - 官方入口：https://gaokao.chsi.com.cn/
3. 院校本科招生网：2026 招生章程、河南分省分专业计划、专业组选科要求。
4. 当前项目已导入数据：`data/datasets/henan_2026_score_rank.csv`、`data/seed/provincial/control_line/henan.yaml`、`data/seed/admissions/admissions.yaml`、`data/seed/admission_offerings/admission_offerings.yaml`。

每条新增数据必须包含：

- `source_name`
- `source_url`
- `as_of`
- `confidence`
- `data_granularity`: `official_plan` / `official_admission` / `official_rule` / `third_party_estimate` / `manual_review`
- `review_status`: `verified` / `needs_review`

## 4. 数据模型

新增或扩展以下模型，优先放在现有招生相关模块中，避免散落。

### 4.1 `ProgramGroupRule`

表示一个院校专业组在河南的可报资格。

字段：

- `school`
- `province`: 招生省份，固定用于计划投放地，如 `河南`
- `year`
- `batch`
- `major_group_code`
- `major_group_name`
- `primary_subject_requirement`: `物理` / `历史` / 空
- `elective_subject_rule`: `{"require": ["化学"], "any_of": []}`
- `accepted_exam_languages`
- `required_exam_language`
- `subject_score_rules`
- `included_majors`
- `source_name`
- `source_url`
- `as_of`
- `confidence`
- `review_status`

### 4.2 `EnrollmentPlan`

表示某院校、某省份、某年份的专业计划。

字段：

- `school`
- `source_province`: 考生生源地，如 `河南`
- `year`
- `major_group_code`
- `major_name`
- `plan_count`
- `tuition`
- `school_system_years`
- `batch`
- `subject_requirement_text`
- `source_name`
- `source_url`
- `as_of`
- `confidence`
- `review_status`

### 4.3 `BatchLineDecision`

引擎内部结构，用于低分段判断。

字段：

- `score`
- `rank`
- `undergrad_line`
- `junior_college_line`
- `distance_to_undergrad_line`
- `batch_position`: `above_undergrad` / `near_undergrad` / `below_undergrad` / `junior_college_only`
- `recommendation_policy_note`

## 5. 推荐链路

主链路仍从 `POST /api/v1/volunteer/advisory` 进入，但需要拆成更清晰的内部阶段。

1. 输入标准化：
   - 省份默认河南。
   - `data_year` 默认 2026。
   - `risk_preference`: `冲` / `中` / `稳`。
   - 物理/历史和再选科目必须标准化为中文枚举。

2. 批次线判断：
   - 先查询河南 2026 对应科类省控线。
   - 若低于本科线，普通本科推荐必须进入“本科冲刺风险”而非安全推荐。
   - 若低于本科线较多，同时输出专科稳妥建议。

3. 资格过滤：
   - 首选科目不符直接不可报。
   - 再选科目不符直接不可报。
   - 应试语种、英语单科、外语单科、数学单科按招生章程硬过滤。
   - 对理工农医强相关专业组，若数据中缺少化学要求来源，标为 `needs_review`，不得作为安全推荐。

4. 位次预测：
   - 当前年分数转当前年位次。
   - 使用同制度历史录取位次作为 baseline。
   - 2026 无录取结果时，结果说明必须写明“录取数据基于 2025 年同制度位次参考”。

5. 冲稳保分桶：
   - `冲`: 学生位次略弱于历史最低投档位次，且满足资格。
   - `稳`: 学生位次接近或略优于历史最低投档位次。
   - `保`: 学生位次明显优于历史最低投档位次。
   - `risk_preference` 影响各桶位次区间和数量比例，而不是事后裁剪。

6. 专业方向排序：
   - 仍使用 `market_value × student_fit`。
   - 数学风险只作用于数学/统计/计算/计量/工程强相关专业。
   - 对历史类高分段必须补齐更高层级院校，否则输出“数据不足，不做高分段学校推荐”。

7. 结果解释：
   - 每个推荐项必须显示或返回：可报资格、录取档位、位次依据、数据年份、数据粒度、来源、置信度、组内专业数据是否充足。

## 6. API 变化

`POST /api/v1/volunteer/advisory` 请求体保留现有字段，新增或正式支持：

- `data_year`
- `risk_preference`
- `source_province`: 可选，本阶段默认等于 `province`，为目标评估功能预留。

响应新增字段：

- `batch_line_decision`
- `data_sources`
- `review_warnings`
- `recommendation_policy`

兼容要求：

- 旧前端字段仍可提交。
- 旧响应字段 `major_directions`、`school_options`、`ineligible_options`、`budget_summary`、`notes` 不移除。

## 7. 验收标准

必须通过以下样本：

- 河南历史 460：低于/接近本科线时，不得把民办本科列为“保”；必须提示本科线风险并给专科稳妥方案。
- 河南历史 480：可给省内外地市公办冲刺、省内民办兜底；英语限报专业对日语考生必须不可报。
- 河南历史 520：不得全是“保”；必须有高分段更合适的冲/稳候选，或明确说明数据覆盖不足。
- 河南物理 540，不选化学：计算机、临床、强工科不得进入普通推荐；若数据缺失必须 `needs_review`。
- 河南物理 540，选化学但数学 70：可报资格与专业学习风险分开；计算机方向不得作为高适配推荐。
- 河南物理 620，物化、数学/英语强：郑大/河大等可进入推荐，但必须区分冲稳保和专业组数据粒度。

测试要求：

- `pytest tests/api/test_advisory_api.py --basetemp .pytest-tmp`
- `pytest tests/engine/test_advisory_engine.py --basetemp .pytest-tmp`
- 新增河南 2026 样本回归测试文件。
- `npm.cmd run build`。

## 8. 风险

- 2026 年最终录取结果尚未产生，不能把预测写成事实。
- 第三方估计数据只能作为低置信度参考，不得覆盖官方数据。
- 招生章程与分省计划可能在不同页面发布，必须记录来源粒度。
- 物化要求不能靠专业名称猜测覆盖，缺来源时必须触发人工复核。

