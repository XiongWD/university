# volunteer-advisory Specification

## Purpose
TBD - created by archiving change volunteer-advisory-engine. Update Purpose after archive.
## Requirements
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

SHALL NOT 计算回本周期、ROI、15年净收益（已由 narrative-policy 禁止）。

#### Scenario: 费用拆分含学费/住宿费/生活费

WHEN 计算 `BudgetSummary` 与 `SchoolOption.total_cost_4y`
THEN MUST 提供学费、住宿费、生活费、总开销的 4 年累计拆分

#### Scenario: 民办/中外合作高费用显示压力

WHEN 某院校为民办/中外合作且费用高
THEN `SchoolOption.affordability_status` MUST 反映费用压力（有压力/明显负担/超预算）
AND 排序 MUST NOT 仅按学校或专业分，忽略费用压力

#### Scenario: 家庭预算不足标记超预算

WHEN 4 年总开销超过家庭可承受总额
THEN `affordability_status` MUST 为"超预算"

### Requirement: 冲稳保分桶与可解释输出

院校候选 SHALL 按 `AdmissionLevel`（冲/偏冲/稳/偏保/保）归并为冲稳保三档输出（reach/match/safe）。

输出 SHALL 含 `fit_explanation`（专业方向适配解释）、`risk_warnings`（风险提示）、`notes`（数据来源与回退说明），使家长能看懂"为什么推荐/为什么不可报/家庭是否扛得住"。

#### Scenario: 冲稳保归并输出

WHEN 院校候选含多个 admission_level
THEN MUST 归并为 reach（冲/偏冲）、match（稳）、safe（偏保/保）三档

#### Scenario: 当前年份数据缺失回退标注

WHEN 当前年份一分一段或录取数据缺失而回退到历史年份
THEN `notes` MUST 说明回退年份与数据来源

