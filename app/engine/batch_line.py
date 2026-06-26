"""批次线判断引擎（design §5.2）。

按考生分数与本科线/专科线的差距，决定本科冲稳保 vs 专科稳妥方案的策略基调。
低分段（低于本科线）普通本科只能作为冲刺，同时需要专科兜底。
"""
from __future__ import annotations

from app.models.program_plan import BatchLineDecision

# 低于本科线但在 15 分以内：视为"贴线"，本科尚有冲刺价值但属高风险
NEAR_UNDERGRAD_WINDOW = 15


def decide_batch_position(
    score: int,
    rank: int,
    undergrad_line: int | None,
    junior_college_line: int | None,
) -> BatchLineDecision:
    """根据分数与本科线/专科线差距，判断批次位置与推荐基调。

    - 达到/超过本科线：可进行本科冲稳保推荐。
    - 低于本科线但在窗口内：本科仅作冲刺，需配套专科稳妥方案。
    - 明显低于本科线：默认以专科稳妥方案为主。
    - 缺少本科线数据：不强行判断，按位次推荐并降低置信度。
    """
    if undergrad_line is None:
        return BatchLineDecision(
            score=score,
            rank=rank,
            undergrad_line=undergrad_line,
            junior_college_line=junior_college_line,
            distance_to_undergrad_line=None,
            batch_position="above_undergrad",
            recommendation_policy_note="缺少本科线数据，仅按位次推荐并降低置信度",
        )

    distance = score - undergrad_line
    if distance >= 0:
        position = "above_undergrad"
        note = "达到本科线，可进行本科冲稳保推荐"
    elif distance >= -NEAR_UNDERGRAD_WINDOW:
        position = "below_undergrad"
        note = "低于本科线，普通本科仅可作为冲刺，同时需要专科稳妥方案"
    else:
        position = "junior_college_only"
        note = "明显低于本科线，默认以专科稳妥方案为主"

    return BatchLineDecision(
        score=score,
        rank=rank,
        undergrad_line=undergrad_line,
        junior_college_line=junior_college_line,
        distance_to_undergrad_line=distance,
        batch_position=position,
        recommendation_policy_note=note,
    )
