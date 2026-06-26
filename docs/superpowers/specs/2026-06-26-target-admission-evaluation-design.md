---
status: draft
role: technical-design
topic: target-admission-evaluation
created: 2026-06-26
---

# Design Doc: target-admission-evaluation

本设计新增“目标院校 + 专业（可选）评估”能力。用户输入考生生源地、分数、3+1+2 选科、外语/单科成绩、目标院校和可选目标专业后，系统判断是否可报、投档成功风险、目标专业录取风险、调剂风险和缺失数据。

## 1. 目标

- 支持按考生生源地筛选目标院校在该省的招生计划。
- 支持目标院校必填、目标专业可选。
- 获取和结构化 2026 招生章程、分省分专业计划、院校专业组、选科要求。
- 区分“能投进专业组”和“能录取目标专业”。
- 输出成功率档位、核心证据、不可报原因、数据缺口和来源。

## 2. 非目标

- 不保证所有院校 2026 数据已经发布；缺数据时必须明确标注。
- 不输出精确百分比；使用 `高 / 中高 / 中 / 低 / 不可报 / 数据不足`。
- 不自动替用户填报志愿。
- 不把外省总计划误认为河南计划。

## 3. 新 API

新增：

`POST /api/v1/target/evaluate`

请求体：

- `source_province`: 考生生源地，如 `河南`
- `target_school`
- `target_major`: 可选
- `data_year`: 默认 2026
- `total_score`
- `primary_subject`: `物理` / `历史`
- `elective_subjects`
- `exam_foreign_language`
- `foreign_language_score`
- `math_score`
- `english_actual_level`
- `accept_adjustment`: 是否服从专业调剂

响应体：

- `target_school`
- `target_major`
- `source_province`
- `eligibility`
  - `eligible`
  - `blocked_reasons`
  - `review_warnings`
- `group_admission`
  - `risk_band`: `高` / `中高` / `中` / `低` / `不可报` / `数据不足`
  - `basis`
  - `student_rank`
  - `baseline_rank`
  - `data_year_used`
  - `confidence`
- `major_admission`
  - `risk_band`
  - `target_major_available`
  - `plan_count`
  - `basis`
  - `adjustment_risk`
- `sources`
- `missing_data`
- `recommendation_summary`

## 4. 数据模型

### 4.1 `TargetEvaluationRequest`

Pydantic 请求模型，放在 `app/models/target_evaluation.py`。

### 4.2 `TargetEvaluationResult`

Pydantic 响应模型，放在 `app/models/target_evaluation.py`。

### 4.3 `AdmissionSource`

结构化来源：

- `source_name`
- `source_url`
- `source_type`: `admission_brochure` / `enrollment_plan` / `score_rank` / `control_line` / `historical_admission`
- `as_of`
- `confidence`

## 5. 评估链路

1. 输入校验：
   - `source_province` 必填。
   - `target_school` 必填。
   - 若 `target_major` 为空，仅评估专业组/学校投档风险。

2. 数据检索：
   - 找目标院校在 `source_province`、`data_year` 的招生计划。
   - 找目标院校 2026 招生章程。
   - 找专业组规则和选科要求。
   - 找 2026 一分一段和 2025 同制度录取基准。

3. 资格判断：
   - 无该省招生计划：不可报或数据不足。
   - 首选/再选不符：不可报。
   - 语种/单科/口试不符：不可报。
   - 目标专业未在该省计划中：目标专业不可评估或不可报。

4. 投档风险：
   - 使用当前分数转当前年位次。
   - 对比目标专业组或学校历史投档位次。
   - 输出风险档位，不输出精确概率。

5. 专业风险：
   - 若目标专业有分专业历史位次或计划数，评估目标专业风险。
   - 若只有专业组数据，输出“能否进组”和“目标专业数据不足”。
   - 若 `accept_adjustment=false` 且目标专业风险高，提示退档/滑档风险。

6. 数据缺口：
   - 缺 2026 招生计划。
   - 缺目标专业在河南计划。
   - 缺专业组历史投档位次。
   - 缺专业历史位次。
   - 招生章程未核验。

## 6. 页面

新增页面 `/target-evaluation`，导航名“目标评估”。

表单字段：

- 生源地
- 目标院校
- 目标专业（可选）
- 分数
- 首选科目
- 再选科目
- 外语语种
- 数学/外语单科
- 是否服从调剂

结果区：

- 总结结论
- 可报资格
- 投档风险
- 目标专业风险
- 数据缺口
- 来源列表

## 7. 验收标准

- 河南考生、郑州大学、计算机类、物理+化学：进入投档和专业风险评估。
- 同样目标但不选化学：返回不可报，原因包含再选科目不符。
- 外省院校必须按河南招生计划判断；没有河南计划时不得使用全国计划。
- 指定专业时必须区分专业组投档成功和目标专业录取成功。
- 缺 2026 分省专业计划时，`missing_data` 必须包含 `2026_enrollment_plan`，并降低置信度。
- API 测试、引擎测试、前端 build 均通过。

## 8. 数据来源策略

优先级：

1. 目标院校本科招生网 2026 招生章程和分省分专业计划。
2. 阳光高考平台院校章程和专业信息：https://gaokao.chsi.com.cn/
3. 河南省教育考试院数据：https://www.haeea.cn/
4. 2025 同制度历史投档数据。

所有来源必须出现在 `sources` 数组中。

