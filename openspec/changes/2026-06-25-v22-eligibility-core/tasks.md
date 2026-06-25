# Tasks — v22-eligibility-core

## Phase 0：Execution Spec
- [x] execution-spec.md（系统执行顺序DAG + 禁止规则 + 资格链 + 数据优先级 + MVV标准）
- [x] proposal.md / tasks.md

## Phase 1：Eligibility Engine（资格链=第0层）
- [ ] StudentAcademicProfile（拆高考语种/外语分/实际英语能力/单科/选科）
- [ ] AdmissionOffering升级（accepted_languages/required_language/单科门槛/选科要求，ABCD四类规则）
- [ ] EligibilityResult（eligible + reasons + blocked_fields）
- [ ] 四类规则实现：A语种(硬) B单科(硬,区分外语/英语) C选科(硬) D数学(仅章程明确硬)
- [ ] 输出 eligible_offerings 可行解空间
- [ ] 测试：日语考生被英语限定专业过滤、选科不符过滤、数学弱不擅自门槛

## Phase 2：Admission 双层结构
- [ ] AdmissionMode枚举（major_school提前批 / major_group本科批）
- [ ] Stage A：专业组投档概率（2025同制度位次+三场景：乐观/基准/悲观）
- [ ] Stage B：组内专业风险（target_major + adjustment_risk + unwanted_major_risk）
- [ ] 数据粒度标注（仅有组数据时显示"目标专业数据不足"）
- [ ] 数据优先级：2025 primary，2024 trend only，不直接平均
- [ ] 测试：两阶段分开输出、数据不足明确标注

## Phase 3：重新挂 JobMarket/Fit/Cost
- [ ] job_market/major_fit 改为对 eligible_offerings 运行
- [ ] 英语适配用 english_actual_level（非高考语种）
- [ ] 数学适配区分章程门槛(硬)与学习风险(软)
- [ ] 测试：优化仅在合法集合上运行

## Phase 4：Life Path Optimizer + MVV
- [ ] MVV数据集（10-15校，覆盖公办6-8/应用型3-5/民办2-3 + ABCD四类规则）
- [ ] 三路径优化器（稳健/均衡/进取独立目标函数 + 多样性约束min_path_distance）
- [ ] 家庭预算硬约束（可承担预算=储蓄+4×年预算+贷款+资助）
- [ ] 弟弟场景MVV验证（7项系统不变量）
- [ ] 测试：路径差异真实、不可报原因输出、预算过滤

## Phase 5：前端（验证后）
- [ ] 三层页面（路径总览/详情/冲稳保）
- [ ] 资格过滤原因展示
- [ ] 数据粒度+置信度+证据等级显示
