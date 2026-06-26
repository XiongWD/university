# Comet Design Handoff

- Change: henan-real-recommendation-pipeline
- Phase: design
- Mode: compact
- Context hash: 6e931bff272c883de0ab5c7a3d9a24f06812ea69a6e1d69a49013deb0189ed7c

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/henan-real-recommendation-pipeline/proposal.md

- Source: openspec/changes/henan-real-recommendation-pipeline/proposal.md
- Lines: 1-40
- SHA256: 20a0f65f23f1202a3cd67f4e41ad3f154f1cf00415ec89a787c552164918160a

```md
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
```

## openspec/changes/henan-real-recommendation-pipeline/design.md

- Source: openspec/changes/henan-real-recommendation-pipeline/design.md
- Lines: 1-49
- SHA256: 3475d1d58af5a82ca634c6edfc75a65acce7773de9186c90a34bd330a8c625dd

```md
## Context

河南志愿推已建立河南专用数据模型（`henan_data.py`）、loader、冲稳保引擎骨架和 `/henan/options`、`/henan/target-evaluation` 端点，但都是样例壳子：数据全 `plan_count=0`/`needs_review`，`build_henan_candidates()` 占位返回空，首页仍走旧 `advisory`。无法通过验收——全量测试绿只证明样例没崩，不证明真实推荐可用。

详细技术设计与任务分解见 `docs/superpowers/plans/2026-06-26-henan-zhiyuantui-remediation.md`（本 design 的实施计划，archived 时标注）。本 design 记录关键架构决策。

## Goals / Non-Goals

**Goals:**
- 真实覆盖报告 + 推荐就绪门禁，缺核验数据时拦截假推荐
- `build_henan_candidates()` 真实生成院校专业组候选（资格+计划+历史位次+分桶）
- 首页和目标评估消费**同一**候选集
- `plan_count=0`/`needs_review`/缺历史位次的候选不得进入稳/保
- 首页走 `/henan/recommendation`，数据未就绪显式提示而非假推荐

**Non-Goals:**
- 不动旧 `/volunteer/*`、`/target/evaluate` 兼容层
- 不做全国/外省扩展
- 不输出伪精确概率
- 不在本次承诺官方全量目录一次性导入（支持增量+人工复核）

## Decisions

**D1 数据先行门禁**：推荐 API 先 `build_actual_henan_coverage()` + `assert_henan_recommendation_ready()`，4 项质量指标（verified 专业组/verified 计划/非零计划/verified 历史位次）任一为 0 则 `data_ready=false`，但仍返回候选（带 需人工复核/不推荐 档位），前端显示未就绪 banner。门禁拦截的是"可信推荐"，不是接口本身。

**D2 候选统一生成器**：`build_henan_candidates(profile)` 是唯一候选来源，首页 `/henan/recommendation` 和目标评估 `/henan/target-evaluation` 都调用它。目标评估只做按校/专业/专业组的筛选与可达性判定，**不重新放宽规则**。

**D3 分桶两层 + 历史硬约束**：
```
资格层(check_henan_eligibility) 不通过 → 不推荐
风险层(classify_group_bucket):
  - 缺 2026 计划(plan_count=0 或非 verified) → 不推荐/需人工复核
  - 缺 verified 历史位次 → 即使位次优也只能 需人工复核（不得稳/保）
  - 位次差比 > 0.15 → 不推荐；0.03~0.15 → 冲；-0.10~0.03 → 稳；< -0.10 → 保
  - 缺 2025 历史或置信度<0.7 → 保 降为 稳
```

**D4 历史基线多层级查找**：`find_best_historical_baseline()` 顺序：2025 专业级 → 2025 专业组级 → 2025+2024 加权趋势 → 2025 校级兜底（低置信）→ 无则 None。返回结构带 `adjusted_min_rank`、`year`、`review_status`、`data_granularity`。

**D5 导入器接受 normalized CSV**：真实官方目录可能非结构化，importer 接受人工/OCR 标准化的 CSV（带 source_url/as_of/review_status），产 YAML。未取得全量时标 needs_review，门禁会拦住进入稳/保。

**D6 前端费用合并**：移除独立费用页导航与路由，费用（学费/住宿/4年估算）并入推荐卡片和目标评估卡片，缺数据时显示"费用待核验"。

## Risks / Trade-offs

- **真实数据可获取性**：2026 河南官方全量目录可能需人工核验。缓解：importer + needs_review + 门禁，未核验不进稳/保，产品可上线但明确标注数据状态。
- **历史位次粒度**：多数院校只有校级投档，专业级稀缺。缓解：D4 多层级兜底，校级仅作低置信参考，不单独支撑保。
- **样例测试误导**：旧样例测试可能掩盖回归。缓解：新增候选生成/覆盖门禁/推荐 API 测试 + Playwright 验收，明确断言「不返回空」「零计划不进稳保」。
- **兼容层维护成本**：旧 advisory/target 保留。缓解：明确不再扩展，文档标注兼容用途。
```

## openspec/changes/henan-real-recommendation-pipeline/tasks.md

- Source: openspec/changes/henan-real-recommendation-pipeline/tasks.md
- Lines: 1-48
- SHA256: 6bace5c885820c169f845c3257d0c9c9444f93698487ec4f5f303521d0c2a52c

```md
## 1. 真实覆盖报告与上线门禁

- [ ] 1.1 实现 `build_actual_henan_coverage(seed_dir)`：基于实际 seed 计数（universities/groups/plans）+ 质量指标（verified 专业组/verified 计划/非零计划/verified 历史位次）
- [ ] 1.2 实现 `assert_henan_recommendation_ready(report)`：4 项质量指标任一为 0 抛 ValueError
- [ ] 1.3 创建 `scripts/build_henan_coverage_report.py` CLI，输出 `data/seed/henan/data_coverage_report.json`
- [ ] 1.4 测试 `tests/loader/test_henan_real_coverage_gate.py`：覆盖计数真实 + 门禁拦截零计划/未核验组

## 2. 导入真实 2026 河南招生目录

- [ ] 2.1 创建 `scripts/import_henan_2026_catalog.py`：接受 normalized CSV，产 universities/program_groups/enrollment_plans YAML（带 source_url/review_status）
- [ ] 2.2 用导入器生成真实 program_groups_2026/enrollment_plans_2026/universities（非零 plan_count）
- [ ] 2.3 更新 source_registry.yaml 反映真实状态

## 3. 导入 2025/2024 历史录取基线

- [ ] 3.1 创建 `scripts/import_henan_admission_history.py`：normalized CSV → admission_history_{year}.yaml，拒绝 verified 行缺 min_rank
- [ ] 3.2 `henan_data_loader.py` 新增 `load_henan_admission_history()` 和 `find_best_historical_baseline()`（专业级→组级→加权趋势→校级兜底→None）
- [ ] 3.3 覆盖报告分离 verified_2025_history / verified_2024_history
- [ ] 3.4 测试 `tests/loader/test_henan_admission_history_import.py`：verified 缺 min_rank 被拒、2025 专业级优先于组兜底、2024 仅趋势、无历史返回 None

## 4. 真实候选生成器

- [ ] 4.1 实现 `build_henan_candidates(profile)`：加载专业组+计划+历史，逐组资格过滤+计划校验+历史位次+分桶，不再返回空
- [ ] 4.2 `plan_count=0`/`needs_review`/缺 verified 历史的稳保降级为 需人工复核
- [ ] 4.3 测试 `tests/engine/test_henan_candidate_generation.py`：返回院校专业组候选、零计划不进冲稳保

## 5. 河南推荐 API

- [ ] 5.1 新增 `POST /henan/recommendation`：返回 data_ready + readiness_errors + coverage + buckets（冲/稳/保/不推荐/需人工复核）
- [ ] 5.2 测试 `tests/api/test_henan_recommendation_api.py`：buckets 键齐全、含 coverage

## 6. 首页接入河南推荐 API

- [ ] 6.1 前端 types/client 新增 `henanRecommendation()` 与 `HenanRecommendationResult`
- [ ] 6.2 HomePage 改调 `/henan/recommendation`，渲染数据就绪 banner + 5 档 buckets + 专业组/专业/计划/阻断原因
- [ ] 6.3 保留旧 `advisory()` 客户端不动，仅首页不再使用

## 7. 目标评估复用候选集

- [ ] 7.1 目标评估 API 复用 `build_henan_candidates()`（已用，验证真实候选能产生可达冲稳保）
- [ ] 7.2 目标评估页显示数据就绪状态/缺口，无可达显示不推荐
- [ ] 7.3 测试 `tests/api/test_henan_api.py`：mock 候选返回稳时按专业组显示稳

## 8. 移除独立费用页 + 验收

- [ ] 8.1 App.tsx 移除 `/cost` 路由与 UniversityCostPage import，费用并入推荐/目标评估卡片
- [ ] 8.2 Playwright e2e：首页标题/数据就绪状态/档位筛选/目标评估联动/480分不推荐/费用页移除
- [ ] 8.3 全量 pytest + npm build + 真实 HTTP 手测覆盖报告与推荐
```

