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
