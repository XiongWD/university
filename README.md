# 高考志愿专业推荐系统

基于分数、选科、外语、数学、一分一段与家庭预算，生成可解释的专业方向与冲稳保院校建议。

**核心功能**：输入考生分数+选科+外语+家庭预算 → 专业方向建议 + 冲稳保院校清单，含大学费用/家庭压力/起薪参考/录取风险/不可报原因。

> 声明：所有数据基于历史数据模拟，非就业或收入预测。正式填报请以省考试院公布数据为准。

## V2.2 架构（资格链核心）

系统语义顺序（强制DAG，Eligibility是"门"不是"权重项"）：
```
[0] Eligibility Chain    选科/语种/单科门槛资格过滤 → 定义可行解空间
[1] Admission            两阶段录取预测（专业组投档 ≠ 组内专业风险）
[2] Career Market        职业×城市快照，双分归一（当前就业+长期趋势）
[3] Major Fit            乘法门控（market × student_fit，弱适配坍缩）
[4] Cost & Budget        家庭可承担预算硬约束
[5] Life Path Optimizer  稳健/均衡/进取三路径（独立目标函数+多样性约束）
```

关键设计（评审纠正）：
- **英语≠日语拆三层**：高考应试语种(硬) / 外语单科分(门槛) / 实际英语能力(软适配)
- **数学门槛vs风险分开**：章程明确才硬过滤，否则只标学习风险
- **专业组≠组内专业**：两阶段分开，数据不足明确标注
- **2025同制度primary**：2024旧制度仅趋势辅助，不直接平均
- **家庭可承担预算**：储蓄+4×年预算+贷款+资助，非年收入×k

## 📊 数据时效

| 数据类型 | 最新年份 | 来源 | 说明 |
|----------|----------|------|------|
| **省控线** | **2026** ✅ | 河南/广东省教育考试院 | 含3+1+2新高考物理/历史类 |
| **一分一段表（河南）** | **2026** ✅ | OCR自官方PDF（5硬锚点校验） | 物理/历史类1016行 |
| 一分一段表（河南2025） | **2025** ✅ | OCR自官方PDF | 新高考首年物理/历史类 |
| **职业市场快照** | **2026** ✅ | BOSS直聘/智联2026 | 职业×城市，8方向市场分 |
| **招生专业组规则** | **2025** ✅ | 各校招生章程 | ABCD四类规则（语种/单科/选科） |
| 院校录取数据 | 2024-2025 | 各校招生网/考试院 | MVV 13校规则模板 |
| 专业薪资 | **2026** ✅ | 招聘网站(河南/非一线校准) | 23专业薪资三分位 |

## 技术栈

Python 3.13 · FastAPI · Pydantic v2 · SQLModel · SQLite · Vite + React 18 + TypeScript + Tailwind CSS · pytest（301测试）

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
| POST | `/api/v1/volunteer/recommend` | 传统冲稳保志愿表 |
| POST | `/api/v1/volunteer/life-paths` | (deprecated) 旧版多方案建议，保留以维持兼容 |
| POST | `/api/v1/volunteer/life-trajectory` | (deprecated) 志愿+费用+就业参考 |
| GET | `/api/v1/volunteer/admissions` | 录取数据（track/year/分数范围筛选） |
| GET | `/api/v1/provincial/score-rank/rank` | 分数→位次 |
| GET | `/api/v1/provincial/control-line` | 省控线 |
| GET | `/api/v1/universities/{school}/cost` | 大学4年费用估算 |
| GET | `/api/v1/careers` | 职业列表（含薪资三档区间 + 来源） |
| GET | `/api/v1/careers/{id}` | 职业详情 |

## 启动前端

```bash
cd web-ui && npm install && npm run dev
```

访问 `http://localhost:5173`，主要页面：

| 路径 | 说明 |
|------|------|
| `/` | 专业推荐（冲稳保+费用+就业参考） |
| `/cost` | 大学费用估算（公立/民办/中外合作对比） |
| `/rank` | 位次查询工具（分数↔位次双向） |
| `/control-line` | 省控线查询 |
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
