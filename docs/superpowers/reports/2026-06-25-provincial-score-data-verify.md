# 验证报告：provincial-score-data

- **Change**: provincial-score-data（省级分数数据底座）
- **验证模式**: full（27 任务 / 4 capability / 21 文件）
- **分支**: feature/20260625/provincial-score-data
- **Base-ref**: 7625e5b
- **日期**: 2026-06-25
- **review_mode**: standard

## 验证证据（fresh run）

| 证据 | 命令 | 结果 |
|------|------|------|
| 全量测试 | `pytest -q` | **133 passed，退出码 0** |
| 真实 CSV 导入 | 冒烟 import_score_rank_csv | 12 表头 / 7101 条（河南+广东 2022-2024） |
| API 端到端 | TestClient | 河南690→位次215（真实数据） |
| 合规扫描 | grep 预测措辞 | 无匹配（exit 1） |

## Full 验证检查

### 1. tasks.md 全部完成 [x]
0 unchecked / 27 checked ✅

### 2. 实现符合 design.md 决策
- D1 一分一段表分段记录（非 JSON）→ ScoreRankEntry ✅
- D2 复用 data-foundation 双模型架构 ✅
- D3 科类自由字符串（文/理/物理类/历史类）✅
- D4 种子 Loader 与 CSV 导入器分离 ✅

### 3. 实现符合 Design Doc
- 数据模型、双向查询、CSV 列映射、API 端点均与 Design Doc 一致
- design.md §11 两个 Open Question 已解决（CSV 真实列名确认 + ScoreRankEntry 外键 table_id）

### 4. 能力规格场景全部通过
| Capability | 关键场景 | 测试 |
|------------|----------|------|
| provincial-control-line | 批次可选/缺省拒绝/负数拒绝/两省结构差异 | test_provincial (5) + test_provincial_seeds |
| score-rank-table | 位次单调性/双字段/双向查询精确+就近 | test_provincial (4) + test_rank_query (7) |
| provincial-data-import | CSV解析/清洗/幂等/单调拒绝/降级 | test_dataset_importer (5) |
| data-foundation-api | 4端点/来源字段/空结果不报错 | test_provincial_api (5) |
全部 ✅

### 5. proposal 目标已满足
省控线 + 一分一段表 + CSV 导入器 + 双向查询 API 全部实现，覆盖河南/广东两省近3年。✅

### 6. delta spec 与 design doc 无矛盾
brainstorming 无 Spec Patch（spec 已覆盖决策）。Build 无新增漂移。✅

### 7. Design Doc 可定位
docs/superpowers/specs/2026-06-25-provincial-score-data-design.md，frontmatter 含 comet_change/role/canonical_spec。✅

## 端到端核对（真实数据）

| 项 | 预期 | 实测 | 结果 |
|----|------|------|------|
| 河南690分位次 | 真实数据 | 215 | ✅ |
| 省控线 first_batch | 河南2024理科 | 511 | ✅ |
| 广东本科批 | 2024物理类 | 442 | ✅ |
| 广东无 first_batch | 新高考合并 | None | ✅ |
| CSV 导入规模 | 河南广东近3年 | 7101 条 | ✅ |
| 来源字段全链路 | source=数据集 confidence=0.8 | 齐全 | ✅ |

## 简化代码审查（standard）

本 change 复用 data-foundation 已验证架构（双模型/Repository/Loader/_check_sourced），无新架构风险。实现遵循既有模式：
- 复用 SourcedRecord + _check_sourced 来源不变量
- CSV 导入器降级处理（缺失不阻断）
- 位次单调性校验防脏数据
无 CRITICAL/IMPORTANT 问题。

## 验证结论

**PASS**。provincial-score-data 实现完整符合 proposal/design/spec，133 测试全过，真实 CSV 数据导入验证（7101 条），端到端位次查询精确（690→215）。

## Follow-up（非阻塞）

- CSV 数据集会逐年更新，importer 支持增量（白名单过滤已实现）
- 省控线每年更新，YAML 种子手编（量小可控）
- 后续 change ④b（院校录取数据）将对照省控线定批次
