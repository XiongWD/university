---
comet_change: deprecate-life-path-narrative
role: technical-design
canonical_spec: openspec
archived-with: 2026-06-26-deprecate-life-path-narrative
status: final
---

# Design Doc: deprecate-life-path-narrative（拆分项 A — 去叙事 / 去交易化）

本设计是父设计文档 `docs/superpowers/specs/2026-06-26-volunteer-recommendation-refocus-design.md` 的拆分项 A 专属技术实现设计。产品定位、背景、验收口径见父文档；本文聚焦**如何实现去叙事/去交易化**、与父文档的关系、以及与拆分项 B `volunteer-advisory-engine` 的边界。

> 注：本设计文档自身包含禁止词（人生路径/回本/ROI 等），属设计论证必要引用，在 narrative-policy 扫描白名单内。

## 1. 实现目标与范围

### 目标
- 用户可见主流程不再出现禁止词作为功能名/推荐结果：`人生路径 / 人生轨迹 / 回本 / ROI / 投资回报 / 15年净收益 / 命运 / 赛道`。
- 回本/ROI 计算与三路径优化器从推荐主链路移除（从**生成侧**切断，非渲染层兜底）。
- `/life-paths`、`/life-trajectory` 降级为 deprecated：可运行维持回归，不在 UI/README/主导航出现。
- `/recommend`、`/score-rank`、大学费用在去叙事后仍可用。

### 非目标
- 不新增 advisory 主接口、不改专业方向评分算法、不动资格/录取引擎（属拆分项 B）。
- 不删除遗留模型/端点源码（保留 deprecated 维持兼容与回归）。
- 不重写整个 TrajectoryCard（仅移除回本列）。

## 2. 现状（经代码勘察交叉验证）

- **回本唯一计算点**：`app/engine/trajectory.py` `_build_payback()`（:107-135），产出 `years_to_break_even` / `lifetime_15y_net` / 判断文案。在 `_item_from_suggestion()`（:149）被调用，挂到 `TrajectoryItem.payback`。
- **三路径优化器**：`app/engine/life_path.py`（`build_life_paths`/`compute_path_score`/`PATH_WEIGHTS` 稳健/均衡/进取）。`LifePath.estimated_payback_years` 恒为 `None`（从未计算）。
- **API**（挂 `/api/v1/volunteer`）：`/recommend`（:143，保留）、`/life-paths`（:301）、`/life-trajectory`（:187）、`/admissions`（保留）。
- **前端**：导航 `App.tsx:9-15`；副标题"人生经济模型模拟器"`App.tsx:28`；HomePage hero"填报志愿，看见孩子的人生轨迹"`HomePage.tsx:42`、副标题含"回本周期"`HomePage.tsx:46`；回本卡片 `TrajectoryCard.tsx:143-156`；"人生路径"导航 `App.tsx:10`；`LifePathsPage.tsx:67`。
- **面向用户的 docstring 含禁止词**：`volunteer.py:4`（模块 docstring"人生路径"）、`:189`（life_trajectory 端点 docstring"多久回本"）、`:1-5` 模块 docstring。
- **README**：`:1,3,5` 仍写"人生经济模型模拟器""教育经济决策系统""三条人生路径（稳健/均衡/进取）"。

## 3. 实现方案

### 3.1 后端：回本从生成侧切断（D2）
- `app/engine/trajectory.py`：
  - `_item_from_suggestion()`（:149）：停止调用 `_build_payback()`，`payback=None`。**这是回本切断的关键点**——使主链路不再生成回本数据。
  - `_build_payback()`（:107）函数体保留 + 加 `# DEPRECATED: 回本叙事已废弃，见 volunteer-recommendation-refocus；主链路不再调用`。
  - `build_life_trajectory` docstring（:182-185）"回本"→ 中性描述（如"费用与就业参考"）。
- `app/models/life_trajectory.py`：`PaybackAnalysis`（:37-44，含 `lifetime_15y_net`）字段保留，模块 docstring + 字段 docstring 加 deprecated 标注（内部注释，不扫）。

### 3.2 后端：三路径优化器去主链路 + deprecated
- `app/engine/life_path.py`：`build_life_paths`/`compute_path_score`/`PATH_WEIGHTS` 加 `# DEPRECATED:` 注释。确认主推荐流程（HomePage→`/life-trajectory`→`build_life_trajectory`）不调用它。
- `app/models/life_path.py`：`LifePath` 及 docstring 加 deprecated 标注（内部注释）。

### 3.3 后端：deprecated 端点可见性
- `app/api/routers/volunteer.py`：
  - 模块 docstring（:1-5）：去"人生路径"，改为中性"志愿填报引擎 API 端点"。
  - `life_paths`（:301）、`life_trajectory`（:187）handler docstring 加 `(deprecated)` 标记 + 说明已降级；响应 `notes` 追加 deprecated 提示（不破坏返回结构）。
  - `life_trajectory` docstring（:189）"多久回本"→ 中性（"费用与就业参考"）。
  - `:166` 取数辅助注释"人生轨迹用"→ 中性。

### 3.4 前端：去人生固化叙事
- `web-ui/src/App.tsx`：移除"人生路径"导航项（`/life-paths`，:10）及其路由；副标题去"人生经济模型模拟器"（:28）；品牌区中性化。
- `web-ui/src/pages/HomePage.tsx`：主标题→"高考志愿专业推荐"（:42）；删除"填报志愿，看见孩子的人生轨迹"；副标题去"回本周期"（:46）。
- `web-ui/src/pages/LifePathsPage.tsx`：移出主导航入口（"三条人生路径"标题、生成按钮不在入口暴露）。
- `web-ui/src/api/types.ts`（:119,183）、`client.ts`（:46,106）："人生轨迹/V2.2 人生路径"注释→中性。

### 3.5 前端：去交易化卡片
- `web-ui/src/components/TrajectoryCard.tsx`：移除整个"回本周期"卡片列（:143-156）与 `payback.lifetime_15y_net` 渲染（:151,163）→ 改两列（费用 + 就业参考）。本地 tsc/构建校验。
- **HomePage 数据源决策**：保留调用 deprecated `/life-trajectory`（仅去回本）。不切 `/recommend`、不复活死代码组件——新 advisory UI 属拆分项 B。

### 3.6 文档
- `README.md`：标题去"人生经济模型模拟器"→"高考志愿专业推荐系统"；首段去"教育经济决策系统/三条人生路径（稳健/均衡/进取）/优化…教育回报"，改为志愿辅助系统定位（父文档 §5 副标题文案）。

### 3.7 测试
- 新增 `tests/test_narrative_policy.py`：`pathlib`+`re` 扫描**用户可见文案**白名单（`web-ui/src/`、`README.md`、API docstring、HTTP 响应字符串），禁止词断言；内部注释不扫；`DEPRECATED` 同行豁免（针对注释）。
- 更新 `/life-trajectory` 回归测试：断言 `payback` 不再生成 + 端点 2xx。
- 全量 `pytest` 回归。

## 4. 关键取舍

| 决策 | 选择 | 理由 |
|------|------|------|
| 回本切断位置 | 生成侧 `_item_from_suggestion`（非渲染层） | 父文档 §7：只改文案不算数 |
| HomePage 数据源 | 保留 deprecated `/life-trajectory`（仅去回本） | 范围最小；符合 deprecated 可见性约束；新 UI 属 B |
| 扫描粒度 | 仅用户可见文案；`app/` 内部注释不扫 | 零误报，聚焦真正用户可见文案 |
| docstring 处理 | 中性化（非 DEPRECATED 豁免） | docstring 是面向用户的 API 说明，须直接改文案 |
| 弃用方式 | 软弃用（保留源码 + 切断调用 + DEPRECATED 注释） | 维持回归、可回滚；父文档 §4 允许 |
| capability | 新建 `narrative-policy` | OpenSpec validate 强制每 change ≥1 delta；归档后可审计 |

## 5. 风险与缓解

- **HomePage 依赖 deprecated 端点** → 符合 deprecated 可见性约束（内部运行、不在导航/README/主导航）；拆分项 B 替换。可接受。
- **`/life-trajectory` 回归测试断言 payback** → 改断言为"不生成"+ 2xx。
- **TrajectoryCard 布局错乱** → 两列 + 本地构建校验。
- **与 `v22-eligibility-core` change Phase 4/5 冲突** → 本 change Impact 已声明；完成后提示调整。
- **死代码长期留存** → 每点 `# DEPRECATED` 注释；B 完成后评估彻底删除。

## 6. 迁移与回滚
每步独立提交，按提交顺序 `git revert` 即可回滚。无 schema/数据迁移、无外部依赖变更，回滚无副作用。

## 7. 与父设计文档 & 拆分项 B 的边界
- **父文档**：覆盖整个 `volunteer-recommendation-refocus` 重构（产品定位、推荐主流程、API/模型调整、验收）。本文是其拆分项 A 的技术实现设计，不重复产品论述。
- **拆分项 B `volunteer-advisory-engine`**：在 A 的干净基线上建 `POST /api/v1/volunteer/advisory` 主接口 + 专业方向评分主链路 + 费用压力评估；A 不动 `major_fit`/`eligibility`/`admission_prediction`、不建 advisory、不做 ETL。
- **A/B 依赖**：A 先行去叙事，B 后续建新主流程。A 完成后 B 可引用 `narrative-policy` 主 spec 保证不重新引入禁止词。

## 8. 开放问题
无阻塞性开放问题。
