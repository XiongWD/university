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
- **[权衡] 复用 reach/match/safe 命名** → 与冲稳保语义对齐（reach=冲、match=稳、safe=保），文档说明映射。

## Migration Plan

1. 新建 `app/models/advisory.py`（输出模型）。
2. 新建 `app/engine/advisory.py`（`build_advisory` + `classify_affordability`）。
3. router 新增 `advisory` handler（复用 helper，调用 build_advisory）。
4. 测试：API + engine + eligibility 边界 + 数据粒度 + narrative-policy 遵守。
5. 每步独立提交。
6. **回滚**：advisory 是纯新增（新端点+新模型+新引擎函数），不改动现有行为，回滚只需删除新增文件 + handler，无副作用。

## Open Questions

- affordability 阈值精确分界（D4）——已在 design doc 记录经验阈值并标注可调，非阻塞。
