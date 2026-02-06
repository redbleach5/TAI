"""Tests for command_parser — pure parsing, zero mocks."""

import pytest

from src.infrastructure.services.command_parser import (
    CommandType,
    ParsedMessage,
    get_help_text,
    parse_message,
)


class TestParseMessage:
    """parse_message: extract @commands from user messages."""

    def test_empty_message(self):
        result = parse_message("")
        assert result.text == ""
        assert result.commands == []
        assert result.has_commands is False

    def test_plain_text_no_commands(self):
        result = parse_message("Just a normal message")
        assert result.text == "Just a normal message"
        assert result.has_commands is False
        assert result.commands == []

    def test_web_command(self):
        result = parse_message("@web python asyncio tutorial")
        assert result.has_commands is True
        assert len(result.commands) == 1
        assert result.commands[0].type == CommandType.WEB
        assert result.commands[0].argument == "python asyncio tutorial"

    def test_rag_command(self):
        result = parse_message("@rag how is auth implemented")
        assert result.has_commands is True
        assert result.commands[0].type == CommandType.RAG
        assert result.commands[0].argument == "how is auth implemented"

    def test_code_command(self):
        result = parse_message("@code src/main.py what does this do?")
        assert result.has_commands is True
        assert result.commands[0].type == CommandType.CODE
        assert "src/main.py" in result.commands[0].argument

    def test_file_command(self):
        result = parse_message("@file README.md")
        assert result.has_commands is True
        assert result.commands[0].type == CommandType.FILE
        assert result.commands[0].argument == "README.md"

    def test_clear_command(self):
        result = parse_message("@clear")
        assert result.has_commands is True
        assert result.commands[0].type == CommandType.CLEAR
        assert result.commands[0].argument == ""

    def test_help_command(self):
        result = parse_message("@help")
        assert result.has_commands is True
        assert result.commands[0].type == CommandType.HELP

    def test_multiple_commands(self):
        result = parse_message("@web python @rag auth explain the difference")
        assert result.has_commands is True
        assert len(result.commands) == 2
        types = {cmd.type for cmd in result.commands}
        assert CommandType.WEB in types
        assert CommandType.RAG in types

    def test_command_removed_from_text(self):
        result = parse_message("Tell me about @web python asyncio")
        assert "Tell me about" in result.text
        assert "@web" not in result.text

    def test_case_insensitive(self):
        result = parse_message("@WEB test query")
        assert result.has_commands is True
        assert result.commands[0].type == CommandType.WEB

    def test_command_at_start(self):
        result = parse_message("@rag find authentication code")
        assert result.has_commands is True
        assert result.commands[0].type == CommandType.RAG

    def test_text_before_command(self):
        result = parse_message("Before @web query")
        assert "Before" in result.text
        assert result.has_commands is True

    def test_unknown_command_ignored(self):
        result = parse_message("@unknown test")
        assert result.has_commands is False

    def test_whitespace_cleanup(self):
        result = parse_message("   @web query   extra    spaces   ")
        assert result.has_commands is True
        # Clean text should not have excessive whitespace
        assert "  " not in result.text

    # --- New command types ---

    def test_folder_command(self):
        result = parse_message("@folder src/api/routes")
        assert result.has_commands is True
        assert result.commands[0].type == CommandType.FOLDER
        assert result.commands[0].argument == "src/api/routes"

    def test_git_command(self):
        result = parse_message("@git")
        assert result.has_commands is True
        assert result.commands[0].type == CommandType.GIT
        assert result.commands[0].argument == ""

    def test_git_with_subcommand(self):
        result = parse_message("@git status")
        assert result.has_commands is True
        assert result.commands[0].type == CommandType.GIT
        assert "status" in result.commands[0].argument

    def test_diff_command(self):
        result = parse_message("@diff src/main.py")
        assert result.has_commands is True
        assert result.commands[0].type == CommandType.DIFF
        assert result.commands[0].argument == "src/main.py"

    def test_diff_no_argument(self):
        result = parse_message("@diff")
        assert result.has_commands is True
        assert result.commands[0].type == CommandType.DIFF

    def test_grep_command(self):
        result = parse_message("@grep def authenticate")
        assert result.has_commands is True
        assert result.commands[0].type == CommandType.GREP
        assert result.commands[0].argument == "def authenticate"

    def test_run_command(self):
        result = parse_message("@run pytest tests/ -v")
        assert result.has_commands is True
        assert result.commands[0].type == CommandType.RUN
        assert "pytest" in result.commands[0].argument

    def test_mixed_old_and_new_commands(self):
        result = parse_message("@git @grep authenticate @web python auth")
        assert result.has_commands is True
        assert len(result.commands) == 3
        types = {cmd.type for cmd in result.commands}
        assert CommandType.GIT in types
        assert CommandType.GREP in types
        assert CommandType.WEB in types


class TestGetHelpText:
    """get_help_text: returns help markdown."""

    def test_returns_non_empty(self):
        text = get_help_text()
        assert len(text) > 50

    def test_contains_all_commands(self):
        text = get_help_text()
        for cmd in ("@web", "@code", "@file", "@rag", "@folder", "@git", "@diff", "@grep", "@run", "@clear", "@help"):
            assert cmd in text

    def test_contains_table(self):
        text = get_help_text()
        assert "Command" in text
        assert "|" in text
