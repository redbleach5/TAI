"""Tests for tool parser (Agent ReAct format)."""

import pytest

from src.application.agent.tool_parser import (
    parse_tool_call,
    parse_all_tool_calls,
    strip_tool_call_from_content,
)


class TestParseToolCall:
    """Tests for parse_tool_call (single)."""

    def test_valid_single(self):
        """Parse single valid tool call."""
        content = '<tool_call>\n{"tool": "read_file", "path": "src/main.py"}\n</tool_call>'
        result = parse_tool_call(content)
        assert result is not None
        assert result.tool == "read_file"
        assert result.args == {"path": "src/main.py"}

    def test_no_tool_call(self):
        """No tool call returns None."""
        assert parse_tool_call("Just text") is None

    def test_invalid_json(self):
        """Invalid JSON returns None."""
        assert parse_tool_call("<tool_call>not json</tool_call>") is None


class TestParseAllToolCalls:
    """Tests for parse_all_tool_calls (B3 multi-file)."""

    def test_single_call(self):
        """Single tool call returns list of one."""
        content = '<tool_call>{"tool": "write_file", "path": "a.py", "content": "x"}</tool_call>'
        result = parse_all_tool_calls(content)
        assert len(result) == 1
        assert result[0].tool == "write_file"
        assert result[0].args["path"] == "a.py"

    def test_multiple_calls(self):
        """Multiple tool calls in one response."""
        content = """
<tool_call>{"tool": "write_file", "path": "a.py", "content": "a"}</tool_call>
<tool_call>{"tool": "write_file", "path": "b.py", "content": "b"}</tool_call>
"""
        result = parse_all_tool_calls(content)
        assert len(result) == 2
        assert result[0].args["path"] == "a.py"
        assert result[1].args["path"] == "b.py"

    def test_empty(self):
        """Empty content returns empty list."""
        assert parse_all_tool_calls("") == []
        assert parse_all_tool_calls("No tool calls here") == []

    def test_mixed_valid_invalid(self):
        """Skips invalid, keeps valid."""
        content = """
<tool_call>{"tool": "read_file", "path": "x"}</tool_call>
<tool_call>invalid</tool_call>
<tool_call>{"tool": "write_file", "path": "y", "content": ""}</tool_call>
"""
        result = parse_all_tool_calls(content)
        assert len(result) == 2
        assert result[0].tool == "read_file"
        assert result[1].tool == "write_file"


class TestStripToolCall:
    """Tests for strip_tool_call_from_content."""

    def test_strips_single(self):
        """Remove single tool call block."""
        content = "Before\n<tool_call>{\"tool\": \"x\"}</tool_call>\nAfter"
        assert "Before" in strip_tool_call_from_content(content)
        assert "After" in strip_tool_call_from_content(content)
        assert "tool_call" not in strip_tool_call_from_content(content)
