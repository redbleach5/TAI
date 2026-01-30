"""Parser for reasoning models (DeepSeek-R1, QwQ) — extracts <think> and content."""

from collections.abc import AsyncIterator, Callable
from typing import Literal

ParsedKind = Literal["thinking", "content"]
THINK_OPEN = "<think>"
THINK_CLOSE = "</think>"


def parse_reasoning_chunk(
    buffer: str,
    chunk: str,
) -> tuple[str, list[tuple[ParsedKind, str]]]:
    """Parse stream chunk, yield (thinking, content) parts.

    Returns:
        (remaining_buffer, [(kind, text), ...])
    """
    buffer += chunk
    emitted: list[tuple[ParsedKind, str]] = []
    i = 0

    while i < len(buffer):
        if buffer[i : i + len(THINK_OPEN)] == THINK_OPEN:
            # Emit any content before this tag
            if i > 0:
                prev = buffer[:i].strip()
                if prev:
                    emitted.append(("content", prev))
            # Find closing tag
            end = buffer.find(THINK_CLOSE, i + len(THINK_OPEN))
            if end == -1:
                return (buffer[i:], emitted)
            think_content = buffer[i + len(THINK_OPEN) : end].strip()
            if think_content:
                emitted.append(("thinking", think_content))
            i = end + len(THINK_CLOSE)
        else:
            next_think = buffer.find(THINK_OPEN, i)
            if next_think == -1:
                rest = buffer[i:].strip()
                if rest:
                    emitted.append(("content", rest))
                return ("", emitted)
            content = buffer[i:next_think].strip()
            if content:
                emitted.append(("content", content))
            i = next_think

    return ("", emitted)


async def stream_with_reasoning(
    chunks: AsyncIterator[str],
    on_chunk: Callable[[str, str], None] | None,
    event_type: str,
) -> tuple[str, str]:
    """Consume stream, parse <think>, call on_chunk for thinking and content.

    Returns:
        (full_content, full_thinking)
    """
    content_parts: list[str] = []
    thinking_parts: list[str] = []
    buffer = ""

    async for chunk in chunks:
        buffer, emitted = parse_reasoning_chunk(buffer, chunk)
        for kind, text in emitted:
            if kind == "thinking":
                thinking_parts.append(text)
                if on_chunk:
                    on_chunk(f"{event_type}_thinking", text)
            else:
                content_parts.append(text)
                if on_chunk:
                    on_chunk(event_type, text)

    if buffer.strip():
        content_parts.append(buffer.strip())
        if on_chunk:
            on_chunk(event_type, buffer.strip())

    return ("".join(content_parts), "".join(thinking_parts))


async def stream_reasoning_chunks(
    chunks: AsyncIterator[str],
) -> AsyncIterator[tuple[ParsedKind, str]]:
    """Yield (kind, text) for each content or thinking chunk. Use for SSE."""
    buffer = ""
    async for chunk in chunks:
        buffer, emitted = parse_reasoning_chunk(buffer, chunk)
        for kind, text in emitted:
            yield (kind, text)
    if buffer.strip():
        yield ("content", buffer.strip())
