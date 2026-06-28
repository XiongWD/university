"""AI 分析引擎 — 高考志愿推荐 & 目标评估

提供流式 AI 分析能力：

1. AI 志愿推荐：系统候选清单 → LLM 生成分析报告
2. AI 目标评估：合规复核 + 多维度综合评估合并为单次 LLM 调用

流式输出的关键改进：
- 在 LLM 调用开始前，先 yield 进度提示（"正在分析..."）
- LLM 的流式 delta 直接透传，不缓存
"""

import logging
from typing import AsyncGenerator

from app.engine.henan_recommendation import build_henan_candidates
from app.engine.henan_target_evaluation import evaluate_target_school
from app.llm.client import stream_chat
from app.llm.markdown_fixer import wrap_stream_with_table_fix
from app.llm.prompts import (
    build_recommendation_prompt,
    build_evaluation_prompt,
)

logger = logging.getLogger(__name__)


async def stream_ai_recommendation(
    profile: dict,
    *,
    extra_preferences: str = "",
) -> AsyncGenerator[str, None]:
    """流式 AI 志愿推荐。

    Yields:
        先 yield 进度提示，再逐段 yield LLM 输出。
    """
    logger.info("AI 推荐开始 score=%s rank=%s", profile.get("score"), profile.get("rank"))

    # 1. 获取系统候选清单
    candidates = build_henan_candidates(profile)
    logger.info("候选清单 %d 条", len(candidates))

    # 2. 组装 prompt
    system_prompt, user_content = build_recommendation_prompt(
        profile=profile,
        candidates=candidates,
        extra_preferences=extra_preferences,
    )

    # 3. 先发送进度提示（确保前端立即看到反馈）
    yield "🔍 *正在分析你的分数位次和候选院校数据...*\n\n"

    # 4. 流式调用 LLM（经表格修复器包裹，确保 Markdown 表格渲染正确）
    async for delta in wrap_stream_with_table_fix(
        stream_chat(system_prompt, user_content)
    ):
        yield delta

    logger.info("AI 推荐完成")


async def stream_ai_target_evaluation(
    profile: dict,
    target_school: str,
    target_majors: list[str] | None = None,
    target_group: str | None = None,
) -> AsyncGenerator[str, None]:
    """流式 AI 目标评估（单次 LLM 调用，合并合规复核 + 综合评估）。

    流程：
    1. 获取系统候选清单
    2. 调用 evaluate_target_school 获取目标可达性
    3. 组装一个融合 prompt → 单次 LLM 调用
    4. 调用前先 yield 进度提示

    Yields:
        先 yield 进度提示，再逐段 yield LLM 输出。
    """
    logger.info(
        "AI 目标评估 school=%s majors=%s group=%s",
        target_school, target_majors, target_group,
    )

    # 1. 获取系统候选清单
    candidates = build_henan_candidates(profile)

    # 2. 目标可达性评估
    target_result = evaluate_target_school(
        profile=profile,
        target_school=target_school,
        target_majors=target_majors or [],
        target_group=target_group,
        candidates=candidates,
    )

    reachable_items = target_result.get("items", [])
    overall_bucket = target_result.get("overall_bucket", "不推荐")
    reasons = target_result.get("reasons", [])

    logger.info(
        "目标评估系统结果 bucket=%s reachable=%d reasons=%s",
        overall_bucket, len(reachable_items), reasons,
    )

    # 3. 组装融合 prompt（合规复核 + 综合评估合并为一次调用）
    system_prompt, user_content = build_evaluation_prompt(
        profile=profile,
        target_items=reachable_items or [],
        target_school=target_school,
        overall_bucket=overall_bucket,
        reasons=reasons,
    )

    # 4. 先发送进度提示
    yield f"🔍 *正在评估 **{target_school}**，分析录取概率与合规风险...*\n\n"

    # 5. 单次流式 LLM 调用（经表格修复器包裹，确保 Markdown 表格渲染正确）
    async for delta in wrap_stream_with_table_fix(
        stream_chat(system_prompt, user_content)
    ):
        yield delta

    logger.info("AI 目标评估完成")
