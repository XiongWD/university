---
comet_change: henan-real-recommendation-pipeline
role: technical-design
canonical_spec: openspec
archived-with: 2026-06-26-henan-real-recommendation-pipeline
status: final
---

# Design Doc: henan-real-recommendation-pipeline

把当前「河南志愿推」从样例壳子修复为可验收的河南 2026 志愿推荐和目标评估主链路。OpenSpec 产物（proposal/design/tasks）是上游事实源；本 Design Doc 记录经 brainstorming 确认的技术实现决策。实施任务分解见 `docs/superpowers/plans/2026-06-26-henan-zhiyuantui-remediation.md`。

## 1. 现状诊断（已核实）

| 维度 | 现状 | 问题 |
|------|------|------|
| 2026 计划 | 3 条全 `plan_count=0` + `needs_review` | 无真实招生计划 |
| 候选生成 | `build_henan_candidates()` 第 163 行 `return []` | 占位空实现 |
| 推荐端点 | `/henan/recommendation` 不存在 | 首页无主链路 |
| 首页 | 仍调旧 `advisory(req)` | 未接河南新链路 |
| 覆盖报告 | example.json 是示例数字 | 不是实际计数 |
| 历史基线 | 无 admission_history_{2025,2024} | 冲稳保无位次依据 |

全量测试通过只证明样例没崩，不证明真实推荐可用。

## 2. 核心决策：数据来源 = 真实可追溯种子（方案 A）

2026 专业组 + 招生计划采用**已网络核实的真实核心校数据**：

- 郑州大学计算机组：物理+化学硬要求（ao.zzu.edu.cn 招生章程核实）、学费 5700、中外合作 25000（章程第二十条）→ `verified` + 真实非零 plan_count。
- 河南大学、河南财经政法大学等核心校：选科/语种/学费按已核实章程填，标 `verified`。
- 未核验扩展校保持 `needs_review`，门禁如实反映。
- 现有真实一分一段表（2025/2026 各 1000+ 行）和旧 36 条录取转为 2024/2025 历史基线。

importer（`import_henan_2026_catalog.py`、`import_henan_admission_history.py`）仍建好，接受 normalized CSV 供后续全量增量导入。

## 3. 架构与数据流

```
真实种子(方案A)                       统一候选生成器
┌──────────────────────┐            ┌────────────────────────────┐
│ 2026 专业组(verified) │            │ build_henan_candidates()   │
│ 2026 计划(非零verified)│───────────▶│ 资格→计划→历史位次→分桶     │
│ 2025/2024 历史录取     │            └─────────────┬──────────────┘
│ 一分一段(已存在)       │                          │
└──────────────────────┘             ┌──────────────┴──────────────┐
        │                            ▼                             ▼
        ▼              POST /henan/recommendation      /henan/target-evaluation
┌─────────────────────┐  data_ready+buckets+coverage    复用同一候选集
│build_actual_        │         │                          │
│coverage()+门禁       │         ▼                          ▼
│ verified组/非零计划  │  HomePage(切新API)        TargetEvaluationPage
│ /历史位次 >0         │  未就绪banner+5档buckets   联动+可达性判定
└─────────────────────┘
```

**关键约束**：首页 `/henan/recommendation` 和目标评估 `/henan/target-evaluation` 都调用同一个 `build_henan_candidates(profile)`。目标评估只做按校/专业/专业组筛选与可达性判定，不重新放宽规则。

## 4. 关键技术决策

### D1 数据先行门禁
`build_actual_henan_coverage(seed_dir)` 基于实际 seed 计数 + 4 项质量指标；`assert_henan_recommendation_ready()` 任一为 0 抛 ValueError。推荐 API 先跑门禁，`data_ready=false` 时仍返回候选（带 需人工复核/不推荐），前端显示未就绪 banner。门禁拦截「可信推荐」不拦截接口。

### D2 新增「需人工复核」档位
缺 verified 历史的稳/保降级为 `需人工复核`。`_BUCKET_ORDER` 补 `需人工复核: 4`。buckets 输出固定 5 档：`{冲, 稳, 保, 不推荐, 需人工复核}`。

### D3 历史基线多层级查找
`find_best_historical_baseline(history, *, school_code, group_code, major_names, track, batch)` 返回：
```python
{
  "adjusted_min_rank": int,   # 修正后参考位次
  "year": int,                # 2025 优先
  "review_status": str,       # verified/needs_review
  "data_granularity": str,    # major/major_group/school_batch
}
```
查找顺序：2025 专业级 → 2025 专业组级 → 2025+2024 加权趋势 → 2025 校级兜底（低置信）→ 无则 None。

### D4 候选生成器分桶规则
```
资格层 check_henan_eligibility 不通过 → 不推荐
风险层 classify_group_bucket:
  缺 2026 计划(plan_count=0 或非 verified) → 不推荐/需人工复核
  缺 verified 历史位次 → 即使位次优也 需人工复核（不得稳/保）
  位次差比 > 0.15 → 不推荐；0.03~0.15 → 冲；-0.10~0.03 → 稳；< -0.10 → 保
  缺 2025 历史或置信度<0.7 → 保 降为 稳
```

### D5 前端费用合并
移除独立费用页导航与 `/cost` 路由，费用（学费/住宿/4年估算）并入推荐卡片和目标评估卡片，缺数据时显示「费用待核验」。

## 5. 测试策略

| 层 | 测试 | 关键断言 |
|----|------|---------|
| 门禁 | test_henan_real_coverage_gate | 覆盖计数真实；零计划/未核验组被拦截 |
| 历史 | test_henan_admission_history_import | verified 缺 min_rank 被拒；2025 专业级优先；2024 仅趋势；无历史 None |
| 候选 | test_henan_candidate_generation | 返回非空；零计划不进冲稳保；缺历史稳保降级 |
| API | test_henan_recommendation_api | buckets 5 档键齐全；含 coverage |
| 目标 | test_henan_api（mock 候选） | mock 返回稳时按专业组显示稳 |
| E2E | Playwright | 数据就绪状态；档位筛选；目标联动；480分不推荐；费用页移除 |

## 6. 验收标准

- `build_henan_candidates()` 不再是空占位
- 首页不再用 `/volunteer/advisory`
- 目标评估有可达候选时返回冲稳保，无可达返回不推荐
- 真实覆盖报告反映实际 seed 计数
- `plan_count=0`/`needs_review`/缺历史位次的候选不进稳/保
- 数据未就绪时 UI 显示 banner 而非假推荐
- 独立费用页移除

## 7. 非目标

- 不动旧 `/volunteer/*`、`/target/evaluate` 兼容层
- 不做全国/外省扩展
- 不输出伪精确概率
- 不承诺官方全量目录一次性导入（支持增量+人工复核）
