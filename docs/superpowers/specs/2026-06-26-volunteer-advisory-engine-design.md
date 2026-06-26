---
comet_change: volunteer-advisory-engine
role: technical-design
canonical_spec: openspec
---

# Design Doc: volunteer-advisory-engine（拆分项 B — advisory 主接口 + 专业方向主链路）

本设计是父设计文档 `docs/superpowers/specs/2026-06-26-volunteer-recommendation-refocus-design.md` §3/§4/§6.2-6.4 的拆分项 B 专属技术实现设计。产品定位、背景、验收口径见父文档；本文聚焦**如何实现 advisory 主接口与专业方向优先主链路**、引擎编排顺序、与父文档的关系、以及与拆分项 A（已归档）的边界。

## 1. 实现目标与范围

### 目标
- 新建 `POST /api/v1/volunteer/advisory`，按 §3 主链路输出 §4.1 `VolunteerAdvisoryResult`。
- 专业方向评分用 `market_value × student_fit`（§3.4 乘法门控）—— 修正现有 life_paths 的错误。
- 费用压力 4 级（§3.6），含学费/住宿费/生活费/总开销拆分。
- 数据粒度提示（§3.3）：仅组数据时提示"组内目标专业数据不足"。
- 满足 §6.2 推荐逻辑验收（日语/选科/数学弱/数据粒度/费用压力/可解释）。

### 非目标
- 不改 eligibility/admission_prediction/major_fit/job_market/cost/rank_query 引擎内部。
- 不动 A 已 deprecated 的 `life_path.py`/`trajectory.py`/`/life-paths`/`/life-trajectory`。
- 不改 `FamilyBudget`（affordability 新建独立分类器）。
- 不做前端 UI 接入（后续单独 change）。
- 不做 ETL/爬虫（父设计 §8 排除）。

## 2. 现状（经代码勘察确认）

B 依赖的引擎**均已落地可调用**：

| 引擎 | 入口 | 关键返回 |
|------|------|---------|
| eligibility | `filter_eligible(profile, offerings) -> (eligible, ineligible)` | `EligibilityResult.blocked_summary` |
| admission_prediction | `predict_group_admission(...) -> GroupAdmissionPrediction` | `admission_level`(冲/稳/保/偏...), `data_granularity`, `confidence` |
| major_fit | `compute_major_value_academic(market_scores, profile, major, english_dependency) -> (major_value, breakdown)` | breakdown 含 `market_value`/`student_fit`/`major_value`/`math_learning_risk`/`english_adaptation` |
| job_market | `score_direction(direction, snap_map) -> MarketScores` | `current_market_score`/`future_outlook_score` |
| cost | `compute_annual_cost(...)` → 单点 CostBand（无分项） | — |
| rank | `convert_score_to_rank(entries, score) -> int\|None`（含插值） | student_rank |

**现有 `life_paths` handler 的三个缺陷（B 修正）**：
1. `major_value` 错设为 `market.current_market_score`（违反 §3.4）→ B 用 `compute_major_value_academic`。
2. 无 §3.6 affordability 4 级分类器 → B 新建。
3. 无 §4.1 输出模型 → B 新建。

**可复用**：`SchoolOption`/`AdmissionBuckets`（`app/models/life_path.py`，字段已兼容 §4.1）；router 的 `_build_academic_profile`/`_build_budget`/`_load_*` helper；`LifePathsRequest`（字段集已含 §3.1 全部 + 家庭预算）。

## 3. 实现方案

### 3.1 输出模型（`app/models/advisory.py`，新建）
- `MajorDirectionAdvice`：direction/recommended_majors/market_value/student_fit/major_value/fit_explanation(list[str])/risk_warnings(list[str])
- `BudgetSummary`：tuition_4y/accommodation_4y/living_4y/total_4y/affordable_total/affordability_status/data_note
- `IneligibleReason`：school/major_group_name/reasons(list[str])/blocked_summary(str)
- `VolunteerAdvisoryResult`：student_rank/province/track/data_year/major_directions(list[MajorDirectionAdvice])/school_options(AdmissionBuckets[SchoolOption])/ineligible_options(list[IneligibleReason])/budget_summary(BudgetSummary)/notes(list[str])
- `SchoolOption`/`AdmissionBuckets` 从 `app.models.life_path` 导入复用。

### 3.2 主链路编排（`app/engine/advisory.py`，新建）
`build_advisory(profile, budget, offerings, directions, snap_map, admissions, unis, cities, majors, careers, rank_entries) -> VolunteerAdvisoryResult`，纯函数、router 注入数据。顺序：
1. `filter_eligible(profile, offerings)` → (eligible, ineligible) [§3.2 资格前置门]
2. track = "历史类" if primary_subject=="历史" else "物理类"；`student_rank = convert_score_to_rank(entries, profile.total_score) or 0` [§3.3]
3. `adm_by_school = {a.school: a for a in admissions}`（2025 同制度 baseline）
4. 对每个 `(off, elig_result) in eligible`：
   - 匹配 MajorDirection（`off.direction_hint` 优先，否则按 major_group_name/school 子串匹配）
   - `market = score_direction(direction, snap_map)`
   - `(major_value, breakdown) = compute_major_value_academic(market, profile, matched_major, english_dependency=off.english_dependency_level)` [§3.4 market×fit]
   - `group_pred = predict_group_admission(off.school, off.major_group_code, student_rank, baseline_rank_2025=adm.min_rank)`
   - 费用 4 年累计：tuition_4y/accommodation_4y/living_4y（monthly_mid*12*4）/total_4y
   - `afford = classify_affordability(total_4y, budget)`
   - 构造 SchoolOption（admission_level/data_granularity/confidence/total_cost_4y/affordability_status/warnings）
   - 数据粒度提示：data_granularity 为 group/school 时 warnings 追加"组内目标专业数据不足，仅按专业组投档参考"
5. 冲稳保分桶（D7）：冲/偏冲→reach，稳→match，偏保/保→safe
6. 按 MajorDirection 聚合 eligible offerings → MajorDirectionAdvice（market_value/student_fit/major_value 取该方向 offerings 的**加权均值**，按 career_weights 或等权；fit_explanation/risk_warnings 来自 breakdown 的 math_learning_risk/english_adaptation）
7. ineligible → IneligibleReason（school/major_group_name/reasons=elig_result.reasons/blocked_summary）
8. BudgetSummary：取结果院校的总开销分项汇总或代表性值；affordable_total=budget.affordable_total
9. notes：数据年份/回退说明（"基于 2025 同制度录取数据"等）

### 3.3 affordability 4 级分类器（D4，新建独立，不改 FamilyBudget）
`classify_affordability(cost_4y: int, budget: FamilyBudget) -> str`：
- `cost_4y <= budget.affordable_total` → "可承受"
- 否则 `pressure = cost_4y / max(budget.annual_income, 1)`：
  - `pressure <= 1.5` → "有压力"
  - `pressure <= 3.0` → "明显负担"
  - `pressure > 3.0` 或 `not budget.can_afford(cost_4y)` → "超预算"
- 阈值常量化（模块级 `AFFORD_*` 常量），design doc 标注可调。

### 3.4 API 端点（`app/api/routers/volunteer.py`，新增 handler）
- 复用 `LifePathsRequest` 作为请求模型（字段集已含 §3.1 全部 + 家庭预算）。
- `@router.post("/advisory")`：复用 `_build_academic_profile`/`_build_budget`/`_load_offerings`/`_load_directions_and_snapshots`/`_load_rank_entries`/`_load_admissions`/`_load_universities`/`_load_cities`/`_load_majors`/`_load_careers`，调用 `build_advisory`，返回 `model_dump(mode="json")`。
- docstring 中性，遵守 narrative-policy（不出现禁止词）。

## 4. 关键取舍

| 决策 | 选择 | 理由 |
|------|------|------|
| 请求模型 | 复用 LifePathsRequest | 字段集已含 §3.1；零新增；helper 直接复用 |
| 方向聚合 | 加权均值（career_weights/等权） | 符合"方向级建议"语义；平滑离群 |
| 回本/ROI | 不计算 | narrative-policy 禁止（A 已建主 spec） |
| affordability | 新建独立 4 级分类器 | §3.6 标签与 FamilyBudget.pressure_level 不一致；不改 deprecated 关联模型 |
| SchoolOption 来源 | 从 life_path 导入复用 | 字段已兼容 §4.1；A 软弃用保留源码 |
| 编排位置 | build_advisory 纯函数 | router 薄、引擎纯、可测试 |
| 前端 | 不接入 | advisory 是后端接口；前端接入后续单独 change |

## 5. 风险与缓解
- **advisory 依赖 life_path 的 SchoolOption 导入** → A 已软弃用保留；若未来彻底删除 life_path，SchoolOption 应迁移到 advisory 模块（本设计记录此迁移点）。
- **affordability 阈值是经验值** → 常量化、标注可调、测试覆盖 4 级边界。
- **major_fit breakdown 字段名假设** → 测试断言 key 存在；缺失回退 current_market_score + warning。
- **不接入前端** → 验收聚焦 API/engine，不阻塞。

## 6. 迁移与回滚
advisory 是纯新增（新端点 + 新模型 + 新引擎函数），不改现有行为。回滚只需删除新增文件 + handler，无副作用。每步独立提交。

## 7. 与父设计 & 拆分项 A 的边界
- **父设计** §3/§4/§6.2-6.4 的落地。
- **拆分项 A**（已归档）：提供 `narrative-policy` 主 spec 作为约束（advisory 输出不出现人生路径/回本/ROI 等禁止词）。
- **本 change 不建前端**、不改现有引擎、不动 deprecated 端点。

## 8. 开放问题
- affordability 阈值精确分界（§3.3）——已记录经验阈值并标注可调，非阻塞。
