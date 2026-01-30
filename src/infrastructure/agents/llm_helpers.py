"""LLM helpers: retry wrapper and streaming with callback."""

from collections.abc import Callable

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.domain.ports.llm import LLMMessage, LLMPort, LLMResponse


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((TimeoutError, ConnectionError, OSError)),
    reraise=True,
)
async def _generate_impl(
    llm: LLMPort,
    messages: list[LLMMessage],
    model: str,
    temperature: float,
) -> LLMResponse:
    """Internal: generate with retry."""
    return await llm.generate(
        messages=messages,
        model=model,
        temperature=temperature,
    )


async def generate_with_retry(
    llm: LLMPort,
    messages: list[LLMMessage],
    model: str,
    temperature: float = 0.7,
) -> LLMResponse:
    """Generate with retry on timeout/connection errors."""
    return await _generate_impl(llm, messages, model, temperature)


async def stream_with_callback(
    llm: LLMPort,
    messages: list[LLMMessage],
    model: str,
    event_type: str,
    on_chunk: Callable[[str, str], None] | None,
    temperature: float = 0.7,
) -> str:
    """Stream LLM response, call on_chunk(event_type, chunk). Parses <think>."""
    from src.infrastructure.llm.reasoning_parser import stream_reasoning_chunks

    content_parts: list[str] = []
    if on_chunk:
        raw_stream = llm.generate_stream(
            messages=messages,
            model=model,
            temperature=temperature,
        )
        async for kind, text in stream_reasoning_chunks(raw_stream):
            if kind == "content":
                content_parts.append(text)
                on_chunk(event_type, text)
            else:
                on_chunk(f"{event_type}_thinking", text)
        return "".join(content_parts)

    # No callback: use generate (simpler, no retry on stream for MVP)
    response = await generate_with_retry(llm, messages, model, temperature)
    return response.content
