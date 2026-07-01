---
name: verify-henan-school
description: 验证/核对河南高考志愿院校的录取数据准确性。当用户提到核对院校官网、验证录取位次、核实河南历史类分数、检查志愿组学校数据是否准确、质疑某校录取数据真假、或担心本地抓取数据（heao/gaokao）不可信时，使用本技能。覆盖任何"用学校官网/招生网权威数据交叉验证本地种子数据"的场景——即使用户没明说"官网"，只要涉及院校录取数据可信度就应触发。
---

# 验证河南院校录取数据（官网交叉验证）

把"郑州经贸 101 组验证方法"固化为可复用流程：**官网是唯一权威源**，本地 heao/gaokao 抓取的种子数据多次出现位次、专业组缺失，可信度低。所有真实数据必须以学校官网和招生网为准。

## 核心原则

**官网 > 本地种子**。当两者冲突，种子是错的，必须按官网修正。这是用户的硬性诉求，不可妥协。

## 工具

核心脚本 `scripts/verify_official_admission.py` 已实现完整三步管线（不要自己重写）：

```bash
# 验证单所学校
python scripts/verify_official_admission.py --school 郑州经贸学院

# 验证弟弟志愿组全部 16 所
python scripts/verify_official_admission.py --all

# 强制重抓官网（忽略缓存，官网数据更新后用）
python scripts/verify_official_admission.py --all --refresh
```

脚本做的事（固定管线，不要改动逻辑）：

1. **抓官网录取表**（脚本自动多策略，按顺序尝试直至命中）：
   - **深度爬取**：urllib 抓招生网首页 → 找栏目页（往年录取/历年分数）→ 进栏目页找 2025 河南录取详情页（BFS 2 层）
   - **JS 动态菜单**：首页若没发现栏目链接，用 playwright 渲染首页拿到 JS 注入的菜单
   - **反爬拦截**：urllib 遇 412/503/SSL 失败时，自动回退 playwright（预算 3 次）
   - **数据形态自适应**：详情页是 PDF（含 vsb 系统 `showVsbpdfIframe` JS 嵌入）→ pdfplumber 解析；是 HTML 表格 → stdlib HTMLParser；是**图片** → PaddleOCR（定位省控线 471 行 = 历史类，取最低分）
   - **省份校验**：多省混合数据时只取"河南"段，防止外省分污染
2. **分数换算位次**：用一分一段表 `_score_to_rank` 把官网分数换算成权威位次（官网通常只给分数不给位次）
3. **比对种子**：权威位次 vs `admission_history_2025.yaml` 的 `min_rank`，输出三态判定

## 判等规则（三态）

报告 `data/verify/report.md` 里每校一个判定，按此处理：

| 判定 | 含义 | 处理 |
|------|------|------|
| ✅ **match** | 官网换算位次与种子 min_rank 差 ≤ 500 位 | 数据可信，无需处理 |
| ⚠️ **conflict** | 差 > 500 位 | **种子错，按官网修正 `admission_history_2025.yaml`** |
| ❓ **no_official_data** | 官网没找到 2025 数据（未公布/深度爬取仍找不到） | 走下方 WebSearch 兜底流程 |

容差 ±500 位的依据：一分一段表是分数档（非精确一分），且 2025→2026 有省控线年际浮动，同分考生位次本身有档位误差。

## 执行流程

1. **跑脚本**：根据用户需求选 `--school` 或 `--all`。
   - ⚠️ **`--all` 较慢**（OCR 每张图 5-10 秒 + playwright 启动浏览器），13 所可能跑 5-15 分钟。建议**后台跑**（`run_in_background`），避免阻塞对话。
   - 首次跑某校会抓官网，之后走缓存 `data/verify/cache.json`。
2. **读报告**：`Read data/verify/report.md`，先看汇总表，再看明细。
3. **报告结论**：向用户用表格汇报每校判定，**明确指出哪些是 conflict（种子错）**。
4. **处理 conflict**（关键）：对每个 conflict 学校，按官网权威位次修正种子：
   - 编辑 `data/seed/henan/admission_history_2025.yaml`，把该校 `min_rank` 改为官网换算位次
   - 在记录里追加注释标明来源：`source_name: <校名>官网核实`、`source_url: <官网URL>`
   - 修正后重跑该学校确认变为 match
5. **处理 no_official_data**（WebSearch 兜底，按优先级）：
   - **第 1 步 WebSearch**：搜 `"<校名> 2025 河南 历史类 录取分数线"`，找第三方权威来源（教育在线/阳光高考/省考试院转载）。找到则用其分数换算位次比对。
   - **第 2 步 回退本地 seed**（**最后手段，不到万不得已不用**）：WebSearch 也找不到时，沿用本地种子 `min_rank`，但必须**显式告知用户"该数据未经官网核实，可信度低"**，并在报告 note 标注 `fallback_seed_low_confidence`。绝不静默采用。

## 关键约束

- **不要用 heao/gaokao 数据覆盖官网**。本地种子（heao 抓取）正是用户怀疑的对象，它只能作为"待验证项"，不能作为"修正依据"。修正的唯一依据是官网。
- **官网只给分数时必须换算位次**。官网 PDF 常写"历史类 501（101组）超线30分"，不直接给位次。必须用一分一段表换算（脚本已自动做）。
- **图片型分数线脚本已自动 OCR**。PaddleOCR 定位省控线 471 行识别历史类分数，不再标 needs_manual（除非 OCR 真的识别失败）。
- **WebSearch 兜底不得静默回退 seed**。回退本地种子是最低可信度，必须明示用户，不可假装已验证。
- **缓存默认信任**。非 `--refresh` 时脚本用缓存，避免重复抓官网。官网数据更新或用户要求重新核实时才加 `--refresh`。
- **playwright 预算有限**（单次运行 3 次），反爬重的站可能耗尽预算。耗尽后该校标 no_official_data，走 WebSearch 兜底。

## 实例（郑州经贸，基线案例）

输入：`python scripts/verify_official_admission.py --school 郑州经贸学院`

输出：
```
✅ match: 分=501 换算位次=61895 种子位次=61895
官网501分→位次61895，种子61895，差+0位（容差±500）
```

证据链：郑州经贸招生网《2025年河南省内本科普通类分专业录取分数统计表》PDF 原文"历史类 501（101组）超线30分" → 一分一段表 501分=位次61895 → 与本地种子 min_rank=61895 完全一致。证明该种子数据可信。

**注意**：单校 match 只证明该校数据准，不能推广到所有学校。其他学校（尤其丽江、贵州商学院那类历史上出过错的）仍需逐个验证。

## 数据文件位置

- 验证脚本：`scripts/verify_official_admission.py`
- 验证报告：`data/verify/report.md`
- 抓取缓存：`data/verify/cache.json`（每校缓存，可删后重抓）
- 失败清单：`data/verify/failed.txt`
- 院校库（URL 来源）：`data/seed/henan/universities.yaml` 的 `official_website` / `enrollment_website` 字段
- 待修正种子：`data/seed/henan/admission_history_2025.yaml`
- 一分一段表（换算依据）：`data/datasets/henan_2025_score_rank.csv`
- 弟弟志愿组学校清单：脚本里 `BROTHER_SCHOOLS` 常量（16 所）
