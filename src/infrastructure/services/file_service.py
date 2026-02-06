"""File Service - handles file system operations."""

import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


# Excluded directories
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "coverage",
    "output",
    "ssl",
}


@dataclass
class FileNode:
    """File tree node."""

    name: str
    path: str
    is_dir: bool
    children: list["FileNode"] = field(default_factory=list)
    size: int = 0
    git_status: str = ""


@dataclass
class FileResult:
    """Result of file operation."""

    success: bool
    data: dict | None = None
    error: str | None = None


class FileService:
    """Service for file system operations."""

    def __init__(
        self,
        root_path: str | None = None,
        backup_dir: str = "output/backups",
    ):
        """Initialize with root path for security checks."""
        self._root = Path(root_path).resolve() if root_path else Path.cwd().resolve()
        self._backup_dir = Path(backup_dir)

    def _is_safe_path(self, path: Path) -> bool:
        """Check if path is within root directory (no path traversal, no symlink escape)."""
        try:
            # resolve() follows symlinks — ensures the real path is under root
            resolved = path.resolve(strict=False)
            root_resolved = self._root.resolve(strict=False)
            # relative_to raises ValueError if path is not under root
            resolved.relative_to(root_resolved)

            # Extra check: if path exists and is a symlink, verify target is also under root
            if path.exists() and path.is_symlink():
                real_target = path.resolve(strict=True)
                real_target.relative_to(root_resolved)

            return True
        except (ValueError, OSError):
            return False
        except Exception as e:
            logger.debug("Path safety check failed for %s: %s", path, e)
            return False

    def _should_exclude(self, name: str) -> bool:
        """Check if directory should be excluded."""
        return name in EXCLUDED_DIRS or name.startswith(".")

    def get_tree(
        self,
        path: str | None = None,
        max_depth: int = 10,
    ) -> FileResult:
        """Get file tree.

        Args:
            path: Subdirectory (relative to root)
            max_depth: Maximum depth to traverse

        """
        target = self._root / path if path else self._root

        if not target.exists():
            return FileResult(success=False, error=f"Path not found: {path}")

        if not self._is_safe_path(target):
            return FileResult(success=False, error="Access denied")

        def build_tree(p: Path, depth: int) -> FileNode:
            node = FileNode(
                name=p.name or str(p),
                path=str(p.relative_to(self._root)),
                is_dir=p.is_dir(),
            )

            if p.is_dir() and depth < max_depth:
                try:
                    for child in sorted(p.iterdir()):
                        if self._should_exclude(child.name):
                            continue
                        node.children.append(build_tree(child, depth + 1))
                except PermissionError:
                    logger.debug("Permission denied scanning directory: %s", p)
            elif p.is_file():
                try:
                    node.size = p.stat().st_size
                except OSError:
                    logger.debug("Failed to stat file: %s", p)

            return node

        tree = build_tree(target, 0)
        return FileResult(success=True, data={"tree": tree})

    def read(self, path: str) -> FileResult:
        """Read file content."""
        target = self._root / path

        if not target.exists():
            return FileResult(success=False, error=f"File not found: {path}")

        if not target.is_file():
            return FileResult(success=False, error=f"Not a file: {path}")

        if not self._is_safe_path(target):
            return FileResult(success=False, error="Access denied")

        try:
            content = target.read_text(encoding="utf-8", errors="replace")
            return FileResult(
                success=True,
                data={"content": content, "size": len(content)},
            )
        except Exception as e:
            logger.warning("File read failed for %s: %s", target, e, exc_info=True)
            return FileResult(success=False, error=str(e))

    def write(
        self,
        path: str,
        content: str,
        create_backup: bool = True,
    ) -> FileResult:
        """Write file content.

        Args:
            path: File path (relative to root)
            content: Content to write
            create_backup: Whether to backup existing file

        """
        target = self._root / path

        if not self._is_safe_path(target):
            return FileResult(success=False, error="Access denied")

        try:
            # Backup if exists
            if create_backup and target.exists():
                self._backup_file(target)

            # Create parent directories
            target.parent.mkdir(parents=True, exist_ok=True)

            # Write
            target.write_text(content, encoding="utf-8")

            return FileResult(
                success=True,
                data={"path": str(target.relative_to(self._root))},
            )
        except Exception as e:
            logger.warning("File write failed for %s: %s", path, e)
            return FileResult(success=False, error=str(e))

    def create(
        self,
        path: str,
        is_directory: bool = False,
        content: str = "",
    ) -> FileResult:
        """Create file or directory."""
        target = self._root / path

        if not self._is_safe_path(target):
            return FileResult(success=False, error="Access denied")

        if target.exists():
            return FileResult(success=False, error=f"Already exists: {path}")

        try:
            if is_directory:
                target.mkdir(parents=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")

            return FileResult(
                success=True,
                data={"path": str(target.relative_to(self._root))},
            )
        except Exception as e:
            logger.warning("File create failed for %s: %s", path, e)
            return FileResult(success=False, error=str(e))

    def delete(
        self,
        path: str,
        create_backup: bool = True,
    ) -> FileResult:
        """Delete file or directory."""
        target = self._root / path

        if not target.exists():
            return FileResult(success=False, error=f"Not found: {path}")

        if not self._is_safe_path(target):
            return FileResult(success=False, error="Access denied")

        try:
            # Backup
            if create_backup:
                self._backup_file(target)

            # Delete
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()

            return FileResult(success=True, data={"deleted": path})
        except Exception as e:
            logger.warning("File delete failed for %s: %s", path, e)
            return FileResult(success=False, error=str(e))

    def rename(self, old_path: str, new_path: str) -> FileResult:
        """Rename/move file or directory."""
        source = self._root / old_path
        dest = self._root / new_path

        if not source.exists():
            return FileResult(success=False, error=f"Not found: {old_path}")

        if dest.exists():
            return FileResult(success=False, error=f"Already exists: {new_path}")

        if not self._is_safe_path(source) or not self._is_safe_path(dest):
            return FileResult(success=False, error="Access denied")

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            source.rename(dest)
            return FileResult(
                success=True,
                data={"old": old_path, "new": new_path},
            )
        except Exception as e:
            logger.warning("File rename failed %s -> %s: %s", old_path, new_path, e)
            return FileResult(success=False, error=str(e))

    def _backup_file(self, path: Path) -> Path | None:
        """Create backup of file."""
        if not path.exists():
            return None

        try:
            self._backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{path.name}.{timestamp}.bak"
            backup_path = self._backup_dir / backup_name

            if path.is_dir():
                shutil.copytree(path, backup_path)
            else:
                shutil.copy2(path, backup_path)

            return backup_path
        except Exception as e:
            logger.debug("Backup failed for %s: %s", path, e)
            return None
