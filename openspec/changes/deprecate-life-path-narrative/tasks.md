# Tasks — deprecate-life-path-narrative

> 拆分项 A：去叙事 / 去交易化。对应 capability `narrative-policy`。
> 范围：禁止人生固化叙事（路径/轨迹/赛道）与交易化叙事（回本/ROI/15年净收益）出现在用户可见主流程。
> 非目标：不改推荐算法、不动资格/录取引擎、不新增 advisory 接口（属拆分项 B）。

## 1. 后端：去交易化（回本/ROI 从主链路切断）

- [x] 1.1 `app/engine/trajectory.py`：停用 `_build_payback()` 在主链路的调用，使 `TrajectoryItem.payback` 不再被填充；为 `_build_payback` 加 `# DEPRECATED:` 注释，指向 volunteer-recommendation-refocus
- [x] 1.2 `app/engine/life_path.py`：为 `build_life_paths`/`compute_path_score`/`PATH_WEIGHTS` 加 `# DEPRECATED:` 注释；确认主推荐流程不再调用其生成面向用户的路径建议
- [x] 1.3 `app/models/life_trajectory.py`：`PaybackAnalysis`（`lifetime_15y_net` "15年净收益"）与 `LifeTrajectory` 模块 docstring 加 deprecated 标注；字段保留但注释明确不再主链路填充
- [x] 1.4 `app/models/life_path.py`：`LifePath.estimated_payback_years` 及"人生路径"相关 docstring 加 deprecated 标注

## 2. 后端：deprecated 端点可见性

- [x] 2.1 `app/api/routers/volunteer.py`：`life_paths`（:301）与 `life_trajectory`（:187）handler 加 deprecated docstring；响应 `notes` 追加 deprecated 提示（不破坏返回结构）
- [x] 2.2 更新 `/life-trajectory` 回归测试：断言 `payback` 不再生成而非断言其值；断言端点仍返回 2xx

## 3. 前端：去人生固化叙事

- [x] 3.1 `web-ui/src/App.tsx`：移除"人生路径"导航项（`/life-paths`）与对应路由暴露；品牌区副标题删除"人生经济模型模拟器"（:28）；导航项 label 文案中性化
- [x] 3.2 `web-ui/src/pages/HomePage.tsx`：主标题改"高考志愿专业推荐"；删除"填报志愿，看见孩子的人生轨迹"（:42）；副标题删除"回本周期"字样（:46）
- [x] 3.3 `web-ui/src/pages/LifePathsPage.tsx`：从路由主导航移除（"三条人生路径"标题、生成按钮不在入口暴露）
- [x] 3.4 `web-ui/src/api/types.ts`、`web-ui/src/api/client.ts`：将"人生轨迹（…）/ V2.2 人生路径"注释改为中性描述

## 4. 前端：去交易化卡片

- [x] 4.1 `web-ui/src/components/TrajectoryCard.tsx`：移除"回本周期"卡片（:143-156）与 `payback.lifetime_15y_net` 渲染（:151,163）；改为两列（费用 + 就业参考）
- [x] 4.2 本地构建校验（`web-ui` 构建/类型检查）确保布局与类型无错

## 5. 文档

- [x] 5.1 `README.md`：标题去"人生经济模型模拟器"、改"高考志愿专业推荐系统"；首段去"教育经济决策系统/三条人生路径（稳健/均衡/进取）/优化…教育回报"，改志愿辅助系统定位与设计 §5 副标题文案

## 6. 测试：narrative-policy 静态扫描

- [x] 6.1 新增 `tests/test_narrative_policy.py`：用 `pathlib`+`re` 扫描白名单目录（`web-ui/src/`、`README.md`、`app/` 面向用户字符串/docstring），断言禁止词（人生路径/人生轨迹/回本/ROI/投资回报/15年净收益/命运/赛道）不出现；豁免 `DEPRECATED` 同行注释、归档文档、`openspec/`、本设计文档
- [x] 6.2 运行 `pytest tests/test_narrative_policy.py` 通过

## 7. 回归验收

- [x] 7.1 运行全量 `pytest`，确认 `/recommend`、`/score-rank`、大学费用相关测试仍通过
- [x] 7.2 `openspec validate deprecate-life-path-narrative` 通过
