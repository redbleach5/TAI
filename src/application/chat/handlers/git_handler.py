"""Git context handler (@git, @diff) — inject git status/diff as chat context."""

import asyncio
import logging
from pathlib import Path

from src.application.chat.handlers.base import CommandHandler, CommandResult

logger = logging.getLogger(__name__)

MAX_DIFF_CHARS = 15000
MAX_LOG_ENTRIES = 15


async def _run_git(args: list[str], cwd: str) -> tuple[int, str]:
    """Run git command and return (code, stdout)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        return proc.returncode or 0, stdout.decode("utf-8", errors="replace")
    except (asyncio.TimeoutError, FileNotFoundError, OSError) as e:
        logger.debug("Git command failed: %s", e)
        return 1, ""


class GitContextHandler(CommandHandler):
    """Handles @git — injects git status, recent log, and short diff as context."""

    @property
    def command_type(self) -> str:
        return "git"

    async def execute(self, argument: str, **context) -> CommandResult:
        """Get git context: status + log + diff summary.

        Args:
            argument: Optional filter (e.g. file path or 'log', 'status', 'diff')
            **context: workspace_path

        """
        workspace_path = context.get("workspace_path")
        cwd = workspace_path or str(Path.cwd())

        subcommand = (argument.strip().lower() if argument else "").split()[0] if argument and argument.strip() else ""
        parts: list[str] = []

        if subcommand in ("", "status", "all"):
            code, status_out = await _run_git(["status", "--short", "--branch"], cwd)
            if code == 0 and status_out.strip():
                parts.append(f"### Git Status\n```\n{status_out.strip()}\n```")

        if subcommand in ("", "log", "all"):
            code, log_out = await _run_git(
                ["log", "--oneline", f"-{MAX_LOG_ENTRIES}", "--no-decorate"], cwd,
            )
            if code == 0 and log_out.strip():
                parts.append(f"### Recent Commits\n```\n{log_out.strip()}\n```")

        if subcommand in ("", "diff", "all"):
            code, diff_out = await _run_git(["diff", "--stat"], cwd)
            if code == 0 and diff_out.strip():
                parts.append(f"### Diff Summary (unstaged)\n```\n{diff_out.strip()}\n```")
            code, diff_staged = await _run_git(["diff", "--cached", "--stat"], cwd)
            if code == 0 and diff_staged.strip():
                parts.append(f"### Diff Summary (staged)\n```\n{diff_staged.strip()}\n```")

        if not parts:
            return CommandResult(
                content="[No git information available — not a git repository or no changes]",
                success=False,
                error="Git info unavailable",
            )

        return CommandResult(content="## Git Context\n\n" + "\n\n".join(parts))


class DiffHandler(CommandHandler):
    """Handles @diff — injects detailed git diff as context.

    @diff              — full working tree diff (unstaged + staged)
    @diff <file>       — diff for specific file
    @diff --staged     — only staged changes
    """

    @property
    def command_type(self) -> str:
        return "diff"

    async def execute(self, argument: str, **context) -> CommandResult:
        """Get git diff.

        Args:
            argument: Optional file path or '--staged'
            **context: workspace_path

        """
        workspace_path = context.get("workspace_path")
        cwd = workspace_path or str(Path.cwd())
        arg = argument.strip() if argument else ""

        # Build git diff command
        diff_args = ["diff"]
        staged_args = ["diff", "--cached"]
        label = "Changes"

        if arg == "--staged":
            # Only staged
            code, diff_out = await _run_git(staged_args, cwd)
            label = "Staged Changes"
        elif arg:
            # Specific file diff (unstaged + staged)
            code_u, diff_unstaged = await _run_git(diff_args + ["--", arg], cwd)
            code_s, diff_staged = await _run_git(staged_args + ["--", arg], cwd)
            diff_out = ""
            if code_u == 0 and diff_unstaged.strip():
                diff_out += diff_unstaged.strip()
            if code_s == 0 and diff_staged.strip():
                if diff_out:
                    diff_out += "\n\n"
                diff_out += diff_staged.strip()
            label = f"Changes in {arg}"
        else:
            # Full diff (unstaged + staged)
            code_u, diff_unstaged = await _run_git(diff_args, cwd)
            code_s, diff_staged = await _run_git(staged_args, cwd)
            diff_out = ""
            if code_u == 0 and diff_unstaged.strip():
                diff_out += diff_unstaged.strip()
            if code_s == 0 and diff_staged.strip():
                if diff_out:
                    diff_out += "\n\n"
                diff_out += diff_staged.strip()

        if not diff_out or not diff_out.strip():
            return CommandResult(
                content="[No changes found]",
                success=True,
            )

        # Truncate if too large
        truncated = ""
        if len(diff_out) > MAX_DIFF_CHARS:
            diff_out = diff_out[:MAX_DIFF_CHARS]
            truncated = "\n\n*[Diff truncated — showing first 15KB]*"

        return CommandResult(
            content=f"## {label}\n```diff\n{diff_out}\n```{truncated}",
        )
