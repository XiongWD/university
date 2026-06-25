# Change: v22-eligibility-core（资格链核心重构）

## Why

V2.1的根本缺陷：**优化发生在非法解空间上**（Optimization over invalid domain）。
JobMarket/MajorFit/Cost 在算推荐，但 Eligibility 只是弱过滤器。导致可能推荐语种不符/选科不符/单科不达标的非法专业，录取概率是"假概率"，路径优化完全失真。

**核心纠正**：Eligibility 是"门"不是"权重项"。必须先定义可行解空间（合法可报集合），所有后续优化（市场/适配/成本/路径）只能在该集合上运行。

## What Changes

### Phase 0：Execution Spec（已完成）
系统执行顺序DAG + 禁止规则 + 资格链定义 + 数据优先级 + MVV标准。

### Phase 1：Eligibility Engine（真正的第0层）
- `StudentAcademicProfile`：拆高考语种/外语分/实际英语能力/单科/选科
- `EligibilityResult`：eligible + reasons + blocked_fields
- 四类规则：A语种(硬) B单科门槛(硬,区分外语/英语) C选科(硬) D数学(仅章程明确时硬)
- 输出 eligible_offerings，定义可行解空间

### Phase 2：Admission 双层结构
- Stage A：专业组投档概率（group_admission_risk，三场景）
- Stage B：组内专业录取风险（target_major + adjustment + unwanted_major）
- `AdmissionMode`：major_school(提前批) vs major_group(本科批)
- 数据优先级：2025同制度primary，2024旧制度trend only

### Phase 3：重新挂 JobMarket/Fit/Cost
- 现有 job_market.py/major_fit.py 保留，但对 eligible_offerings 运行
- 英语/数学适配用拆分后的字段（实际英语能力 vs 高考语种）

### Phase 4：Life Path Optimizer + MVV验证
- 稳健/均衡/进取三路径（多样性约束）
- MVV弟弟场景（480+日语+历史+低收入）闭环验证系统不变量

## Capabilities

### New
- `eligibility-engine`：资格链判定（四类规则+EligibilityResult）
- `admission-prediction`：两阶段录取预测（专业组+组内专业）

### Modified
- `volunteer-engine`：Eligibility 从弱过滤升级为可行解空间定义层
- `major-fit`（第2步）：适配用拆分后的学业画像字段

## Impact

- **代码**：新增 app/engine/eligibility.py + app/models/eligibility.py；重构 volunteer.py 的资格判定
- **数据**：MVV数据集（10-15校×AdmissionOffering规则模板，覆盖ABCD四类规则）
- **架构**：系统执行顺序重排，Eligibility成为强制前置门
- **测试**：系统不变量测试（资格/预算/路径/数据/可复现）

## 关键不变量（测试标准）
1. 日语考生不可进入英语限定专业
2. 未过滤资格时不做排名
3. 数学弱标学习风险但不擅自创造录取门槛
4. 学校级数据不伪装成专业级
5. 2024/2025数据不直接平均
6. 低置信不输出确定性措辞
