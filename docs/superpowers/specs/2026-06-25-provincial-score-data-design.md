---
comet_change: provincial-score-data
role: technical-design
canonical_spec: openspec
---

# Design Doc: provincial-score-data

承接已归档的 data-foundation，建立"真实志愿填报流程"的第一块拼图——位次法所需的省级基础数据（省控线 + 一分一段表）。本设计基于 OpenSpec 产物经 brainstorming 确认定稿。

## 1. 背景与目标

高考录取本质**按位次录取**（同分不同年含金量不同，位次稳定）。做"位次法志愿筛选"必须先有：
- **省控线**：分数过线才能报对应批次
- **一分一段表**：分数↔位次映射，做"今年分→位次"换算

覆盖两种高考模式：河南（文/理）+ 广东（物理/历史类 3+1+2），近 3 年。

**边界**：本层只提供数据 + 查询。位次稳定性修正、冲稳保分类、志愿表生成归 change⑤ volunteer-engine。

## 2. 技术栈

复用 data-foundation：Python 3.13 · FastAPI · Pydantic v2 · SQLModel · SQLite · PyYAML · pytest

## 3. 数据来源（brainstorming 确认）

```
一分一段表：GitHub CSV 数据集（sdgedfegw/Gaokao-score-distribution）
  └─ data/datasets/gaokao_score_distribution.csv（随项目分发）
  └─ 运行时由导入器解析，提取 河南/广东 × 近3年 × 各科类
  └─ 数据量大（每省每年数百条），适合 CSV 批量导入

省控线：手编 YAML 种子（data/seed/provincial/control_line/*.yaml）
  └─ 数据量小（每省每年每科类 1 条），官方可查，手编可控
```

**导入时机**：运行时。FastAPI 启动时若一分一段表数据缺失，触发导入器从随项目分发的 CSV 加载。导入器需健壮降级（CSV 缺失→空集不阻断启动）。

## 4. 数据模型（复用 data-foundation 双模型架构）

### 4.1 省控线 ProvincialControlLine（Domain, 继承 SourcedRecord）

```python
BatchLines: {                      # 批次线集合，各省按适用性填写
  special_line: int | None         #   特殊类型招生控制线
  first_batch: int | None          #   一本线（河南用）
  second_batch: int | None         #   二本线（河南用）
  undergrad_batch: int | None      #   本科批（广东新高考合并批次用）
  junior_college: int | None       #   专科线
}
ProvincialControlLine(SourcedRecord):
  province: str                    # 省份
  year: int                        # 年份
  track: str                       # 科类（文/理/物理类/历史类）
  batches: BatchLines              # 批次线（各可选）
```

### 4.2 一分一段表（表头 + 分段记录）

```python
ScoreRankTable(SourcedRecord):     # 表头
  province: str
  year: int
  track: str

ScoreRankEntry(BaseModel):         # 分段记录
  score: int                       # 分数
  count_at: int                    # 该分人数
  cumulative_rank: int             # 累计位次
  # 不变量：同一表内，score 降序时 cumulative_rank 递增（高分位次小）
```

### 4.3 Table 层（SQLModel 拍平，加 _check_sourced）

- `ProvincialControlLineRow`：拍平 batches 为 5 列 + 来源字段
- `ScoreRankTableRow`：表头（省/年/科类 + 来源）
- `ScoreRankEntryRow`：分段记录（table_id 外键 + score/count_at/cumulative_rank）

## 5. 查询逻辑（位次法双向查询，纯函数）

```python
def score_to_rank(entries: list[ScoreRankEntry], score: int) -> int | None:
    """分数→累计位次（精确匹配）"""

def rank_to_score(entries: list[ScoreRankEntry], rank: int) -> int | None:
    """位次→分数（就近匹配：找 cumulative_rank 最接近 rank 的 score）"""
```

位次查询就近匹配：精确位次不存在时，取 cumulative_rank 与目标最接近的 entry 的 score。

## 6. 数据集导入器（app/loader/dataset_importer.py）

```python
def import_score_rank_csv(csv_path: Path, session: Session,
                          provinces: list[str], years: list[int]) -> dict:
    """从 CSV 导入一分一段表。
    - 解析 CSV（列：省份/年份/科类/分数/该分人数/累计位次）
    - 过滤目标省份与年份
    - 清洗：类型转换、去重、缺失剔除
    - 校验：位次单调性（每表内 score 降序时 cumulative_rank 递增）
    - 幂等 upsert（复用 Repository）
    - 来源标注：source="Gaokao-score-distribution数据集", confidence=0.8
    - CSV 缺失/异常 → 降级返回空报告，不抛异常（不阻断启动）
    """
```

CSV 格式预期（基于 sdgedfegw 仓库）：
```
province,year,track,score,count_at,cumulative_rank
河南,2024,理科,700,5,50
河南,2024,理科,699,8,58
...
```

## 7. API 设计（扩展 data-foundation-api）

```
GET /api/v1/provincial/control-line?province=&year=&track=    # 省控线
GET /api/v1/provincial/score-rank?province=&year=&track=      # 一分一段表（列表）
GET /api/v1/provincial/score-rank/rank?province=&year=&track=&score=  # 分数查位次
GET /api/v1/provincial/score-rank/score?province=&year=&track=&rank=  # 位次查分数
```

所有响应带来源字段。空结果返回空列表/404 不报错。

## 8. 包结构（扩展 data-foundation）

```
app/
├── models/provincial.py          # 新增：省控线 + 一分一段表 Domain
├── models/tables.py              # 扩展：3 个新 Row
├── repositories/mappers.py       # 扩展：省级数据映射
├── loader/
│   ├── seed_loader.py            # 扩展：注册省级种子（省控线）
│   └── dataset_importer.py       # 新增：CSV 导入器
├── api/routers/provincial.py     # 新增：省级数据端点
└── engine/rank_query.py          # 新增：位次双向查询纯函数

data/
├── seed/provincial/control_line/*.yaml   # 省控线手编种子
└── datasets/gaokao_score_distribution.csv # 一分一段表 CSV（随项目分发）
```

## 9. 测试策略

| 层 | 测试 |
|----|------|
| models | 省控线批次可选/分数非负；一分一段表位次单调性校验；双字段完整 |
| 查询 | 分数→位次精确；位次→分数就近；不存在分数就近匹配 |
| 导入器 | CSV 解析；清洗（去重/类型）；幂等；脏数据（位次违反）拒绝；CSV 缺失降级 |
| API | 省控线查询；分数查位次；位次查分数；空结果不报错；来源字段 |
| 来源链路 | CSV/种子→Domain→DB→API 来源不丢 |

## 10. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 运行时依赖 CSV | CSV 随项目分发 data/datasets/；导入器降级处理（缺失→空集不阻断） |
| 一分一段表数据量大 | 分段记录+索引；按省/年/科类分区；SQLite 承载（3年×2省×2科类≈数千条） |
| CSV 格式/列名不确定 | 导入器做列名容错（支持中英文列名映射）；首次运行记录实际格式 |
| 两省高考模式差异 | track 自由字符串；批次线可选；新高考合并批次用 undergrad_batch |
| 数据时效 | as_of 记录年份；标注"历史数据，非当年实时" |

## 11. 待解决问题（implementation 细化，不阻塞）

- CSV 实际列名需首次导入时核对（可能需列名映射表）
- 一分一段表 ScoreRankEntry 与 ScoreRankTable 的外键关系在 SQLModel 的具体实现
