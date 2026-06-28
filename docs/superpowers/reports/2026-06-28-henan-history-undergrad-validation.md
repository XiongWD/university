# 河南 2026 历史类普通本科批主链路验收记录

日期：2026-06-28

## 本轮验收范围

- 只核验 `河南 / 2026 / 历史类 / 普通本科批`
- 核验首页 `志愿推荐`
- 核验 `target-evaluation` 目标评估
- 核验后端 `henan` 新链路健康度、响应耗时、门禁状态
- 核验当前仓库测试是否可稳定运行

## 运行态核验

### 本地服务

- `GET http://127.0.0.1:8000/api/v1/health` 返回 `200`
- `GET http://127.0.0.1:5173/` 返回 `200`

### 推荐接口样例

请求条件：

- 分数 `480`
- 生源地 `河南`
- 科类 `历史类`
- 首选科目 `历史`
- 再选科目 `政治 + 地理`
- 外语语种 `日语`
- 数学 `64`
- 外语单科 `98`

结果：

- `data_ready = true`
- `pilot_ready = true`
- `production_ready = false`
- `coverage_status = "pilot_ready"`
- 耗时约 `7.5s`
- 档位数量：
  - `冲 = 29`
  - `稳 = 65`
  - `保 = 107`
  - `不推荐 = 1693`
  - `需人工复核 = 206`

说明：

- 当前推荐链路已不是空壳，能返回真实候选。
- 当前仍未达到 `production_ready`，原因是缺少 `河南 2026 官方全量专业目录结构化源`，现阶段主链路仍为 `gaokao.cn` 核验数据。

## 页面实测

### 首页志愿推荐

浏览器实测确认：

- 表单已固定到 `河南 / 2026 / 历史类 / 普通本科批`
- 成功提交后页面可展示：
  - `推荐数据未完全就绪`
  - `pilot_ready` 风险提示
  - `冲 / 稳 / 保 / 需人工复核`
  - `不推荐` 院校查看入口
- 首页已实际调用河南新推荐链路，不再是旧模拟链路

### 目标评估页

浏览器实测确认：

- 学校下拉存在，且为当前河南历史类普通本科批覆盖院校集合
- 页面会展示 `pilot_ready` / `production_ready` 状态
- 评估结果会直接给出 `不推荐`，并带具体原因
- 目标评估逻辑与首页资格链一致，不是单独的宽松判断

接口样例：

- `480分 / 日语 / 郑州大学` -> `不推荐`
- 原因包括：
  - `没有达到冲稳保条件的专业或专业组`
  - `再选科目要求包含思想政治`

## 数据覆盖现状

当前 `data/seed/henan/data_coverage_report.json`：

- `universities_2026 = 1096`
- `program_groups_2026 = 2100`
- `enrollment_plans_henan_2026 = 7863`

质量指标：

- `verified_program_groups_2026 = 2100`
- `verified_enrollment_plans_2026 = 7863`
- `nonzero_enrollment_plans_2026 = 7863`
- `scoped_unverified_groups_2026 = 0`
- `scoped_unverified_plans_2026 = 0`
- `excluded_special_groups_2026 = 255`
- `excluded_special_plans_2026 = 403`
- `verified_2025_history = 2690`
- `verified_2024_history = 3139`
- `verified_2025_major_group_history = 1778`
- `verified_2024_major_group_history = 2071`
- `single_subject_requirement_groups_2026 = 83`
- `public_foreign_language_groups_2026 = 31`
- `accommodation_plans_2026 = 1023`
- `official_catalog_source_ready = 0`

当前结论：

- 已达到 `pilot_ready`
- 未达到 `production_ready`
- 当前河南 `2026 / 历史类 / 普通本科批` 范围内专业组与计划已全部 `verified`
- 主要缺口不是普通本科主链路缺计划，而是缺少官方全量结构化目录源
- 另外有 `255` 个专业组、`403` 条计划被判定为专项/预科/艺术等非当前范围数据，已从主链路排除

## 来源可追溯性增强

本轮已把 `gaokao.cn` 的可重取证据回填进当前 seed：

- `source_api_endpoint`
- `source_params`
- `source_page`
- `source_response_checksum`

影响文件：

- `data/seed/henan/universities.yaml`
- `data/seed/henan/program_groups_2026.yaml`
- `data/seed/henan/enrollment_plans_2026.yaml`

效果：

- 每条普通本科历史类计划都不再只有泛化 `source_url`
- 现在可以直接拿 `school_id / special_group / year / local_batch_id / local_type_id` 回放请求
- 组级和学校级也保留了聚合后的响应校验指纹

## 测试验收

本机默认 `pytest -q` 会因为系统临时目录权限异常而失败，这不是代码逻辑失败，而是环境问题。

可用验收命令：

```powershell
pytest -q --basetemp .pytest-tmp-current -p no:cacheprovider
```

或：

```powershell
pytest -q --basetemp .pytest-tmp-smoke
```

本轮结果：

- `487 passed`

说明：

- 当前仓库代码在工作区临时目录下可稳定通过全量测试。
- 不建议把 `basetemp` 固定写入 pytest 默认配置；固定目录会触发下一次运行时的目录清理权限问题。

## 仍未完成的关键项

以下项仍阻止“可放心生产使用”：

1. `official_catalog_source_ready = 0`
   - 仍缺 `河南 2026 官方全量专业目录结构化源`
   - 因此只能保持 `pilot_ready`

2. 专业组核验仍非绝对全量
   - 当前非常接近全量，但不是官方目录闭环

3. 页面交互仍有体验欠缺
   - `target-evaluation` 学校选择为长列表，检索效率一般
   - 这不影响当前功能正确性，但影响实际填报效率

4. 仍需继续补强与复核的字段
   - 外语语种限制的剩余空白
   - 单科门槛剩余空白
   - 住宿费的省外扩覆盖
   - 需要更多可追溯来源将 `needs_review` 继续提升为 `verified`

## 本轮结论

当前系统已经具备：

- 河南 2026 历史类普通本科批主链路
- 可运行的首页推荐
- 可运行的目标评估
- 位次自动换算
- 单科 / 语种 / 选科限制生效
- `pilot_ready` 级别的数据门禁

当前系统还不能宣称：

- 官方全量
- `production_ready`
- 可完全替代人工志愿审核
