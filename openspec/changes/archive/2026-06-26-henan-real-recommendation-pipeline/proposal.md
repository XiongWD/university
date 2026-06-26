## Why

当前「河南志愿推」是一个样例壳子，不是可验收的真实链路。核实证据：

- `data/seed/henan/enrollment_plans_2026.yaml` 的 3 条计划 `plan_count` 全为 `0`，且均为 `needs_review`。
- `app/engine/henan_recommendation.py::build_henan_candidates()`（第 163 行）只校验生源地后返回 `[]`，未接真实数据。
- `web-ui/src/pages/HomePage.tsx` 仍调用旧 `advisory(req)`，未接入河南新推荐 API；`POST /henan/recommendation` 端点不存在。
- `data/seed/henan/data_coverage_report.example.json` 是示例数字，不是实际覆盖报告。

全量测试通过只能说明样例链路未崩溃，不能证明河南志愿推验收通过。需要从数据先行、引擎统一候选、首页与目标评估消费同一候选集三个层面修复，使其成为可验收的河南 2026 志愿推荐和目标评估主链路。

## What Changes

- **数据先行**：用真实覆盖报告（基于实际 seed 计数）+ 上线门禁替代示例数字。门禁在缺核验专业组/非零计划/历史位次时阻断推荐就绪，杜绝假推荐。
- **历史录取基线**：新增 2025/2024 历史录取位次导入与 `find_best_historical_baseline()` 查找。冲稳保必须依赖历史位次；无 verified 历史支持时不得标 `稳`/`保`。
- **真实候选生成**：`build_henan_candidates()` 真实实现——加载 2026 专业组+计划+历史，逐组做资格过滤、计划校验、历史位次、冲稳保分桶。
- **推荐 API**：新增 `POST /api/v1/henan/recommendation`，返回 `data_ready` + `readiness_errors` + `coverage` + `buckets`（冲/稳/保/不推荐/需人工复核）。
- **前端主链路**：首页切换到 `/henan/recommendation`，数据未就绪时显示 banner 而非假推荐；目标评估复用同一候选集；移除独立费用页。
- **兼容层保留**：旧 `/volunteer/*` 和旧 `/target/evaluate` 保留兼容，不再作为河南志愿推主链路扩展。

## Capabilities

### New Capabilities
- `henan-real-coverage-gate`: 基于实际 seed 计数的真实覆盖报告 + 推荐就绪门禁（verified 专业组、非零计划、verified 历史位次缺一即阻断）
- `henan-candidate-generation`: 院校专业组候选统一生成器（资格→计划校验→历史位次→冲稳保分桶），首页推荐与目标评估共同消费
- `henan-recommendation-api`: `POST /henan/recommendation` 推荐主端点，输出 data_ready + buckets + coverage
- `henan-history-baseline`: 2025/2024 历史录取位次导入与多层级基线查找（专业级→专业组级→校级兜底）

### Modified Capabilities
（无现有 spec 级 requirement 变更——河南志愿推主链路为本次新建）

## Impact

- **数据**：`data/seed/henan/` 下 program_groups/enrollment_plans/universities/admission_history 真实化；新增 coverage_report.json
- **引擎**：`app/engine/henan_recommendation.py`（build_henan_candidates）、`app/engine/henan_target_evaluation.py`
- **loader**：`app/loader/henan_coverage_report.py`、`app/loader/henan_data_loader.py`（历史录取加载+基线查找）
- **API**：`app/api/routers/henan.py`（新增 /recommendation）、`app/api/main.py`
- **前端**：`web-ui/src/pages/HomePage.tsx`、`TargetEvaluationPage.tsx`、`App.tsx`、`api/types.ts`、`api/client.ts`、`components/ScoreForm.tsx`
- **脚本**：`scripts/build_henan_coverage_report.py`、`scripts/import_henan_2026_catalog.py`、`scripts/import_henan_admission_history.py`
- **测试**：loader/engine/api 测试 + Playwright e2e
