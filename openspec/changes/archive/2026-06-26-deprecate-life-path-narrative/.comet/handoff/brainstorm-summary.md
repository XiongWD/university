# Brainstorm Summary

- Change: deprecate-life-path-narrative
- Date: 2026-06-26

## 确认的技术方案

拆分项 A：去叙事 / 去交易化。两轮澄清的关键决策已敲定：

1. **HomePage 数据源**：保留调用 deprecated 的 `/life-trajectory`，**仅去回本**（不切 `/recommend`、不复活死代码组件）。新 advisory UI 留给拆分项 B。这样拆分项 A 范围最小、回本不再生成。
2. **回本切断点**：`_build_payback()` 当前在 `_item_from_suggestion()`（`trajectory.py:149`）被调用 → 主链路停用此调用，使 `TrajectoryItem.payback = None`。`_build_payback` 函数体保留 + 加 `# DEPRECATED` 注释（D2：从生成侧切断，非渲染侧兜底）。
3. **禁止词扫描粒度**：只扫**用户可见文案**——README、API 模块/端点 docstring、HTTP 响应中的面向用户字符串、前端 `web-ui/src/`。`app/` 内部算法注释（如 `trajectory.py:108-128` 的回本计算注释）**不在扫描范围**，不强制改写。
4. **docstring 中性化（非 deprecated 标记）**：`volunteer.py:4`（模块 docstring "人生路径"）、`:189`（life_trajectory 端点 docstring "多久回本"）属面向用户的 API 描述，须改为中性描述，**不能**靠 `# DEPRECATED` 豁免——因为 docstring 本身就是用户可见的 API 说明。`DEPRECATED` 豁免仅用于内部注释。

## 关键取舍与风险

- **取舍**：HomePage 仍依赖 deprecated 端点——但符合 narrative-policy 的 deprecated 可见性约束（内部可运行、不在导航/README/主导航），且拆分项 B 会替换它。可接受。
- **风险**：`/life-trajectory` 回归测试可能断言 `payback` 字段值 → 缓解：改断言为"payback 不再生成"且端点仍 2xx。
- **风险**：TrajectoryCard 移除回本列后布局 → 改两列（费用 + 就业参考），本地 tsc/构建校验。
- **与父设计文档关系**：父文档 `2026-06-26-volunteer-recommendation-refocus-design.md` 覆盖整个重构（含 B）。本 change Design Doc 是父文档的拆分项 A 专属技术设计，聚焦实现细节与 A/B 边界，不重复父文档的产品定位论述。

## 测试策略

- 新增 `tests/test_narrative_policy.py`：`pathlib`+`re` 扫描白名单目录，禁止词断言；豁免逻辑 = 内部注释不扫 + `DEPRECATED` 同行豁免（针对注释）。
- 更新 `/life-trajectory` 回归测试：断言 payback 不生成、端点 2xx。
- 全量 `pytest` 回归：`/recommend`、`/score-rank`、大学费用。
- `openspec validate` 通过。

## Spec Patch

无（narrative-policy delta spec 的 5 个 requirements / 10 个场景已充分覆盖上述决策；docstring 中性化属 D3 扫描范围已含，无需新增 scenario）。
