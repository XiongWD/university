# Tasks

## 1. Schema 扩展
- [x] AdmissionRecord 加 major_group + subject_requirement 可选字段
- [x] Batch 枚举加 本科批 / 专科
- [x] AdmissionRow 表模型同步加字段
- [x] mappers.py admission_to_row/to_domain 同步新字段
- [x] 回归测试通过（145）

## 2. 种子数据
- [x] 河南 6 校 2024 理科真实录取位次（郑大/河大/河师大/财经政法/中原工/农大）
- [x] 广东新高考示例（深圳大学，展示 major_group+subject_requirement）
- [x] 数据源网络核实（各校招生网/考试院 2024 投档线）

## 3. 志愿引擎（TDD）
- [x] domain 模型 volunteer.py（VolunteerTable/Suggestion/Strategy/Probability）
- [x] convert_score_to_rank（精确+插值）测试
- [x] equivalent_rank（比例折算）测试
- [x] classify_strategy（冲稳保分档）测试
- [x] estimate_probability（概率估算）测试
- [x] generate_volunteer_table（端到端，含 track/year 过滤、风险偏好配额、空数据容错）测试
- [x] 20 引擎测试全部通过

## 4. API 端点
- [x] POST /volunteer/recommend（输入考生画像→志愿表）
- [x] GET /volunteer/admissions（track/year/分数范围筛选）
- [x] router 注册到 main.py
- [x] 8 API 端到端测试通过
- [x] 全量回归 176 通过

## 5. 端到端验证
- [x] 真实场景：543 分河南理科考生 → 冲稳保志愿表（河大冲/河师大稳/农大等保）
- [x] 录取概率随位次比单调变化
- [x] 风险偏好改变各档数量

## 6. 文档
- [x] proposal.md / design.md / tasks.md
- [x] specs/volunteer-engine/spec.md
- [x] .comet.yaml + .openspec.yaml
- [x] 全量回归 176 通过（验证完成）
