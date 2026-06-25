# 人生经济模型模拟器 — 数据底座 + 志愿填报引擎

三层架构第 1 层数据底座（data-foundation）+ 省级分数数据（provincial-score-data）+ **志愿填报引擎（volunteer-engine）**。

核心功能：**根据考生分数用位次法筛选可报学校，生成冲稳保三档完整志愿表**。覆盖六类实体 + 录取数据 + 省控线 + 一分一段表，暴露查询、纯计算与志愿推荐 API。

> 声明：所有数据基于历史数据模拟，非就业或收入预测。

## 📊 数据时效说明（重要）

| 数据类型 | 最新年份 | 来源 | 说明 |
|----------|----------|------|------|
| **省控线** | **2026** ✅ | 河南/广东省教育考试院（教育在线核实） | 2026 官方已更新，含 3+1+2 新高考物理/历史类 |
| **一分一段表（河南）** | **2026** ✅ | 河南省教育考试院（OCR 自官方 PDF，5 硬锚点校验） | 物理/历史类 1016 行，位次法核心数据已最新 |
| 一分一段表（其他） | 2024 | 公开数据集 Gaokao-score-distribution | 广东等省份位次查询基于 2024，待官方整理后更新 |
| **院校录取数据** | 2024 | 各校招生网/考试院投档线 | 河南 6 核心校真实录取位次，覆盖冲到保梯度；后续 OCR 扩充 |

> ⚠️ 志愿推荐基于 2024 历史录取数据预测（2026 投档线 8 月公布后可增量补充）。年份波动会使位次略有偏差，**正式填报请以当年省考试院公布数据为准**。每个数字均带 source 字段，可点开核对来源。

## 三层架构

```
① data-foundation（本层）   数据底座：模型 + 种子 + 来源追溯 + 查询 API + 纯计算
② decision-engine（后续）    评分模型 + 3 条路径推演 + 城市生存模型
③ web-ui（后续）             Vite+React 精致 UI + 路径卡片 + 收入曲线
```

## 技术栈

Python 3.13 · FastAPI · Pydantic v2 · SQLModel · SQLite · PyYAML · pytest · httpx

## 安装

```bash
pip install -e ".[dev]"
```

## 加载种子

应用启动时若 DB 为空，自动加载 `data/seed/*.yaml`。亦可手动：

```python
from app.config import settings
from app.db import init_db, get_session
from app.loader.seed_loader import load_all_seeds

init_db()
with get_session() as s:
    load_all_seeds(settings.seed_dir, s)
```

## 启动 API

```bash
uvicorn app.api.main:app --reload
```

访问 `http://localhost:8000/docs` 查看交互文档。主要端点：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/careers` | 职业列表（含薪资三档区间 + 来源） |
| GET | `/api/v1/careers/{id}` | 职业详情 |
| GET | `/api/v1/cities` | 城市列表 |
| GET | `/api/v1/cities/{city}/cost` | 城市成本明细（租房三档 + 生活成本） |
| GET | `/api/v1/universities?tier="211"` | 大学（按层级筛选） |
| GET | `/api/v1/majors` | 专业（薪资 P25/P50/P75） |
| GET | `/api/v1/admissions?province=&track=` | 录取数据（原始查询） |
| **POST** | **`/api/v1/volunteer/recommend`** | **志愿推荐（考生画像 → 冲稳保三档志愿表）** ⭐ |
| **GET** | **`/api/v1/volunteer/admissions`** | **录取数据（支持按 track/year/分数范围筛选可报学校）** |
| GET | `/api/v1/provincial/score-rank/rank` | 分数→位次（位次法） |
| GET | `/api/v1/provincial/score-rank/score` | 位次→分数（反向查询） |
| GET | `/api/v1/provincial/control-line` | 省控线（各批次分数线） |
| POST | `/api/v1/insurance/compute` | 五险一金计算（工资 + 城市 → 企业成本 / 到手） |
| GET | `/api/v1/health` | 健康检查 + 种子加载状态 |

## 运行测试

```bash
pytest
```

## 架构（方案 B 双模型 + 映射层）

- **Domain 层**（`app/models/`）：Pydantic v2，保留嵌套结构，继承 `SourcedRecord` 基类。用于 YAML 校验与 API 响应。
- **Table 层**（`app/models/tables.py`）：SQLModel `table=True`，字段拍平存储。
- **Repository 层**（`app/repositories/mappers.py`）：Table Row ↔ Domain Read 映射。
- **Loader 层**（`app/loader/`）：YAML → Domain（校验来源字段）→ Table Row（幂等 upsert）。
- **Engine 层**（`app/engine/`）：纯函数（五险一金 + 2024 个税累进 + 城市成本年化 + **志愿填报引擎：位次换算/等效位次/冲稳保分档/志愿表生成**），无 DB 依赖。

## 端到端验证预期值

- `POST /api/v1/insurance/compute` body `{"salary": 9000, "city": "全国基准"}` →
  - `total_labor_cost` = 9000 × (1 + 单位比例合计 0.34) = **12060**
  - `take_home_pay` > 0（扣个人五险 + 个税后）
- `GET /api/v1/cities/深圳/cost` → 一房一厅 high ≈ 2600，综合月成本 3500–6000

## 来源追溯

每个数字都带 `source` / `as_of` / `confidence` / `note`，从 YAML 种子 → Domain 校验 → SQLite 存储 → API 响应全链路不丢失。手编种子 `confidence ≤ 0.6` 且 `note` 含「待爬虫校准」，后续爬虫可按 `source` 比对替换。

## 设计文档

详见 `docs/superpowers/specs/2026-06-25-data-foundation-design.md`。
