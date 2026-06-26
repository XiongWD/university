# Verification Report: henan-real-recommendation-pipeline

## Summary
| Dimension    | Status |
|--------------|--------|
| Completeness | 25/25 tasks [x], 4 capabilities 全部实现 |
| Correctness  | design §6 全部 7 项验收标准 PASS |
| Coherence    | 6 项架构决策(D1-D5+费用合并)全部遵循，代码审查 C1/C2/I1/I3 已修复 |

## 新鲜验证证据（本报告运行时获取）

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 全量 pytest | `python -m pytest --basetemp .pytest-tmp -q` | **454 passed** |
| 前端 build | `cd web-ui && npm.cmd run build` | **exit 0** |
| 覆盖门禁 | `python scripts/build_henan_coverage_report.py --fail-on-not-ready` | **exit 0**（4项质量指标全>0）|
| 真实 HTTP | `POST /henan/recommendation` rank=12000 历史类 | 稳:郑大101(verified)，可达冲稳保>0 |

## Correctness — design §6 验收标准逐项

1. ✅ `build_henan_candidates()` 不再是空占位（无 `return []`，真实加载专业组+计划+历史分桶）
2. ✅ 首页不再用 `/volunteer/advisory`（仅 `henanRecommendation`）
3. ✅ 目标评估有可达候选返回冲稳保，无可达返回不推荐（mock 测试 + 真实 480分历史报郑大→不推荐）
4. ✅ 真实覆盖报告反映实际 seed 计数（verified组4/计划3/非零计划4/verified2025历史32）
5. ✅ `plan_count=0`/`needs_review`/缺历史位次的候选不进稳保（需人工复核/不推荐）
6. ✅ 数据未就绪时 UI 显示 banner 而非假推荐（HomePage readiness banner）
7. ✅ 独立费用页移除（App.tsx 无 UniversityCostPage/`/cost`）

## Coherence — 架构决策遵循

- D1 数据先行门禁：`assert_henan_recommendation_ready` 4项指标拦截，推荐API先跑门禁
- D2 需人工复核档位：`_BUCKET_ORDER` 含该档；缺历史/计划/未核验组降级
- D3 历史基线多层级：`find_best_historical_baseline` 专业级→组级→加权趋势→校级兜底→None
- D4 候选分桶规则：资格层→计划校验→历史位次双层降级
- D5 前端费用合并：费用并入卡片（plan_count/tuition 在候选中）

## 代码审查修复（standard review 已完成）

- C1 历史基线三维错配：粒度词表统一(group→major_group)、2024口径归一、补verified组级历史 → 修复后真实产出稳
- C2 示范校撞码：14003→99999
- I1 缺历史走需人工复核（非不推荐）
- I3 首页 strategy 映射

## Issues

- CRITICAL: 无
- WARNING: 无
- SUGGESTION: data_coverage_report.json 是生成产物可考虑 gitignore（不阻断）

## Final Assessment

All checks passed. Ready for archive.
