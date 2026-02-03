"""Tests for reasoning parser (DeepSeek-R1, QwQ think blocks)."""

import pytest

from src.infrastructure.llm.reasoning_parser import (
    parse_reasoning_chunk,
    stream_reasoning_chunks,
    stream_with_reasoning,
)


class TestParseReasoningChunk:
    """Tests for parse_reasoning_chunk function."""

    def test_plain_content_no_think(self):
        """Plain content without think tags."""
        buffer, emitted = parse_reasoning_chunk("", "Hello world")
        assert buffer == ""
        assert emitted == [("content", "Hello world")]

    def test_think_block_complete(self):
        """Complete think block in one chunk."""
        buffer, emitted = parse_reasoning_chunk("", "<think>reasoning</think>answer")
        assert buffer == ""
        assert emitted == [("thinking", "reasoning"), ("content", "answer")]

    def test_think_block_incomplete(self):
        """Incomplete think block - should buffer."""
        buffer, emitted = parse_reasoning_chunk("", "<think>partial reasoning")
        assert buffer == "<think>partial reasoning"
        assert emitted == []

    def test_think_block_continues(self):
        """Continue buffered think block."""
        buffer, emitted = parse_reasoning_chunk("<think>partial", " reasoning</think>done")
        assert buffer == ""
        assert emitted == [("thinking", "partial reasoning"), ("content", "done")]

    def test_content_before_think(self):
        """Content before think block."""
        buffer, emitted = parse_reasoning_chunk("", "prefix<think>thought</think>suffix")
        assert buffer == ""
        # Should have content, thinking, content
        assert any(e[0] == "content" and "prefix" in e[1] for e in emitted)
        assert any(e[0] == "thinking" and "thought" in e[1] for e in emitted)
        assert any(e[0] == "content" and "suffix" in e[1] for e in emitted)

    def test_multiple_think_blocks(self):
        """Multiple think blocks in sequence."""
        buffer, emitted = parse_reasoning_chunk("", "<think>first</think>middle<think>second</think>end")
        # The parser handles first block, then re-parses with new content
        assert ("thinking", "first") in emitted
        assert any("middle" in e[1] for e in emitted if e[0] == "content")

    def test_empty_think_block(self):
        """Empty think block should not emit."""
        buffer, emitted = parse_reasoning_chunk("", "<think></think>content")
        assert buffer == ""
        assert emitted == [("content", "content")]

    def test_whitespace_only_think(self):
        """Whitespace-only think block should not emit."""
        buffer, emitted = parse_reasoning_chunk("", "<think>   </think>content")
        assert buffer == ""
        assert emitted == [("content", "content")]

    def test_empty_input(self):
        """Empty input."""
        buffer, emitted = parse_reasoning_chunk("", "")
        assert buffer == ""
        assert emitted == []

    def test_only_whitespace(self):
        """Only whitespace input."""
        buffer, emitted = parse_reasoning_chunk("", "   ")
        assert buffer == ""
        assert emitted == []

    def test_nested_angle_brackets(self):
        """Content with other angle brackets."""
        buffer, emitted = parse_reasoning_chunk("", "use <div> tag<think>reasoning</think>done")
        assert buffer == ""
        # Should extract thinking and content
        assert any(e[0] == "thinking" and "reasoning" in e[1] for e in emitted)
        assert any(e[0] == "content" for e in emitted)


class TestStreamWithReasoning:
    """Tests for stream_with_reasoning async function."""

    @pytest.mark.asyncio
    async def test_simple_stream(self):
        """Simple stream without think blocks."""

        async def chunks():
            yield "Hello "
            yield "world"

        content, thinking = await stream_with_reasoning(chunks(), None, "test")
        # Note: parser strips and joins, so spaces may be lost between chunks
        assert "Hello" in content
        assert "world" in content
        assert thinking == ""

    @pytest.mark.asyncio
    async def test_stream_with_think(self):
        """Stream with think block."""

        async def chunks():
            yield "<think>reasoning"
            yield "</think>answer"

        content, thinking = await stream_with_reasoning(chunks(), None, "test")
        assert content == "answer"
        assert thinking == "reasoning"

    @pytest.mark.asyncio
    async def test_callback_called(self):
        """Callback is called with events."""
        events = []

        def callback(event_type: str, text: str):
            events.append((event_type, text))

        async def chunks():
            yield "<think>thought</think>result"

        await stream_with_reasoning(chunks(), callback, "code")
        assert ("code_thinking", "thought") in events
        assert ("code", "result") in events

    @pytest.mark.asyncio
    async def test_remaining_buffer_emitted(self):
        """Remaining buffer emitted as content at end."""

        async def chunks():
            yield "partial content"

        content, _ = await stream_with_reasoning(chunks(), None, "test")
        assert content == "partial content"


class TestStreamReasoningChunks:
    """Tests for stream_reasoning_chunks async generator."""

    @pytest.mark.asyncio
    async def test_yields_content(self):
        """Yields content chunks."""

        async def chunks():
            yield "Hello world"

        result = []
        async for kind, text in stream_reasoning_chunks(chunks()):
            result.append((kind, text))

        assert result == [("content", "Hello world")]

    @pytest.mark.asyncio
    async def test_yields_thinking_and_content(self):
        """Yields both thinking and content."""

        async def chunks():
            yield "<think>reasoning</think>answer"

        result = []
        async for kind, text in stream_reasoning_chunks(chunks()):
            result.append((kind, text))

        assert result == [("thinking", "reasoning"), ("content", "answer")]

    @pytest.mark.asyncio
    async def test_buffered_content_yielded(self):
        """Buffered content yielded at end."""

        async def chunks():
            yield "start "
            yield "end"

        result = []
        async for kind, text in stream_reasoning_chunks(chunks()):
            result.append((kind, text))

        # Content is accumulated and stripped
        assert len(result) == 2
        assert all(k == "content" for k, _ in result)
