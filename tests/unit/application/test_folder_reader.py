"""Tests for FolderReaderHandler — zero mocks, uses tmp_path."""

import pytest

from src.application.chat.handlers.folder_reader import FolderReaderHandler


@pytest.fixture()
def handler():
    return FolderReaderHandler()


@pytest.fixture()
def workspace(tmp_path):
    """Create a workspace with files."""
    # src/main.py
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("print('hello')\n")
    (src / "utils.py").write_text("def add(a, b):\n    return a + b\n")
    # src/sub/
    sub = src / "sub"
    sub.mkdir()
    (sub / "helper.py").write_text("# helper\n")
    # README.md
    (tmp_path / "README.md").write_text("# Project\n")
    # Binary-like (no matching extension)
    (tmp_path / "image.png").write_bytes(b"\x89PNG fake")
    return tmp_path


class TestFolderReaderHandler:
    """Tests for @folder handler."""

    @pytest.mark.asyncio()
    async def test_command_type(self, handler):
        assert handler.command_type == "folder"

    @pytest.mark.asyncio()
    async def test_empty_argument(self, handler):
        result = await handler.execute("", workspace_path="/tmp")
        assert not result.success
        assert "@folder requires" in result.error

    @pytest.mark.asyncio()
    async def test_nonexistent_directory(self, handler, tmp_path):
        result = await handler.execute("nodir", workspace_path=str(tmp_path))
        assert not result.success
        assert "does not exist" in result.error

    @pytest.mark.asyncio()
    async def test_file_instead_of_directory(self, handler, workspace):
        result = await handler.execute("README.md", workspace_path=str(workspace))
        assert not result.success
        assert "not a directory" in result.error

    @pytest.mark.asyncio()
    async def test_path_traversal_denied(self, handler, workspace):
        result = await handler.execute("../../etc", workspace_path=str(workspace))
        assert not result.success
        assert "Access denied" in result.content

    @pytest.mark.asyncio()
    async def test_read_directory(self, handler, workspace):
        result = await handler.execute("src", workspace_path=str(workspace))
        assert result.success
        assert "main.py" in result.content
        assert "utils.py" in result.content
        assert "helper.py" in result.content
        assert "Folder: src" in result.content

    @pytest.mark.asyncio()
    async def test_skips_binary_files(self, handler, workspace):
        result = await handler.execute(".", workspace_path=str(workspace))
        assert result.success
        assert "image.png" not in result.content

    @pytest.mark.asyncio()
    async def test_skips_excluded_dirs(self, handler, workspace):
        pycache = workspace / "src" / "__pycache__"
        pycache.mkdir()
        (pycache / "cache.py").write_text("cached")
        result = await handler.execute("src", workspace_path=str(workspace))
        assert result.success
        assert "cache.py" not in result.content

    @pytest.mark.asyncio()
    async def test_empty_directory(self, handler, workspace):
        empty = workspace / "empty"
        empty.mkdir()
        result = await handler.execute("empty", workspace_path=str(workspace))
        assert not result.success
        assert "No readable files" in result.content

    @pytest.mark.asyncio()
    async def test_truncation_on_large_files(self, handler, workspace):
        big = workspace / "src" / "big.py"
        big.write_text("x" * 10000)
        result = await handler.execute("src", workspace_path=str(workspace))
        assert result.success
        assert "big.py" in result.content

    @pytest.mark.asyncio()
    async def test_file_count_in_header(self, handler, workspace):
        result = await handler.execute("src", workspace_path=str(workspace))
        assert result.success
        # Should have 3 files: main.py, utils.py, sub/helper.py
        assert "3 files" in result.content
