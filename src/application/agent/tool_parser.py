"""Tool parser - extracts tool calls from LLM response (ReAct format)."""

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ParsedToolCall:
    """Parsed tool call from LLM output."""
    tool: str
    args: dict[str, Any]
    raw: str


def parse_tool_call(content: str) -> ParsedToolCall | None:
    """Parse first tool call from LLM response.
    
    Expected format:
    <tool_call>
    {"tool": "read_file", "path": "src/main.py"}
    </tool_call>
    
    Returns:
        ParsedToolCall if found, None otherwise
    """
    pattern = r"<tool_call>\s*([\s\S]*?)\s*</tool_call>"
    match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    
    raw = match.group(1).strip()
    try:
        data = __import__("json").loads(raw)
        if not isinstance(data, dict):
            return None
        tool = data.get("tool", "").strip()
        if not tool:
            return None
        args = {k: v for k, v in data.items() if k != "tool"}
        return ParsedToolCall(tool=tool, args=args, raw=raw)
    except (ValueError, TypeError):
        return None


def strip_tool_call_from_content(content: str) -> str:
    """Remove tool_call block from content, return clean text."""
    pattern = r"<tool_call>\s*[\s\S]*?\s*</tool_call>"
    return re.sub(pattern, "", content, flags=re.IGNORECASE | re.DOTALL).strip()
