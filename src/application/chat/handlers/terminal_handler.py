"""Terminal handler (@run) — execute command and inject output as context."""

import asyncio
import logging
import shlex
from pathlib import Path

from src.application.chat.handlers.base import CommandHandler, CommandResult

logger = logging.getLogger(__name__)

MAX_OUTPUT_CHARS = 10000
TIMEOUT_SECONDS = 15

# Allowed commands (prefix whitelist for safety)
ALLOWED_PREFIXES = (
    "ls", "dir", "cat", "head", "tail", "wc", "find", "tree",
    "python", "python3", "pip", "node", "npm", "npx",
    "git", "rg", "grep", "awk", "sed", "sort", "uniq", "cut",
    "echo", "env", "which", "whoami", "pwd", "date",
    "pytest", "ruff", "mypy", "black", "isort",
    "cargo", "go", "make", "cmake",
    "docker", "kubectl",
    "curl", "wget",
)

# Blocked shell metacharacters (checked on raw input)
_BLOCKED_PATTERNS = ("&&", "||", ";", "|", ">", "<", "`", "$(")


def _is_allowed(command: str) -> bool:
    """Check if command is in the allowed whitelist using safe parsing."""
    try:
        parts = shlex.split(command.strip())
    except ValueError:
        return False
    if not parts:
        return False
    return parts[0].lower() in ALLOWED_PREFIXES


def _has_blocked_pattern(command: str) -> str | None:
    """Return the first blocked pattern found in raw command, or None."""
    for pattern in _BLOCKED_PATTERNS:
        if pattern in command:
            return pattern
    return None


class TerminalHandler(CommandHandler):
    """Handles @run — executes a shell command and injects output as context."""

    @property
    def command_type(self) -> str:
        return "run"

    async def execute(self, argument: str, **context) -> CommandResult:
        """Execute command and return output.

        Args:
            argument: Shell command to execute
            **context: workspace_path

        """
        if not argument.strip():
            return CommandResult(
                content="",
                success=False,
                error="@run requires a command. Example: @run pytest tests/unit/ -v --tb=short",
            )

        command = argument.strip()
        workspace_path = context.get("workspace_path")
        cwd = workspace_path or str(Path.cwd())

        # Check for shell metacharacters on raw input first
        blocked = _has_blocked_pattern(command)
        if blocked:
            return CommandResult(
                content=f"[Blocked pattern in command: {blocked}]",
                success=False,
                error=f"Shell metacharacter '{blocked}' is not allowed for security reasons.",
            )

        # Safety check
        if not _is_allowed(command):
            try:
                first_word = shlex.split(command)[0]
            except (ValueError, IndexError):
                first_word = command
            return CommandResult(
                content=f"[Command not allowed: {first_word}]",
                success=False,
                error=f"Command '{first_word}' is not in the allowed list. "
                       f"Allowed: {', '.join(ALLOWED_PREFIXES[:10])}...",
            )

        try:
            args = shlex.split(command)
            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT_SECONDS)
            output = stdout.decode("utf-8", errors="replace") if stdout else ""
            exit_code = proc.returncode or 0

            truncated = ""
            if len(output) > MAX_OUTPUT_CHARS:
                output = output[:MAX_OUTPUT_CHARS]
                truncated = "\n... [output truncated]"

            header = f"## Terminal: `{command}`"
            if exit_code != 0:
                header += f" (exit code: {exit_code})"

            return CommandResult(
                content=f"{header}\n```\n{output}{truncated}\n```",
            )

        except asyncio.TimeoutError:
            return CommandResult(
                content=f"[Command timed out after {TIMEOUT_SECONDS}s: {command}]",
                success=False,
                error=f"Command timed out after {TIMEOUT_SECONDS}s",
            )
        except Exception as e:
            logger.warning("Terminal handler error: %s", e, exc_info=True)
            return CommandResult(
                content=f"[Command execution error: {e}]",
                success=False,
                error=str(e),
            )
