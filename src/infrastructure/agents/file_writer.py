"""FileWriter Agent - safe file operations with backup."""

import shutil
from datetime import datetime
from pathlib import Path

# Patterns to exclude from file tree
EXCLUDED_PATTERNS = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "dist",
    "build",
    "*.egg-info",
    ".DS_Store",
    "*.pyc",
    "*.pyo",
    ".env",
    "output/backups",
}


def _should_exclude(path: Path) -> bool:
    """Check if path should be excluded from tree."""
    name = path.name
    for pattern in EXCLUDED_PATTERNS:
        if pattern.startswith("*"):
            if name.endswith(pattern[1:]):
                return True
        elif name == pattern:
            return True
    return False


class FileWriter:
    """Safe file writer with automatic backup."""

    def __init__(self, backup_dir: str = "output/backups") -> None:
        self._backup_dir = Path(backup_dir)
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    def _create_backup(self, file_path: Path) -> Path | None:
        """Create backup of existing file. Returns backup path or None."""
        if not file_path.exists():
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        relative = file_path.name
        backup_path = self._backup_dir / f"{relative}.{timestamp}.bak"
        
        shutil.copy2(file_path, backup_path)
        return backup_path

    def _is_safe_path(self, file_path: Path) -> bool:
        """Check path is within cwd or allowed temp directories (security)."""
        try:
            file_path.resolve().relative_to(Path.cwd())
            return True
        except ValueError:
            path_str = str(file_path.resolve())
            safe_prefixes = ("/tmp", "/var/folders", "/private/var/folders")
            return any(path_str.startswith(p) for p in safe_prefixes)

    def write_file(
        self,
        path: str | Path,
        content: str,
        create_backup: bool = True,
        create_dirs: bool = True,
    ) -> dict:
        """Write content to file with optional backup.
        
        Returns:
            {
                "success": bool,
                "path": str,
                "backup_path": str | None,
                "created": bool,  # True if file was created (didn't exist)
                "error": str | None
            }
        """
        file_path = Path(path).resolve()
        if not self._is_safe_path(file_path):
            return {
                "success": False,
                "path": str(file_path),
                "backup_path": None,
                "created": False,
                "error": f"Security: cannot write outside project directory: {file_path}",
            }

        try:
            # Create directories if needed
            if create_dirs:
                file_path.parent.mkdir(parents=True, exist_ok=True)

            # Backup existing file
            backup_path = None
            created = not file_path.exists()
            if create_backup and not created:
                backup_path = self._create_backup(file_path)

            # Write content
            file_path.write_text(content, encoding="utf-8")

            return {
                "success": True,
                "path": str(file_path),
                "backup_path": str(backup_path) if backup_path else None,
                "created": created,
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "path": str(file_path),
                "backup_path": None,
                "created": False,
                "error": str(e),
            }

    def read_file(self, path: str | Path) -> dict:
        """Read file content.
        
        Returns:
            {
                "success": bool,
                "path": str,
                "content": str | None,
                "error": str | None
            }
        """
        file_path = Path(path).resolve()
        if not self._is_safe_path(file_path):
            return {
                "success": False,
                "path": str(file_path),
                "content": None,
                "error": "Security: path is outside allowed directory",
            }
        try:
            content = file_path.read_text(encoding="utf-8")
            return {
                "success": True,
                "path": str(file_path),
                "content": content,
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "path": str(file_path),
                "content": None,
                "error": str(e),
            }

    def restore_backup(self, backup_path: str | Path, original_path: str | Path) -> dict:
        """Restore file from backup.
        
        Returns:
            {
                "success": bool,
                "restored_path": str,
                "error": str | None
            }
        """
        backup = Path(backup_path)
        original = Path(original_path)
        
        try:
            if not backup.exists():
                return {
                    "success": False,
                    "restored_path": str(original),
                    "error": f"Backup not found: {backup}",
                }
            
            shutil.copy2(backup, original)
            return {
                "success": True,
                "restored_path": str(original),
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "restored_path": str(original),
                "error": str(e),
            }

    def list_backups(self, filename: str | None = None) -> list[dict]:
        """List available backups, optionally filtered by filename."""
        backups = []
        for backup_file in self._backup_dir.glob("*.bak"):
            if filename and not backup_file.name.startswith(filename):
                continue
            
            # Parse timestamp from backup name: filename.YYYYMMDD_HHMMSS.bak
            parts = backup_file.stem.rsplit(".", 1)
            original_name = parts[0] if len(parts) > 1 else backup_file.stem
            timestamp = parts[1] if len(parts) > 1 else "unknown"
            
            backups.append({
                "backup_path": str(backup_file),
                "original_name": original_name,
                "timestamp": timestamp,
                "size": backup_file.stat().st_size,
            })
        
        return sorted(backups, key=lambda x: x["timestamp"], reverse=True)

    def get_file_tree(
        self,
        root: str | Path = ".",
        max_depth: int = 10,
    ) -> dict:
        """Get file tree structure.
        
        Returns:
            {
                "success": bool,
                "tree": {
                    "name": str,
                    "path": str,
                    "type": "file" | "directory",
                    "children": [...] | None,
                    "size": int | None,
                    "extension": str | None
                },
                "error": str | None
            }
        """
        root_path = Path(root).resolve()
        
        # Security check
        try:
            root_path.relative_to(Path.cwd())
        except ValueError:
            return {
                "success": False,
                "tree": None,
                "error": f"Security: cannot access outside project: {root_path}",
            }
        
        if not root_path.exists():
            return {
                "success": False,
                "tree": None,
                "error": f"Path not found: {root_path}",
            }
        
        def build_tree(path: Path, depth: int) -> dict | None:
            if _should_exclude(path):
                return None
            
            node = {
                "name": path.name or str(path),
                "path": str(path.relative_to(Path.cwd())),
                "type": "directory" if path.is_dir() else "file",
            }
            
            if path.is_file():
                node["size"] = path.stat().st_size
                node["extension"] = path.suffix.lstrip(".") if path.suffix else None
                node["children"] = None
            elif path.is_dir() and depth < max_depth:
                children = []
                try:
                    for child in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                        child_node = build_tree(child, depth + 1)
                        if child_node:
                            children.append(child_node)
                except PermissionError:
                    pass
                node["children"] = children
            else:
                node["children"] = []
            
            return node
        
        try:
            tree = build_tree(root_path, 0)
            return {
                "success": True,
                "tree": tree,
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "tree": None,
                "error": str(e),
            }

    def create_file(self, path: str | Path, is_directory: bool = False) -> dict:
        """Create a new file or directory.
        
        Returns:
            {
                "success": bool,
                "path": str,
                "type": "file" | "directory",
                "error": str | None
            }
        """
        file_path = Path(path).resolve()
        
        # Security check
        try:
            file_path.relative_to(Path.cwd())
        except ValueError:
            return {
                "success": False,
                "path": str(file_path),
                "type": "directory" if is_directory else "file",
                "error": f"Security: cannot create outside project: {file_path}",
            }
        
        try:
            if file_path.exists():
                return {
                    "success": False,
                    "path": str(file_path),
                    "type": "directory" if is_directory else "file",
                    "error": f"Already exists: {file_path}",
                }
            
            if is_directory:
                file_path.mkdir(parents=True, exist_ok=True)
            else:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.touch()
            
            return {
                "success": True,
                "path": str(file_path),
                "type": "directory" if is_directory else "file",
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "path": str(file_path),
                "type": "directory" if is_directory else "file",
                "error": str(e),
            }

    def delete_file(self, path: str | Path, create_backup: bool = True) -> dict:
        """Delete a file or directory.
        
        Returns:
            {
                "success": bool,
                "path": str,
                "backup_path": str | None,
                "error": str | None
            }
        """
        file_path = Path(path).resolve()
        
        # Security check
        try:
            file_path.relative_to(Path.cwd())
        except ValueError:
            return {
                "success": False,
                "path": str(file_path),
                "backup_path": None,
                "error": f"Security: cannot delete outside project: {file_path}",
            }
        
        if not file_path.exists():
            return {
                "success": False,
                "path": str(file_path),
                "backup_path": None,
                "error": f"Not found: {file_path}",
            }
        
        try:
            backup_path = None
            if create_backup and file_path.is_file():
                backup_path = self._create_backup(file_path)
            
            if file_path.is_dir():
                shutil.rmtree(file_path)
            else:
                file_path.unlink()
            
            return {
                "success": True,
                "path": str(file_path),
                "backup_path": str(backup_path) if backup_path else None,
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "path": str(file_path),
                "backup_path": None,
                "error": str(e),
            }

    def rename_file(self, old_path: str | Path, new_path: str | Path) -> dict:
        """Rename/move a file or directory.
        
        Returns:
            {
                "success": bool,
                "old_path": str,
                "new_path": str,
                "error": str | None
            }
        """
        old = Path(old_path).resolve()
        new = Path(new_path).resolve()
        
        # Security check
        try:
            old.relative_to(Path.cwd())
            new.relative_to(Path.cwd())
        except ValueError:
            return {
                "success": False,
                "old_path": str(old),
                "new_path": str(new),
                "error": "Security: cannot rename outside project directory",
            }
        
        if not old.exists():
            return {
                "success": False,
                "old_path": str(old),
                "new_path": str(new),
                "error": f"Not found: {old}",
            }
        
        if new.exists():
            return {
                "success": False,
                "old_path": str(old),
                "new_path": str(new),
                "error": f"Already exists: {new}",
            }
        
        try:
            new.parent.mkdir(parents=True, exist_ok=True)
            old.rename(new)
            return {
                "success": True,
                "old_path": str(old),
                "new_path": str(new),
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "old_path": str(old),
                "new_path": str(new),
                "error": str(e),
            }
