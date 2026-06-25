## Why

人生经济模型模拟器的产品价值在于"把模糊的高考志愿决策变成可追溯的数字决策"。但当前项目零数据基础——没有任何职业、城市、大学、专业数据可供计算，也没有考生画像结构来承载"根据考生情况模拟填报"的核心输入。后续的决策引擎（评分/路径推演）和 Web 前端（精致展示）都依赖一个**结构化、可扩展、带来源追溯**的数据底座。本 change 建立这个底座，让产品从"想法"变成"有真实数字可算"。

数据真实性是产品成败关键（文档原话："产品成败 = 数据真实性，而不是算法"），因此本 change 同时建立**来源追溯机制**：每个数字都带数据来源、采集时间、置信度，为信任与合规（"基于历史数据模拟"而非"预测未来"）打基础。

## What Changes

- 新增**六类核心数据模型**（Python dataclass / Pydantic schema）：
  - 考生画像 `StudentProfile`：总分、省份、偏科分数（数学/英语/语文/文综·理综）、小语种能力、家庭体制资源（体制内/医疗/教育亲属）、性别、兴趣与强项、风险偏好
  - 职业 `Career`：起薪、5 年中位薪资、15 年薪资上限、稳定性、晋升速度、编制属性、关联学科
  - 五险一金 `SocialInsurance`：统一的"总用工成本模型"（企业成本/到手工资公式）+ 全国基准比例，可按城市调参
  - 城市成本 `CityCost`：租房 3 档（单间/一房一厅/合租）、吃饭、通勤、其他、综合月成本、房价均价
  - 大学实力 `University`：层级（985/211/双一流/一本/二本/专科）、就业能力指标、学科评估
  - 专业实力 `Major`：就业密度、薪资分布（P25/P50/P75）、门槛难度、上升空间
- 新增**录取数据 schema**（仅定义结构与少量手编示例，不批量入库——批量历年分数线/位次留给后续爬虫 change）
- 新增 **YAML 种子数据**：覆盖约 7 个代表城市、15 个职业、15–20 个专业，数值参考文档范例量级，全部标注"待爬虫校准"
- 新增 **SQLite 加载层**：YAML 种子首次/按需加载进 SQLite，提供带索引的查询能力
- 新增 **FastAPI 数据访问 API**：按实体提供查询端点，返回结果附带 `source` / `as_of` / `confidence` 来源字段
- 新增**来源追溯约束**：所有数据记录强制带 `source`、`as_of`、`confidence` 字段，加载与 API 层均做校验
- 新增**五险一金成本计算引擎**（纯计算，非决策）：实现"企业成本 = 工资 × (1 + 单位比例)"、"到手 = 工资 - 个人部分 - 个税"公式

## Capabilities

### New Capabilities

- `student-profile-data`: 考生画像数据模型与校验——承载"根据考生情况模拟填报"的输入结构
- `career-data`: 职业数据模型与种子（薪资曲线/稳定性/编制/学科关联）
- `social-insurance-model`: 五险一金统一用工成本模型与计算引擎（企业成本/到手工资）
- `city-cost-data`: 城市生活成本数据模型与种子（租房 3 档/吃饭/通勤/房价）
- `university-data`: 大学实力三维数据模型与种子（层级/就业能力/学科评估）
- `major-data`: 专业实力数据模型与种子（就业密度/薪资分布/门槛/上升空间）
- `admission-data-schema`: 录取数据 schema 定义与示例（仅结构，不批量入库）
- `data-foundation-api`: 数据访问 FastAPI 层 + SQLite 加载层 + 来源追溯约束

### Modified Capabilities

（无——这是项目的首个 change，`openspec/specs/` 当前为空，无既有 spec 被修改。）

## Impact

- **代码**：在仓库根新增 Python 包（如 `app/` 或 `data_foundation/`），含 models、seed（YAML）、loader、api、engine 模块
- **依赖**：新增 Python 依赖——FastAPI、Uvicorn、Pydantic、SQLModel/SQLAlchemy、PyYAML；测试依赖 pytest
- **数据**：新增 `data/seed/*.yaml` 种子目录与 `data/llm_sim.db`（gitignore，首次加载生成）
- **API**：新增本地 FastAPI 服务（如 `localhost:8000`），暴露六类数据查询端点
- **后续依赖**：`decision-engine` change 将消费本层的数据模型与 API；`web-ui` change 将消费本层 API 展示数字
- **合规**：数据组织为"基于历史数据的模拟区间"，不包含任何"保证就业/确切预测未来收入"类字段
