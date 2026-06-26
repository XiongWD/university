# 验证报告：volunteer-advisory-engine（拆分项 B — advisory 主接口 + 专业方向主链路）

- **Change**: volunteer-advisory-engine
- **Date**: 2026-06-26
- **Branch**: feature/20260626/volunteer-advisory-engine
- **Base-ref**: 34bab46
- **verify_mode**: full（24 任务 / 18 文件 / 1 capability）
- **关联**：父设计 `docs/superpowers/specs/2026-06-26-volunteer-recommendation-refocus-design.md` §3/§4/§6.2-6.4；拆分项 A（已归档）提供 narrative-policy 约束。

## Summary

| 维度 | 状态 |
|------|------|
| Completeness | 24/24 任务完成；7/7 requirements 实现 |
| Correctness | 14/14 scenarios 覆盖（实现 + 测试） |
| Coherence | 实现遵循 Design Doc 8 项决策；无矛盾 |

**Fresh verification evidence（本次报告内现场运行）：**
- `python -m pytest -q` → **340 passed**（含 A 的 narrative-policy、现有回归、advisory 全部测试）
- build_command（import check）→ BUILD OK
- `openspec validate volunteer-advisory-engine` → valid
- advisory 路由注册：`['/api/v1/volunteer/advisory']`
- 代码审查（standard）：verdict = **Ready to merge: With fixes → 已全部修复**

## Completeness

- **任务完成**：24/24 `[x]`（`grep -c '\- \[ \]'` = 0）。
- **requirements 实现**：volunteer-advisory delta spec 7 个 requirement 全部落地：
  1. advisory 主接口契约 → POST /api/v1/volunteer/advisory 返回 VolunteerAdvisoryResult ✓
  2. 专业方向优先主链路顺序 → filter_eligible 前置、评分仅 eligible ✓
  3. 专业方向乘法门控 → compute_major_value_academic 的 market×fit ✓
  4. 录取风险与数据粒度 → group/school 时 warnings 提示 ✓
  5. 费用压力 4 级 → classify_affordability 可承受/有压力/明显负担/超预算 ✓
  6. 冲稳保分桶与可解释输出 → 冲/偏冲→reach, 稳→match, 偏保/保→safe + fit_explanation/risk_warnings/notes ✓
  7. （scenario：跨年回退标注）→ notes 含数据年份 ✓

## Correctness（scenario 逐项核验）

| Scenario | 核验 | 结果 |
|----------|------|------|
| advisory 端点返回完整结构 | API 测试断言 7 个顶层 key + 3 桶 | ✓ |
| 输入画像区分高考语种与真实英语能力 | StudentAcademicProfile 含 exam_foreign_language + english_actual_level | ✓ |
| 资格过滤前置于评分 | filter_eligible(:113) 先行；评分循环仅遍历 eligible(:128) | ✓ |
| 不可报原因保留并输出 | ineligible → IneligibleReason(blocked_summary) | ✓ |
| 专业方向评分用 market × fit | compute_major_value_academic(:140) + breakdown major_value(:190)；测试断言 major_value≈market×fit | ✓ |
| 数学弱考生数学强依赖专业不前置 | market×fit 门控 + risk_warnings 含数学风险；engine 测试覆盖 | ✓ |
| 仅专业组数据提示目标专业不确定 | data_granularity group/school → warnings(:162) | ✓ |
| 跨年数据标注年份与制度 | notes 含 "{data_year} 年同制度位次参考" | ✓ |
| 费用拆分含学费/住宿费/生活费 | _compute_4y_cost 返回 (t4,a4,l4,total4) | ✓ |
| 民办/中外合作高费用显示压力 | classify_affordability + affordability_status；测试覆盖 | ✓ |
| 家庭预算不足标记超预算 | ratio>3 或超 affordable → "超预算"；边界测试覆盖 | ✓ |
| 冲稳保归并输出 | _LEVEL_BUCKETS 映射；不推荐跳过（审查修复） | ✓ |
| 当前年份数据缺失回退标注 | router actual_year = admissions[0].year if admissions else 2025 | ✓ |
| 正常考生产出非空建议 | 端到端测试 test_build_advisory_produces_nonempty（审查补充） | ✓ |

## Coherence（Design Doc 决策遵循）

| 决策 | 遵循 | 证据 |
|------|------|------|
| D1 输出模型新建 + SchoolOption 复用 | ✓ | app/models/advisory.py 新建；SchoolOption/AdmissionBuckets 从 life_path 导入 |
| D2 build_advisory 纯函数 + router 注入 | ✓ | app/engine/advisory.py；handler 注入数据 |
| D3 用 compute_major_value_academic | ✓ | :140；修正 life_paths 的 current_market_score 错误 |
| D4 affordability 新建独立 4 级分类器 | ✓ | classify_affordability；不改 FamilyBudget |
| D5 费用 4 年分项在 advisory 层累计 | ✓ | _compute_4y_cost |
| D6 数据粒度复用 admission_prediction | ✓ | group_pred.data_granularity 透传 |
| D7 冲稳保用 admission_level 映射 | ✓ | _LEVEL_BUCKETS |
| D8 单一 capability volunteer-advisory | ✓ | delta spec 7 reqs / 14 scenarios |

**Spec 漂移检查**：delta spec 与 Design Doc 无矛盾。Build 阶段审查反馈的修复（不推荐跳过、None-major 防御、边界/e2e 测试）属实现细节，未改变 spec 契约。

## 代码审查（standard review_mode）

- 审查范围：`34bab46..HEAD`（18 文件）
- verdict：**Ready to merge: With fixes → 全部已修复**
- Critical / Important：原 2 项 Important → 均已修复
  - #2 缺端到端非空测试 → **已修复**（test_build_advisory_produces_nonempty）
  - （#3 不推荐误归 match、#4 None-major、#7 边界）→ **均已修复**
- Minor：#1 data_granularity 警告当前 Stage A 总是 group 级（结构如此），已记录；#5/#6/#8 属可接受取舍。

## Issues

- **CRITICAL**：无
- **WARNING**：无
- **SUGGESTION**：data_granularity 警告当前总触发（Stage A 结构性 group 级）——未来接入 major 级数据时需细化；已记录非阻塞。

## 安全检查

- 无硬编码密钥
- 无新增 unsafe 操作
- 无新依赖引入
- 纯新增（不改动现有行为），向后兼容

## Final Assessment

所有检查通过。340 测试全绿，advisory 主链路经验证：资格前置门 + market×fit 门控 + affordability 4 级 + 数据粒度提示 + 冲稳保分桶均符合 §3/§6 验收；端到端测试确认正常考生产出非空建议；遵守 narrative-policy；代码审查 Ready to merge。

**Ready for archive.**
