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

## Open Questions

- 无阻塞性开放问题。D5（是否需要 capability spec）已决策为不创建；若 `/comet-verify` 阶段静态扫描发现需要更强约束，再回头补充。
