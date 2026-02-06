"""Folder reader command handler (@folder) — include directory contents as context."""

import logging
from pathlib import Path

from src.application.chat.handlers.base import CommandHandler, CommandResult

logger = logging.getLogger(__name__)

# Limits
MAX_FILES = 50
MAX_TOTAL_CHARS = 30000
MAX_FILE_CHARS = 5000
SUPPORTED_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".toml", ".yaml", ".yml",
    ".md", ".txt", ".html", ".css", ".scss", ".sh", ".sql", ".graphql",
    ".rst", ".cfg", ".ini", ".env",
}
EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".ruff_cache", ".mypy_cache", "dist", "build",
    ".next", "coverage", ".tox",
}


class FolderReaderHandler(CommandHandler):
    """Handles @folder command — reads all files in a directory as context."""

    @property
    def command_type(self) -> str:
        return "folder"

    async def execute(self, argument: str, **context) -> CommandResult:
        """Read folder contents and return formatted context.

        Args:
            argument: Folder path (relative to workspace)
            **context: workspace_path — project root

        """
        if not argument.strip():
            return CommandResult(
                content="",
                success=False,
                error="@folder requires a directory path. Example: @folder src/api/routes",
            )

        try:
            raw = argument.strip()
            workspace_path = context.get("workspace_path")
            base = Path(workspace_path).resolve() if workspace_path else Path.cwd().resolve()
            folder_path = (base / raw).resolve()

            # Security: must be inside workspace
            try:
                folder_path.relative_to(base)
            except ValueError:
                return CommandResult(
                    content=f"[Access denied: {argument}]",
                    success=False,
                    error="Cannot access directories outside project",
                )

            if not folder_path.exists():
                return CommandResult(
                    content=f"[Directory not found: {argument}]",
                    success=False,
                    error=f"Directory does not exist: {argument}",
                )

            if not folder_path.is_dir():
                return CommandResult(
                    content=f"[Not a directory: {argument}]",
                    success=False,
                    error=f"Path is not a directory: {argument}",
                )

            # Collect files
            files_content: list[str] = []
            total_chars = 0
            file_count = 0

            for p in sorted(folder_path.rglob("*")):
                if file_count >= MAX_FILES:
                    break
                if total_chars >= MAX_TOTAL_CHARS:
                    break
                if not p.is_file():
                    continue
                # Skip excluded dirs
                if any(part in EXCLUDED_DIRS for part in p.relative_to(base).parts):
                    continue
                # Skip unsupported extensions
                if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
                    continue

                try:
                    content = p.read_text(encoding="utf-8", errors="replace")
                    if len(content) > MAX_FILE_CHARS:
                        content = content[:MAX_FILE_CHARS] + "\n... [truncated]"
                    rel = str(p.relative_to(base))
                    lang = p.suffix.lstrip(".") or "text"
                    files_content.append(f"### {rel}\n```{lang}\n{content}\n```")
                    total_chars += len(content)
                    file_count += 1
                except (OSError, UnicodeDecodeError):
                    continue

            if not files_content:
                return CommandResult(
                    content=f"[No readable files found in: {argument}]",
                    success=False,
                    error=f"No supported files in directory: {argument}",
                )

            header = f"## Folder: {argument} ({file_count} files)\n\n"
            truncation_note = ""
            if file_count >= MAX_FILES or total_chars >= MAX_TOTAL_CHARS:
                truncation_note = f"\n\n*[Showing {file_count} files, some content may be truncated]*"

            return CommandResult(
                content=header + "\n\n".join(files_content) + truncation_note,
            )

        except Exception as e:
            logger.warning("Folder read error for %s: %s", argument, e, exc_info=True)
            return CommandResult(
                content=f"[Folder read error: {e}]",
                success=False,
                error=str(e),
            )
