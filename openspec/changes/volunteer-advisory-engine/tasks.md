# Tasks — volunteer-advisory-engine

> 拆分项 B：advisory 主接口 + 专业方向优先主链路。对应 capability `volunteer-advisory`。
> 范围：新建 POST /api/v1/volunteer/advisory + 输出模型 + 主链路编排引擎 + §3.6 affordability 4 级。
> 非目标：不改现有引擎内部、不动 A 已 deprecated 的 life_path/trajectory、不做前端接入、不做 ETL。

## 1. 输出模型（app/models/advisory.py）

- [ ] 1.1 新建 `app/models/advisory.py`：`MajorDirectionAdvice`（direction/recommended_majors/market_value/student_fit/major_value/fit_explanation: list[str]/risk_warnings: list[str]）
- [ ] 1.2 `BudgetSummary`（tuition_4y/accommodation_4y/living_4y/total_4y/affordable_total/affordability_status/data_note）
- [ ] 1.3 `IneligibleReason`（school/major_group_name/reasons: list[str]/blocked_summary: str）
- [ ] 1.4 `VolunteerAdvisoryResult`（student_rank/province/track/data_year/major_directions: list[MajorDirectionAdvice]/school_options: AdmissionBuckets[SchoolOption]/ineligible_options: list[IneligibleReason]/budget_summary: BudgetSummary/notes: list[str]）；SchoolOption/AdmissionBuckets 从 `app.models.life_path` 导入复用

## 2. 主链路编排引擎（app/engine/advisory.py）

- [ ] 2.1 新建 `app/engine/advisory.py`；`classify_affordability(cost_4y, budget) -> str`：返回 可承受/有压力/明显负担/超预算（阈值常量化：cost_4y<=affordable_total→可承受；否则按 cost_4y/annual_income 分级）
- [ ] 2.2 `build_advisory(profile, budget, offerings, directions, snap_map, admissions, unis, cities, majors, careers, rank_entries) -> VolunteerAdvisoryResult`：资格过滤 `filter_eligible` → 位次 `convert_score_to_rank` → 对每个 eligible offering 匹配 MajorDirection → `score_direction` → `compute_major_value_academic`（market×fit 门控）→ `predict_group_admission` → 费用 4 年累计 → affordability 分类 → 冲稳保分桶（冲/偏冲→reach，稳→match，偏保/保→safe）
- [ ] 2.3 数据粒度提示：data_granularity 来自 group_pred；group/school 时 warnings 追加"组内目标专业数据不足"
- [ ] 2.4 专业方向聚合：按 MajorDirection 聚合 SchoolOption，生成 MajorDirectionAdvice（market_value/student_fit/major_value 取该方向 offerings 的代表值或均值；fit_explanation/risk_warnings 来自 breakdown 的 math_learning_risk/english_adaptation）
- [ ] 2.5 ineligible_options 来自 ineligible 的 blocked_summary；notes 含数据年份/回退说明

## 3. API 端点（app/api/routers/volunteer.py）

- [ ] 3.1 新增 `AdvisoryRequest`（复用 LifePathsRequest 字段集：province/total_score/primary_subject/scores/exam_foreign_language/english_actual_level/electives/家庭预算）；或直接复用 LifePathsRequest
- [ ] 3.2 新增 `@router.post("/advisory")` handler：复用 `_build_academic_profile`/`_build_budget`/`_load_offerings`/`_load_directions_and_snapshots`/`_load_rank_entries`/`_load_admissions`/`_load_universities`/`_load_cities`/`_load_majors`/`_load_careers`，调用 `build_advisory`，返回 model_dump

## 4. 测试：API 契约

- [ ] 4.1 `tests/api/test_advisory_api.py`：advisory 端点返回 2xx + 完整结构（major_directions/school_options/ineligible_options/budget_summary/notes/student_rank/data_year）
- [ ] 4.2 advisory 响应不出现禁止词（遵守 narrative-policy，断言无"人生路径/回本/ROI"等）

## 5. 测试：engine 主链路（market×fit 门控）

- [ ] 5.1 `tests/engine/test_advisory_engine.py`：`classify_affordability` 4 级边界（可承受/有压力/明显负担/超预算）
- [ ] 5.2 `build_advisory` 中 MajorDirectionAdvice.major_value == market_value × student_fit（断言乘法门控，非单独市场分）
- [ ] 5.3 数学弱考生 → 数学强依赖方向的 student_fit 显著降低、major_value 不前置、risk_warnings 含数学风险

## 6. 测试：资格/数据粒度边界

- [ ] 6.1 日语考生 → 英语限定专业出现在 ineligible_options（或被过滤）
- [ ] 6.2 选科不符 → 不进 school_options，出现在 ineligible_options
- [ ] 6.3 仅专业组数据 → SchoolOption.data_granularity="group" + warnings 含"组内目标专业数据不足"，且不声称可录取目标专业
- [ ] 6.4 跨年回退 → notes 含数据年份/回退说明

## 7. 测试：费用压力

- [ ] 7.1 民办/中外合作高费用 → affordability_status 反映压力（有压力/明显负担/超预算），排序不忽略费用
- [ ] 7.2 BudgetSummary 含学费/住宿费/生活费/总开销 4 年累计拆分

## 8. 回归与验收

- [ ] 8.1 全量 pytest 通过（含 A 的 narrative-policy 扫描、现有 /recommend//score-rank//life-trajectory 回归）
- [ ] 8.2 `openspec validate volunteer-advisory-engine` 通过
