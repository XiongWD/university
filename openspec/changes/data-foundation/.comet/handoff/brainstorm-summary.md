# Brainstorm Summary

- Change: data-foundation
- Date: 2026-06-25

## 确认的技术方案

技术栈：Python 3.13 + FastAPI + Pydantic v2 + SQLModel + SQLite + YAML 种子

分层架构（方案 B：双模型 + 映射层）：
- Domain 层（`app/models/`）：纯 Pydantic v2，保留嵌套结构（薪资三档区间、租房三档、学科评估列表），继承 SourcedRecord 基类。用于 YAML 校验与 API 响应。
- Table 层（SQLModel table=True）：字段拍平存储，纯持久化，不做业务。
- Repository 层（`app/repositories/`）：Table Row ↔ Domain Read 的映射，集中重组嵌套/拍平逻辑，可独立测试。
- Loader 层：YAML → Domain（校验来源字段）→ Table Row（幂等 upsert）。
- Engine 层（`app/engine/`）：纯函数计算（五险一金、年成本、个税累进），无 DB 依赖，可纯单元测试。

边界：data-foundation 只做"查询/存取/纯计算"；所有"根据考生画像评分/筛选/推演路径"归属 decision-engine（change②）。

## brainstorming 已确认的设计决策

1. **考生画像表达**
   - 偏科能力：真实高考科目分数（subject_scores: dict[str,int]，如 {数学:120, 英语:75}），而非 1–5 分制
   - 家庭体制资源：6 个布尔位
     - has_govt_resource（体制内）、has_medical_resource（医生/医疗）、has_education_resource（教师/教育）
     - has_finance_resource（银行/金融/证券）、has_law_resource（法律/司法）、has_business_resource（企业主/商业/外贸）
   - 其他字段：province、total_score、minor_language{lang,level}、gender、interests[]、strengths[]、risk_preference(稳/中/冲)

2. **数据层与引擎边界**
   - 本层只提供原始数据查询 + 纯计算
   - "按省份+分数筛选可报大学"属决策逻辑 → 归 change②
   - 本层 `GET /admissions` 仅返回原始录取记录，不做筛选

3. **个税计算**
   - 2024 完整累进税率表（7 档，3%→45%），起征点 5000/月
   - 预留专项附加扣除接口（首版可选填）

4. **数据模型架构**：方案 B（Domain 双模型 + Repository 映射）

## 关键取舍与风险

| 取舍/风险 | 决策/缓解 |
|-----------|-----------|
| 嵌套对象存储 | Domain 保嵌套，Table 拍平，Repository 映射（多写映射代码换类型安全与查询能力）|
| 种子数据失真 | confidence≤0.6 手编 + note"待爬虫校准" + as_of 日期；后续爬虫按 source 比对替换 |
| SQLModel×Pydantic v2 兼容 | 锁定 pydantic≥2.5 + sqlmodel≥0.0.16，CI 验证 |
| 合规风险 | 字段命名"预期/历史区间"，标注"基于历史数据模拟"，无"保证/预测"措辞 |
| 数据组合爆炸 | YAML 模板化：职业存薪资比例曲线，城市存基数，引擎组合计算 |

## 测试策略

分层测试：
- models 测试：各实体合法构造、非法构造被拒（缺字段/区间倒挂/枚举非法/confidence>1）、嵌套对象完整
- engine 测试：企业成本公式、到手工资（低/中/高跨档）、个税 7 档边界值、年成本公式
- loader 测试：YAML→Domain→Table 全流程、幂等重复加载、损坏记录被拒并报告
- API 测试（httpx）：GET 各端点返回来源字段、?tier= 筛选、POST /insurance/compute 计算正确
- 来源追溯链路测试：种子→模型→DB→响应来源字段全链路不丢失

## Spec Patch（将回写的 delta spec 变更）

1. `student-profile-data/spec.md`：
   - 偏科用 subject_scores dict（真实分数），非 1–5 分制
   - 家庭资源改 6 布尔位（govt/medical/education/finance/law/business）
2. `admission-data-schema/spec.md`：
   - 移除"按省份+分数筛选"决策性查询，改为"仅提供原始录取数据查询"
3. `social-insurance-model/spec.md`：
   - 明确 2024 累进税率表 7 档 + 起征点 5000 + 专项扣除接口
