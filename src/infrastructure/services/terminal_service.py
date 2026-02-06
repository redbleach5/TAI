"""Terminal Service - handles shell command execution."""

import asyncio
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Allowed commands (whitelist)
ALLOWED_COMMANDS = {
    "python",
    "python3",
    "pip",
    "pytest",
    "ruff",
    "node",
    "npm",
    "npx",
    "git",
    "ls",
    "cat",
    "head",
    "tail",
    "grep",
    "find",
    "wc",
    "echo",
    "pwd",
    "cd",
    "mkdir",
    "rm",
    "cp",
    "mv",
    "touch",
    "make",
    "cargo",
    "go",
}

# Blocked patterns (security)
BLOCKED_PATTERNS = [
    "&&",
    "||",
    ";",
    "|",
    ">",
    "<",
    "`",
    "$",
    "eval",
    "exec",
]


@dataclass
class CommandResult:
    """Result of command execution."""

    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    error: str | None = None


class TerminalService:
    """Service for terminal/shell operations."""

    def __init__(
        self,
        cwd: str | None = None,
        timeout: float = 30.0,
    ):
        """Initialize with working directory and timeout."""
        self._cwd = cwd
        self._timeout = timeout

    def validate_command(self, command: str) -> tuple[bool, str]:
        """Validate command against whitelist and blocked patterns.

        Returns:
            (is_valid, error_message)

        """
        if not command.strip():
            return False, "Empty command"

        # Check blocked patterns
        for pattern in BLOCKED_PATTERNS:
            if pattern in command:
                return False, f"Blocked pattern: {pattern}"

        # Check whitelist
        cmd_name = command.split()[0]
        if cmd_name not in ALLOWED_COMMANDS:
            return False, f"Command not allowed: {cmd_name}"

        return True, ""

    async def execute(
        self,
        command: str,
        cwd: str | None = None,
        timeout: float | None = None,
    ) -> CommandResult:
        """Execute a shell command.

        Args:
            command: Command to execute
            cwd: Working directory (overrides default)
            timeout: Timeout in seconds (overrides default)

        Returns:
            CommandResult with output or error

        """
        # Validate
        is_valid, error = self.validate_command(command)
        if not is_valid:
            return CommandResult(
                success=False,
                error=error,
                exit_code=-1,
            )

        working_dir = cwd or self._cwd
        cmd_timeout = timeout or self._timeout

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=cmd_timeout,
            )

            return CommandResult(
                success=proc.returncode == 0,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                exit_code=proc.returncode or 0,
            )

        except asyncio.TimeoutError:
            logger.warning("Command timed out after %ss: %s", cmd_timeout, command)
            return CommandResult(
                success=False,
                error=f"Command timed out after {cmd_timeout}s",
                exit_code=-1,
            )
        except Exception as e:
            logger.warning("Command execution failed: %s — %s", command, e)
            return CommandResult(
                success=False,
                error=str(e),
                exit_code=-1,
            )

    async def stream(
        self,
        command: str,
        cwd: str | None = None,
    ):
        """Stream command output line by line.

        Yields:
            Lines of output (stdout and stderr combined)

        """
        # Validate
        is_valid, error = self.validate_command(command)
        if not is_valid:
            yield f"Error: {error}"
            return

        working_dir = cwd or self._cwd

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                yield line.decode("utf-8", errors="replace")

            await proc.wait()

        except Exception as e:
            logger.warning("Stream command failed: %s — %s", command, e)
            yield f"Error: {e}"

    def list_allowed_commands(self) -> list[str]:
        """List all allowed commands."""
        return sorted(ALLOWED_COMMANDS)
