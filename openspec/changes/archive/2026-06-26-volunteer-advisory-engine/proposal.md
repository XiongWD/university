## Why

拆分项 A（`deprecate-life-path-narrative`，已归档）已完成去叙事/去交易化，留下了 `/life-paths`、`/life-trajectory` 两个 deprecated 端点。但产品缺少一个**面向新定位的推荐主接口**：当前 `/recommend`（传统冲稳保）只看分数位次、不含资格过滤与专业方向；`/life-paths`（deprecated）虽串了资格/市场/录取，但其 `major_value` 被错设为 `market.current_market_score`（违反父设计 §3.4 的 `market × fit` 门控），且输出绑定废弃的三路径模型。

本变更（拆分项 B）按父设计文档 `docs/superpowers/specs/2026-06-26-volunteer-recommendation-refocus-design.md` §3/§4，在已落地的资格/录取/适配/市场/费用/位次引擎之上，新建 `POST /api/v1/volunteer/advisory` 主接口，输出"专业方向优先"的可解释建议，并修正适配评分门控。

## What Changes

- **新增 advisory 主接口**：`POST /api/v1/volunteer/advisory`，输入完整考生画像（`StudentAcademicProfile` + 家庭预算，复用 `LifePathsRequest` 字段集），按 §3 主链路编排：考生画像 → 资格过滤 → 位次转换 → 专业方向评分 → 院校候选 → 费用压力评估 → 冲稳保 → 可解释输出。
- **新增输出模型**（`app/models/advisory.py`）：`VolunteerAdvisoryResult`、`MajorDirectionAdvice`（含 `market_value`/`student_fit`/`major_value`/`fit_explanation`/`risk_warnings`）、`BudgetSummary`、`IneligibleReason`。`SchoolOption`/`AdmissionBuckets` 复用 `app/models/life_path.py` 现有结构（已含 `total_cost_4y`/`affordability_status`/`data_granularity`/`confidence`/`warnings`，与 §4.1 兼容）。
- **新增主链路编排引擎**（`app/engine/advisory.py`）：`build_advisory()` 串联 `filter_eligible` → `convert_score_to_rank` → `score_direction` → **`compute_major_value_academic`（market×fit 门控，修正现有 life_paths 的错误）** → `predict_group_admission` → 费用 4 年累计 → affordability 分类 → 冲稳保分桶。
- **新增 §3.6 affordability 4 级分类器**：输出 `可承受 / 有压力 / 明显负担 / 超预算`（父设计 §3.6）。现有 `FamilyBudget.pressure_level` 标签为"可轻松承受/有压力/明显负担/极高风险"，与 §3.6 不一致——**新建独立分类器，不修改 `FamilyBudget`**。
- **费用分项**：§3.6 要求学费/住宿费/生活费/总开销拆分，而 `cost.compute_annual_cost` 仅返回单点 `CostBand`——advisory 层单独累计 4 年分项。
- **数据粒度与可信度**：`SchoolOption.data_granularity`（major/group/school）来自 `GroupAdmissionPrediction.data_granularity`；仅组数据时按 §3.3 提示"组内目标专业数据不足"。
- **遵守 narrative-policy**：A 已建主 spec `openspec/specs/narrative-policy/`，advisory 输出不出现人生路径/回本/ROI 等禁止词。

## Capabilities

### New Capabilities
- `volunteer-advisory`: 志愿推荐 advisory 主接口与专业方向优先主链路。规约 `POST /api/v1/volunteer/advisory` 的输入输出契约、§3 主链路顺序（资格前置→位次→专业方向 market×fit→院校→费用压力→冲稳保→可解释）、§3.4 乘法门控、§3.6 费用压力 4 级、§3.3 数据粒度提示、§6.2 推荐逻辑验收。归档后成为 `openspec/specs/volunteer-advisory/` 主 spec。

### Modified Capabilities
<!-- 无。advisory 是全新接口与编排；不修改现有 capability 的 requirements。narrative-policy（A 已建主 spec）作为约束被遵守，不被修改。 -->
_无_

## Impact

- **代码（新增）**：
  - `app/api/routers/volunteer.py`：新增 `advisory` handler（复用现有 `_build_academic_profile`/`_build_budget`/`_load_offerings`/`_load_directions_and_snapshots`/`_load_rank_entries`/`_load_admissions` 等 helper）。
  - `app/engine/advisory.py`：`build_advisory()` 主链路编排 + affordability 分类器。
  - `app/models/advisory.py`：输出模型。
- **代码（不动）**：`eligibility.py`/`admission_prediction.py`/`major_fit.py`/`job_market.py`/`cost.py`/`rank_query.py` 内部逻辑（仅调用）；`life_path.py`/`trajectory.py`（A 已 deprecated，不动）。
- **数据**：复用现有 seed（admission_offerings / major_directions / job_snapshots / universities / cities / majors / careers / score_rank），无新数据需求。
- **测试**：API 测试（advisory 返回专业方向/学校清单/费用压力/不可报原因）；engine 测试（market×fit 门控、affordability 4 级）；eligibility 边界（日语考生/选科不符/数学弱不前置）；数据粒度（仅组数据提示）；遵守 narrative-policy。
- **依赖**：无新增依赖。
- **与父设计/拆分项 A 的关系**：父设计 §3/§4/§6.2-6.4 的落地；A（已归档）提供的 `narrative-policy` 主 spec 作为约束；B 不复活任何 A 已废弃的叙事。
