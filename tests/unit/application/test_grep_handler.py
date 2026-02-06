"""Tests for GrepHandler — uses tmp_path + real file search."""

import pytest

from src.application.chat.handlers.grep_handler import GrepHandler


@pytest.fixture()
def handler():
    return GrepHandler()


@pytest.fixture()
def workspace(tmp_path):
    """Workspace with searchable files."""
    (tmp_path / "main.py").write_text("def authenticate(user):\n    return True\n")
    (tmp_path / "utils.py").write_text("def helper():\n    pass\n")
    sub = tmp_path / "src"
    sub.mkdir()
    (sub / "service.py").write_text("class AuthService:\n    def login(self):\n        authenticate()\n")
    return tmp_path


class TestGrepHandler:
    """Tests for @grep handler."""

    @pytest.mark.asyncio()
    async def test_command_type(self, handler):
        assert handler.command_type == "grep"

    @pytest.mark.asyncio()
    async def test_empty_argument(self, handler):
        result = await handler.execute("", workspace_path="/tmp")
        assert not result.success
        assert "@grep requires" in result.error

    @pytest.mark.asyncio()
    async def test_search_finds_matches(self, handler, workspace):
        result = await handler.execute("authenticate", workspace_path=str(workspace))
        assert result.success
        assert "authenticate" in result.content

    @pytest.mark.asyncio()
    async def test_search_no_matches(self, handler, workspace):
        result = await handler.execute("nonexistent_function_xyz", workspace_path=str(workspace))
        assert result.success
        assert "No matches" in result.content

    @pytest.mark.asyncio()
    async def test_search_pattern_in_header(self, handler, workspace):
        result = await handler.execute("def helper", workspace_path=str(workspace))
        assert result.success
        assert "Search:" in result.content
        assert "`def helper`" in result.content

    @pytest.mark.asyncio()
    async def test_search_class(self, handler, workspace):
        result = await handler.execute("class AuthService", workspace_path=str(workspace))
        assert result.success
        assert "AuthService" in result.content
