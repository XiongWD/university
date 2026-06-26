"""风险偏好分桶引擎（design §5.5）。

按考生位次与历史录取基准位次的差距，结合报考策略（冲/中/稳），
生成"保/稳/偏冲/不推荐"档位。注意位次越大代表成绩越靠后。
gap_ratio > 0 表示考生位次弱于基准（更难录），< 0 表示优于基准。

不输出伪精确概率；只用档位（冲/稳/保）解释风险区间。
"""
from __future__ import annotations


def classify_rank_gap(student_rank: int, baseline_rank: int, risk_preference: str) -> str:
    """根据位次差比和风险偏好返回档位标签。

    返回值：保 / 稳 / 偏冲 / 不推荐（"不推荐"不进入任何推荐桶）。
    risk_preference: 冲 / 中 / 稳，影响各档位次区间宽窄。
    """
    if student_rank <= 0 or baseline_rank <= 0:
        return "不推荐"

    gap_ratio = (student_rank - baseline_rank) / baseline_rank

    if risk_preference == "冲":
        # 激进：允许更宽的冲刺区间
        if gap_ratio <= -0.12:
            return "保"
        if gap_ratio <= 0.06:
            return "稳"
        if gap_ratio <= 0.18:
            return "偏冲"
        return "不推荐"

    if risk_preference == "稳":
        # 保守：压缩冲刺、突出兜底
        if gap_ratio <= -0.18:
            return "保"
        if gap_ratio <= -0.03:
            return "稳"
        if gap_ratio <= 0.04:
            return "偏冲"
        return "不推荐"

    # 中（默认）：三档均衡
    if gap_ratio <= -0.15:
        return "保"
    if gap_ratio <= 0.06:
        return "稳"
    if gap_ratio <= 0.12:
        return "偏冲"
    return "不推荐"
