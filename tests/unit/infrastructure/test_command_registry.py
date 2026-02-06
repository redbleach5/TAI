"""Tests for command registry — pure registry logic, zero mocks."""

import pytest

from src.application.chat.handlers.base import CommandHandler, CommandResult
from src.application.chat.handlers.registry import CommandRegistry, create_default_registry


class StubHandler(CommandHandler):
    """Minimal handler for testing (no external deps)."""

    def __init__(self, cmd_type: str):
        self._type = cmd_type

    @property
    def command_type(self) -> str:
        return self._type

    async def execute(self, argument: str, **context) -> CommandResult:
        return CommandResult(content=f"executed {self._type}: {argument}")


class TestCommandRegistry:
    """CommandRegistry: register, get, has, list."""

    def test_empty_registry(self):
        reg = CommandRegistry()
        assert reg.list_commands() == []
        assert reg.has("web") is False
        assert reg.get("web") is None

    def test_register_and_get(self):
        reg = CommandRegistry()
        handler = StubHandler("web")
        reg.register(handler)
        assert reg.has("web") is True
        assert reg.get("web") is handler

    def test_case_insensitive(self):
        reg = CommandRegistry()
        reg.register(StubHandler("Web"))
        assert reg.has("web") is True
        assert reg.has("WEB") is True
        assert reg.get("web") is not None

    def test_list_commands(self):
        reg = CommandRegistry()
        reg.register(StubHandler("web"))
        reg.register(StubHandler("rag"))
        reg.register(StubHandler("code"))
        commands = reg.list_commands()
        assert sorted(commands) == ["code", "rag", "web"]

    def test_multiple_handlers(self):
        reg = CommandRegistry()
        web = StubHandler("web")
        rag = StubHandler("rag")
        reg.register(web)
        reg.register(rag)
        assert reg.get("web") is web
        assert reg.get("rag") is rag

    def test_overwrite_handler(self):
        reg = CommandRegistry()
        h1 = StubHandler("web")
        h2 = StubHandler("web")
        reg.register(h1)
        reg.register(h2)
        assert reg.get("web") is h2

    @pytest.mark.asyncio
    async def test_execute_registered(self):
        reg = CommandRegistry()
        reg.register(StubHandler("web"))
        result = await reg.execute("web", "python tutorial")
        assert result.success is True
        assert "web" in result.content

    @pytest.mark.asyncio
    async def test_execute_unknown(self):
        reg = CommandRegistry()
        result = await reg.execute("unknown", "test")
        assert result.success is False
        assert result.error is not None


class TestCanHandle:
    """CommandHandler.can_handle: case-insensitive matching."""

    def test_can_handle_exact(self):
        handler = StubHandler("web")
        assert handler.can_handle("web") is True

    def test_can_handle_case_insensitive(self):
        handler = StubHandler("web")
        assert handler.can_handle("Web") is True
        assert handler.can_handle("WEB") is True

    def test_cannot_handle_other(self):
        handler = StubHandler("web")
        assert handler.can_handle("rag") is False


class TestCreateDefaultRegistry:
    """create_default_registry: creates registry with standard handlers."""

    def test_has_standard_commands(self):
        reg = create_default_registry()
        for cmd in ("web", "rag", "code", "file", "help"):
            assert reg.has(cmd), f"Missing handler for @{cmd}"

    def test_has_new_commands(self):
        reg = create_default_registry()
        for cmd in ("folder", "git", "diff", "grep", "run"):
            assert reg.has(cmd), f"Missing handler for @{cmd}"

    def test_list_has_expected_count(self):
        reg = create_default_registry()
        commands = reg.list_commands()
        # 10 handlers: web, rag, code, file, folder, help, git, diff, grep, run
        assert len(commands) >= 10
