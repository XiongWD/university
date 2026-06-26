## Why

项目定位需从"人生经济模型/路径推演"纠偏为"高考志愿与专业选择辅助系统"。当前实现把"三条人生路径（稳健/均衡/进取）""人生轨迹""回本周期 / ROI / 15年净收益"作为主流程输出，前者暗示孩子成长路径被系统固化、后者把上大学描述成交易，均不适合面向高考生和家长的志愿决策场景。本次变更作为 `volunteer-recommendation-refocus` 设计文档（`docs/superpowers/specs/2026-06-26-volunteer-recommendation-refocus-design.md`）落地的**第一步**：彻底从主流程、UI、README 中清除这两类叙事，为后续 advisory 主接口（拆分项 B）让出干净基线。

## What Changes

- **去交易化（回本/ROI）**
  - 停用 `app/engine/trajectory.py` 的 `_build_payback()`（计算 `years_to_break_even` / `lifetime_15y_net` / "回本极快/较快/正常/较慢" 判断），不再作为主流程输出。
  - `app/models/life_trajectory.py` 的 `PaybackAnalysis`（含 `lifetime_15y_net` "15年净收益"）不再在主流程生成；字段保留为历史遗留，标注 deprecated。
  - `web-ui/src/components/TrajectoryCard.tsx` 移除"回本周期"卡片与 `payback.lifetime_15y_net` 渲染（第三列）。
  - `web-ui/src/pages/HomePage.tsx` 副标题删除"回本周期"字样。
- **去人生固化叙事（路径/轨迹/赛道）**
  - `app/engine/life_path.py` 三路径优化器（`build_life_paths` / `compute_path_score` / `PATH_WEIGHTS` 稳健/均衡/进取）从主链路移除。
  - `POST /api/v1/volunteer/life-paths`、`POST /api/v1/volunteer/life-trajectory` 改为 deprecated：内部保留兼容、可运行，但不出现在 UI 导航、README、主导航。**BREAKING**（对外可见性层面：从主导航与文档中移除）。
  - `web-ui/src/App.tsx`：移除"人生路径"导航项（`/life-paths`）、移除"人生经济模型模拟器"副标题、更新品牌区。
  - `web-ui/src/pages/LifePathsPage.tsx` 从路由入口移除（页面可保留为内部遗留，不在导航出现）。
  - `web-ui/src/pages/HomePage.tsx`：主标题改"高考志愿专业推荐"，删除"填报志愿，看见孩子的人生轨迹"。
  - `web-ui/src/api/types.ts`、`web-ui/src/api/client.ts` 中"人生轨迹（…）/ V2.2 人生路径"注释改为中性描述。
  - `README.md` 标题与首段改写：去掉"人生经济模型模拟器""教育经济决策系统""三条人生路径（稳健/均衡/进取）""优化…教育回报"叙事，改为志愿辅助系统定位。
- **验收工具**
  - 新增禁止词静态扫描测试（§6.1）：扫描用户可见主流程（前端 src、README、API 描述、docstring），禁止出现 `人生路径/人生轨迹/回本/ROI/投资回报/15年净收益/命运/赛道` 作为功能名或推荐结果；允许在归档文档、deprecated 注释、本设计文档自身出现。
- **回归保障**：`/recommend`（传统冲稳保）、`/score-rank`（位次工具）、大学费用模块在去叙事后仍可用。

## Capabilities

### New Capabilities
- `narrative-policy`: 产品叙事口径策略。规约系统在用户可见主流程中不得呈现的两类叙事——人生固化叙事（人生路径/人生轨迹/赛道/命运）与交易化叙事（回本/ROI/投资回报/15年净收益），以及 deprecated 端点 `/life-paths`、`/life-trajectory` 的可见性约束。这是本变更的核心契约，使禁止词策略从测试约定升级为可验证的 capability requirement。归档后将成为 `openspec/specs/narrative-policy/` 主 spec。

### Modified Capabilities
<!-- 现有 specs 中 REQUIREMENTS 层面无变更：`score-rank-table`、`provincial-control-line`、`admission-data-schema`、`career-data`、`city-cost-data`、`student-profile-data` 行为均不变。项目无 volunteer/life-path/trajectory capability spec，去叙事作为新建 `narrative-policy` capability 处理。 -->
_无（本变更不修改任何现有 capability 的 requirements）_

## Impact

- **代码（后端）**：`app/engine/trajectory.py`（`_build_payback` 停用）、`app/engine/life_path.py`（从主链路移除）、`app/api/routers/volunteer.py`（`life_paths`/`life_trajectory` 标记 deprecated）、`app/models/life_trajectory.py`、`app/models/life_path.py`（字段/注释 deprecated 标注）。
- **代码（前端）**：`web-ui/src/App.tsx`、`web-ui/src/pages/HomePage.tsx`、`web-ui/src/pages/LifePathsPage.tsx`、`web-ui/src/components/TrajectoryCard.tsx`、`web-ui/src/api/types.ts`、`web-ui/src/api/client.ts`。
- **文档**：`README.md`。
- **测试**：新增禁止词静态扫描测试（pytest，扫描仓库）；更新/保留回归测试覆盖 `/recommend`、`/score-rank`、大学费用。
- **API**：`/life-paths`、`/life-trajectory` 从导航与文档移除（deprecated），端点本身不禁用以保持回归可用。
- **依赖**：无新增依赖。
- **与活跃 change `v22-eligibility-core` 的关系**：其 Phase 1-2（资格/录取）与本变更无冲突，保留；其 Phase 4（三路径）/Phase 5（路径前端）属本次去叙事覆盖范围，本变更完成后该 change 若继续推进需调整其 Phase 4/5 范围。
- **与拆分项 B（volunteer-advisory-engine）的关系**：本变更先行清除叙事与冲突代码，B 在干净基线上建 advisory 主接口；本变更不动推荐算法逻辑、不动资格/录取引擎。
