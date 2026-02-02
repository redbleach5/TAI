"""Tests for FileService (path safety, tree, read/write)."""

from pathlib import Path

import pytest

from src.infrastructure.services.file_service import FileService


class TestFileServicePathSafety:
    """Tests for _is_safe_path (no path traversal)."""

    def test_path_inside_root_is_safe(self, tmp_path: Path):
        """Path under root is safe."""
        svc = FileService(root_path=str(tmp_path))
        sub = tmp_path / "src" / "main.py"
        sub.parent.mkdir(parents=True, exist_ok=True)
        sub.touch()
        assert svc._is_safe_path(sub) is True
        assert svc._is_safe_path(tmp_path) is True

    def test_path_traversal_outside_root_is_unsafe(self, tmp_path: Path):
        """Path escaping root via .. is unsafe."""
        svc = FileService(root_path=str(tmp_path))
        escape = tmp_path / "foo" / ".." / ".." / "etc" / "passwd"
        # resolve() normalizes: goes outside tmp_path
        resolved = escape.resolve()
        assert resolved != tmp_path and str(resolved) != str(tmp_path)
        assert svc._is_safe_path(escape) is False

    def test_absolute_path_outside_root_is_unsafe(self, tmp_path: Path):
        """Absolute path pointing outside root is unsafe."""
        svc = FileService(root_path=str(tmp_path))
        # Use another directory that is not under tmp_path
        other = tmp_path.resolve().parent / "other_outside"
        other.mkdir(exist_ok=True)
        try:
            assert svc._is_safe_path(other) is False
        finally:
            other.rmdir()
