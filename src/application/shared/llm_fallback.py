"""LLM fallback chain utilities — shared across use cases.

Provides generate/stream helpers that try a list of models in order,
falling back to the next on failure.
"""

import logging
from collections.abc import AsyncIterator

from src.domain.ports.llm import LLMMessage, LLMPort

logger = logging.getLogger(__name__)


async def generate_with_fallback(
    llm: LLMPort,
    messages: list[LLMMessage],
    models: list[str],
    temperature: float = 0.7,
):
    """Generate LLM response trying each model in *models* until one succeeds.

    Args:
        llm: LLM adapter (port).
        messages: Conversation messages.
        models: Ordered list of model names to try (e.g. [primary, fallback]).
        temperature: Sampling temperature.

    Returns:
        LLM response object from the first model that succeeds.

    Raises:
        RuntimeError: If all models fail.

    """
    last_error: Exception | None = None

    for model in models:
        try:
            return await llm.generate(
                messages=messages,
                model=model,
                temperature=temperature,
            )
        except Exception as e:
            logger.warning("LLM generate failed with model=%s: %s", model, e)
            last_error = e

    raise last_error or RuntimeError("All LLM models failed to generate")


async def stream_with_fallback(
    llm: LLMPort,
    messages: list[LLMMessage],
    models: list[str],
    temperature: float = 0.7,
) -> AsyncIterator[str]:
    """Stream LLM response trying each model in *models* until one succeeds.

    Args:
        llm: LLM adapter (port).
        messages: Conversation messages.
        models: Ordered list of model names to try.
        temperature: Sampling temperature.

    Yields:
        Text chunks from the first model that succeeds.

    Raises:
        RuntimeError: If all models fail.

    """
    last_error: Exception | None = None

    for model in models:
        try:
            async for chunk in llm.generate_stream(
                messages=messages,
                model=model,
                temperature=temperature,
            ):
                yield chunk
            return
        except Exception as e:
            logger.warning("LLM stream failed with model=%s: %s", model, e)
            last_error = e

    raise last_error or RuntimeError("All LLM models failed to stream")
