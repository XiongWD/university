## 1. 真实覆盖报告与上线门禁

- [x] 1.1 实现 `build_actual_henan_coverage(seed_dir)`：基于实际 seed 计数（universities/groups/plans）+ 质量指标（verified 专业组/verified 计划/非零计划/verified 历史位次）
- [x] 1.2 实现 `assert_henan_recommendation_ready(report)`：4 项质量指标任一为 0 抛 ValueError
- [x] 1.3 创建 `scripts/build_henan_coverage_report.py` CLI，输出 `data/seed/henan/data_coverage_report.json`
- [x] 1.4 测试 `tests/loader/test_henan_real_coverage_gate.py`：覆盖计数真实 + 门禁拦截零计划/未核验组

## 2. 导入真实 2026 河南招生目录

- [x] 2.1 创建 `scripts/import_henan_2026_catalog.py`：接受 normalized CSV，产 universities/program_groups/enrollment_plans YAML（带 source_url/review_status）
- [x] 2.2 用导入器生成真实 program_groups_2026/enrollment_plans_2026/universities（非零 plan_count）
- [x] 2.3 更新 source_registry.yaml 反映真实状态

## 3. 导入 2025/2024 历史录取基线

- [x] 3.1 创建 `scripts/import_henan_admission_history.py`：normalized CSV → admission_history_{year}.yaml，拒绝 verified 行缺 min_rank
- [x] 3.2 `henan_data_loader.py` 新增 `load_henan_admission_history()` 和 `find_best_historical_baseline()`（专业级→组级→加权趋势→校级兜底→None）
- [x] 3.3 覆盖报告分离 verified_2025_history / verified_2024_history
- [x] 3.4 测试 `tests/loader/test_henan_admission_history_import.py`：verified 缺 min_rank 被拒、2025 专业级优先于组兜底、2024 仅趋势、无历史返回 None

## 4. 真实候选生成器

- [x] 4.1 实现 `build_henan_candidates(profile)`：加载专业组+计划+历史，逐组资格过滤+计划校验+历史位次+分桶，不再返回空
- [x] 4.2 `plan_count=0`/`needs_review`/缺 verified 历史的稳保降级为 需人工复核
- [x] 4.3 测试 `tests/engine/test_henan_candidate_generation.py`：返回院校专业组候选、零计划不进冲稳保

## 5. 河南推荐 API

- [x] 5.1 新增 `POST /henan/recommendation`：返回 data_ready + readiness_errors + coverage + buckets（冲/稳/保/不推荐/需人工复核）
- [x] 5.2 测试 `tests/api/test_henan_recommendation_api.py`：buckets 键齐全、含 coverage

## 6. 首页接入河南推荐 API

- [x] 6.1 前端 types/client 新增 `henanRecommendation()` 与 `HenanRecommendationResult`
- [x] 6.2 HomePage 改调 `/henan/recommendation`，渲染数据就绪 banner + 5 档 buckets + 专业组/专业/计划/阻断原因
- [x] 6.3 保留旧 `advisory()` 客户端不动，仅首页不再使用

## 7. 目标评估复用候选集

- [x] 7.1 目标评估 API 复用 `build_henan_candidates()`（已用，验证真实候选能产生可达冲稳保）
- [x] 7.2 目标评估页显示数据就绪状态/缺口，无可达显示不推荐
- [x] 7.3 测试 `tests/api/test_henan_api.py`：mock 候选返回稳时按专业组显示稳

## 8. 移除独立费用页 + 验收

- [x] 8.1 App.tsx 移除 `/cost` 路由与 UniversityCostPage import，费用并入推荐/目标评估卡片
- [x] 8.2 Playwright e2e：首页标题/数据就绪状态/档位筛选/目标评估联动/480分不推荐/费用页移除
- [x] 8.3 全量 pytest + npm build + 真实 HTTP 手测覆盖报告与推荐
