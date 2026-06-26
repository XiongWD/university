# deprecate-life-path-narrative Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从主流程、UI、README 中清除"人生路径/人生轨迹/赛道"人生固化叙事与"回本/ROI/15年净收益"交易化叙事，使产品口径符合"高考志愿专业推荐系统"定位。

**Architecture:** 从生成侧切断回本计算（`_item_from_suggestion` 不再调用 `_build_payback`），三路径优化器与 `/life-paths`、`/life-trajectory` 端点软弃用（保留源码+切断主流程调用+加 DEPRECATED 注释），前端移除人生路径导航与回本卡片，README 重写。禁止词口径落地为可执行的静态扫描测试。

**Tech Stack:** Python/FastAPI（后端）、React18+TypeScript+Vite+Tailwind（前端）、pytest（测试）、OpenSpec（规约）

## Global Constraints

- **软弃用优先**：`life_path.py`、`trajectory._build_payback()`、`/life-paths`、`/life-trajectory`、`LifePathsPage` 源码保留，仅切断主流程调用与用户可见入口，加 `# DEPRECATED:` 注释。禁止物理删除。
- **回本从生成侧切断**：`_item_from_suggestion()` 不再调用 `_build_payback()`，`TrajectoryItem.payback` 在主链路为 `None`。`_build_payback()` 签名保留但函数体改为直接返回 `None`，不得继续保留任何交易化判断字符串。不得只在渲染层隐藏。
- **HomePage 数据源不变**：保留调用 `/life-trajectory`（仅去回本），不切 `/recommend`、不复活死代码组件。新 advisory UI 属拆分项 B。
- **扫描粒度**：禁止词扫描只覆盖用户可见文案（`web-ui/src/`、`README.md`、API 模块/端点 docstring、HTTP 响应字符串）。`app/` 内部算法注释不扫。`# DEPRECATED` / `// DEPRECATED` 同行豁免（仅针对注释，docstring 必须直接中性化）。计划执行后 `web-ui/src/` 和 `README.md` 全文扫描应通过，不能依赖“未路由文件”逃避扫描。
- **docstring 中性化（非 DEPRECATED 豁免）**：面向用户的 API docstring 含禁止词时，直接改文案，不能靠 `# DEPRECATED` 豁免。
- **不动的范围**：不改推荐算法逻辑、不动 `eligibility.py`/`admission_prediction.py`/`major_fit.py`、不建 advisory 接口（属拆分项 B）。
- **禁止词清单**：`人生路径`、`人生轨迹`、`回本`、`ROI`、`投资回报`、`15年净收益`、`命运`、`赛道`（+ `人生经济模型模拟器`）。
- **回归保障**：`/recommend`、`/score-rank`、大学费用在去叙事后仍可用。

---

## File Structure

**后端（Python）— Modify only**
- `app/engine/trajectory.py` — `_item_from_suggestion` 切断回本调用；`_build_payback` 加 DEPRECATED；`build_life_trajectory` docstring 中性化
- `app/engine/life_path.py` — 模块 + 关键函数加 DEPRECATED 注释
- `app/models/life_trajectory.py` — 模块 docstring + `PaybackAnalysis`/`LifeTrajectory` docstring 加 DEPRECATED 标注
- `app/models/life_path.py` — 模块 + `LifePath` docstring 加 DEPRECATED 标注
- `app/api/routers/volunteer.py` — 模块 docstring 中性化；`life_paths`/`life_trajectory` handler docstring 加 deprecated + notes；`:166` 取数注释中性化

**前端（TS/React）— Modify only**
- `web-ui/src/App.tsx` — 移除"人生路径"导航 + 去副标题；移除 `/life-paths` 路由（导航层面）
- `web-ui/src/pages/HomePage.tsx` — 主标题改"高考志愿专业推荐"；副标题去"回本周期"
- `web-ui/src/components/TrajectoryCard.tsx` — 移除回本卡片列 + 回本判断行；改两列
- `web-ui/src/pages/LifePathsPage.tsx` — 源码保留但中性化为 deprecated 内部页；文件内用户文案也必须通过禁止词扫描
- `web-ui/src/api/types.ts` — 注释中性化
- `web-ui/src/api/client.ts` — 注释中性化

**文档 — Modify only**
- `README.md` — 全文用户可见叙事清理，不限于标题 + 首段

**测试 — Create + Modify**
- `tests/test_narrative_policy.py` — Create：禁止词静态扫描
- `tests/test_*life_trajectory*`（如存在）— Modify：断言 payback 不生成

---

### Task 1: 后端回本从生成侧切断

**Files:**
- Modify: `app/engine/trajectory.py:107-167,182-185`

**Interfaces:**
- Produces: `TrajectoryItem.payback` 在主链路恒为 `None`；`_build_payback` 签名保留但函数体禁用并直接返回 `None`

- [ ] **Step 1: 切断 `_item_from_suggestion` 的回本调用**

把 `app/engine/trajectory.py:147-149`（`_item_from_suggestion` 内）：

```python
    cost = _build_cost(sug.school, unis, cities, years)
    career = _build_career(sug.major, majors, careers)
    payback = _build_payback(cost, career)
```

改为：

```python
    cost = _build_cost(sug.school, unis, cities, years)
    career = _build_career(sug.major, majors, careers)
    # DEPRECATED: 回本(payback)叙事已废弃，见 volunteer-recommendation-refocus；主链路不再生成
    payback = None
```

- [ ] **Step 2: 禁用 `_build_payback` 函数体并加 DEPRECATED 注释**

把 `app/engine/trajectory.py:107-135` 的 `_build_payback` 函数替换为签名保留、直接返回 `None` 的 deprecated 版本。不得保留 `"回本极快"`、`"回本较快"`、`"回本正常"`、`"回本较慢"`、`lifetime_15y_net` 等交易化判断字符串：

```python
# DEPRECATED: 教育投入产出/收益叙事已废弃，见 volunteer-recommendation-refocus；主链路不再调用，仅保留签名以维持兼容
def _build_payback(cost: CostSummary | None, career: CareerProspect | None) -> PaybackAnalysis | None:
    return None
```

- [ ] **Step 3: `build_life_trajectory` docstring 中性化**

把 `app/engine/trajectory.py:182-186`：

```python
    """构建完整人生轨迹。

    1. 先生成冲稳保志愿表（复用 volunteer 引擎）
    2. 每条志愿附加费用/就业/回本
    """
```

改为：

```python
    """构建志愿推荐结果：冲稳保志愿 + 每校费用 + 就业参考。

    1. 先生成冲稳保志愿表（复用 volunteer 引擎）
    2. 每条志愿附加费用与就业参考
    """
```

- [ ] **Step 4: 提交**

```bash
git add app/engine/trajectory.py
git commit -m "refactor(trajectory): 从生成侧切断回本计算，主链路不再产出 payback

DEPRECATED _build_payback；_item_from_suggestion 不再调用，TrajectoryItem.payback 恒 None。
见 volunteer-recommendation-refocus 设计。"
```

---

### Task 2: 后端模型 docstring 标注 DEPRECATED（内部注释，不扫）

**Files:**
- Modify: `app/models/life_trajectory.py:1-5,37-44,66-67`
- Modify: `app/models/life_path.py:1,15-21,107-128`（模块 docstring + PathType/LifePath）

**Interfaces:** 无（仅注释，字段保留以维持 deprecated 端点序列化兼容）

- [ ] **Step 1: `life_trajectory.py` 模块 docstring 加 DEPRECATED 标注**

把 `app/models/life_trajectory.py:1-5`（模块顶部 docstring）整段前缀加一行 DEPRECATED 说明。即把：

```python
"""人生轨迹模拟：把志愿推荐与大学费用、就业收入、回本周期串联。

核心问题：读这所大学（某专业）4年要花多少？毕业后能赚多少？多久回本？
家长和孩子在筛选志愿的那一刻，就能看到「投入产出」全貌。
"""
```

改为（在首行前加 `# DEPRECATED:` 块注释 + docstring 中性化；docstring 会被 narrative-policy 扫描，不能含禁止词）：

```python
# DEPRECATED: 旧版志愿集成模型，见 volunteer-recommendation-refocus；本模型保留字段以维持 deprecated 端点序列化，主链路不再填充 payback
"""志愿推荐集成模型：志愿 + 费用 + 就业参考（历史名 life_trajectory）。

本模型承载冲稳保志愿的附加信息。历史兼容字段保留为遗留序列化用途，主链路不再生成。
"""
```

- [ ] **Step 2: `PaybackAnalysis` docstring 加 DEPRECATED 标注**

在 `app/models/life_trajectory.py:37`（`class PaybackAnalysis` 上方）插入：

```python
# DEPRECATED: 旧版教育收益分析模型，主链路不再生成，仅遗留端点序列化保留
class PaybackAnalysis(BaseModel):
```

- [ ] **Step 3: `LifeTrajectory` 顶层 docstring 中性化**

`app/models/life_trajectory.py:66-67`（`class LifeTrajectory` docstring "完整人生轨迹"）改为：

```python
class LifeTrajectory(BaseModel):
    """志愿推荐结果：志愿表 + 每校费用/就业参考。"""
```

- [ ] **Step 4: `life_path.py` 模块 docstring 加 DEPRECATED 标注**

读取 `app/models/life_path.py:1-3`，在模块顶部 docstring 前加 `# DEPRECATED:` 行（指向 volunteer-recommendation-refocus）。具体文本：在第一行 import/docstring 前插入：

```python
# DEPRECATED: 旧版多方案优化器已废弃，见 volunteer-recommendation-refocus；模型保留以维持 deprecated 端点序列化
```

- [ ] **Step 5: 提交**

```bash
git add app/models/life_trajectory.py app/models/life_path.py
git commit -m "refactor(models): 标注 life_trajectory/life_path 回本与路径叙事为 DEPRECATED

字段保留以维持 deprecated 端点序列化兼容，主链路不再填充。"
```

---

### Task 3: 后端 life_path.py 引擎 DEPRECATED 注释

**Files:**
- Modify: `app/engine/life_path.py:1,20-33,65,119,149`

**Interfaces:** 无（仅注释，函数保留以维持 deprecated 端点可运行）

- [ ] **Step 1: 读取确认 life_path.py 主推荐流程是否调用**

读取 `app/engine/life_path.py` 与 `app/api/routers/volunteer.py`，确认 `build_life_paths` 仅被 `/life-paths` 端点（:301 区）调用，主推荐流程（HomePage→`/life-trajectory`→`build_life_trajectory`）不调用它。这是回归断言的依据。

- [ ] **Step 2: 模块顶部 + 关键函数加 DEPRECATED 注释**

在 `app/engine/life_path.py` 模块顶部 docstring 前插入：

```python
# DEPRECATED: 旧版多方案优化器已废弃，见 volunteer-recommendation-refocus
# 仅 /life-paths deprecated 端点调用，主推荐流程不再使用
```

在 `def compute_path_score`（:65）、`def select_best_for_path`（:119）、`def build_life_paths`（:149）上方各加一行：

```python
# DEPRECATED: 旧版多方案优化器，见 volunteer-recommendation-refocus；仅 deprecated /life-paths 调用
```

- [ ] **Step 3: 提交**

```bash
git add app/engine/life_path.py
git commit -m "refactor(life_path): 标注三路径优化器为 DEPRECATED

主推荐流程不调用；仅 /life-paths deprecated 端点保留。"
```

---

### Task 4: 后端 deprecated 端点可见性（FastAPI metadata + docstring + notes）

**Files:**
- Modify: `app/api/routers/volunteer.py:1-6,166,187-193,301-303`（模块 docstring、取数注释、life_trajectory handler、life_paths handler）

**Interfaces:** 端点返回结构不变；FastAPI 标记 `deprecated=True`，OpenAPI 中显示为 deprecated；docstring/notes 文案中性化

- [ ] **Step 1: 模块 docstring 中性化**

把 `app/api/routers/volunteer.py:1-6`：

```python
"""志愿填报引擎 API 端点。

POST /volunteer/recommend：输入考生画像 → 返回冲稳保志愿表（传统）。
POST /volunteer/life-paths：人生路径（V2.2 三路径+资格链+预算）。
GET /volunteer/admissions：录取数据查询。
"""
```

改为：

```python
"""志愿填报引擎 API 端点。

POST /volunteer/recommend：输入考生画像 → 返回冲稳保志愿表（传统）。
POST /volunteer/life-paths：(deprecated) 旧版多方案建议，保留以维持兼容。
POST /volunteer/life-trajectory：(deprecated) 志愿推荐 + 费用 + 就业参考。
GET /volunteer/admissions：录取数据查询。
"""
```

- [ ] **Step 1.5: 为 deprecated 端点添加 FastAPI metadata**

把两个遗留端点装饰器改为显式 deprecated：

```python
@router.post("/life-trajectory", deprecated=True)
...
@router.post("/life-paths", deprecated=True)
...
```

说明：本阶段仍保留 OpenAPI 可见性以便兼容调用方识别迁移状态；主导航与 README 不再暴露。若后续拆分项 B 完成 advisory 主接口，可再评估 `include_in_schema=False`。

- [ ] **Step 2: `:166` 取数注释中性化**

把 `app/api/routers/volunteer.py:166`：

```python
# ---------- 取数辅助（人生轨迹用）----------
```

改为：

```python
# ---------- 取数辅助（志愿推荐集成用）----------
```

- [ ] **Step 3: `life_trajectory` handler docstring 中性化 + deprecated 标记**

把 `app/api/routers/volunteer.py:187-193`（`life_trajectory` 函数及其 docstring）：

```python
@router.post("/life-trajectory")
def life_trajectory(req: RecommendRequest, session: Session = Depends(get_session_dep)):
    """人生轨迹：志愿推荐 + 每校费用 + 就业前景 + 回本分析。

    家长和孩子筛选志愿时一站式看到「读这所大学要花多少、毕业后赚多少、多久回本」。
    复用 volunteer 引擎生成冲稳保，再附加 University(费用)+Major/Career(就业)数据。
    """
```

改为：

```python
@router.post("/life-trajectory")
def life_trajectory(req: RecommendRequest, session: Session = Depends(get_session_dep)):
    """(deprecated) 志愿推荐 + 每校费用 + 就业参考。

    一站式看到「读这所大学要花多少、毕业起薪区间」。
    复用 volunteer 引擎生成冲稳保，再附加 University(费用)+Major/Career(就业)数据。
    该端点已 deprecated，保留以维持兼容；新主流程将由 advisory 接口提供。
    """
```

- [ ] **Step 4: `life_paths` handler docstring 加 deprecated 标记**

读取 `app/api/routers/volunteer.py:301-303`（`life_paths` 函数 docstring 开头），将其改为不含禁止词的中性描述，例如：

```python
"""(deprecated) 旧版多方案建议：资格链、录取参考、市场参考与预算信息的组合输出。

该端点保留以维持兼容；新主流程将由 advisory 接口提供。
"""
```

保持返回结构不变。

- [ ] **Step 5: 响应 notes 追加 deprecated 提示**

在 `life_trajectory` 与 `life_paths` 的返回组装处，向结果的 `notes`/`source_note` 字段（ whichever 存在且为 list/str）追加一条 deprecated 提示，如 `"该接口已 deprecated，保留以维持兼容。"`。需先读取返回结构确认字段名（`LifeTrajectory.source_note` 为 str；`LifePathResult` 查 `notes`）。**不得破坏返回结构或类型。**

- [ ] **Step 6: 提交**

```bash
git add app/api/routers/volunteer.py
git commit -m "refactor(volunteer-api): life-paths/life-trajectory 端点降级为 deprecated

模块与端点 docstring 中性化，去人生路径/回本叙事；notes 追加 deprecated 提示。
端点保留可运行以维持回归。"
```

---

### Task 5: 前端 App.tsx 去人生路径导航 + 副标题，并中性化遗留页面

**Files:**
- Modify: `web-ui/src/App.tsx:2,4,9-15,27-28,55-60`
- Modify: `web-ui/src/pages/LifePathsPage.tsx`

**Interfaces:** 移除 `Compass`/`LifePathsPage` 导入；移除 `/life-paths` 导航项与路由；`LifePathsPage` 源码保留但用户文案中性化

- [ ] **Step 1: 移除导航项 + 导入**

把 `web-ui/src/App.tsx:2`（`import { GraduationCap, Calculator, LineChart, Wallet, Compass } from "lucide-react";`）改为（去 `Compass`）：

```tsx
import { GraduationCap, Calculator, LineChart, Wallet } from "lucide-react";
```

把 `:4`（`import LifePathsPage from "./pages/LifePathsPage";`）整行删除。

把 `:9-15`（`navItems` 数组）改为（移除"人生路径"项）：

```tsx
const navItems = [
  { to: "/", label: "专业推荐", icon: GraduationCap, end: true },
  { to: "/cost", label: "大学费用", icon: Wallet },
  { to: "/rank", label: "位次工具", icon: LineChart },
  { to: "/control-line", label: "省控线", icon: Calculator },
];
```

- [ ] **Step 2: 移除 `/life-paths` 路由**

把 `:56`（`<Route path="/life-paths" element={<LifePathsPage />} />`）整行删除。

- [ ] **Step 3: 去副标题"人生经济模型模拟器"**

把 `:27-28`：

```tsx
            <span className="font-bold text-lg tracking-tight">志愿推</span>
            <span className="text-xs text-white/50 hidden sm:inline">人生经济模型模拟器</span>
```

改为：

```tsx
            <span className="font-bold text-lg tracking-tight">志愿推</span>
            <span className="text-xs text-white/50 hidden sm:inline">高考志愿专业推荐</span>
```

- [ ] **Step 4: 中性化 `LifePathsPage.tsx` 遗留页面文案**

虽然 `LifePathsPage` 不再路由暴露，但 `web-ui/src/` 全文会被 narrative-policy 扫描。必须把文件内用户文案改成中性 deprecated 表述，不能保留禁止词。至少处理：

- 页面标题“三条人生路径” → “旧版多方案建议（已弃用）”
- 说明“资格链 → 录取预测 → 就业市场 → 家庭预算 → 稳健/均衡/进取” → “资格、录取、就业参考与预算信息的旧版组合输出”
- 按钮“生成三条人生路径” → “生成旧版多方案建议”
- 展示标题中 `path.path_type` 后接“路径”的文案 → 改为“方案”
- 注释中出现的禁止词也要中性化或加 `// DEPRECATED:` 同行豁免

保留组件源码和 API 调用，作为 deprecated 内部页，但执行后 `rg "人生路径|人生轨迹|回本|ROI|投资回报|15年净收益|命运|赛道|人生经济模型模拟器" web-ui/src` 应无非 deprecated 命中。

- [ ] **Step 5: 类型检查**

Run: `cd web-ui && npx tsc --noEmit`
Expected: 无 TS 错误（确认 `Compass`/`LifePathsPage` 未残留引用）

- [ ] **Step 6: 提交**

```bash
git add web-ui/src/App.tsx web-ui/src/pages/LifePathsPage.tsx
git commit -m "refactor(web-ui): 移除旧版方案导航与路由，副标题改志愿专业推荐

去 Compass/LifePathsPage 路由引用；主导航不再暴露 /life-paths；遗留页文案中性化。"
```

---

### Task 6: 前端 HomePage 标题/副标题中性化

**Files:**
- Modify: `web-ui/src/pages/HomePage.tsx:42,46`

**Interfaces:** 无（仅文案）

- [ ] **Step 1: 主标题改"高考志愿专业推荐"**

把 `web-ui/src/pages/HomePage.tsx:42`：

```tsx
              填报志愿，看见孩子的人生轨迹
```

改为：

```tsx
              高考志愿专业推荐
```

- [ ] **Step 2: 副标题去"回本周期"**

把 `:46`：

```tsx
            输入分数 → 冲稳保志愿 → 大学花费 · 毕业收入 · 回本周期，一目了然
```

改为：

```tsx
            输入分数 → 冲稳保志愿 → 大学花费 · 毕业起薪，一目了然
```

- [ ] **Step 3: 类型检查**

Run: `cd web-ui && npx tsc --noEmit`
Expected: 无错误

- [ ] **Step 4: 提交**

```bash
git add web-ui/src/pages/HomePage.tsx
git commit -m "refactor(web-ui): HomePage 主标题改志愿专业推荐，去回本周期文案"
```

---

### Task 7: 前端 TrajectoryCard 移除回本卡片

**Files:**
- Modify: `web-ui/src/components/TrajectoryCard.tsx:1-3,18,106-157,159-165`

**Interfaces:** 移除 `TrendingUp`/`Clock` 导入与 `payback` 解构；卡片从三列改两列

- [ ] **Step 1: 移除回本相关导入**

把 `web-ui/src/components/TrajectoryCard.tsx:1-3`：

```tsx
import {
  Wallet, Briefcase, TrendingUp, Clock,
} from "lucide-react";
```

改为：

```tsx
import { Wallet, Briefcase } from "lucide-react";
```

- [ ] **Step 2: 解构去 payback**

把 `:18`（`const { cost, career, payback } = item;`）改为：

```tsx
  const { cost, career } = item;
```

- [ ] **Step 3: 三列改两列 + 移除回本卡片**

把 `:106-157`（从 `{/* 三栏：费用 / 就业 / 回本 */}` 到回本卡片 `</div>` 结束，含整个 `grid grid-cols-3` 块）整段替换为两列：

```tsx
      {/* 两栏：费用 / 就业 */}
      <div className="grid grid-cols-2 gap-2 mt-3">
        {/* 费用 */}
        <div className="bg-pink-500/10 rounded-xl p-2.5 border border-pink-400/20">
          <div className="flex items-center gap-1 text-[10px] text-pink-300 mb-1">
            <Wallet className="w-3 h-3" /> 大学总花费
          </div>
          {cost ? (
            <>
              <div className="text-base font-bold text-pink-200">¥{wan(cost.grand_total)}</div>
              <div className="text-[9px] text-white/40 mt-0.5">
                学{wan(cost.tuition_total)}·住{wan(cost.accommodation_total)}·活{wan(cost.living_total)}
              </div>
            </>
          ) : (
            <div className="text-xs text-white/30 py-1">无数据</div>
          )}
        </div>

        {/* 就业 */}
        <div className="bg-indigo-500/10 rounded-xl p-2.5 border border-indigo-400/20">
          <div className="flex items-center gap-1 text-[10px] text-indigo-300 mb-1">
            <Briefcase className="w-3 h-3" /> 毕业起薪
          </div>
          {career ? (
            <>
              <div className="text-base font-bold text-indigo-200">¥{fmt(career.entry_salary_mid)}</div>
              <div className="text-[9px] text-white/40 mt-0.5">
                {fmt(career.entry_salary_low)}-{fmt(career.entry_salary_high)}/月
                {career.mid_salary_5y && `·5年${fmt(career.mid_salary_5y)}`}
              </div>
            </>
          ) : (
            <div className="text-xs text-white/30 py-1">无数据</div>
          )}
        </div>
      </div>
```

- [ ] **Step 4: 移除回本判断行**

把 `:159-165`（整个 `{/* 回本判断 */}` 块）整段删除。

- [ ] **Step 5: 类型检查**

Run: `cd web-ui && npx tsc --noEmit`
Expected: 无错误（确认 `TrendingUp`/`Clock`/`payback` 无残留引用）

- [ ] **Step 6: 提交**

```bash
git add web-ui/src/components/TrajectoryCard.tsx
git commit -m "refactor(web-ui): TrajectoryCard 移除回本卡片，改两列(费用+就业)

去 TrendingUp/Clock/payback 引用。"
```

---

### Task 8: 前端 api types.ts / client.ts 注释中性化

**Files:**
- Modify: `web-ui/src/api/types.ts:119,183`
- Modify: `web-ui/src/api/client.ts:106`

**Interfaces:** 无（仅注释）

- [ ] **Step 1: types.ts 注释中性化**

把 `web-ui/src/api/types.ts:119`：

```ts
// ===== 人生轨迹（志愿推荐+费用+就业+回本集成）=====
```

改为：

```ts
// ===== 志愿推荐集成（志愿+费用+就业参考）=====
```

把 `:183`：

```ts
// ===== V2.2 人生路径 =====
```

改为：

```ts
// ===== 志愿推荐请求（遗留）=====
```

- [ ] **Step 2: client.ts 注释中性化**

把 `web-ui/src/api/client.ts:106`：

```ts
// POST /volunteer/life-paths（V2.2 人生路径）
```

改为：

```ts
// POST /volunteer/life-paths（deprecated）
```

- [ ] **Step 3: 类型检查**

Run: `cd web-ui && npx tsc --noEmit`
Expected: 无错误

- [ ] **Step 4: 提交**

```bash
git add web-ui/src/api/types.ts web-ui/src/api/client.ts
git commit -m "refactor(web-ui): api types/client 注释去人生路径/回本叙事"
```

---

### Task 9: README 全文重写与禁止词清理

**Files:**
- Modify: `README.md`

**Interfaces:** 无

- [ ] **Step 1: 读取 README 并定位全部禁止词**

先运行：

```bash
rg -n "人生路径|人生轨迹|回本|ROI|投资回报|15年净收益|命运|赛道|人生经济模型模拟器|教育回报" README.md
```

记录全部命中。README 会被全文扫描，不能只改首部。

- [ ] **Step 2: 标题改"高考志愿专业推荐系统"**

把 `README.md:1`：

```markdown
# 人生经济模型模拟器 — 教育经济决策系统（V2.2）
```

改为：

```markdown
# 高考志愿专业推荐系统
```

- [ ] **Step 3: 首段重写**

把 `:3`（"在录取资格、专业适配、家庭预算约束下，优化风险调整后的长期就业与教育回报。"）改为：

```markdown
基于分数、选科、外语、数学、一分一段与家庭预算，生成可解释的专业方向与冲稳保院校建议。
```

- [ ] **Step 4: 核心功能行去旧版叙事**

把 `:5`（含"三条人生路径（稳健/均衡/进取）"的核心功能行）改为面向志愿推荐的描述（去路径/回本叙事），如：

```markdown
提供专业方向建议、冲稳保院校清单、大学费用估算与位次查询。
```

- [ ] **Step 5: 全文中性化剩余命中**

对 Step 1 的全部命中逐项处理：

- `/life-paths` 页面和 API 说明：改为 deprecated 旧版多方案建议，或从 README 主流程中删除。
- `/life-trajectory` 页面和 API 说明：改为 deprecated 志愿推荐集成，不能出现交易化词。
- V2.2 架构中的相关阶段：改为“旧版多方案优化器（deprecated）”或移出主说明。
- “教育回报”等交易化表达：改为“费用压力 / 就业参考 / 专业适配”。

处理后运行同一 `rg` 命令，README 不应再有命中。

- [ ] **Step 6: 提交**

```bash
git add README.md
git commit -m "docs: README 重写为高考志愿专业推荐系统定位

去人生经济模型模拟器/三路径/教育回报叙事。"
```

---

### Task 10: 新增禁止词静态扫描测试

**Files:**
- Create: `tests/test_narrative_policy.py`

**Interfaces:** 产出 `tests/test_narrative_policy.py`，覆盖 narrative-policy delta spec 的静态扫描场景

**TDD**: 先写测试（此时因前面任务已改文案，预期 PASS；若仍有违规，测试会指出具体位置供修复）

- [ ] **Step 1: 写测试文件**

创建 `tests/test_narrative_policy.py`：

```python
"""narrative-policy 静态扫描测试。

校验用户可见主流程不出现禁止叙事词：
- 人生固化叙事：人生路径/人生轨迹/赛道/命运/人生经济模型模拟器
- 交易化叙事：回本/ROI/投资回报/15年净收益

扫描范围（用户可见文案）：
- web-ui/src/ 全部 .ts/.tsx
- README.md
- app/api/ 下 Python 文件的 docstring 与字符串字面量（用户可见 API 描述）

豁免：
- app/ 内部算法注释（# 开头的纯注释行，非 docstring）不扫
- 同行含 DEPRECATED 关键字的注释豁免
- 归档目录、openspec/ 规约、设计文档本身不在扫描路径
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# 禁止词（作为功能名/结果呈现时禁止）
FORBIDDEN = [
    "人生路径",
    "人生轨迹",
    "赛道",
    "命运",
    "人生经济模型模拟器",
    "回本",
    "ROI",
    "投资回报",
    "15年净收益",
]

# 扫描的前端源码目录
FRONTEND_SRC = REPO_ROOT / "web-ui" / "src"

# 扫描的后端 API 目录（只扫 docstring 与字符串字面量里的用户可见 API 文案）
BACKEND_API = REPO_ROOT / "app" / "api"

# 扫描的文档
README = REPO_ROOT / "README.md"

# 豁免：路径包含这些片段的不扫
PATH_EXEMPT_FRAGMENTS = (
    "openspec",
    "docs/superpowers/specs",  # 设计文档自身
    "docs/superpowers/plans",
    ".comet",
    "node_modules",
    "dist",
    "archive",
)


def _is_path_exempt(p: Path) -> bool:
    s = str(p).replace("\\", "/")
    return any(frag in s for frag in PATH_EXEMPT_FRAGMENTS)


def _forbidden_in_line(line: str) -> list[str]:
    hits = []
    for w in FORBIDDEN:
        if w in line:
            hits.append(w)
    return hits


def _scan_frontend(root: Path) -> list[tuple[Path, int, str, list[str]]]:
    """前端 src：扫全部行（注释与文案都属用户可见）。DEPRECATED 同行豁免。"""
    out = []
    if not root.exists():
        return out
    for f in root.rglob("*"):
        if not f.is_file() or f.suffix not in {".ts", ".tsx"}:
            continue
        if _is_path_exempt(f):
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if "DEPRECATED" in line:
                continue
            hits = _forbidden_in_line(line)
            if hits:
                out.append((f, i, line.strip(), hits))
    return out


def _scan_readme(path: Path) -> list[tuple[Path, int, str, list[str]]]:
    out = []
    if not path.exists():
        return out
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if "DEPRECATED" in line:
            continue
        hits = _forbidden_in_line(line)
        if hits:
            out.append((path, i, line.strip(), hits))
    return out


def _extract_python_visible_lines(text: str) -> list[tuple[int, str]]:
    """从 Python 文件抽取用户可见行：docstring 与字符串字面量。

    纯注释行（# 开头，去掉空格后）不算用户可见，跳过。
    """
    lines = text.splitlines()
    visible: list[tuple[int, str]] = []
    in_docstring = False
    for i, raw in enumerate(lines, 1):
        stripped = raw.strip()
        # docstring 边界（三引号）
        triple_count = raw.count('"""')
        if in_docstring:
            visible.append((i, raw))
            if triple_count % 2 == 1:
                in_docstring = False
            continue
        if triple_count == 1:
            visible.append((i, raw))
            in_docstring = True
            continue
        if triple_count >= 2:
            visible.append((i, raw))
            continue
        # 纯注释行跳过（非 docstring 内）
        if stripped.startswith("#"):
            continue
        # 字符串字面量行视为可见
        if '"""' not in raw and ("\"" in raw or "'" in raw):
            visible.append((i, raw))
    return visible


def _scan_backend_api(root: Path) -> list[tuple[Path, int, str, list[str]]]:
    out = []
    if not root.exists():
        return out
    for f in root.rglob("*.py"):
        if _is_path_exempt(f):
            continue
        text = f.read_text(encoding="utf-8")
        for i, raw in _extract_python_visible_lines(text):
            if "DEPRECATED" in raw:
                continue
            hits = _forbidden_in_line(raw)
            if hits:
                out.append((f, i, raw.strip(), hits))
    return out


def _format(violations: list[tuple[Path, int, str, list[str]]]) -> str:
    return "\n".join(
        f"  {p.relative_to(REPO_ROOT)}:{i} hits={hits} :: {line}"
        for p, i, line, hits in violations
    )


def test_frontend_no_forbidden_narrative():
    violations = _scan_frontend(FRONTEND_SRC)
    assert not violations, f"前端存在禁止叙事词:\n{_format(violations)}"


def test_readme_no_forbidden_narrative():
    violations = _scan_readme(README)
    assert not violations, f"README 存在禁止叙事词:\n{_format(violations)}"


def test_backend_docstrings_no_forbidden_narrative():
    violations = _scan_backend_api(BACKEND_API)
    assert not violations, f"后端 API docstring/字面量存在禁止叙事词:\n{_format(violations)}"
```

- [ ] **Step 2: 运行测试，预期 PASS（前面任务已清文案）**

Run: `python -m pytest tests/test_narrative_policy.py -v`
Expected: 3 passed

若失败，测试输出会指出剩余违规的 `file:line`，回到对应任务修复后重跑。

- [ ] **Step 3: 提交**

```bash
git add tests/test_narrative_policy.py
git commit -m "test(narrative-policy): 新增禁止叙事词静态扫描测试

覆盖前端 src / README / 后端 docstring；DEPRECATED 与内部注释豁免。"
```

---

### Task 11: 更新 /life-trajectory 回归测试 + 全量回归

**Files:**
- Modify: `tests/` 下涉及 life-trajectory payback 的测试（先检索）
- Verify: `tests/test_narrative_policy.py` + 全量 pytest

**Interfaces:** 无

- [ ] **Step 1: 检索依赖 payback 的测试**

Run: `grep -rn "payback\|years_to_break_even\|lifetime_15y_net\|_build_payback" tests/`

记录所有命中的测试文件与断言行。

- [ ] **Step 2: 调整断言**

对每个命中：把"断言 payback 字段值"改为"断言主链路 payback 为 None（不再生成）"，并保留"端点返回 2xx"断言。例如，若有 `assert traj["sprint"][0]["payback"]["years_to_break_even"] == X`，改为：

```python
# 回本已从主链路移除（见 narrative-policy）
assert traj["sprint"][0]["payback"] is None
```

对端点可用性，确保仍有 `assert response.status_code == 200`（或对应客户端调用成功）。

- [ ] **Step 3: 运行全量 pytest**

Run: `python -m pytest -q`
Expected: 全部 PASS（含 narrative-policy 3 项 + life-trajectory 回归 + /recommend + /score-rank + 大学费用）

- [ ] **Step 4: 提交**

```bash
git add tests/
git commit -m "test: 调整 life-trajectory 回归断言 payback 不再生成；全量回归通过

回本从生成侧切断后，断言主链路 payback 为 None；端点仍 2xx。"
```

---

### Task 12: openspec validate + 任务勾选

**Files:**
- Verify only: OpenSpec change

- [ ] **Step 1: 校验 change**

Run: `openspec validate deprecate-life-path-narrative`
Expected: `Change 'deprecate-life-path-narrative' is valid`

- [ ] **Step 2: 勾选 tasks.md 全部任务**

把 `openspec/changes/deprecate-life-path-narrative/tasks.md` 中所有 `- [ ]` 改为 `- [x]`（17 项）。

计划任务与 OpenSpec tasks 映射：

- Plan Task 1 -> OpenSpec 1.1
- Plan Task 2 -> OpenSpec 1.3, 1.4
- Plan Task 3 -> OpenSpec 1.2
- Plan Task 4 -> OpenSpec 2.1
- Plan Task 5 -> OpenSpec 3.1, 3.3
- Plan Task 6 -> OpenSpec 3.2
- Plan Task 7 -> OpenSpec 4.1, 4.2
- Plan Task 8 -> OpenSpec 3.4
- Plan Task 9 -> OpenSpec 5.1
- Plan Task 10 -> OpenSpec 6.1, 6.2
- Plan Task 11 -> OpenSpec 2.2, 7.1
- Plan Task 12 -> OpenSpec 7.2

- [ ] **Step 3: 提交**

```bash
git add openspec/changes/deprecate-life-path-narrative/tasks.md
git commit -m "chore: 勾选 deprecate-life-path-narrative 全部任务"
```

---

## Self-Review

**1. Spec coverage（narrative-policy delta spec 5 requirements / 10 scenarios）:**
- "禁止人生固化叙事"（前端导航/主页标题/README）→ Task 5, 6, 9 ✓
- "禁止交易化叙事"（卡片不含回本/主流程不生成/静态扫描）→ Task 1, 7, 10 ✓
- "三路径优化器移出主链路"→ Task 3 ✓（确认主流程不调用 + DEPRECATED）
- "deprecated 端点可见性"（仍可运行 + 不在主导航）→ Task 4（docstring/notes）+ Task 5（导航移除）+ Task 11（回归 2xx）✓
- "回归可用性"（/recommend、/score-rank、大学费用）→ Task 11 ✓

**2. Placeholder scan:** 无 TBD/TODO；README 已要求全文 `rg` 清理，`life_paths` docstring 已给中性示例，`LifePathsPage` 也纳入中性化，避免静态扫描误伤。✓

**3. Type consistency:** `payback` 解构在 Task 7 移除后无后续引用；`TrajectoryItem.payback` 仍为模型字段（保留），前端不再读。✓

无遗漏，无需补充任务。
