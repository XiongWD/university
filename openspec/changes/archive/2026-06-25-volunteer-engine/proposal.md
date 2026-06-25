## Why

产品的核心价值——用户多次强调"最关键"——是**根据考生分数筛选可报学校、生成完整志愿表**。data-foundation（实体模型）与 provincial-score-data（省控线+一分一段表位次换算）两层底座已就绪，但缺把"考生分数→可报学校"这条决策链路打通的**引擎**。本 change 建立志愿填报引擎，是三层架构第②层 decision-engine 的核心子能力，直接服务 2026 志愿填报季考生。

与已归档 change 的关系：provincial-score-data 的 design.md 把"志愿筛选引擎（位次换算/冲稳保/表生成）"明确划为后续 change。本 change 正是该职责的落地。注意厘清边界：**本 change（志愿筛选引擎）≠ change② 人生路径决策引擎**——前者是"分数→学校"的志愿表生成，后者是"选择→收入/生存推演"的人生模拟，两者解耦。

## What Changes

- 新增**志愿填报引擎** `app/engine/volunteer.py`（纯函数，无 DB 依赖），4 个核心能力：
  - `convert_score_to_rank`：分数→位次（复用 rank_query 精确匹配 + 缺失线性插值）
  - `equivalent_rank`：等效位次换算（按考生总量比例折算跨年位次）
  - `classify_strategy`：冲稳保分档（考生位次 ±5% 为稳，更优为冲，更差为保）
  - `generate_volunteer_table`：志愿表生成（风险偏好驱动各档配额 + 录取概率估算）
- 新增**志愿结果 domain 模型** `app/models/volunteer.py`：`VolunteerTable` / `VolunteerSuggestion` / `Strategy`(冲稳保枚举) / `AdmissionProbability`
- 扩展**录取数据 schema**：`AdmissionRecord` 加 `major_group`（院校专业组代码）、`subject_requirement`（选科要求）；`Batch` 枚举加 `本科批`/`专科`（支持新高考合并批次）
- 新增**种子录取数据**：河南 6 校 2024 理科真实录取位次（郑州大学 22963 ~ 河南农业大学 114271，覆盖冲到保全梯度），数据源已网络核实
- 扩展 **API 访问层**：`POST /volunteer/recommend`（输入考生画像→冲稳保志愿表）、`GET /volunteer/admissions`（支持 track/year/分数范围筛选可报学校）

## Capabilities

### New Capabilities

- `volunteer-engine`: 志愿填报引擎纯函数（位次换算/等效位次/冲稳保分档/志愿表生成/录取概率估算）

### Modified Capabilities

- `admission-data-schema`: 扩展 AdmissionRecord（major_group + subject_requirement），Batch 枚举加本科批/专科
- `data-foundation-api`: 新增 volunteer router（recommend + admissions 分数范围筛选）

## Impact

- **代码**：新增 `app/engine/volunteer.py` + `app/models/volunteer.py` + `app/api/routers/volunteer.py`；修改 `admission.py`/`tables.py`/`mappers.py`/`main.py`
- **数据**：`data/seed/admissions/admissions.yaml` 扩充真实录取数据（6 校）；后续阶段 B 将 OCR 扩充至 30-40 校
- **依赖**：无新增（复用 pydantic/sqlmodel/fastapi）
- **测试**：20 引擎纯函数测试 + 8 API 端到端测试，全量 176 通过
- **合规**：志愿表标注"基于 2024 历史录取数据预测（实际录取以当年投档为准）"；2026 投档线未公布，用历年位次预测是志愿填报标准做法
- **后续**：阶段 B（OCR 批量录取数据）扩充数据覆盖；change② 人生路径决策引擎与本 change 解耦，独立推进
