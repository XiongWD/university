# Spec Delta: narrative-policy

本 delta 为新建 capability `narrative-policy` 定义 requirements。规约系统在用户可见主流程中不得呈现的两类叙事，以及 deprecated 端点的可见性约束。对应 `docs/superpowers/specs/2026-06-26-volunteer-recommendation-refocus-design.md` §2/§5/§6.1。

## ADDED Requirements

### Requirement: 禁止人生固化叙事

系统在用户可见主流程中 SHALL NOT 把"人生路径""人生轨迹""人生赛道""命运路线"等成长固化叙事作为功能名称、导航项或推荐结果呈现。

用户可见主流程包括：前端源码（`web-ui/src/`）、README 主说明、API 端点描述与 docstring、面向用户的响应字符串。归档文档、`openspec/` 规约、标注 `DEPRECATED` 的注释豁免。

#### Scenario: 前端导航不含人生路径入口

WHEN 扫描前端导航定义（`web-ui/src/App.tsx` 的 `navItems`）
THEN 导航项的 label 与 path 中 MUST NOT 出现 "人生路径"/"人生轨迹"/"赛道"/"命运"
AND MUST 存在面向志愿推荐的主入口

#### Scenario: 主页标题不含人生固化叙事

WHEN 渲染主页 hero 区域（`HomePage.tsx`）
THEN 标题与副标题文本 MUST NOT 包含 "填报志愿，看见孩子的人生轨迹"
AND MUST NOT 包含 "人生路径"/"人生轨迹"/"赛道"/"命运"

#### Scenario: README 不以人生固化叙事定位产品

WHEN 读取 `README.md` 首部标题与首段
THEN MUST NOT 出现 "人生经济模型模拟器" 作为产品定位
AND MUST NOT 宣传 "三条人生路径（稳健/均衡/进取）" 作为核心功能

### Requirement: 禁止交易化叙事

系统在用户可见主流程中 SHALL NOT 把"回本""回本周期""ROI""投资回报""投资回报率""15年净收益"等把上大学描述为交易的叙事作为功能名称、卡片或推荐结果呈现。

费用、就业、薪资区间仍可作为"约束与参考"呈现，但不得计算或展示投资回本指标。

#### Scenario: 推荐卡片不含回本指标

WHEN 渲染志愿推荐结果卡片（`TrajectoryCard.tsx`）
THEN MUST NOT 存在 "回本周期" 卡片/列
AND MUST NOT 渲染 `lifetime_15y_net`（15年净收益）字段

#### Scenario: 主流程不生成回本数据

WHEN 执行志愿推荐主链路（`/life-trajectory` 主流程组装）
THEN 系统 MUST NOT 调用 `_build_payback()` 生成 `years_to_break_even`/`lifetime_15y_net`
AND `TrajectoryItem.payback` 在主链路 MUST NOT 被填充为回本分析结果

#### Scenario: 静态扫描禁止交易化词汇

WHEN 对用户可见主流程目录（`web-ui/src/`、`README.md`、`app/` 的面向用户字符串/docstring）执行静态扫描
THEN MUST NOT 出现 "回本"/"ROI"/"投资回报"/"15年净收益" 作为功能名或结果描述
EXCEPT 标注 `DEPRECATED` 的同行注释、归档文档、本设计文档自身

### Requirement: 三路径优化器移出推荐主链路

三路径优化器（稳健/均衡/进取）SHALL NOT 作为推荐主链路的输出生成。相关引擎代码可保留为 deprecated 以维持回归兼容，但 MUST NOT 在主推荐流程中被调用并呈现给用户。

#### Scenario: 推荐主链路不调用三路径优化

WHEN 组装志愿推荐主流程结果
THEN 主链路 MUST NOT 调用 `app/engine/life_path.py` 的 `build_life_paths()` 生成面向用户的路径建议
AND 三路径优化器模块 MUST 标注为 deprecated

### Requirement: deprecated 端点的可见性约束

`POST /api/v1/volunteer/life-paths` 与 `POST /api/v1/volunteer/life-trajectory` SHALL 保留可运行以维持回归兼容，但 MUST 标注为 deprecated，且 MUST NOT 出现在 UI 导航、README 主说明、主导航中。

#### Scenario: deprecated 端点仍可运行

WHEN 调用 `POST /api/v1/volunteer/life-trajectory` 与 `POST /api/v1/volunteer/life-paths`
THEN 端点 MUST 返回成功响应（HTTP 2xx）以维持回归
AND 端点 docstring/notes MUST 标注 deprecated

#### Scenario: deprecated 端点不在主导航出现

WHEN 读取前端导航项与 README 主说明
THEN `/life-paths`、`/life-trajectory` 端点 MUST NOT 作为导航项或推荐功能出现
AND `LifePathsPage` MUST NOT 在主导航入口暴露

### Requirement: 回归可用性

去叙事后，传统冲稳保接口、位次工具、大学费用模块 SHALL 保持可用。

#### Scenario: 传统冲稳保与位次工具仍可用

WHEN 去叙事变更完成后调用 `POST /api/v1/volunteer/recommend`、`GET /api/v1/provincial/score-rank/rank`、大学费用相关端点
THEN 这些端点 MUST 返回成功响应
AND 其核心返回结构 MUST 不因去叙事变更而破坏
