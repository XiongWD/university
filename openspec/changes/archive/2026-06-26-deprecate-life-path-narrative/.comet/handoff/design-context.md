# Comet Design Handoff

- Change: deprecate-life-path-narrative
- Phase: design
- Mode: compact
- Context hash: 5982573f06d9704e10a1269ea36bed88d4974cc05d54ce1bd3aad7801c94db6a

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/deprecate-life-path-narrative/proposal.md

- Source: openspec/changes/deprecate-life-path-narrative/proposal.md
- Lines: 1-42
- SHA256: 05640cb9bbc902db655becf33d2eae25b0537dba9d5271b71aae37c0d2573d9f

```md
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
```

## openspec/changes/deprecate-life-path-narrative/design.md

- Source: openspec/changes/deprecate-life-path-narrative/design.md
- Lines: 1-84
- SHA256: cfa3a4d18c260cf9e557eef519f72fc2e16ed65799b9f42a500a7801ac608c80

[TRUNCATED]

```md
## Context

本变更是 `volunteer-recommendation-refocus` 设计文档落地的第一步，目标是把产品从"人生经济模型/路径推演"纠偏为"高考志愿与专业选择辅助系统"，**只做去叙事/去交易化，不引入新推荐能力**。

当前状态（经代码勘察确认）：

- **回本/ROI 的唯一计算点**：`app/engine/trajectory.py` 的 `_build_payback()`（107-135 行），产出 `years_to_break_even`（回收周期）、`lifetime_15y_net`（15年净收益）、判断文案"回本极快/较快/正常/较慢"。流入 `PaybackAnalysis`（`app/models/life_trajectory.py:37-44`）并挂在每个 `TrajectoryItem.payback`。
- **三路径优化器**：`app/engine/life_path.py`，`PATH_WEIGHTS`（稳健/均衡/进取）、`compute_path_score`、`build_life_paths`。`LifePath.estimated_payback_years` 字段恒为 `None`（从未计算），实际回本只在 trajectory 路径——说明两套遗留代码有重复/不一致。
- **API 端点**（均挂 `/api/v1/volunteer` 前缀）：`/recommend`（`volunteer.py:143`，传统冲稳保，**保留**）、`/life-paths`（`volunteer.py:301`）、`/life-trajectory`（`volunteer.py:187`）、`/admissions`（查询，保留）。
- **前端**：React18+TS+Vite。导航在 `App.tsx:9-15`；副标题"人生经济模型模拟器"在 `App.tsx:28`；HomePage hero"填报志愿，看见孩子的人生轨迹"`HomePage.tsx:42`、副标题含"回本周期"`HomePage.tsx:46`；回本卡片在 `TrajectoryCard.tsx:143-156`；"人生路径"导航 `/life-paths` 在 `App.tsx:10`；`LifePathsPage.tsx:67` 标题"三条人生路径"。
- **README**：`README.md:1,3,5` 仍写"人生经济模型模拟器""教育经济决策系统""三条人生路径（稳健/均衡/进取）"。
- **约束**：现有活跃 change `v22-eligibility-core` 的资格/录取引擎（`eligibility.py`/`admission_prediction.py`）与本变更无冲突、需保留；其 Phase 4/5（三路径/路径前端）属本次去叙事范围。

参考：`docs/superpowers/specs/2026-06-26-volunteer-recommendation-refocus-design.md` §1/§5/§6.1。

## Goals / Non-Goals

**Goals:**
- 用户可见主流程（前端 src、README、API 描述、docstring）中不再出现禁止词作为功能名或推荐结果：`人生路径 / 人生轨迹 / 回本 / ROI / 投资回报 / 15年净收益 / 命运 / 赛道`。
- 回本/ROI 计算与三路径优化器从推荐主链路移除，不再生成、不再渲染。
- `/life-paths`、`/life-trajectory` 降级为 deprecated：可运行以维持回归，但不在 UI/README/导航出现。
- 现有 `/recommend`、`/score-rank`、大学费用在去叙事后仍可用（回归保障）。

**Non-Goals:**
- 不新增 advisory 主接口、不改专业方向评分算法、不动资格/录取引擎（属拆分项 B `volunteer-advisory-engine`）。
- 不删除遗留模型/端点源码（保留 deprecated 以维持兼容与回归），只切断主流程生成与用户可见入口。
- 不做数据 ETL、不爬招生章程（设计 §8 明确排除）。
- 不重写整个 TrajectoryCard——只移除回本卡片列，其余（冲稳保、费用、就业参考）保留。

## Decisions

### D1. "软弃用"而非物理删除
- **决策**：`life_path.py`、`trajectory._build_payback()`、`/life-paths`、`/life-trajectory`、`LifePathsPage` 源码保留，仅切断主流程调用与用户可见入口，加 `# DEPRECATED:` 注释说明。
- **理由**：① 维持 `/life-trajectory`、`/life-paths` 端点可运行以满足回归测试（设计 §6.5）；② 物理删除涉及大范围改动且无法回滚，软弃用风险更低、范围可控；③ 设计 §4 允许"短期保留兼容，改为内部 deprecated，不在 UI/README/主导航中出现"。
- **替代方案**：物理删除 `life_path.py` 与端点——风险高、违背"维持回归可用"验收、与设计兼容性表述冲突，**不采用**。

### D2. 回本从生成侧切断，而非渲染侧兜底
- **决策**：让 `life-trajectory` 主流程不再调用 `_build_payback()`，使 `TrajectoryItem.payback` 在主链路为 `None`/不生成；前端 `TrajectoryCard` 移除整个回本列，而非用占位符兜底。
- **理由**：若只在渲染层隐藏、后端仍算，属于"只改文案不改模型"——设计 §7 明确"若实现只改文案但保留回本模型作为主流程输出，不通过验收"。必须从生成侧切断。
- **权衡**：`life-trajectory` 端点回归测试需相应调整为不依赖 `payback` 字段。

### D3. 禁止词白名单：按"可见性+语境"而非全局禁用
- **决策**：静态扫描只覆盖**用户可见主流程**目录：`web-ui/src/`、`README.md`、`app/` 的 docstring/面向用户的字符串。允许在以下位置出现禁止词：本设计文档自身、归档文档、`openspec/` 规约、deprecated 注释（`# DEPRECATED` / `// DEPRECATED` 同行）。
- **理由**：全局禁用会误伤历史文档与本次规约；设计 §6.1 明确"允许在归档文档或 deprecated 注释中出现，但必须明确为历史遗留或废弃接口"。
- **替代方案**：全局 `grep` 禁止——误报多、阻塞归档，**不采用**。

### D4. README 与品牌重写口径
- **决策**：
  - 标题改为"高考志愿专业推荐系统"（去"人生经济模型模拟器"）。
  - 首段定位改为：基于分数、选科、外语、数学、一分一段与家庭预算，生成可解释的专业方向与冲稳保院校建议。
  - 副标题采用设计 §5 建议文案。
- **理由**：直接对齐设计 §5 主/副标题建议，避免自创口径。

### D5. 新建 `narrative-policy` capability（OpenSpec 硬约束）
- **决策**：新建 capability `narrative-policy`，把禁止词口径与 deprecated 可见性约束规约为可验证的 requirements（含 WHEN/THEN 场景）。
- **理由**：OpenSpec `validate` 强制每个 change 至少有一个 delta（`validate` 实测报错 "Change must have at least one delta"）。最初设想的"不创建 spec、仅靠测试"违反该硬约束。将口径规约为 capability 比纯测试更优：归档后成为 `openspec/specs/narrative-policy/` 主 spec，长期可审计、可演进，且拆分项 B 与后续变更都能引用同一套叙事口径。
- **范围**：`narrative-policy` 只规约"不得呈现什么 + deprecated 可见性"，不含推荐算法行为（属 B）。
- **替代方案**：把禁止词塞进现有 `student-profile-data` 等不相关 spec——语义错位，**不采用**。

### D6. 测试落地为 pytest 静态扫描，不引入新依赖
- **决策**：新增 `tests/test_narrative_policy.py`，用标准库 `pathlib`+`re` 扫描白名单目录，断言禁止词不出现；不引入第三方 lint。
- **理由**：项目用 pytest；零新增依赖；扫描逻辑简单可控；deprecated 行靠"同行含 DEPRECATED 关键字"豁免。

## Risks / Trade-offs

- **[风险] 软弃用导致死代码长期留存** → 缓解：每个 deprecated 点加 `# DEPRECATED: 见 volunteer-recommendation-refocus` 注释，便于后续清理；拆分项 B 完成后可评估彻底删除。
- **[风险] `/life-trajectory` 回归测试因 payback 切断而失败** → 缓解：同步更新该端点测试，断言 `payback` 不再生成而非断言其值；新增回归确认端点仍 200。
- **[风险] 前端移除回本卡片导致布局错乱** → 缓解：`TrajectoryCard` 改为两列（费用 + 就业参考），本地构建校验；保留组件其余结构。
- **[风险] 与 `v22-eligibility-core` change 的 Phase 4/5 范围冲突** → 缓解：本变更 proposal 的 Impact 段已声明覆盖范围；完成后提示该 change 调整 Phase 4/5。
- **[权衡] 禁止词扫描可能漏掉编译产物 `web-ui/dist/`** → 决策：扫描只针对 `src/`，dist 是 src 编译结果，源端无禁止词即等价；CI 不额外扫 dist。
- **[权衡] `LifePath`/`PaybackAnalysis` 模型字段保留** → 保留以便 deprecated 端点仍可序列化历史结构，但主流程不再填充；属可接受遗留。

## Migration Plan

1. 后端：`trajectory.py` 停用 `_build_payback` 主链路调用 + 加 deprecated 注释；`life_path.py` 加 deprecated 注释（不从模块级移除，仅切断 `/life-trajectory` 主流程对相关生成的依赖，`/life-paths` 端点自身保留但标注 deprecated）。
2. API：`volunteer.py` 中 `life_paths`/`life_trajectory` handler 加 deprecated docstring 与响应 `notes` 提示。
3. 前端：`App.tsx` 去"人生路径"导航 + 改品牌/副标题；`HomePage.tsx` 改标题/副标题；`TrajectoryCard.tsx` 移除回本列；`LifePathsPage` 移出路由导航；`types.ts`/`client.ts` 注释中性化。
4. 文档：`README.md` 重写。
5. 测试：新增 `tests/test_narrative_policy.py`；更新 `/life-trajectory` 回归测试。
6. **回滚**：每步独立提交；若需回滚按提交顺序 `git revert`，无 schema/数据迁移、无外部依赖变更，回滚无副作用。
```

Full source: openspec/changes/deprecate-life-path-narrative/design.md

## openspec/changes/deprecate-life-path-narrative/tasks.md

- Source: openspec/changes/deprecate-life-path-narrative/tasks.md
- Lines: 1-43
- SHA256: b77952c2562aaba348c50b8196b096dcac1e725cac965ce8efd54f1552551a03

```md
# Tasks — deprecate-life-path-narrative

> 拆分项 A：去叙事 / 去交易化。对应 capability `narrative-policy`。
> 范围：禁止人生固化叙事（路径/轨迹/赛道）与交易化叙事（回本/ROI/15年净收益）出现在用户可见主流程。
> 非目标：不改推荐算法、不动资格/录取引擎、不新增 advisory 接口（属拆分项 B）。

## 1. 后端：去交易化（回本/ROI 从主链路切断）

- [ ] 1.1 `app/engine/trajectory.py`：停用 `_build_payback()` 在主链路的调用，使 `TrajectoryItem.payback` 不再被填充；为 `_build_payback` 加 `# DEPRECATED:` 注释，指向 volunteer-recommendation-refocus
- [ ] 1.2 `app/engine/life_path.py`：为 `build_life_paths`/`compute_path_score`/`PATH_WEIGHTS` 加 `# DEPRECATED:` 注释；确认主推荐流程不再调用其生成面向用户的路径建议
- [ ] 1.3 `app/models/life_trajectory.py`：`PaybackAnalysis`（`lifetime_15y_net` "15年净收益"）与 `LifeTrajectory` 模块 docstring 加 deprecated 标注；字段保留但注释明确不再主链路填充
- [ ] 1.4 `app/models/life_path.py`：`LifePath.estimated_payback_years` 及"人生路径"相关 docstring 加 deprecated 标注

## 2. 后端：deprecated 端点可见性

- [ ] 2.1 `app/api/routers/volunteer.py`：`life_paths`（:301）与 `life_trajectory`（:187）handler 加 deprecated docstring；响应 `notes` 追加 deprecated 提示（不破坏返回结构）
- [ ] 2.2 更新 `/life-trajectory` 回归测试：断言 `payback` 不再生成而非断言其值；断言端点仍返回 2xx

## 3. 前端：去人生固化叙事

- [ ] 3.1 `web-ui/src/App.tsx`：移除"人生路径"导航项（`/life-paths`）与对应路由暴露；品牌区副标题删除"人生经济模型模拟器"（:28）；导航项 label 文案中性化
- [ ] 3.2 `web-ui/src/pages/HomePage.tsx`：主标题改"高考志愿专业推荐"；删除"填报志愿，看见孩子的人生轨迹"（:42）；副标题删除"回本周期"字样（:46）
- [ ] 3.3 `web-ui/src/pages/LifePathsPage.tsx`：从路由主导航移除（"三条人生路径"标题、生成按钮不在入口暴露）
- [ ] 3.4 `web-ui/src/api/types.ts`、`web-ui/src/api/client.ts`：将"人生轨迹（…）/ V2.2 人生路径"注释改为中性描述

## 4. 前端：去交易化卡片

- [ ] 4.1 `web-ui/src/components/TrajectoryCard.tsx`：移除"回本周期"卡片（:143-156）与 `payback.lifetime_15y_net` 渲染（:151,163）；改为两列（费用 + 就业参考）
- [ ] 4.2 本地构建校验（`web-ui` 构建/类型检查）确保布局与类型无错

## 5. 文档

- [ ] 5.1 `README.md`：标题去"人生经济模型模拟器"、改"高考志愿专业推荐系统"；首段去"教育经济决策系统/三条人生路径（稳健/均衡/进取）/优化…教育回报"，改志愿辅助系统定位与设计 §5 副标题文案

## 6. 测试：narrative-policy 静态扫描

- [ ] 6.1 新增 `tests/test_narrative_policy.py`：用 `pathlib`+`re` 扫描白名单目录（`web-ui/src/`、`README.md`、`app/` 面向用户字符串/docstring），断言禁止词（人生路径/人生轨迹/回本/ROI/投资回报/15年净收益/命运/赛道）不出现；豁免 `DEPRECATED` 同行注释、归档文档、`openspec/`、本设计文档
- [ ] 6.2 运行 `pytest tests/test_narrative_policy.py` 通过

## 7. 回归验收

- [ ] 7.1 运行全量 `pytest`，确认 `/recommend`、`/score-rank`、大学费用相关测试仍通过
- [ ] 7.2 `openspec validate deprecate-life-path-narrative` 通过
```

## openspec/changes/deprecate-life-path-narrative/specs/narrative-policy/spec.md

- Source: openspec/changes/deprecate-life-path-narrative/specs/narrative-policy/spec.md
- Lines: 1-89
- SHA256: 583f9c55230793369f5519388bc1ffc2b856ba3be25f0c7973925d1e08a3e7d0

[TRUNCATED]

```md
# Spec Delta: narrative-policy

本 delta 为新建 capability `narrative-policy` 定义 requirements。规约系统在用户可见主流程中不得呈现的两类叙事，以及 deprecated 端点的可见性约束。对应 `docs/superpowers/specs/2026-06-26-volunteer-recommendation-refocus-design.md` §2/§5/§6.1。

## ADDED Requirements

### Requirement: 禁止人生固化叙事

系统在用户可见主流程中 SHALL NOT 把"人生路径""人生轨迹""人生赛道""命运路线"等成长固化叙事作为功能名称、导航项或推荐结果呈现。

用户可见主流程包括：前端源码（`web-ui/src/`）、README 主说明、API 端点描述与 docstring、面向用户的响应字符串。归档文档、`openspec/` 规约、标注 `DEPRECATED` 的注释豁免。

#### Scenario: 前端导航不含人生路径入口

WHEN 扫描前端导航定义（`web-ui/src/App.tsx` 的 `navItems`）
THEN 导航项的 label 与 path 中 MUST NOT 出现 "人生路径"/"人生轨迹"/"赛道"/"命运"
AND MUST 存在面向志愿推荐的主入口

#### Scenario: 主页标题不含人生固化叙事

WHEN 渲染主页 hero 区域（`HomePage.tsx`）
THEN 标题与副标题文本 MUST NOT 包含 "填报志愿，看见孩子的人生轨迹"
AND MUST NOT 包含 "人生路径"/"人生轨迹"/"赛道"/"命运"

#### Scenario: README 不以人生固化叙事定位产品

WHEN 读取 `README.md` 首部标题与首段
THEN MUST NOT 出现 "人生经济模型模拟器" 作为产品定位
AND MUST NOT 宣传 "三条人生路径（稳健/均衡/进取）" 作为核心功能

### Requirement: 禁止交易化叙事

系统在用户可见主流程中 SHALL NOT 把"回本""回本周期""ROI""投资回报""投资回报率""15年净收益"等把上大学描述为交易的叙事作为功能名称、卡片或推荐结果呈现。

费用、就业、薪资区间仍可作为"约束与参考"呈现，但不得计算或展示投资回本指标。

#### Scenario: 推荐卡片不含回本指标

WHEN 渲染志愿推荐结果卡片（`TrajectoryCard.tsx`）
THEN MUST NOT 存在 "回本周期" 卡片/列
AND MUST NOT 渲染 `lifetime_15y_net`（15年净收益）字段

#### Scenario: 主流程不生成回本数据

WHEN 执行志愿推荐主链路（`/life-trajectory` 主流程组装）
THEN 系统 MUST NOT 调用 `_build_payback()` 生成 `years_to_break_even`/`lifetime_15y_net`
AND `TrajectoryItem.payback` 在主链路 MUST NOT 被填充为回本分析结果

#### Scenario: 静态扫描禁止交易化词汇

WHEN 对用户可见主流程目录（`web-ui/src/`、`README.md`、`app/` 的面向用户字符串/docstring）执行静态扫描
THEN MUST NOT 出现 "回本"/"ROI"/"投资回报"/"15年净收益" 作为功能名或结果描述
EXCEPT 标注 `DEPRECATED` 的同行注释、归档文档、本设计文档自身

### Requirement: 三路径优化器移出推荐主链路

三路径优化器（稳健/均衡/进取）SHALL NOT 作为推荐主链路的输出生成。相关引擎代码可保留为 deprecated 以维持回归兼容，但 MUST NOT 在主推荐流程中被调用并呈现给用户。

#### Scenario: 推荐主链路不调用三路径优化

WHEN 组装志愿推荐主流程结果
THEN 主链路 MUST NOT 调用 `app/engine/life_path.py` 的 `build_life_paths()` 生成面向用户的路径建议
AND 三路径优化器模块 MUST 标注为 deprecated

### Requirement: deprecated 端点的可见性约束

`POST /api/v1/volunteer/life-paths` 与 `POST /api/v1/volunteer/life-trajectory` SHALL 保留可运行以维持回归兼容，但 MUST 标注为 deprecated，且 MUST NOT 出现在 UI 导航、README 主说明、主导航中。

#### Scenario: deprecated 端点仍可运行

WHEN 调用 `POST /api/v1/volunteer/life-trajectory` 与 `POST /api/v1/volunteer/life-paths`
THEN 端点 MUST 返回成功响应（HTTP 2xx）以维持回归
AND 端点 docstring/notes MUST 标注 deprecated

#### Scenario: deprecated 端点不在主导航出现

WHEN 读取前端导航项与 README 主说明
THEN `/life-paths`、`/life-trajectory` 端点 MUST NOT 作为导航项或推荐功能出现
AND `LifePathsPage` MUST NOT 在主导航入口暴露

```

Full source: openspec/changes/deprecate-life-path-narrative/specs/narrative-policy/spec.md

