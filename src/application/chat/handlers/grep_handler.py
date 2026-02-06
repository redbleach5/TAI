"""Grep handler (@grep) — text search in codebase, injects matches as context."""

import asyncio
import logging
from pathlib import Path

from src.application.chat.handlers.base import CommandHandler, CommandResult

logger = logging.getLogger(__name__)

MAX_MATCHES = 30
MAX_OUTPUT_CHARS = 12000


class GrepHandler(CommandHandler):
    """Handles @grep — searches codebase by text pattern (complements @rag semantic search)."""

    @property
    def command_type(self) -> str:
        return "grep"

    async def execute(self, argument: str, **context) -> CommandResult:
        """Search codebase for text pattern.

        Args:
            argument: Search pattern (text or regex)
            **context: workspace_path

        """
        if not argument.strip():
            return CommandResult(
                content="",
                success=False,
                error="@grep requires a search pattern. Example: @grep def authenticate",
            )

        workspace_path = context.get("workspace_path")
        cwd = workspace_path or str(Path.cwd())
        pattern = argument.strip()

        # Try ripgrep first, fall back to grep
        output = await self._search_rg(pattern, cwd)
        if output is None:
            output = await self._search_grep(pattern, cwd)

        if not output or not output.strip():
            return CommandResult(
                content=f"[No matches found for: {pattern}]",
                success=True,
            )

        # Truncate
        truncated = ""
        if len(output) > MAX_OUTPUT_CHARS:
            output = output[:MAX_OUTPUT_CHARS]
            truncated = "\n\n*[Results truncated]*"

        return CommandResult(
            content=f"## Search: `{pattern}`\n```\n{output}\n```{truncated}",
        )

    async def _search_rg(self, pattern: str, cwd: str) -> str | None:
        """Search using ripgrep (fast, respects .gitignore)."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "rg", "--no-heading", "--line-number", "--color=never",
                f"--max-count={MAX_MATCHES}", "--max-columns=200",
                "--type-add", "code:*.{py,js,ts,tsx,jsx,json,toml,yaml,yml,md,html,css,sh,sql}",
                "--type=code",
                pattern,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            if proc.returncode in (0, 1):  # 1 = no matches
                return stdout.decode("utf-8", errors="replace")
        except (FileNotFoundError, asyncio.TimeoutError, OSError):
            pass
        return None

    async def _search_grep(self, pattern: str, cwd: str) -> str | None:
        """Fallback: search using grep."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "grep", "-rn", "--include=*.py", "--include=*.js", "--include=*.ts",
                "--include=*.json", "--include=*.md",
                f"--max-count={MAX_MATCHES}", pattern,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            if proc.returncode in (0, 1):
                return stdout.decode("utf-8", errors="replace")
        except (FileNotFoundError, asyncio.TimeoutError, OSError):
            pass
        return None
