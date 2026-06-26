# Comet Design Handoff

- Change: volunteer-advisory-engine
- Phase: design
- Mode: compact
- Context hash: 044839221aac2acd84fe66fc6388228bebf55fab52bda3d9f3291058bed983df

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/volunteer-advisory-engine/proposal.md

- Source: openspec/changes/volunteer-advisory-engine/proposal.md
- Lines: 1-36
- SHA256: 78f6e9472c71a509623006315fb68dc7e7c32b9f0c6237e3b901a1eeae5c3bbc

```md
## Why

拆分项 A（`deprecate-life-path-narrative`，已归档）已完成去叙事/去交易化，留下了 `/life-paths`、`/life-trajectory` 两个 deprecated 端点。但产品缺少一个**面向新定位的推荐主接口**：当前 `/recommend`（传统冲稳保）只看分数位次、不含资格过滤与专业方向；`/life-paths`（deprecated）虽串了资格/市场/录取，但其 `major_value` 被错设为 `market.current_market_score`（违反父设计 §3.4 的 `market × fit` 门控），且输出绑定废弃的三路径模型。

本变更（拆分项 B）按父设计文档 `docs/superpowers/specs/2026-06-26-volunteer-recommendation-refocus-design.md` §3/§4，在已落地的资格/录取/适配/市场/费用/位次引擎之上，新建 `POST /api/v1/volunteer/advisory` 主接口，输出"专业方向优先"的可解释建议，并修正适配评分门控。

## What Changes

- **新增 advisory 主接口**：`POST /api/v1/volunteer/advisory`，输入完整考生画像（`StudentAcademicProfile` + 家庭预算，复用 `LifePathsRequest` 字段集），按 §3 主链路编排：考生画像 → 资格过滤 → 位次转换 → 专业方向评分 → 院校候选 → 费用压力评估 → 冲稳保 → 可解释输出。
- **新增输出模型**（`app/models/advisory.py`）：`VolunteerAdvisoryResult`、`MajorDirectionAdvice`（含 `market_value`/`student_fit`/`major_value`/`fit_explanation`/`risk_warnings`）、`BudgetSummary`、`IneligibleReason`。`SchoolOption`/`AdmissionBuckets` 复用 `app/models/life_path.py` 现有结构（已含 `total_cost_4y`/`affordability_status`/`data_granularity`/`confidence`/`warnings`，与 §4.1 兼容）。
- **新增主链路编排引擎**（`app/engine/advisory.py`）：`build_advisory()` 串联 `filter_eligible` → `convert_score_to_rank` → `score_direction` → **`compute_major_value_academic`（market×fit 门控，修正现有 life_paths 的错误）** → `predict_group_admission` → 费用 4 年累计 → affordability 分类 → 冲稳保分桶。
- **新增 §3.6 affordability 4 级分类器**：输出 `可承受 / 有压力 / 明显负担 / 超预算`（父设计 §3.6）。现有 `FamilyBudget.pressure_level` 标签为"可轻松承受/有压力/明显负担/极高风险"，与 §3.6 不一致——**新建独立分类器，不修改 `FamilyBudget`**。
- **费用分项**：§3.6 要求学费/住宿费/生活费/总开销拆分，而 `cost.compute_annual_cost` 仅返回单点 `CostBand`——advisory 层单独累计 4 年分项。
- **数据粒度与可信度**：`SchoolOption.data_granularity`（major/group/school）来自 `GroupAdmissionPrediction.data_granularity`；仅组数据时按 §3.3 提示"组内目标专业数据不足"。
- **遵守 narrative-policy**：A 已建主 spec `openspec/specs/narrative-policy/`，advisory 输出不出现人生路径/回本/ROI 等禁止词。

## Capabilities

### New Capabilities
- `volunteer-advisory`: 志愿推荐 advisory 主接口与专业方向优先主链路。规约 `POST /api/v1/volunteer/advisory` 的输入输出契约、§3 主链路顺序（资格前置→位次→专业方向 market×fit→院校→费用压力→冲稳保→可解释）、§3.4 乘法门控、§3.6 费用压力 4 级、§3.3 数据粒度提示、§6.2 推荐逻辑验收。归档后成为 `openspec/specs/volunteer-advisory/` 主 spec。

### Modified Capabilities
<!-- 无。advisory 是全新接口与编排；不修改现有 capability 的 requirements。narrative-policy（A 已建主 spec）作为约束被遵守，不被修改。 -->
_无_

## Impact

- **代码（新增）**：
  - `app/api/routers/volunteer.py`：新增 `advisory` handler（复用现有 `_build_academic_profile`/`_build_budget`/`_load_offerings`/`_load_directions_and_snapshots`/`_load_rank_entries`/`_load_admissions` 等 helper）。
  - `app/engine/advisory.py`：`build_advisory()` 主链路编排 + affordability 分类器。
  - `app/models/advisory.py`：输出模型。
- **代码（不动）**：`eligibility.py`/`admission_prediction.py`/`major_fit.py`/`job_market.py`/`cost.py`/`rank_query.py` 内部逻辑（仅调用）；`life_path.py`/`trajectory.py`（A 已 deprecated，不动）。
- **数据**：复用现有 seed（admission_offerings / major_directions / job_snapshots / universities / cities / majors / careers / score_rank），无新数据需求。
- **测试**：API 测试（advisory 返回专业方向/学校清单/费用压力/不可报原因）；engine 测试（market×fit 门控、affordability 4 级）；eligibility 边界（日语考生/选科不符/数学弱不前置）；数据粒度（仅组数据提示）；遵守 narrative-policy。
- **依赖**：无新增依赖。
- **与父设计/拆分项 A 的关系**：父设计 §3/§4/§6.2-6.4 的落地；A（已归档）提供的 `narrative-policy` 主 spec 作为约束；B 不复活任何 A 已废弃的叙事。
```

## openspec/changes/volunteer-advisory-engine/design.md

- Source: openspec/changes/volunteer-advisory-engine/design.md
- Lines: 1-94
- SHA256: a3c4e2f52ec3f0cd33ee8f9b3fbed5853e336a1d964d36105cf2561c5954eb99

[TRUNCATED]

```md
## Context

本变更（拆分项 B）在拆分项 A（已归档，去叙事完成）的干净基线上，新建志愿推荐 advisory 主接口，落地父设计 `docs/superpowers/specs/2026-06-26-volunteer-recommendation-refocus-design.md` §3/§4/§6.2-6.4。

经代码勘察确认，B 依赖的引擎**均已落地可调用**（A 期间已验证）：

| 引擎 | 入口 | 关键返回 |
|------|------|---------|
| eligibility | `filter_eligible(profile, offerings)` → `(eligible, ineligible)` | `EligibilityResult.blocked_summary` |
| admission_prediction | `predict_group_admission(...)` → `GroupAdmissionPrediction` | `admission_level`(冲/稳/保/偏...), `data_granularity`, `confidence` |
| major_fit | `compute_major_value_academic(market_scores, profile, major, english_dependency)` → `(major_value, breakdown)` | breakdown 含 `market_value`/`student_fit`/`major_value`/`math_learning_risk`/`english_adaptation` |
| job_market | `score_direction(direction, snap_map)` → `MarketScores` | `current_market_score`/`future_outlook_score` |
| cost | `compute_annual_cost(city_cost, tuition, accommodation)` → `CostBand`（单点，无分项） | low/high |
| rank | `convert_score_to_rank(entries, score)` → `int\|None`（含插值） | student_rank |

**现有 `life_paths` handler 的三个关键缺陷（B 必须修正）**：
1. `major_value` 被错设为 `market.current_market_score`（违反 §3.4 的 market×fit 门控）—— B 正确调用 `compute_major_value_academic`。
2. 无 §3.6 affordability 4 级分类器（`FamilyBudget.pressure_level` 标签为"可轻松承受/有压力/明显负担/极高风险"，与 §3.6 的"可承受/有压力/明显负担/超预算"不一致）—— B 新建独立分类器。
3. 无 §4.1 输出模型（`VolunteerAdvisoryResult`/`MajorDirectionAdvice`/`BudgetSummary`/`IneligibleReason` 均不存在）—— B 新建。

**可复用**：`SchoolOption`/`AdmissionBuckets`（`app/models/life_path.py`）结构与 §4.1 兼容（已含 `total_cost_4y`/`affordability_status`/`data_granularity`/`confidence`/`warnings`）；router 的 `_build_academic_profile`/`_build_budget`/`_load_*` helper 均可直接复用。

## Goals / Non-Goals

**Goals:**
- 新建 `POST /api/v1/volunteer/advisory`，按 §3 主链路输出 §4.1 `VolunteerAdvisoryResult`。
- 专业方向评分用 `market_value × student_fit`（§3.4 乘法门控）。
- 费用压力 4 级（§3.6），含学费/住宿费/生活费/总开销拆分。
- 数据粒度提示（§3.3）：仅组数据时提示"组内目标专业数据不足"。
- 满足 §6.2 推荐逻辑验收（日语/选科/数学弱/数据粒度/费用压力/可解释）。

**Non-Goals:**
- 不改 eligibility/admission_prediction/major_fit/job_market/cost/rank_query 引擎内部。
- 不动 A 已 deprecated 的 `life_path.py`/`trajectory.py`/`/life-paths`/`/life-trajectory`。
- 不做 ETL/爬虫（父设计 §8 排除）。
- 不改 `FamilyBudget`（affordability 用新建独立分类器）。
- 不做新前端 UI（advisory 是后端接口；前端接入可后续单独 change）。

## Decisions

### D1. 输出模型新建于 `app/models/advisory.py`，SchoolOption/AdmissionBuckets 复用 life_path
- **决策**：`VolunteerAdvisoryResult`/`MajorDirectionAdvice`/`BudgetSummary`/`IneligibleReason` 新建；`SchoolOption`/`AdmissionBuckets` 从 `life_path` 导入复用（字段已兼容 §4.1）。
- **理由**：避免与 deprecated 三路径模型耦合；SchoolOption 已是中性结构（A 已去其叙事），复用避免重复定义。
- **权衡**：advisory 依赖 life_path 模块导入，但 life_path 是 deprecated 源码保留（A 决策 D1 软弃用），导入其模型类不触发废弃叙事。

### D2. 主链路编排放 `app/engine/advisory.py`，`build_advisory()` 纯函数
- **决策**：新建 `build_advisory(profile, budget, offerings, directions, snap_map, admissions, unis, cities, majors, careers, rank_entries)` 纯函数，router 注入数据（与 `build_life_trajectory` 模式一致）。
- **理由**：保持 router 薄、引擎纯、可测试；数据注入便于单测。

### D3. 专业方向评分用 `compute_major_value_academic`（非 `compute_major_value`）
- **决策**：调用 `compute_major_value_academic(market_scores, profile, major, english_dependency=offering.english_dependency_level)`，从 breakdown 提取 `market_value`/`student_fit`/`major_value`/`math_learning_risk`/`english_adaptation` 填入 `MajorDirectionAdvice`。
- **理由**：§3.1 canonical 画像是 `StudentAcademicProfile`；`_academic` 变体用 `english_actual_level`（真实英语能力）而非高考语种，符合 §3.1 区分要求；修正现有 life_paths 的错误。

### D4. affordability 新建独立 4 级分类器（不改 FamilyBudget）
- **决策**：在 `app/engine/advisory.py` 新建 `classify_affordability(cost_4y, budget) -> str`，返回 §3.6 的 `可承受/有压力/明显负担/超预算`。阈值：`cost_4y <= budget.affordable_total` → 可承受；否则按 `pressure_coefficient = cost_4y / annual_income` 分级（如 ≤1.5 有压力、≤3 明显负担、>3 或 `not can_afford` 超预算）。
- **理由**：§3.6 明确 4 级且标签与 `FamilyBudget.pressure_level` 不一致；新建避免改动 deprecated 关联的 FamilyBudget 语义。
- **权衡**：阈值是经验值，设计未给精确分界——在 design doc 记录阈值并标注可调。

### D5. 费用 4 年分项在 advisory 层累计
- **决策**：router 取 `UniversityRow`(tuition/accommodation) + `CityCostRow`(monthly living)，advisory 计算 `tuition_4y = tuition*4`、`accommodation_4y = accommodation*4`、`living_4y = monthly_mid*12*4`、`total_4y = sum`，填入 SchoolOption.total_cost_4y 与 BudgetSummary。
- **理由**：`compute_annual_cost` 不返回分项；§3.6 要求分项展示。

### D6. 数据粒度提示复用 admission_prediction 的 data_granularity
- **决策**：`SchoolOption.data_granularity = group_pred.data_granularity`；当为 "group"/"school" 时，`warnings` 追加"组内目标专业数据不足，仅按专业组投档参考"（§3.3）。
- **理由**：admission_prediction 已实现 anti-disguise 粒度标注，直接透传。

### D7. 冲稳保分桶用 admission_level 映射
- **决策**：`冲=[冲,偏冲]`、`稳=[稳]`、`保=[偏保,保]`，填入 `AdmissionBuckets.reach/match/safe`（复用 life_path 的 reach/match/safe 命名）。
- **理由**：复用现有 buckets 结构；admission_prediction 的 5 级自然归并到 3 桶。

### D8. capability 单一 `volunteer-advisory`
- **决策**：单一 capability 覆盖接口契约 + 主链路 + 评分门控 + 费用压力 + 数据粒度 + 验收。
- **理由**：内聚；避免拆成多个 delta。

## Risks / Trade-offs

- **[风险] advisory 依赖 life_path 的 SchoolOption 导入** → 缓解：A 已软弃用保留源码；若未来彻底删除 life_path，SchoolOption 应迁移到 advisory 模块（design doc 记录此迁移点）。
- **[风险] affordability 阈值是经验值** → 缓解：阈值常量化、design doc 标注可调、测试覆盖 4 级边界。
- **[风险] major_fit 的 breakdown dict 字段名假设** → 缓解：测试断言 breakdown 含所需 key；若字段缺失回退用 current_market_score 并 warning。
- **[权衡] 不接入前端** → advisory 是后端接口；前端接入（替换 HomePage 的 /life-trajectory 调用）可后续单独 change，不阻塞 B 验收（验收聚焦 API/engine）。
```

Full source: openspec/changes/volunteer-advisory-engine/design.md

## openspec/changes/volunteer-advisory-engine/tasks.md

- Source: openspec/changes/volunteer-advisory-engine/tasks.md
- Lines: 1-53
- SHA256: 4990c610c7067efc911732aa316e541d77e7995f270aea272866a2d6c45cd47b

```md
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
```

## openspec/changes/volunteer-advisory-engine/specs/volunteer-advisory/spec.md

- Source: openspec/changes/volunteer-advisory-engine/specs/volunteer-advisory/spec.md
- Lines: 1-114
- SHA256: 5ae250d2127d7efc2c58600f6b5192d757a6a880db4f4d95a09d111c97aaca8f

[TRUNCATED]

```md
# Spec Delta: volunteer-advisory

本 delta 为新建 capability `volunteer-advisory` 定义 requirements。规约 `POST /api/v1/volunteer/advisory` 主接口的输入输出契约、§3 专业方向优先主链路、§3.4 乘法门控评分、§3.6 费用压力 4 级、§3.3 数据粒度提示，以及 §6.2/§6.3 推荐逻辑与费用验收。对应父设计 `docs/superpowers/specs/2026-06-26-volunteer-recommendation-refocus-design.md` §3/§4/§6.2/§6.3/§6.4。

## ADDED Requirements

### Requirement: advisory 主接口契约

系统 SHALL 提供 `POST /api/v1/volunteer/advisory`，输入完整考生画像（省份/年份/总分/首选科目/再选科目/数学分/外语语种与分数/实际英语能力/家庭预算），输出 `VolunteerAdvisoryResult`（含 `student_rank`/`province`/`track`/`data_year`/`major_directions`/`school_options`/`ineligible_options`/`budget_summary`/`notes`）。

输入画像 SHALL 基于 `StudentAcademicProfile`（含 `english_actual_level` 区分高考语种与真实英语能力），符合父设计 §3.1。

#### Scenario: advisory 端点返回完整结构

WHEN 调用 `POST /api/v1/volunteer/advisory` 传入合法考生画像
THEN 响应 MUST 为 2xx
AND 响应体 MUST 包含 `major_directions`、`school_options`（含冲稳保分桶）、`ineligible_options`、`budget_summary`、`notes`、`student_rank`、`data_year`

#### Scenario: 输入画像区分高考语种与真实英语能力

WHEN 构造 `StudentAcademicProfile`
THEN MUST 同时接受 `exam_foreign_language`（高考语种）与 `english_actual_level`（真实英语能力）两个独立字段

### Requirement: 专业方向优先主链路顺序

推荐主链路 SHALL 按父设计 §3 顺序执行，且资格过滤 MUST 前置于所有评分：考生画像 → 政策与资格过滤 → 位次与历年同制度对照 → 专业方向适配评分 → 院校专业组候选生成 → 费用与家庭承受压力评估 → 冲稳保分桶 → 可解释输出。

资格过滤定义可行解空间；所有评分与排序 MUST 仅在 `eligible` 集合上运行。

#### Scenario: 资格过滤前置于评分

WHEN 执行 advisory 主链路
THEN MUST 先调用资格过滤得到 `(eligible, ineligible)`
AND 后续专业方向评分与院校候选 MUST 仅对 `eligible` 集合运行

#### Scenario: 不可报原因保留并输出

WHEN 存在不满足资格的 offering
THEN `ineligible_options` MUST 包含该 offering 及其不可报原因（来自 `EligibilityResult.blocked_summary`）

### Requirement: 专业方向乘法门控评分

专业方向评分 SHALL 采用乘法门控 `major_value = market_value × student_fit`（父设计 §3.4），避免"市场热但孩子学不动"的专业被强推。

`market_value` 来自市场参考（岗位密度/薪资/城市覆盖/趋势），`student_fit` 来自选科资格/数学学习风险/英语适配/兴趣。MUST 调用 `compute_major_value_academic`（基于 `StudentAcademicProfile` 与 `english_actual_level`）。

#### Scenario: 专业方向评分用 market × fit

WHEN 计算专业方向 `MajorDirectionAdvice`
THEN `major_value` MUST 等于 `market_value × student_fit`（而非单独的市场分）
AND MUST 调用 `compute_major_value_academic`（基于 `StudentAcademicProfile`）

#### Scenario: 数学弱考生数学强依赖专业不因市场热度前置

WHEN 考生数学较弱且某专业方向数学学习风险高、但市场热度高
THEN 该方向的 `student_fit` MUST 显著降低，使 `major_value` 不排在前列
AND `risk_warnings` MUST 包含数学学习风险说明

### Requirement: 录取风险与数据粒度

录取判断 SHALL 区分"专业组投档可能性"与"组内目标专业风险"，不得把"可投进专业组"写成"可录取目标专业"（父设计 §3.3）。

`SchoolOption.data_granularity`（major/group/school）来自 `GroupAdmissionPrediction`。当仅有专业组或学校级数据时，MUST 在 `warnings` 提示数据不足。

#### Scenario: 仅专业组数据提示目标专业不确定

WHEN 某院校仅有专业组投档线而无目标专业录取线
THEN `SchoolOption.data_granularity` MUST 为 "group"（或 "school"）
AND `warnings` MUST 提示"组内目标专业数据不足，仅按专业组投档参考"
AND MUST NOT 声称可录取目标专业

#### Scenario: 跨年数据标注年份与制度

WHEN 使用历年录取数据
THEN 结果 MUST 标注数据年份
AND 2025 及以后同制度数据 MUST NOT 与旧文理科制度简单平均

### Requirement: 费用压力 4 级评估

费用模块 SHALL 输出大学期间总开销与家庭承受压力 4 级：`可承受 / 有压力 / 明显负担 / 超预算`（父设计 §3.6）。MUST 展示学费/住宿费/生活费/总开销拆分，区分公办/民办/中外合作。
```

Full source: openspec/changes/volunteer-advisory-engine/specs/volunteer-advisory/spec.md

