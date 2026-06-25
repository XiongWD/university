# Execution Spec — 系统执行顺序与资格链定义（V2.2基线）

> **核心纠正**：当前问题是"优化发生在非法解空间上"（Optimization over invalid domain）。
> Eligibility 是"门"不是"权重项"。必须先定义可行解空间，再优化。
> 本文档强制规定系统语义顺序、禁止规则、数据优先级。

## 一、系统执行顺序（强制DAG，不得跳序）

```
[0] Eligibility Chain（合法性门——定义可行解空间）
      ↓ 输出：eligible_offerings（合法可报集合）
[1] Admission Structure（录取结构——专业组+组内专业）
      ↓ 输出：feasible_schools（可录取学校集合+两阶段概率）
[2] Market System（就业市场——评估收益）
      ↓ 输出：major_market_scores
[3] Fit System（能力适配——乘法门控）
      ↓ 输出：major_fit_scores
[4] Cost System（家庭约束——硬预算过滤）
      ↓ 输出：affordable_set
[5] Path Optimizer（三路径——在合法集合上优化）
      ↓ 输出：life_paths（稳健/均衡/进取）
```

**语义铁律**：每一层只能在前一层的输出集合上工作。
- Market/Fit/Cost 是"合法集合上的优化"，不是过滤器。
- 若跳过 Eligibility 直接做 Market 排名，则排名无意义（含不可报项）。

## 二、禁止规则（决策红线）

1. **不允许用 JobMarket 覆盖 Eligibility**：就业再好的专业，语种/选科/单科不符=不可报。
2. **不允许在未过滤资格时做排名**：所有排序/评分必须先过 Eligibility Chain。
3. **不允许用学校分数替代专业资格**：学校级最低投档≠专业录取线，data_granularity 标注防伪装。
4. **不允许混用 2025 同制度数据与 2024 旧制度数据做直接平均**。
5. **不允许用单一"外语能力"字段**：高考应试语种（硬）、外语单科分（门槛）、实际英语能力（软）三者不可混用。
6. **不允许把"数学差→排除"当作章程规则**：仅当章程明确数学门槛才可过滤，否则只能标学习风险。
7. **不允许把"大概率投进专业组"写成"大概率录取目标专业"**：两阶段分开。
8. **低置信度数据不允许输出确定性措辞**：证据D只能"值得关注"。

## 三、资格链定义（Phase 1 核心重构）

### 3.1 StudentAcademicProfile（学业画像，替换原模糊字段）

```python
class StudentAcademicProfile:
    province: str
    admission_year: int
    total_score: int
    primary_subject: str              # 历史 / 物理（3+1+2的首选）
    province_rank: int                # 当前位次（查一分一段表）

    # 单科（高考实考分）
    chinese_score: int
    math_score: int
    exam_foreign_language: str        # 高考应试语种：日语/英语/俄语...
    foreign_language_score: int       # 该语种的高考成绩

    # 实际英语能力（与高考语种独立，用于软适配）
    english_actual_level: str         # none/basic/intermediate/advanced
    english_self_test_score: int | None  # 如有四六级/自评

    # 3+1+2 再选
    elective_subjects: list[str]      # 如["政治","地理"]
    oral_test_taken: bool | None
    oral_test_result: str | None
```

**关键区分**：
- `exam_foreign_language` + `foreign_language_score`：高考录取资格用（日语考生用日语分）。
- `english_actual_level`：入学后课程适配+就业用（日语考生可能英语薄弱）。
- **两者绝不混用**。

### 3.2 EligibilityResult（资格判定输出）

```python
class EligibilityResult:
    eligible: bool
    reasons: list[str]          # 通过/不通过的具体原因
    blocked_fields: list[str]   # 被哪个规则阻挡（language/subject/math/score）
```

### 3.3 四类资格规则（必须逐条实现）

**A. 高考应试语种（硬约束）**
- `required_exam_language`：章程要求英语语种 → 日语考生 INELIGIBLE。
- `accepted_exam_languages`：章程接受哪些语种。

**B. 外语/英语单科门槛（硬约束，需区分"外语"vs"英语"）**
- 章程写"外语单科≥110"且无限语种 → 日语考生用日语分判断。
- 章程写"英语单科≥110"或"要求英语语种" → 日语考生不符。

**C. 3+1+2 选科（硬约束）**
- 首选科目（历史/物理）符合专业组要求。
- 再选2科符合专业组的再选要求（等级赋分，官方一分一段仅按历史/物理分）。
- 再选科目用于**资格过滤**，不单独生成另一套全省位次。

**D. 数学/其他单科门槛（仅章程明确时硬过滤）**
- 章程明确"数学≥95"→ 低于则 INELIGIBLE。
- 章程无规定 → **不得擅自创造门槛**，只能标 math_learning_risk（软适配）。

## 四、两阶段录取模型（Phase 2 核心）

### Stage A：专业组投档概率（group_admission_risk）
输入：2025同制度专业组最低位次 + 2026招生计划变化 + 考生位次
输出：group_probability（乐观/基准/悲观三场景）

### Stage B：组内专业录取风险（target_major_risk）
输入：组内具体专业历史位次 + 专业招生数 + 调剂规则
输出：major_probability + adjustment_risk + unwanted_major_risk

**强制**：仅有专业组数据无组内专业数据时，显示"专业组录取可估算，目标专业数据不足"。

### 三场景预测（替代"比去年高10分=稳"）
- 乐观/基准/悲观三场景，附数据置信度。
- 输出档位：冲/偏冲/稳/偏保/保/不推荐（非精确到个位数概率）。

## 五、数据优先级（2026预测关键）

| 数据 | 角色 | 用法 |
|---|---|---|
| 2025 同制度（历史类/物理类位次+专业组线） | **primary 主依据** | 2026预测核心基准 |
| 2024 旧制度（文理科） | trend only 趋势辅助 | 转换为考生分位百分比，作学校热度/波动参考，**不直接平均** |
| 2023 及以前 | 长期热度参考 | 极低权重 |
| 手编种子 | fallback | confidence 标注，低置信向基准收缩 |

**2026是河南新高考第二年，同制度历史数据仅2025一年完整招生年度**：
- 不向用户展示"精确到个位数的录取概率"。
- 输出冲/偏冲/稳/偏保/保 + 数据置信度。

## 六、批次策略（不能同一算法）

```python
class AdmissionMode(str, Enum):
    MAJOR_SCHOOL = "major_school"        # 提前批：专业+院校
    SCHOOL_MAJOR_GROUP = "major_group"   # 普通本科批：院校专业组（组内填专业+调剂）
```

提前批（公费师范/军事/公安/定向医学）与普通本科批算法不同，模型必须带 batch 策略。

## 七、MVV 验证集（弟弟场景，最小可验证闭环）

### 输入边界样本
河南 / 480分 / 日语 / 历史类 / 政治+地理 / 家庭低收入（8万）/ 数学弱（75）/ 英语薄弱

### MVV 必须覆盖
1. **学校类型**：公办普通本科6-8 + 公办应用型3-5 + 民办2-3
2. **专业方向**：外语外贸(核心) + 师范(备选) + 财经(中风险) + 数字商务(新兴) + 综合(兜底)
3. **规则复杂度**（关键）：
   - A类：无语种限制（只看总分+位次）
   - B类：限英语语种（**必须触发日语考生过滤失败**）
   - C类：单科门槛（数学≥90 或 外语≥100）
   - D类：不明确但入学后英语教学（软风险标注）

### MVV 验证标准（系统不变量）
1. 语种过滤正确：日语考生不可进入英语限定专业。
2. 至少出现一次"被过滤掉的高分学校"（验证非乱推荐）。
3. 必须生成3条有真实差异的路径（非仅换学校名）。
4. 必须输出"不可报原因"（如"该专业要求英语语种，当前为日语考生"）。
5. 数学弱标记学习风险，但不擅自创造录取门槛。
6. 所有结论带 data_granularity + confidence + as_of。
7. 2024旧制度数据不与2025同制度直接平均。

## 八、现有代码处置

- `job_market.py` / `major_fit.py`（第1-2步）：**保留逻辑，但在 Phase 3 重新挂载到合法集合上**。它们本身正确，问题在于之前可能对非法集合运行。
- `school_major.py` / `data_granularity`（第0步）：**保留**，是资格链的数据基础。
- `volunteer.py` 的 `_meets_requirements`：**升级为完整 Eligibility Engine**（Phase 1）。

## 九、执行顺序（强约束）

- **Phase 0**：写本 Execution Spec（完成即本文档）
- **Phase 1**：Eligibility Engine 重写（资格链=第0层）
- **Phase 2**：Admission 双层结构（group + major）
- **Phase 3**：重新挂 JobMarket / Fit / Cost（在合法集合上优化）
- **Phase 4**：Life Path Optimizer + MVV 弟弟场景验证
- **Phase 5**：前端（三层页面）

每 Phase 测试通过+提交后才进下一 Phase。
