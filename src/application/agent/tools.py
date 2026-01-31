"""Agent tools - definitions and executor for ReAct-style agent."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.api.routes.projects import get_store
from src.infrastructure.services.file_service import FileService
from src.infrastructure.services.terminal_service import TerminalService


def _get_workspace_path() -> str:
    """Get current workspace path."""
    store = get_store()
    current = store.get_current()
    return current.path if current else str(Path.cwd().resolve())


@dataclass
class ToolResult:
    """Result of tool execution."""
    success: bool
    content: str
    error: str | None = None
    tool: str = ""
    args: dict[str, Any] = field(default_factory=dict)


# Tool definitions for system prompt
AGENT_TOOLS_PROMPT = """
You have access to these tools. Use them when needed to accomplish the user's task.

Format your tool call as:
<tool_call>
{"tool": "TOOL_NAME", "arg1": "value1", "arg2": "value2"}
</tool_call>

Available tools:
1. read_file(path) - Read file content. path: relative to project root.
2. write_file(path, content) - Write content to file. path: relative to project root.
3. search_rag(query) - Search codebase semantically. query: search question.
4. run_terminal(command) - Run shell command. command: e.g. "ls -la", "pytest tests/".
5. list_files(path?) - List files in directory. path: optional, default "."

Rules:
- Use ONE tool call per response. If you need multiple tools, call one, wait for result, then call next.
- After receiving tool result (Observation), analyze it and either call another tool or give final answer.
- For write_file: only suggest safe changes. Do not overwrite critical files without explicit user request.
- For run_terminal: use simple commands. Avoid destructive commands (rm -rf, etc).
- When done, respond with your final answer WITHOUT a tool_call block.
"""


class ToolExecutor:
    """Executes agent tools with workspace context."""

    def __init__(
        self,
        workspace_path: str | None = None,
        rag=None,
    ) -> None:
        self._workspace = Path(workspace_path or _get_workspace_path()).resolve()
        self._file_service = FileService(root_path=str(self._workspace))
        self._terminal = TerminalService(cwd=str(self._workspace))
        self._rag = rag

    async def execute(self, tool: str, args: dict[str, Any]) -> ToolResult:
        """Execute tool with given args."""
        tool_lower = tool.lower().strip()
        if tool_lower == "read_file":
            return await self._read_file(args)
        if tool_lower == "write_file":
            return await self._write_file(args)
        if tool_lower == "search_rag":
            return await self._search_rag(args)
        if tool_lower == "run_terminal":
            return await self._run_terminal(args)
        if tool_lower == "list_files":
            return await self._list_files(args)
        return ToolResult(
            success=False,
            content="",
            error=f"Unknown tool: {tool}",
            tool=tool,
            args=args,
        )

    async def _read_file(self, args: dict) -> ToolResult:
        path = args.get("path", "").strip()
        if not path:
            return ToolResult(success=False, content="", error="path required", tool="read_file", args=args)
        result = self._file_service.read(path)
        if not result.success:
            return ToolResult(success=False, content="", error=result.error, tool="read_file", args=args)
        content = result.data["content"]
        lang = Path(path).suffix.lstrip(".") or "text"
        formatted = f"## File: {path}\n```{lang}\n{content}\n```"
        return ToolResult(success=True, content=formatted, tool="read_file", args=args)

    async def _write_file(self, args: dict) -> ToolResult:
        path = args.get("path", "").strip()
        content = args.get("content", "")
        if not path:
            return ToolResult(success=False, content="", error="path required", tool="write_file", args=args)
        result = self._file_service.write(path, content, create_backup=True)
        if not result.success:
            return ToolResult(success=False, content="", error=result.error, tool="write_file", args=args)
        return ToolResult(success=True, content=f"Written to {path}", tool="write_file", args=args)

    async def _search_rag(self, args: dict) -> ToolResult:
        query = args.get("query", "").strip()
        if not query:
            return ToolResult(success=False, content="", error="query required", tool="search_rag", args=args)
        if not self._rag:
            return ToolResult(success=False, content="", error="RAG not available", tool="search_rag", args=args)
        try:
            results = await self._rag.search(query, limit=5)
            if not results:
                return ToolResult(success=True, content="No results found.", tool="search_rag", args=args)
            parts = []
            for i, r in enumerate(results, 1):
                meta = r.metadata if hasattr(r, "metadata") else {}
                source = meta.get("source", meta.get("file", "unknown"))
                parts.append(f"### Result {i}\n**{source}**\n```\n{r.content}\n```")
            return ToolResult(success=True, content="\n\n".join(parts), tool="search_rag", args=args)
        except Exception as e:
            return ToolResult(success=False, content="", error=str(e), tool="search_rag", args=args)

    async def _run_terminal(self, args: dict) -> ToolResult:
        command = args.get("command", "").strip()
        if not command:
            return ToolResult(success=False, content="", error="command required", tool="run_terminal", args=args)
        result = await self._terminal.execute(command)
        if result.error:
            return ToolResult(
                success=False,
                content=f"stdout: {result.stdout}\nstderr: {result.stderr}",
                error=result.error,
                tool="run_terminal",
                args=args,
            )
        output = result.stdout
        if result.stderr:
            output += f"\n\nstderr:\n{result.stderr}"
        return ToolResult(success=True, content=output or "(no output)", tool="run_terminal", args=args)

    async def _list_files(self, args: dict) -> ToolResult:
        path = args.get("path", ".").strip() or "."
        result = self._file_service.get_tree(path, max_depth=1)
        if not result.success:
            return ToolResult(success=False, content="", error=result.error, tool="list_files", args=args)
        node = result.data["tree"]
        if not node.children:
            return ToolResult(success=True, content=f"Empty directory: {path}", tool="list_files", args=args)
        items = [f"{'📁' if c.is_dir else '📄'} {c.name}" for c in node.children]
        return ToolResult(success=True, content="\n".join(items), tool="list_files", args=args)
