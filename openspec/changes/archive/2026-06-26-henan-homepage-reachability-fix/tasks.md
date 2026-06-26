## 1. 首页不推荐折叠交互

- [x] 1.1 HomePage 渲染「不推荐」bucket 时默认折叠，提供展开按钮显示不可达院校及原因
- [x] 1.2 可达档位（冲/稳/保/需人工复核）始终展示

## 2. 扩充 28 所可追溯院校

- [x] 2.1 从 admission_history 提取 28 所院校，补全 universities.yaml（修 school_code 冲突）
- [x] 2.2 为历史类院校补 program_groups（基于历史专业，needs_review）
- [x] 2.3 补对应 enrollment_plans（needs_review，plan_count 合理推断）

## 3. UI 覆盖标注

- [x] 3.1 首页 + 目标评估显示「已覆盖 N 所院校/全量待导入」
- [x] 3.2 build + 测试验证
