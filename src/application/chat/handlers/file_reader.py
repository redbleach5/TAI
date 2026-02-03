"""File reader command handler (@code, @file)."""

from pathlib import Path

from src.application.chat.handlers.base import CommandHandler, CommandResult


class FileReaderHandler(CommandHandler):
    """Handles @code and @file commands - reads file content."""

    def __init__(self, command: str = "code"):
        """Initialize with command type ('code' or 'file')."""
        self._command = command
        self._max_size = 10000  # Max characters to include

    @property
    def command_type(self) -> str:
        return self._command

    async def execute(self, argument: str, **context) -> CommandResult:
        """Read file and return content.

        Args:
            argument: File path (relative to workspace_root when provided)
            **context: Optional workspace_path — project root for resolving paths (Cursor-like).
        """
        if not argument.strip():
            return CommandResult(
                content="",
                success=False,
                error=f"@{self._command} requires a file path. Example: @{self._command} src/main.py",
            )

        try:
            raw = argument.strip()
            # Use workspace root when provided (same as Files API / Agent), else cwd
            workspace_path = context.get("workspace_path")
            if workspace_path:
                base = Path(workspace_path).resolve()
            else:
                base = Path.cwd().resolve()
            # Resolve path relative to base to prevent path traversal (e.g. ../../etc/passwd)
            file_path = (base / raw).resolve()
            try:
                file_path.relative_to(base)
            except ValueError:
                return CommandResult(
                    content=f"[Access denied: {argument}]",
                    success=False,
                    error="Cannot access files outside project directory",
                )

            if not file_path.exists():
                return CommandResult(
                    content=f"[File not found: {argument}]",
                    success=False,
                    error=f"File does not exist: {argument}",
                )

            if not file_path.is_file():
                return CommandResult(
                    content=f"[Not a file: {argument}]",
                    success=False,
                    error=f"Path is not a file: {argument}",
                )

            # Read content
            content = file_path.read_text(encoding="utf-8", errors="replace")

            # Truncate if too large
            truncated = False
            if len(content) > self._max_size:
                content = content[: self._max_size]
                truncated = True

            # Format output
            lang = file_path.suffix.lstrip(".") or "text"
            output = f"## File: {argument}\n```{lang}\n{content}\n```"
            if truncated:
                output += "\n\n*[File truncated - showing first 10KB]*"

            return CommandResult(content=output)

        except PermissionError:
            return CommandResult(
                content=f"[Permission denied: {argument}]",
                success=False,
                error="Permission denied",
            )
        except Exception as e:
            return CommandResult(
                content=f"[File read error: {e}]",
                success=False,
                error=str(e),
            )


# Pre-configured handlers
def code_handler() -> FileReaderHandler:
    """Create handler for @code command."""
    return FileReaderHandler("code")


def file_handler() -> FileReaderHandler:
    """Create handler for @file command."""
    return FileReaderHandler("file")
