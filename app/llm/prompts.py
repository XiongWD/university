"""AI 提示词模板 — 高考志愿推荐 & 目标评估

两套核心提示词：
1. build_recommendation_prompt   — 志愿推荐（基于系统候选清单）
2. build_evaluation_prompt       — 目标评估（合规复核 + 多维度综合评估，单次调用）
"""

# ============================================================================
# 系统角色提示词
# ============================================================================

RECOMMENDATION_SYSTEM = """# Role
你是高考志愿首席规划专家，深耕河南省高考录取数据 10 年以上。
你精通新高考 3+1+2 选科制度、院校专业组投档规则、各专业就业出口。
你的每个建议都基于数据，有理有据，不模棱两可。

# Context
- 省份/批次：河南 2026 年普通本科批（历史类）
- 投档：平行志愿，48 个院校专业组，每组最多 6 专业
- 选科：3+1+2（首选历史，再选 2 门）
- 数据基础：系统已用历年录取位次 + 2026 招生计划做了资格过滤和冲稳保分桶

# Constraints
1. 紧密结合系统筛选的实际候选数据，不凭空杜撰院校
2. 结合考生家庭偏好给出针对建议
3. 风险提示具体到院校/专业组，不泛泛而谈
4. 输出 Markdown，层次清晰，表格对齐

# Output Format

## 📊 考生定位
（一句话：位次在河南省内的相对位置、超本科线分数）

## 🔥 冲刺院校
逐校分析，每校一段，包含：名称·专业组代码、核心优势、风险点、适配专业

## ✅ 稳妥院校
同上格式

## 🛡️ 保底院校
同上格式

## 📚 专业匹配分析
结合选科组合，推荐 3-5 个最适合的专业方向，说明理由和就业出口

## 🎯 填报策略
- 志愿排序建议
- 省内 vs 省外、公办 vs 民办权衡
- 调剂策略

## ⚠️ 风险提醒
- 语种/单科/体检硬性限制
- 学费差异
- 保底双保险方案"""


EVALUATION_SYSTEM = """# Role
你是首席高考志愿规划专家兼职业发展顾问。你同时具备以下能力：
- 招生合规审查：熟读各校招生章程，能识别退档红线
- 就业市场分析：跟踪各行业招聘趋势、薪资数据、政策风向
- 职业生涯规划：能绘制专业→职业→10年收益的完整路径

# Task
对考生选定的目标院校进行一次综合评估，覆盖三个层次：
1. **合规风险排查**：招生章程核查、语种限制、学费变动、退档红线
2. **就业与经济分析**：结合当前国内外政策和经济形势，分析各专业的就业前景、薪资曲线、长期ROI
3. **综合排序与决策**：基于语种适配、地域、成本、专业前景给出最终推荐

# 就业与经济分析要点（必须覆盖）
- **当前就业形势**：该专业2024-2026年的招聘需求量、竞争激烈程度
- **政策面分析**：国家/地方对该专业的扶持政策（如考公岗位增减、基层项目、专项计划）
- **薪资数据**：应届起薪、5年薪资中位数、10年薪资天花板（分一线/二线/河南本地）
- **收益对比**：对比不同专业方向的10年累计收入与学费投入的ROI
- **长期趋势**：AI/自动化对该专业的替代风险、行业增长预期

# Evaluation Weights
- 语种适配度 (25%)：能否延续外语优势
- 地域与发展 (25%)：城市经济体量、对河南籍毕业生就业友好度
- 办学成本 (25%)：学费与家庭承受能力匹配度
- 专业前景 (25%)：考公合规率、行业转轨灵活度、薪资增长曲线

# Markdown 表格格式 — 严格约束（违反将导致渲染失败）
- **表格的每一行必须独占一行，行与行之间必须用换行符分隔。严禁把多行挤在一行里。**
- 每行必须以 | 开头、以 | 结尾。**禁止**在结尾 | 之后再添加任何 |。
- 正确（3列）:
| A | B | C |
|-----|-----|-----|
| 1 | 2 | 3 |
- 错误（多余空列）: | A | B | C | |
- 错误（行合并）: | A | B | C | |-----|-----|-----|
- 分隔行格式: |-----|-----|-----|（分隔符数量等于列数）
- 所有数据行的列数必须等于表头列数

# Constraints
1. 风险项必须具体到专业组代码，无风险的条目不列出
2. 薪资数据标注来源依据（"基于2025届就业报告估算"等），不确定时标明"估算"
3. 博弈分析给出明确倾向，不两面讨好
4. 针对外语考生给出入学后具体可操作的注意事项

# Output Format

## 🔍 合规风险排查
> 仅列出存在风险的条目。无风险的不列出。

（表格，4列：专业组代码 | 风险类型 | 具体描述 | 核实建议）

## 💼 就业市场与薪资分析

### 当前就业形势
（简要分析各相关专业的2024-2026年招聘趋势、竞争格局）

### 政策环境
（国家/省级层面对该专业的扶持或限制政策，考公/考编岗位变化）

### 薪资曲线对比
（表格，按专业方向列出：应届起薪 | 5年中位数 | 10年天花板 | 河南本地薪资）

### 长期收益评估
（对比不同选择的10年累计收入、ROI、风险）

## 📊 综合排序与推荐
（按推荐优先级排列的表格：推荐顺序 | 专业组代码·名称 | 建议位置 | 核心理由 | 风险备注）

## ⚖️ 核心博弈点
（对最纠结的2个选择做直接比较，给出明确倾向和量化理由）

## 🗺️ 学业与职业规划路线图
（入学后4年+毕业后5年的关键节点建议，含外语衔接、实习方向、证书规划）"""


# ============================================================================
# 上下文构建辅助函数
# ============================================================================


def _build_profile_text(profile: dict) -> str:
    """将考生 profile 转为可读文本。"""
    lines = [
        f"- 省份/批次：{profile.get('source_province', '河南')} 2026年普通本科批",
        f"- 选科类别：{profile.get('track', '历史类')}",
        f"- 总分：**{profile.get('score', '?')}** 分",
        f"- 全省位次：**{profile.get('rank', '?')}**",
        f"- 首选科目：{profile.get('primary_subject', '历史')}",
        f"- 再选科目：{'、'.join(profile.get('elective_subjects', [])) or '未指定'}",
        f"- 外语语种：**{profile.get('exam_foreign_language', '英语')}**",
    ]
    subject_scores = profile.get("subject_scores_detail", {})
    if subject_scores:
        score_parts = []
        for k, v in subject_scores.items():
            if v and v > 0:
                score_parts.append(f"{k}={v}分")
        if score_parts:
            lines.append(f"- 单科成绩：{'、'.join(score_parts)}")
    if profile.get("obey_adjustment") is not None:
        lines.append(f"- 服从调剂：{'是' if profile['obey_adjustment'] else '否'}")
    return "\n".join(lines)


def _build_candidate_summary(candidate: dict) -> str:
    """单个候选摘要。"""
    school = candidate.get("school_name", "未知院校")
    group_code = candidate.get("major_group_code", "?")
    group_name = candidate.get("major_group_name", "")
    majors = candidate.get("selected_majors", [])
    plan_count = candidate.get("plan_count", "?")
    bucket = candidate.get("bucket", "?")
    ownership = candidate.get("school_ownership", "?")
    province = candidate.get("school_province", "?")
    city = candidate.get("school_city", "?")
    tuition = candidate.get("tuition", "?")

    bucket_detail = candidate.get("bucket_detail", {})
    ref_rank = bucket_detail.get("adjusted_min_rank", "?")
    baseline_year = bucket_detail.get("baseline_year", "?")

    parts = [
        f"### 【{bucket}】{school} | {group_code} {group_name}",
        f"- 含专业：{', '.join(majors) if majors else '未指定'}",
        f"- 2026计划：{plan_count}人 | 办学性质：{ownership} | 所在地：{province} {city}",
        f"- 学费：{tuition}元/年",
    ]
    if ref_rank and ref_rank != "?":
        parts.append(f"- 参考：{baseline_year}年录取位次≈{ref_rank}")

    blocked = candidate.get("blocked_reasons", [])
    warnings = candidate.get("warnings", [])
    if blocked:
        parts.append(f"- ⛔ 硬阻断：{'；'.join(blocked)}")
    if warnings:
        parts.append(f"- ⚠️ 系统警告：{'；'.join(warnings)}")

    return "\n".join(parts) + "\n"


def _build_candidates_text(candidates: list[dict]) -> str:
    """候选列表转批量 Markdown。"""
    if not candidates:
        return "（无系统候选数据）"

    buckets: dict[str, list[dict]] = {}
    for c in candidates:
        b = c.get("bucket", "其他")
        buckets.setdefault(b, []).append(c)

    sections = []
    for bk in ("冲", "稳", "保"):
        items = buckets.pop(bk, [])
        if not items:
            continue
        sections.append(f"\n## {bk}（{len(items)} 个）\n")
        for item in items:
            sections.append(_build_candidate_summary(item))

    for bk, items in buckets.items():
        if not items:
            continue
        sections.append(f"\n## {bk}（{len(items)} 个）\n")
        for item in items:
            sections.append(_build_candidate_summary(item))

    return "\n".join(sections)


def _build_target_items_text(items: list[dict]) -> str:
    """目标评估 items 转紧凑文本。"""
    if not items:
        return "（系统未找到可达专业组，以下评估基于考生手动指定的院校信息）"

    lines = []
    for i, item in enumerate(items, 1):
        school = item.get("school_name", "?")
        group_code = item.get("major_group_code", "?")
        group_name = item.get("major_group_name", "")
        majors = item.get("selected_majors", [])
        bucket = item.get("bucket", "?")
        prob = item.get("admission_probability", "?")
        tuition = item.get("tuition", "?")
        ownership = item.get("school_ownership", "?")
        province = item.get("school_province", "?")

        line = (
            f"{i}. **{group_code}** {school}·{group_name} "
            f"| 位置: {bucket} | 录取概率≈{prob}% | {ownership} | {province}"
        )
        if majors:
            line += f" | 含: {', '.join(majors)}"
        if tuition and tuition != "?":
            line += f" | 学费: {tuition}元/年"
        lines.append(line)

        blocked = item.get("blocked_reasons", [])
        if blocked:
            lines.append(f"   ⛔ {', '.join(blocked)}")

    return "\n".join(lines)


# ============================================================================
# 公开提示词构建函数
# ============================================================================


def build_recommendation_prompt(
    profile: dict,
    candidates: list[dict],
    *,
    extra_preferences: str = "",
) -> tuple[str, str]:
    """构建志愿推荐提示词。

    Returns:
        (system_prompt, user_content)
    """
    profile_text = _build_profile_text(profile)
    candidates_text = _build_candidates_text(candidates)

    user_parts = [
        "## 考生信息",
        profile_text,
    ]
    if extra_preferences:
        user_parts.append(f"\n## 考生偏好\n{extra_preferences}")
    user_parts.append(f"\n## 系统筛选的候选院校清单\n{candidates_text}")
    user_parts.append("\n---\n请基于以上数据，为该考生生成志愿填报分析报告。")

    return RECOMMENDATION_SYSTEM, "\n".join(user_parts)


def build_evaluation_prompt(
    profile: dict,
    target_items: list[dict],
    *,
    target_school: str = "",
    overall_bucket: str = "",
    reasons: list[str] | None = None,
) -> tuple[str, str]:
    """构建目标评估提示词（合规复核 + 综合评估，单次调用）。

    Args:
        profile: 考生信息字典
        target_items: 目标院校的可达专业组（从 evaluate_target_school 获得）
        target_school: 目标院校名称
        overall_bucket: 系统评估的总体桶位（可评估/不推荐）
        reasons: 不推荐的原因列表

    Returns:
        (system_prompt, user_content)
    """
    profile_text = _build_profile_text(profile)
    items_text = _build_target_items_text(target_items)

    user_parts = [
        "## 考生信息",
        profile_text,
    ]

    if overall_bucket == "不推荐" and reasons:
        user_parts.append(f"\n## ⚠️ 系统初步评估：不推荐\n原因：{'；'.join(reasons)}")
        user_parts.append("> 以下分析基于考生手动指定的院校信息，请特别关注合规风险。")

    user_parts.append(f"\n## 目标院校：{target_school}")
    user_parts.append(f"\n## 系统匹配到的专业组\n{items_text}")
    user_parts.append(
        "\n---\n请对该目标院校进行一次性综合评估：先排查合规风险，再做多维度决策分析。"
    )

    return EVALUATION_SYSTEM, "\n".join(user_parts)
