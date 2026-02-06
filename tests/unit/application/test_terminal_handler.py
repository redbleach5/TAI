"""Tests for TerminalHandler — uses real command execution."""

import pytest

from src.application.chat.handlers.terminal_handler import TerminalHandler, _is_allowed


class TestIsAllowed:
    """Pure tests for _is_allowed function."""

    def test_allowed_commands(self):
        assert _is_allowed("ls -la") is True
        assert _is_allowed("git status") is True
        assert _is_allowed("python --version") is True
        assert _is_allowed("pytest tests/") is True
        assert _is_allowed("ruff check .") is True
        assert _is_allowed("echo hello") is True

    def test_disallowed_commands(self):
        assert _is_allowed("rm -rf /") is False
        assert _is_allowed("shutdown now") is False
        assert _is_allowed("reboot") is False
        assert _is_allowed("sudo anything") is False

    def test_empty_command(self):
        assert _is_allowed("") is False


class TestTerminalHandler:
    """Tests for @run handler."""

    @pytest.fixture()
    def handler(self):
        return TerminalHandler()

    @pytest.mark.asyncio()
    async def test_command_type(self, handler):
        assert handler.command_type == "run"

    @pytest.mark.asyncio()
    async def test_empty_argument(self, handler):
        result = await handler.execute("", workspace_path="/tmp")
        assert not result.success
        assert "@run requires" in result.error

    @pytest.mark.asyncio()
    async def test_disallowed_command(self, handler):
        result = await handler.execute("rm -rf /", workspace_path="/tmp")
        assert not result.success
        assert "not allowed" in result.content

    @pytest.mark.asyncio()
    async def test_echo_command(self, handler, tmp_path):
        result = await handler.execute("echo hello world", workspace_path=str(tmp_path))
        assert result.success
        assert "hello world" in result.content
        assert "Terminal:" in result.content

    @pytest.mark.asyncio()
    async def test_pwd_command(self, handler, tmp_path):
        result = await handler.execute("pwd", workspace_path=str(tmp_path))
        assert result.success
        assert str(tmp_path) in result.content

    @pytest.mark.asyncio()
    async def test_exit_code_shown(self, handler, tmp_path):
        result = await handler.execute("python3 -c \"exit(1)\"", workspace_path=str(tmp_path))
        assert result.success  # Command executed, even if exit code != 0
        assert "exit code: 1" in result.content

    @pytest.mark.asyncio()
    async def test_ls_command(self, handler, tmp_path):
        (tmp_path / "test.txt").write_text("hi")
        result = await handler.execute("ls", workspace_path=str(tmp_path))
        assert result.success
        assert "test.txt" in result.content
