# Brainstorm Summary

- Change: volunteer-advisory-engine
- Date: 2026-06-26

## 确认的技术方案

拆分项 B：advisory 主接口 + 专业方向优先主链路。两轮澄清的关键决策已敲定：

1. **请求模型**：复用现有 `LifePathsRequest`（字段集已含 §3.1 全部 + 家庭预算），零新增请求模型，`_build_academic_profile`/`_build_budget` 直接复用。
2. **专业方向聚合**：`MajorDirectionAdvice.market_value/student_fit/major_value` 取该方向下各 eligible offering 计算结果的**加权均值**（按 career_weights 或等权）。符合"方向级建议"语义，平滑离群。
3. **主链路**（§3 顺序，build_advisory 纯函数，router 注入数据）：
   - `filter_eligible(profile, offerings)` → (eligible, ineligible) [§3.2 资格前置门]
   - `convert_score_to_rank(entries, total_score)` → student_rank [§3.3 位次]
   - 对每个 eligible offering：匹配 MajorDirection（direction_hint 优先）→ `score_direction(direction, snap_map)` → `compute_major_value_academic(market_scores, profile, major, english_dependency)` [§3.4 market×fit 门控，修正现有 life_paths 错误] → `predict_group_admission(...)` [§3.3 录取] → 费用 4 年累计（tuition/accommodation/living 分项）→ `classify_affordability(cost_4y, budget)` [§3.6 4 级]
   - 冲稳保分桶：冲/偏冲→reach，稳→match，偏保/保→safe（D7）
   - 按 MajorDirection 聚合 eligible offerings → MajorDirectionAdvice（加权均值）
   - ineligible → IneligibleReason（blocked_summary）
   - notes：数据年份/回退说明
4. **affordability 4 级**（D4，新建独立分类器，不改 FamilyBudget）：cost_4y ≤ affordable_total → 可承受；否则 pressure_coefficient = cost_4y/annual_income：≤1.5 有压力、≤3 明显负担、>3 或 not can_afford → 超预算。阈值常量化、可调。
5. **输出模型**（D1）：VolunteerAdvisoryResult/MajorDirectionAdvice/BudgetSummary/IneligibleReason 新建于 `app/models/advisory.py`；SchoolOption/AdmissionBuckets 从 `app.models.life_path` 导入复用（字段已兼容 §4.1）。
6. **数据粒度**（D6）：SchoolOption.data_granularity 来自 group_pred；group/school 时 warnings 追加"组内目标专业数据不足"。

## 关键取舍与风险

- **取舍**：advisory 依赖 life_path 的 SchoolOption 导入——A 已软弃用保留源码，导入模型类不触发废弃叙事；若未来彻底删除 life_path，SchoolOption 应迁移到 advisory 模块（design doc 记录迁移点）。
- **取舍**：不接入前端（advisory 是后端接口）；前端替换 HomePage 的 /life-trajectory 调用可后续单独 change，不阻塞 B 验收。
- **风险**：affordability 阈值是经验值 → 常量化、design doc 标注可调、测试覆盖 4 级边界。
- **风险**：major_fit 的 breakdown dict 字段名假设 → 测试断言 key 存在；缺失则回退 current_market_score + warning。
- **修正点**：现有 life_paths 把 major_value 错设为 current_market_score——B 在 advisory 正确用 compute_major_value_academic 的 market×fit。

## 测试策略

- API：`tests/api/test_advisory_api.py`——端点返回完整结构 + 不含禁止词（遵守 narrative-policy）。
- engine：`tests/engine/test_advisory_engine.py`——classify_affordability 4 级边界；major_value==market×fit 门控；数学弱→student_fit 降低不前置。
- 资格/粒度边界：日语考生英语限定→ineligible；选科不符→ineligible；仅组数据→data_granularity=group + warnings；跨年回退→notes 说明。
- 费用：民办/中外合作高费用→压力反映；BudgetSummary 含学费/住宿费/生活费/总开销拆分。
- 回归：全量 pytest（A 的 narrative-policy 扫描 + 现有 /recommend//score-rank//life-trajectory）。

## Spec Patch

无（volunteer-advisory delta spec 的 7 requirements / 14 scenarios 已充分覆盖上述决策；加权均值聚合属实现细节，不改变 spec 契约；affordability 4 级阈值在 design doc 记录，spec 只约束 4 级标签集合）。
