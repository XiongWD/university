"""LLM 模块 — OpenAI 兼容流式客户端 + 提示词模板"""

from app.llm.client import get_llm_client, stream_chat
from app.llm.prompts import (
    build_recommendation_prompt,
    build_evaluation_prompt,
)

__all__ = [
    "get_llm_client",
    "stream_chat",
    "build_recommendation_prompt",
    "build_evaluation_prompt",
]
