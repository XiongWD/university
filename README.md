# 人生经济模型模拟器 — 数据底座层（data-foundation）

三层架构第 1 层：结构化、可扩展、带来源追溯的数据底座，覆盖六类实体（考生画像 / 职业 / 五险一金 / 城市成本 / 大学 / 专业）+ 录取 schema + 省级分数数据，暴露查询与纯计算 API。

**本层只做查询 / 存取 / 纯计算**；评分与路径推演归属后续 decision-engine。

> 声明：所有数据基于历史数据模拟，非就业或收入预测。

## 📊 数据时效说明（重要）

| 数据类型 | 最新年份 | 来源 | 说明 |
|----------|----------|------|------|
| **省控线** | **2026** ✅ | 河南/广东省教育考试院（教育在线核实） | 2026 官方已更新，含 3+1+2 新高考物理/历史类 |
| **一分一段表** | 2024 | 公开数据集 Gaokao-score-distribution | 位次查询基于 2024 数据，**仅供参考**；2025/2026 待官方整理后更新 |
| 河南 2025 前 | 文理分科 | 历史保留 | 2025 起河南改 3+1+2，旧文理数据仅作历史对比 |

> ⚠️ 使用一分一段表做位次查询时，请注意数据为 2024 年。年份波动会使位次略有偏差，**正式填报请以当年省考试院公布的一分一段表为准**。每个数字均带 source 字段，可点开核对来源。

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
- **Engine 层**（`app/engine/`）：纯函数（五险一金 + 2024 个税累进 + 城市成本年化），无 DB 依赖。

## 端到端验证预期值

- `POST /api/v1/insurance/compute` body `{"salary": 9000, "city": "全国基准"}` →
  - `total_labor_cost` = 9000 × (1 + 单位比例合计 0.34) = **12060**
  - `take_home_pay` > 0（扣个人五险 + 个税后）
- `GET /api/v1/cities/深圳/cost` → 一房一厅 high ≈ 2600，综合月成本 3500–6000

## 来源追溯

每个数字都带 `source` / `as_of` / `confidence` / `note`，从 YAML 种子 → Domain 校验 → SQLite 存储 → API 响应全链路不丢失。手编种子 `confidence ≤ 0.6` 且 `note` 含「待爬虫校准」，后续爬虫可按 `source` 比对替换。

## 设计文档

详见 `docs/superpowers/specs/2026-06-25-data-foundation-design.md`。
