# Brainstorm Summary

- Change: henan-real-recommendation-pipeline
- Date: 2026-06-26

## 确认的技术方案

把河南志愿推从样例壳子修复为可验收真实链路。数据先行 + 统一候选生成器 + 首页/目标评估消费同一候选集。

**核心决策：2026 数据来源 = 方案 A（真实可追溯种子）**
用已核实的郑大/河大等核心校真实章程（物化要求、学费已网络核实）构造 verified 专业组 + 真实非零 plan_count，让覆盖门禁真实通过；未核验扩展校保持 needs_review。importer 仍建好供后续全量导入。现有真实一分一段表（2025/2026各1000+行）和 36 条旧录取转为历史基线。

### 5 项关键决策
1. 数据先行门禁：4 项质量指标（verified 专业组/verified 计划/非零计划/verified 历史位次）任一为 0 → data_ready=false，拦截可信推荐不拦截接口。
2. 新增「需人工复核」档位：缺 verified 历史的稳/保降级目标；_BUCKET_ORDER 补 需人工复核:4。
3. find_best_historical_baseline() 返回 {adjusted_min_rank, year, review_status, data_granularity}，查找顺序 2025专业级→组级→加权趋势→校级兜底→None。
4. 候选生成器 build_henan_candidates() 真实实现：资格→计划校验→历史位次→分桶，不再返回空。
5. 前端首页切 /henan/recommendation，旧 advisory() 保留；移除独立费用页，费用并入卡片。

## 关键取舍与风险

- **取舍**：方案 A 用核心校 verified 数据让门禁真实通过，非全量但每条可追溯不造假；纯 importer 方案会让门禁持续阻断、验收又是壳子。
- **风险**：真实数据非全量 → 缓解：needs_review 标注 + 门禁如实反映 + importer 支持后续增量导入。
- **风险**：历史位次粒度多为校级 → 缓解：多层级兜底，校级仅低置信参考，不单独支撑保。

## 测试策略

- 门禁：覆盖计数真实、零计划/未核验组被拦截
- 历史基线：verified 缺 min_rank 被拒、2025 专业级优先于组兜底、2024 仅趋势、无历史返回 None
- 候选生成：返回非空院校专业组、零计划不进冲稳保、缺历史稳保降级需人工复核
- 推荐 API：buckets 键齐全（含需人工复核）、含 coverage
- Playwright：数据就绪状态、档位筛选、目标评估联动、480分不推荐

## Spec Patch

无。4 个新 capability 在 proposal 已定义，验收场景在 design 已覆盖，无歧义需修正。
