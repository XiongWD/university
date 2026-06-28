"""异步 OpenAI 兼容流式客户端

支持任意兼容 OpenAI Chat Completions API 的服务商（DeepSeek / Qwen / GLM / Kimi 等）。
配置通过环境变量传入，详见 app.config.Settings。
"""

import logging
from typing import AsyncGenerator

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

_llm_client: AsyncOpenAI | None = None


def get_llm_client() -> AsyncOpenAI | None:
    """懒加载获取 LLM 客户端实例。未配置 API Key 时返回 None。"""
    global _llm_client
    if not settings.llm_configured:
        logger.warning("LLM 客户端未配置：OPENAI_API_KEY 为空，AI 功能不可用")
        return None
    if _llm_client is None:
        _llm_client = AsyncOpenAI(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
        )
        logger.info(
            "LLM 客户端已初始化 base_url=%s model=%s",
            settings.openai_base_url,
            settings.openai_model,
        )
    return _llm_client


async def stream_chat(
    system_prompt: str,
    user_content: str,
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> AsyncGenerator[str, None]:
    """流式调用 LLM，逐段 yield delta 文本内容。

    Args:
        system_prompt: 系统角色提示词
        user_content: 用户消息内容
        model: 模型名（默认使用 settings.openai_model）
        temperature: 温度参数（默认使用 settings.ai_temperature）
        max_tokens: 最大 token 数（默认使用 settings.ai_max_tokens）

    Yields:
        str: 每次 LLM 输出的文本增量（delta）

    Raises:
        RuntimeError: LLM 客户端未配置
        Exception: API 调用失败
    """
    client = get_llm_client()
    if client is None:
        raise RuntimeError(
            "LLM 客户端未配置。请设置环境变量 OPENAI_API_KEY。"
        )

    effective_model = model or settings.openai_model
    effective_temperature = temperature if temperature is not None else settings.ai_temperature
    effective_max_tokens = max_tokens or settings.ai_max_tokens

    logger.info(
        "开始流式 LLM 调用 model=%s temperature=%.2f max_tokens=%d",
        effective_model,
        effective_temperature,
        effective_max_tokens,
    )

    try:
        stream = await client.chat.completions.create(
            model=effective_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=effective_temperature,
            max_tokens=effective_max_tokens,
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content

    except Exception:
        logger.exception("LLM 流式调用失败")
        raise
