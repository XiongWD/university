"""AI 分析 API 路由 — SSE 流式端点

提供两个流式端点：
- POST /henan/ai/recommend   AI 志愿推荐（SSE 流式）
- POST /henan/ai/evaluate     AI 目标评估（SSE 流式）

SSE 格式：data: {"delta":"文本片段..."}\n\n
错误格式：data: {"error":"错误信息"}\n\n
结束信号：data: [DONE]\n\n
"""

import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session

from app.config import settings
from app.db import get_session_dep
from app.engine.henan_ai import (
    stream_ai_recommendation,
    stream_ai_target_evaluation,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/henan/ai", tags=["henan-ai"])


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------

class AIRecommendationRequest(BaseModel):
    """AI 志愿推荐请求"""
    score: int
    rank: int | None = None
    track: str = "历史类"
    source_province: str = "河南"
    primary_subject: str = "历史"
    elective_subjects: list[str] = []
    exam_foreign_language: str = "英语"
    subject_scores_detail: dict[str, int] = {}
    obey_adjustment: bool = True
    extra_preferences: str = ""  # 额外偏好描述


class AITargetEvaluationRequest(BaseModel):
    """AI 目标评估请求"""
    score: int
    rank: int | None = None
    track: str = "历史类"
    source_province: str = "河南"
    target_school: str
    target_majors: list[str] = []
    target_group: str | None = None
    primary_subject: str = "历史"
    elective_subjects: list[str] = []
    exam_foreign_language: str = "英语"
    subject_scores_detail: dict[str, int] = {}
    obey_adjustment: bool = True


# ---------------------------------------------------------------------------
# SSE 辅助函数
# ---------------------------------------------------------------------------

async def _sse_event_generator(
    stream: AsyncGenerator[str, None],
) -> AsyncGenerator[str, None]:
    """将 LLM 文本流包装为 SSE 格式的字符串流。

    Args:
        stream: 产生文本增量的异步生成器

    Yields:
        str: SSE 格式的事件字符串
    """
    try:
        async for delta in stream:
            # 转义 delta 中的特殊字符，确保 JSON 合法
            payload = json.dumps({"delta": delta}, ensure_ascii=False)
            yield f"data: {payload}\n\n"
    except Exception as exc:
        logger.exception("SSE 流式生成异常")
        error_payload = json.dumps({"error": str(exc)}, ensure_ascii=False)
        yield f"data: {error_payload}\n\n"
    finally:
        yield "data: [DONE]\n\n"


def _build_profile(req) -> dict:
    """从请求对象构建 profile 字典。"""
    return {
        "score": req.score,
        "rank": req.rank,
        "track": req.track,
        "source_province": req.source_province,
        "primary_subject": req.primary_subject,
        "elective_subjects": req.elective_subjects,
        "exam_foreign_language": req.exam_foreign_language,
        "subject_scores_detail": req.subject_scores_detail,
        "obey_adjustment": req.obey_adjustment,
    }


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------


@router.post("/recommend")
async def ai_recommend(
    req: AIRecommendationRequest,
    session: Session = Depends(get_session_dep),
):
    """AI 志愿推荐（SSE 流式）

    接收考生信息和偏好，流式返回 AI 生成的志愿填报分析报告。
    """
    if not settings.llm_configured:
        raise HTTPException(
            status_code=503,
            detail="AI 功能未配置：请设置环境变量 OPENAI_API_KEY",
        )

    # 仅支持河南历史类
    if req.source_province != "河南":
        raise HTTPException(
            status_code=400,
            detail="河南志愿推仅支持河南考生",
        )
    if req.track != "历史类":
        raise HTTPException(
            status_code=400,
            detail="河南志愿推当前仅支持 2026 历史类普通本科批",
        )

    # 位次推导（如果未提供）
    profile = _build_profile(req)
    if profile.get("rank") in (None, 0):
        # 尝试从一分一段表推导
        from app.api.routers.henan import _resolve_rank_from_score
        resolved = _resolve_rank_from_score(session, req.score)
        if resolved is not None:
            profile["rank"] = resolved

    return StreamingResponse(
        _sse_event_generator(
            stream_ai_recommendation(
                profile=profile,
                extra_preferences=req.extra_preferences,
            )
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        },
    )


@router.post("/evaluate")
async def ai_evaluate(
    req: AITargetEvaluationRequest,
    session: Session = Depends(get_session_dep),
):
    """AI 目标评估（SSE 流式）

    接收考生信息和目标院校/专业，流式返回两阶段分析：
    1. 合规性复核
    2. 多维度综合评估
    """
    if not settings.llm_configured:
        raise HTTPException(
            status_code=503,
            detail="AI 功能未配置：请设置环境变量 OPENAI_API_KEY",
        )

    # 仅支持河南历史类
    if req.source_province != "河南":
        raise HTTPException(
            status_code=400,
            detail="河南志愿推仅支持河南考生",
        )
    if req.track != "历史类":
        raise HTTPException(
            status_code=400,
            detail="河南志愿推当前仅支持 2026 历史类普通本科批",
        )

    # 位次推导
    profile = _build_profile(req)
    if profile.get("rank") in (None, 0):
        from app.api.routers.henan import _resolve_rank_from_score
        resolved = _resolve_rank_from_score(session, req.score)
        if resolved is not None:
            profile["rank"] = resolved

    if not req.target_school.strip():
        raise HTTPException(
            status_code=400,
            detail="请提供目标院校名称",
        )

    return StreamingResponse(
        _sse_event_generator(
            stream_ai_target_evaluation(
                profile=profile,
                target_school=req.target_school,
                target_majors=req.target_majors,
                target_group=req.target_group,
            )
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
