"""Agent tools - definitions and executor for ReAct-style agent."""

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.api.dependencies import get_store
from src.infrastructure.services.file_service import FileService
from src.infrastructure.services.terminal_service import TerminalService

# Type for optional web search: (query: str) -> formatted results string
WebSearchRun = Callable[[str], Awaitable[str]]


def _is_project_indexed() -> bool:
    """Whether current project is marked as indexed in store."""
    current = get_store().get_current()
    return bool(current and getattr(current, "indexed", False))


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
    proposed_edit: dict | None = None  # When propose_edits and write_file: {path, content, old_content?}
    report_path: str | None = None  # C3.1: when run_project_analysis, path to report (e.g. docs/ANALYSIS_REPORT.md)


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
3. search_rag(query) - Search codebase semantically. query: search question. If no results, project may need indexing — use get_index_status then index_workspace if needed.
4. run_terminal(command, cwd?, timeout_seconds?) - Run shell command in project root or subfolder. command: e.g. "ls -la", "npm install", "pytest tests/". cwd: optional subfolder relative to project root (e.g. "bot", "frontend"). timeout_seconds: optional, max 300 (use for npm install, pip install).
5. list_files(path?) - List files in directory. path: optional, default ".".
6. get_index_status() - Check if project is indexed for code search. Use when user asks about codebase but search_rag returns nothing.
7. index_workspace(incremental?) - Index the project for semantic search. Call when user needs codebase search but project is not indexed. incremental: optional, default true (faster).
8. run_project_analysis(question?) - Run deep project analysis (architecture, quality, recommendations). Saves report to docs/ANALYSIS_REPORT.md. Use when user asks to analyze the project or "проанализируй проект". question: optional, specific question to answer in the report.
9. web_search(query) - Search the internet for current information. Use for: news, best practices, documentation, recent APIs, refactoring advice, or any up-to-date information. query: search phrase (e.g. "Python asyncio best practices 2024", "today news summary").

Rules:
- For current information (news, best practices, recent docs, refactoring advice): use web_search(query). Do not claim you have no internet — call web_search first.
- You can use multiple tool calls in one response when editing several files (e.g. several write_file blocks).
- For other tools (read_file, search_rag, etc.), use one at a time, wait for result, then call next.
- After receiving tool result (Observation), analyze it and either call another tool or give final answer. You MUST always add a short summary or final answer in plain text for the user (e.g. "Tests passed: 12" or "Command completed. Output: ..."). Never end your turn with only a tool call.
- For write_file: only suggest safe changes. Do not overwrite critical files without explicit user request.
- For run_terminal: use simple commands. Avoid destructive commands (rm -rf, etc).
- When done, respond with your final answer WITHOUT a tool_call block.
"""


# C3.1: (path, question?) -> (summary, report_path)
DeepAnalyzerRun = Callable[[str, str | None], Awaitable[tuple[str, str]]]


class ToolExecutor:
    """Executes agent tools with workspace context."""

    def __init__(
        self,
        workspace_path: str | None = None,
        rag=None,
        propose_edits: bool = False,
        deep_analyzer_run: DeepAnalyzerRun | None = None,
        web_search_run: WebSearchRun | None = None,
    ) -> None:
        self._workspace = Path(workspace_path or _get_workspace_path()).resolve()
        self._file_service = FileService(root_path=str(self._workspace))
        self._terminal = TerminalService(cwd=str(self._workspace))
        self._rag = rag
        self._propose_edits = propose_edits
        self._deep_analyzer_run = deep_analyzer_run
        self._web_search_run = web_search_run

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
        if tool_lower == "get_index_status":
            return await self._get_index_status(args)
        if tool_lower == "index_workspace":
            return await self._index_workspace(args)
        if tool_lower == "run_project_analysis":
            return await self._run_project_analysis(args)
        if tool_lower == "web_search":
            return await self._web_search(args)
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
        if self._propose_edits:
            old_content = ""
            read_result = self._file_service.read(path)
            if read_result.success:
                old_content = read_result.data.get("content", "")
            return ToolResult(
                success=True,
                content=f"Proposed edit for {path} (pending user approval)",
                tool="write_file",
                args=args,
                proposed_edit={"path": path, "content": content, "old_content": old_content},
            )
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
                hint = ""
                if not _is_project_indexed():
                    hint = " Project may not be indexed. Use get_index_status() to check, then index_workspace() to index the project and search again."
                return ToolResult(
                    success=True,
                    content="No results found." + hint,
                    tool="search_rag",
                    args=args,
                )
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
        cwd = args.get("cwd", "").strip() or None
        work_dir = str(self._workspace)
        if cwd:
            sub = (self._workspace / cwd).resolve()
            try:
                sub.relative_to(self._workspace)
            except ValueError:
                return ToolResult(
                    success=False,
                    content="",
                    error="cwd must be inside project",
                    tool="run_terminal",
                    args=args,
                )
            if not sub.exists() or not sub.is_dir():
                return ToolResult(
                    success=False,
                    content="",
                    error=f"Directory does not exist: {cwd}",
                    tool="run_terminal",
                    args=args,
                )
            work_dir = str(sub)
        timeout_sec = args.get("timeout_seconds")
        if timeout_sec is not None:
            try:
                timeout_sec = min(300, max(5, int(timeout_sec)))
            except (TypeError, ValueError):
                timeout_sec = 30
        else:
            timeout_sec = 30
        result = await self._terminal.execute(command, cwd=work_dir, timeout=timeout_sec)
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

    async def _get_index_status(self, args: dict) -> ToolResult:
        """Return whether project is indexed so model can suggest or trigger indexing."""
        current = get_store().get_current()
        if not current:
            return ToolResult(
                success=True,
                content="No project selected. User should open a folder (workspace) first.",
                tool="get_index_status",
                args=args,
            )
        indexed = getattr(current, "indexed", False)
        files_count = getattr(current, "files_count", 0)
        last_indexed = getattr(current, "last_indexed", None)
        lines = [
            f"Project: {current.name}",
            f"Indexed: {indexed}",
            f"Files in index: {files_count}",
        ]
        if last_indexed:
            lines.append(f"Last indexed: {last_indexed}")
        if not indexed:
            lines.append("You can call index_workspace() to index the project for code search.")
        return ToolResult(success=True, content="\n".join(lines), tool="get_index_status", args=args)

    async def _index_workspace(self, args: dict) -> ToolResult:
        """Index current workspace for RAG/search. User may forget to index — model can trigger this."""
        incremental = args.get("incremental", True)
        if isinstance(incremental, str):
            incremental = incremental.strip().lower() not in ("false", "0", "no")
        if not self._rag:
            return ToolResult(
                success=False,
                content="",
                error="RAG not available; indexing disabled.",
                tool="index_workspace",
                args=args,
            )
        try:
            stats = await self._rag.index_path(
                str(self._workspace),
                incremental=incremental,
                generate_map=True,
            )
            current = get_store().get_current()
            if current:
                from datetime import datetime
                get_store().update_project(
                    current.id,
                    indexed=True,
                    files_count=stats.get("files_found", 0),
                    last_indexed=datetime.now().isoformat(),
                )
            summary = f"Indexed: {stats.get('files_found', 0)} files, {stats.get('total_chunks', 0)} chunks."
            return ToolResult(success=True, content=summary, tool="index_workspace", args=args)
        except Exception as e:
            return ToolResult(
                success=False,
                content="",
                error=str(e),
                tool="index_workspace",
                args=args,
            )

    async def _run_project_analysis(self, args: dict) -> ToolResult:
        """C3.1: Run deep project analysis, save report to docs/ANALYSIS_REPORT.md, return summary + report_path."""
        if not self._deep_analyzer_run:
            return ToolResult(
                success=False,
                content="",
                error="Deep analysis not available (run_project_analysis not configured).",
                tool="run_project_analysis",
                args=args,
            )
        question = args.get("question", "").strip() or None
        try:
            summary, report_path = await self._deep_analyzer_run(str(self._workspace), question)
            content = summary
            if report_path:
                content += f"\n\nReport path: {report_path}"
            return ToolResult(
                success=True,
                content=content,
                tool="run_project_analysis",
                args=args,
                report_path=report_path or None,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                content="",
                error=str(e),
                tool="run_project_analysis",
                args=args,
            )

    async def _web_search(self, args: dict) -> ToolResult:
        """Search the web for current info, best practices, news. Uses backend multi_search if configured."""
        query = args.get("query", "").strip()
        if not query:
            return ToolResult(success=False, content="", error="query required", tool="web_search", args=args)
        if not self._web_search_run:
            return ToolResult(
                success=False,
                content="",
                error="Web search is not configured. User can set BRAVE_API_KEY or TAVILY_API_KEY in settings.",
                tool="web_search",
                args=args,
            )
        try:
            content = await self._web_search_run(query)
            if not content or not content.strip():
                return ToolResult(
                    success=True,
                    content="No results found. Try different keywords or check API keys (Brave/Tavily) in settings.",
                    tool="web_search",
                    args=args,
                )
            return ToolResult(success=True, content=content, tool="web_search", args=args)
        except Exception as e:
            return ToolResult(
                success=False,
                content="",
                error=str(e),
                tool="web_search",
                args=args,
            )
