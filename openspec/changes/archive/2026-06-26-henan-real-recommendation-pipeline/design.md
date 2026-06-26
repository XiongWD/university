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
