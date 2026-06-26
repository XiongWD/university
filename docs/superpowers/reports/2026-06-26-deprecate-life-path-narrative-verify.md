# 验证报告：deprecate-life-path-narrative（拆分项 A — 去叙事 / 去交易化）

- **Change**: deprecate-life-path-narrative
- **Date**: 2026-06-26
- **Branch**: feature/20260626/deprecate-life-path-narrative
- **Base-ref**: bad9258
- **verify_mode**: full（17 任务 / 26 文件 / 1 capability）
- **关联**：父设计 `docs/superpowers/specs/2026-06-26-volunteer-recommendation-refocus-design.md`

## Summary

| 维度 | 状态 |
|------|------|
| Completeness | 17/17 任务完成；5/5 requirements 实现 |
| Correctness | 10/10 scenarios 覆盖（实现 + 测试） |
| Coherence | 实现遵循 Design Doc 6 项决策；无矛盾 |

**Fresh verification evidence（本次报告内现场运行）：**
- `python -m pytest -q` → **323 passed**（含 narrative-policy 3 项 + 新增 deprecated 端点 smoke 2 项）
- build_command（import check）→ BUILD OK
- `openspec validate deprecate-life-path-narrative` → valid
- `npm run build`（web-ui）→ exit 0，1586 modules
- 代码审查（standard）：verdict = **Ready to merge: Yes**，无 Critical/Important

## Completeness

- **任务完成**：17/17 `[x]`（grep 确认 `- [ ]` 计数为 0）。
- **requirements 实现**：narrative-policy delta spec 5 个 requirement 全部落地：
  1. 禁止人生固化叙事 → 前端导航/标题/README 清除 ✓
  2. 禁止交易化叙事 → 回本卡片移除 + 生成侧切断 + 静态扫描 ✓
  3. 三路径优化器移出主链路 → `trajectory.py` 不导入 `life_path`；`build_life_paths` 仅 `/life-paths` deprecated 端点调用 ✓
  4. deprecated 端点可见性 → FastAPI `deprecated=True` + 导航移除 + smoke 测试 2xx ✓
  5. 回归可用性 → `/recommend`、`/score-rank`、大学费用、`/life-trajectory`、`/life-paths` 全部回归通过 ✓

## Correctness（scenario 逐项核验）

| Scenario | 核验 | 结果 |
|----------|------|------|
| 前端导航不含人生路径入口 | `App.tsx navItems` 无"人生路径" | ✓ |
| 主页标题不含人生固化叙事 | `HomePage.tsx:42` = "高考志愿专业推荐" | ✓ |
| README 不以人生固化叙事定位 | `rg` 0 命中 | ✓ |
| 推荐卡片不含回本指标 | `TrajectoryCard.tsx` 0 处 `回本/lifetime_15y_net/TrendingUp/Clock` | ✓ |
| 主流程不生成回本数据 | `_build_payback` 仅定义（:108），**0 调用点**；`_item_from_suggestion` 直设 `payback=None` | ✓ |
| 静态扫描禁止交易化词汇 | `tests/test_narrative_policy.py` 3 passed | ✓ |
| 推荐主链路不调用三路径优化 | `trajectory.py` 不导入 `life_path`；`build_life_paths` 仅 `volunteer.py:405`（`/life-paths`） | ✓ |
| deprecated 端点仍可运行 | smoke 测试：`/life-trajectory`、`/life-paths` 均 200 + 结构完整 + payback None + deprecated 标记 | ✓ |
| deprecated 端点不在主导航出现 | `App.tsx` 无 `/life-paths` 路由/导航；README 无 `/life-paths` 页面行 | ✓ |
| 传统冲稳保与位次工具仍可用 | `/recommend`、`/score-rank` 回归全绿 | ✓ |

## Coherence（Design Doc 决策遵循）

| 决策 | 遵循 | 证据 |
|------|------|------|
| D1 软弃用（非物理删除） | ✓ | `life_path.py`/`trajectory._build_payback`/`LifePathsPage` 源码保留 + `# DEPRECATED` |
| D2 回本从生成侧切断（非渲染层） | ✓ | `_item_from_suggestion` 设 `payback=None`；`_build_payback` return None；**0 调用点** |
| D3 禁止词白名单按可见性+语境 | ✓ | 扫描覆盖 `web-ui/src`+`README`+`app/api`；`app/engine`/`app/models` 内部注释不扫 |
| D4 README/品牌口径 | ✓ | 标题"高考志愿专业推荐系统"；副标题对齐设计 §5 |
| D5 新建 narrative-policy capability | ✓ | delta spec 5 reqs / 10 scenarios，validate 通过 |
| D6 pytest 静态扫描零依赖 | ✓ | `tests/test_narrative_policy.py` 仅用 stdlib |

**Spec 漂移检查（检查项 6）**：delta spec 与 Design Doc 无矛盾。Build 阶段未对 spec 做偏离 Design Doc 的增量修改。

## 代码审查（standard review_mode）

- 审查范围：`bad9258..HEAD`（26 文件）
- verdict：**Ready to merge: Yes**
- Critical / Important：无
- Minor（已处理）：
  - M1 缺 deprecated 端点 HTTP smoke 测试 → **已修复**（新增 2 项，323 passed）
  - M2 LifePathsPage 死代码 → **已验证** `npm run build` exit 0，属有意保留的 deprecated 内部页
  - M3 `_build_payback` 缺 docstring → **已修复**（补一行 stub docstring）

## Issues

- **CRITICAL**：无
- **WARNING**：无
- **SUGGESTION**：无（M1-M3 审查反馈均已闭环）

## 安全检查

- 无硬编码密钥
- 无新增 unsafe 操作
- 无新依赖引入

## Final Assessment

所有检查通过。323 测试全绿，禁止词静态扫描通过，回本从生成侧彻底切断，deprecated 端点经 smoke 测试确认仍可运行，代码审查 Ready to merge。

**Ready for archive.**
