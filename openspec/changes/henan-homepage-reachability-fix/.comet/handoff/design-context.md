# Comet Design Handoff

- Change: henan-homepage-reachability-fix
- Phase: design
- Mode: compact
- Context hash: 4696dc07cb5b49c9e72c0243708606604e7730a51701b00865396f15b02e4bf1

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/henan-homepage-reachability-fix/proposal.md

- Source: openspec/changes/henan-homepage-reachability-fix/proposal.md
- Lines: 1-26
- SHA256: 621980d7a1c7fb4e6223dcc32dcfd9cea29986764f7eeef4d8f5779eaa86f746

```md
## Why

用户反馈两个真实问题：
1. 首页生成志愿表时，用户未选择任何院校，结果却出现很多「不推荐」院校。原因是首页把所有 2026 专业组都列出（含资格不符/位次差距过大的），而非只展示可达候选。「不推荐」档位本意是「资格不符」，但用户没主动关注这些院校时，硬塞进结果造成干扰。
2. target-evaluation 院校只有 4 所。全量院校数据官方公开渠道拿不到（多轮真实浏览器+脚本+API 探测均被反爬/字体混淆），但现有 28 所可追溯院校（有 verified 历史位次）应扩充进 seed，UI 诚实标注覆盖比例。

## What Changes

- **首页交互修复**：默认只展示「冲/稳/保/需人工复核」可达候选，「不推荐」院校默认折叠隐藏（可展开查看原因）。不再硬塞用户未关注的不可达院校。
- **扩充 28 所可追溯院校**：从 admission_history 提取的 28 所院校（有 verified 历史位次）补全 universities.yaml + 对应 program_groups/enrollment_plans（基于历史数据推断，标 needs_review）。
- **修 school_code 冲突**：现有数据 10467 同时用于河南城建学院和黄淮学院、14003 用于升达和西亚斯，需用真实官方代码区分。
- **UI 覆盖标注**：首页和目标评估显示「已覆盖 N 所/全量待导入」，诚实反映数据状态。

## Capabilities

### Modified Capabilities
- `henan-candidate-generation`：候选生成不变，但首页消费层只展示可达候选，不推荐折叠

## Impact

- `web-ui/src/pages/HomePage.tsx`（不推荐折叠交互）
- `web-ui/src/pages/TargetEvaluationPage.tsx`（覆盖标注）
- `data/seed/henan/universities.yaml`（扩充到 28 所）
- `data/seed/henan/program_groups_2026.yaml`（补对应专业组）
- `data/seed/henan/enrollment_plans_2026.yaml`（补对应计划）
- 修 school_code 冲突（黄淮学院/西亚斯等真实代码）
```

## openspec/changes/henan-homepage-reachability-fix/design.md

- Source: openspec/changes/henan-homepage-reachability-fix/design.md
- Lines: 1-33
- SHA256: 7ed5e0160045d47755a369f9a7020b3d2d6f6e074711be7d1b1c4725262fe11c

```md
---
comet_change: henan-homepage-reachability-fix
role: technical-design
canonical_spec: openspec
---

## Context

首页推荐把所有 2026 专业组列出（含不推荐），用户未关注时造成干扰。target-evaluation 仅 4 所院校，全量官方源拿不到。现有 28 所可追溯院校可扩充。

## Goals / Non-Goals

**Goals:**
- 首页默认只展示可达候选（冲/稳/保/需人工复核），不推荐折叠
- 扩充 28 所可追溯院校 + 修 school_code 冲突
- UI 诚实标注覆盖比例

**Non-Goals:**
- 不攻克全量院校抓取（用户另行提供源）
- 不改候选生成算法（只改消费层展示）

## Decisions

**D1 不推荐默认折叠**：首页 buckets 渲染时，「不推荐」档位默认 `collapsed`，提供「查看 N 所不可达院校及原因」展开按钮。可达档位（冲/稳/保/需人工复核）始终展示。

**D2 扩充用历史数据推断**：28 所院校从 admission_history 提取，专业组/计划基于历史专业推断（标 needs_review），历史位次直接复用。已有 verified 的核心校保持 verified。

**D3 school_code 去重**：用官方院校代码（黄淮学院 10919、西亚斯 14003 实为独立代码需核实）。冲突的用「校名+代码」双校验。

## Risks / Trade-offs

- 28 所仍非全量 → UI 标注覆盖比例诚实告知
- 推断的专业组 needs_review → 不进稳保，符合门禁
```

## openspec/changes/henan-homepage-reachability-fix/tasks.md

- Source: openspec/changes/henan-homepage-reachability-fix/tasks.md
- Lines: 1-15
- SHA256: 4deddc0541124efa157dd26f2793a3e051e2d146de9657bf13c6e04ee68f5c13

```md
## 1. 首页不推荐折叠交互

- [ ] 1.1 HomePage 渲染「不推荐」bucket 时默认折叠，提供展开按钮显示不可达院校及原因
- [ ] 1.2 可达档位（冲/稳/保/需人工复核）始终展示

## 2. 扩充 28 所可追溯院校

- [ ] 2.1 从 admission_history 提取 28 所院校，补全 universities.yaml（修 school_code 冲突）
- [ ] 2.2 为历史类院校补 program_groups（基于历史专业，needs_review）
- [ ] 2.3 补对应 enrollment_plans（needs_review，plan_count 合理推断）

## 3. UI 覆盖标注

- [ ] 3.1 首页 + 目标评估显示「已覆盖 N 所院校/全量待导入」
- [ ] 3.2 build + 测试验证
```

