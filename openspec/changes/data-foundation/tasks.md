## 1. 项目脚手架

- [x] 1.1 创建 Python 包结构 `app/{models,engine,loader,api/routers}`、`data/seed/{cities,careers,universities,majors}`、`tests/` 目录与 `__init__.py`
- [x] 1.2 创建 `pyproject.toml`，声明依赖：fastapi、uvicorn、pydantic v2、sqlmodel、sqlalchemy、pyyaml；dev 依赖 pytest、httpx
- [x] 1.3 创建 `.gitignore`（忽略 `data/llm_sim.db`、`__pycache__`、`.venv`、`node_modules` 等）
- [x] 1.4 创建 `app/config.py` 配置模块（数据库路径、种子目录路径、API 版本前缀）

## 2. 数据模型层（app/models）

- [x] 2.1 实现 `app/models/base.py`：`SourcedRecord` 基类（Pydantic），含 `source`、`as_of`、`confidence`（0–1）、`note` 字段，校验 confidence 取值范围
- [x] 2.2 实现 `app/models/student.py`：`StudentProfile` 模型（总分/省份/偏科分数含文理两种模式/小语种/家庭体制资源/性别/兴趣/强项/风险偏好三档枚举）
- [x] 2.3 实现 `app/models/career.py`：`Career` 模型（薪资区间起薪/5年中位/15年上限/稳定性/晋升速度/编制/关联学科），校验区间最低≤最高
- [x] 2.4 实现 `app/models/insurance.py`：`SocialInsurance` 城市社保模型（各险种个人/单位比例，比例≤1.0 校验）+ 全国基准常量
- [x] 2.5 实现 `app/models/city.py`：`CityCost` 模型（租房3档区间/吃饭/通勤/其他/综合月成本/房价均价），校验区间
- [x] 2.6 实现 `app/models/university.py`：`University` 三维模型（层级枚举/就业能力/学科评估列表）
- [x] 2.7 实现 `app/models/major.py`：`Major` 模型（就业密度/薪资P25-P50-P75三分位/门槛难度/上升空间），强制三分位
- [x] 2.8 实现 `app/models/admission.py`：`AdmissionRecord` schema（学校/专业/省份/年份/科类/最低分/位次/批次）

## 3. 计算引擎（app/engine）

- [x] 3.1 实现 `app/engine/insurance.py`：纯函数 `compute_total_labor_cost(salary, insurance)` 返回企业成本（工资×(1+单位比例合计)）
- [x] 3.2 实现 `compute_take_home_pay(salary, insurance)`：到手 = 工资 - 个人五险一金 - 个税
- [x] 3.3 实现累进个税计算（2024 税率表），支持多档累进
- [x] 3.4 实现城市成本年化计算：`compute_annual_cost(city_cost, tuition, accommodation)` = 12×月成本中位 + 学费 + 住宿费

## 4. 数据库与加载层

- [x] 4.1 实现 `app/db.py`：SQLite 引擎创建 + SQLModel 表定义映射各模型 + Session 工厂
- [x] 4.2 实现 `app/loader/seed_loader.py`：读取 `data/seed/*.yaml`，按模型校验，校验来源字段完整性
- [x] 4.3 实现幂等加载（按主键 upsert），重复执行不产生重复
- [x] 4.4 校验失败时拒绝记录并报告文件与记录标识（不静默跳过）

## 5. 种子数据（data/seed/*.yaml）

- [x] 5.1 编写 7 个城市成本种子（深圳/北京/上海/郑州/成都/武汉/西安），数值参考文档量级，全部标注 source/as_of/confidence/note"待爬虫校准"
- [x] 5.2 编写 15 个职业种子（公务员/医生/教师/IT/外贸/跨境电商/国企/日企商务等），含薪资区间
- [x] 5.3 编写城市社保比例种子（各城五险一金比例配置，含全国基准）
- [x] 5.4 编写 ≥10 所大学种子（985/211/双一流/一本各样本），学科评估用第四轮并标注
- [x] 5.5 编写 ≥15 个专业种子（含日语/国贸/历史等文科 + 理工科），薪资强制 P25/P50/P75
- [x] 5.6 编写录取数据示例（3–5 校 × 2 省），验证 schema 可用

## 6. FastAPI 访问层（app/api）

- [x] 6.1 实现 `app/api/main.py`：FastAPI 应用 + `/api/v1` 前缀 + 启动时自动加载种子（若 DB 空）
- [x] 6.2 实现职业 router：`GET /careers`、`GET /careers/{id}`，响应含来源字段
- [x] 6.3 实现城市 router：`GET /cities`、`GET /cities/{city}/cost`
- [x] 6.4 实现薪资查询：`GET /careers/{id}/salary?city={city}`
- [x] 6.5 实现大学 router：`GET /universities` 支持 `?tier=` 筛选
- [x] 6.6 实现专业 router：`GET /majors`
- [x] 6.7 实现五险一金计算端点：`POST /insurance/compute`（工资+城市→企业成本/到手）
- [x] 6.8 实现录取数据查询端点（按省份+分数+科类筛选，空数据集不报错）

## 7. 单元测试（tests）

- [x] 7.1 测试模型校验：各实体合法构造 + 非法构造（缺字段/区间倒挂/枚举非法）被拒绝
- [x] 7.2 测试五险一金计算引擎：企业成本、到手工资、个税累进（含高工资跨档）
- [x] 7.3 测试城市成本年化计算
- [x] 7.4 测试种子加载：首次加载、幂等重复加载、损坏记录被拒绝
- [x] 7.5 测试 API 端点：主要查询（含来源字段返回）、按层级筛选、五险一金计算端点
- [x] 7.6 测试来源追溯全链路：种子→模型→DB→API 响应来源字段不丢失

## 8. 验证与文档

- [x] 8.1 编写 `README.md`：项目简介、安装（`pip install -e .`）、启动 API（`uvicorn app.api.main:app`）、加载种子、运行测试说明
- [x] 8.2 端到端验证：启动服务，用文档范例（深圳公务员/郑州成本）查询确认数字与来源正确
- [x] 8.3 确认合规：全代码库无"保证就业/预测未来收入"措辞，数据均标注"基于历史数据模拟"
