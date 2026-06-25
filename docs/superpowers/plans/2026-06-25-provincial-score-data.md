---
change: provincial-score-data
design-doc: docs/superpowers/specs/2026-06-25-provincial-score-data-design.md
base-ref: 7625e5b31b2e57699375865f8692bae220b3d385
archived-with: 2026-06-25-provincial-score-data
---

# 省级分数数据 (provincial-score-data) 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: 使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务执行。步骤使用复选框语法跟踪（已完成项标记为已勾选）。

**Goal:** 在 data-foundation 之上扩展省级分数数据层（省控线 + 一分一段表），支撑位次法所需的双向查询与 CSV 运行时导入。

**Architecture:** 复用 data-foundation 双模型架构（Domain Pydantic + Table SQLModel 拍平 + Repository 映射 + SourcedRecord 来源基类）。新增省级 Domain/Table/Mapper、位次双向查询纯函数、CSV 导入器、省控线手编种子、FastAPI 端点。一分一段表运行时从随项目分发的 CSV 导入（缺失降级为空集不阻断启动）。

**Tech Stack:** Python 3.13 · FastAPI · Pydantic v2 · SQLModel · SQLite · PyYAML · pytest

## Global Constraints

- Python 3.13；不引入超出 design doc 技术栈的新依赖。
- CSV 读取 MUST 用 `encoding="utf-8-sig"` 处理 BOM。
- CSV 真实列名（带 BOM）：`最高分,最低分,人数,累计,省级行政区,综合,年份,总分(裸分),模式`。列映射：`最高分`/`最低分`→`score`（恒等取一）；`人数`→`count_at`；`累计`→`cumulative_rank`；`省级行政区`→`province`；`综合`→`track`；`年份`→`year`；`模式`→仅校验不入库。
- 累计位次不变量：同一表内 score 降序时 cumulative_rank 严格递增（高分位次小）。
- 来源标注：CSV 导入 source="Gaokao-score-distribution数据集"、confidence=0.8；省控线手编 confidence ≥ 0.8。
- 所有实体继承 SourcedRecord（confidence∈[0,1]）。
- 空结果返回空列表/None，不抛异常。
- 命名/文案：不使用"预测"措辞，标注历史数据。

## File Structure

**新建：** `app/models/provincial.py`、`app/engine/rank_query.py`、`app/loader/dataset_importer.py`、`app/api/routers/provincial.py`、`data/seed/provincial/control_line/{henan,guangdong}.yaml`、对应 tests/。
**修改：** `app/models/tables.py`（+3 Row）、`app/repositories/mappers.py`（+3 映射）、`app/loader/seed_loader.py`（目录多文件支持 + 注册省控线）、`app/api/main.py`（注册 router + lifespan CSV 导入）、`app/config.py`（+data_dir）。

## 关键复用契约（来自 data-foundation）

- `SourcedRecord`（app/models/base.py）：source/as_of/confidence/note + confidence∈[0,1] 校验
- `_check_sourced(row)`（app/repositories/mappers.py）：写回前防御性校验 confidence
- Table 层：SQLModel table=True + id 主键 + 嵌套拍平 + JSON 列
- `load_all_seeds`：遍历 SEED_SPECS，model_validate→to_row→_check_sourced→upsert
- 测试 fixture `isolated_db`（tests/conftest.py）
- Router 模式：APIRouter + *_to_domain.model_dump(mode="json") + d["id"]=r.id

archived-with: 2026-06-25-provincial-score-data
---

### Task 1: 省控线与一分一段表 Domain 模型

**Files:** Create `app/models/provincial.py`; Test `tests/models/test_provincial.py`
**Interfaces:** BatchLines(5 int|None)、ProvincialControlLine(SourcedRecord)、ScoreRankEntry(score/count_at/cumulative_rank 非负)、ScoreRankTable(SourcedRecord + entries + 位次单调性校验)

- [x] **Step 1: 写失败测试** — 河南传统理综、广东新高考批次可选、缺省/负数拒绝、entry 非负、表单调性通过/违反拒绝（9 测试）
- [x] **Step 2: 运行确认失败** — ModuleNotFoundError
- [x] **Step 3: 实现 app/models/provincial.py** — BatchLines(field_validator "*" 非负) + ScoreRankEntry(非负) + ScoreRankTable(model_validator after 校验 score 降序时 cumulative_rank 严格递增)
- [x] **Step 4: 运行确认通过** — 9 passed
- [x] **Step 5: Commit** — `feat(provincial): add domain models for control line and score-rank table`

### Task 2: Table 层 Row 模型

**Files:** Modify `app/models/tables.py`
**Interfaces:** ProvincialControlLineRow(batches 拍平 5 列)、ScoreRankTableRow(表头)、ScoreRankEntryRow(table_id 外键 + score/count_at/cumulative_rank)

- [x] **Step 1: 追加 3 个 Row 到 tables.py**
- [x] **Step 2: 验证建表** — `python -c "from app.db import init_db; init_db(); print('ok')"`
- [x] **Step 3: Commit** — `feat(provincial): add SQLModel rows for control line and score-rank`

### Task 3: 位次双向查询纯函数

**Files:** Create `app/engine/rank_query.py`; Test `tests/engine/test_rank_query.py`
**Interfaces:** score_to_rank(entries,score)->int|None(精确)、rank_to_score(entries,rank)->int|None(就近)

- [x] **Step 1: 写失败测试** — 精确匹配(690→215)、缺失返 None、空表返 None、就近匹配(220→690, 230→689)（7 测试）
- [x] **Step 2-4: 失败→实现→通过** — rank_to_score 用 min(key=abs(cumulative_rank-rank))
- [x] **Step 5: Commit** — `feat(provincial): add bidirectional score-rank query functions`

### Task 4: Repository 映射层

**Files:** Modify `app/repositories/mappers.py`; Test `tests/repositories/test_provincial_mappers.py`
**Interfaces:** provincial_control_line_to_row/domain、score_rank_table_to_row/domain(接 entries 参数)、score_rank_entry_to_row(接 table_id)/domain

- [x] **Step 1: 写失败测试** — control_line 往返(广东 special_line=539/undergrad_batch=442/first_batch=None)、table 往返、entry 往返（3 测试）
- [x] **Step 2-4: 失败→实现(import+追加 6 函数)→通过**
- [x] **Step 5: Commit** — `feat(provincial): add mappers for control line and score-rank`

### Task 5: CSV 一分一段表导入器

**Files:** Create `app/loader/dataset_importer.py`; Test `tests/loader/test_dataset_importer.py`
**Interfaces:** import_score_rank_csv(csv_path,session,provinces,years)->dict。CSV 缺失→{}不抛；位次单调违反→ValueError

- [x] **Step 1: 写失败测试** — 解析存储(河南3条)、幂等、白名单过滤(省/年)、单调违反拒绝、CSV缺失降级（5 测试）
- [x] **Step 2-4: 失败→实现(utf-8-sig/列映射/分桶/ScoreRankTable校验/upsert删旧写新)→通过**
- [x] **Step 5: 真实CSV冒烟** — import_score_rank_csv('data/datasets/gaokao_raw.csv',...,['河南','广东'],[2022,2023,2024])
- [x] **Step 6: Commit** — `feat(provincial): add CSV score-rank importer with graceful degradation`

### Task 6: 省控线手编种子 + seed_loader 注册

**Files:** Create `data/seed/provincial/control_line/{henan,guangdong}.yaml`; Modify `app/loader/seed_loader.py`; Test `tests/loader/test_provincial_seeds.py`

- [x] **Step 1: henan.yaml** — 2022-2024 文/理科各批次线（一本/二本/专科），confidence 0.9
- [x] **Step 2: guangdong.yaml** — 2022-2024 物理/历史类（special_line/undergrad_batch/专科），confidence 0.9，note 标注合并批次
- [x] **Step 3: 扩展 seed_loader** — SEED_SPECS 加 provincial/control_line 目录(主键 province/year/track)；load_all_seeds 支持目录多文件(is_dir 则 glob *.yaml)
- [x] **Step 4: 写失败测试** — 种子≥12条、confidence≥0.8、河南有first_batch/广东有undergrad_batch/广东无first_batch（2 测试）
- [x] **Step 5-6: 通过 + 既有 seed 测试不回归**
- [x] **Step 7: Commit** — `feat(provincial): add hand-authored control-line seeds and register in loader`

### Task 7: FastAPI 省级数据端点

**Files:** Create `app/api/routers/provincial.py`; Modify `app/api/main.py`+`app/config.py`; Test `tests/api/test_provincial_api.py`
**Interfaces:** 4 端点：control-line / score-rank / score-rank/rank / score-rank/score。空结果不报错

- [x] **Step 1: 写失败测试** — control_line 带来源(first_batch=511)、空查询不报错、score-rank 列表、score→rank(690→215)、rank→score(215→690)（5 测试）
- [x] **Step 2: 运行确认失败**
- [x] **Step 3: 实现 routers/provincial.py** — _load_table_entries 辅助 + 4 端点(model_dump + 来源字段)
- [x] **Step 4: main.py 注册 + lifespan CSV 导入 + config 加 data_dir**
- [x] **Step 5: 运行确认通过** — 5 passed（含真实 690→215）
- [x] **Step 6: Commit** — `feat(provincial): add FastAPI endpoints and runtime CSV import on startup`

### Task 8: 来源链路集成验证 + 文档

**Files:** Modify `tests/test_provenance_chain.py`; README

- [x] **Step 1: 追加省级来源断言** — control_line provenance、score_rank 全链路(690→215 source=数据集)
- [x] **Step 2: 全量回归** — `pytest tests/ -v` 全过无回归
- [x] **Step 3: 合规检查** — grep 无"预测"措辞
- [x] **Step 4: 更新 README** — 省级端点 + 标注历史数据
- [x] **Step 5: Commit** — `test(provincial): add provenance chain assertions for provincial data`

archived-with: 2026-06-25-provincial-score-data
---

## Self-Review

**Spec 覆盖：** 4 capability 全覆盖（provincial-control-line Task1+6、score-rank-table Task1+3+7、provincial-data-import Task5、data-foundation-api Task7）。

**与 design doc 偏差校正（基于真实数据核对，已写入计划）：**
1. CSV 真实列名带 BOM + 中文列名 → utf-8-sig + 列映射表
2. design 示例"690→300"与真实"690→215"不符 → 测试用真实值 215
3. CSV 含额外 track(综合/文科/理科) → 导入器按 province+year 白名单 + track 自然分组
4. load_all_seeds 原仅单文件 → Task6 扩展目录多文件
5. config 无 data_dir → Task7 新增

**类型一致性：** score_rank_entry_to_row(e,table_id=) / score_rank_table_to_domain(r,entries=) 签名贯穿 Task4/5/7。

**关键真实数据（实测）：** 河南2024理科 690→215；max==min 恒等；cumulative 严格单调；广东2024物理类数据齐全。
