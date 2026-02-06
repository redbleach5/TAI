"""Command Parser - handles @commands in chat messages."""

import re
from dataclasses import dataclass, field
from enum import Enum


class CommandType(Enum):
    """Types of quick commands."""

    WEB = "web"  # @web query - search the web
    CODE = "code"  # @code file.py - include file in context
    FILE = "file"  # @file path - read file content
    RAG = "rag"  # @rag query - search codebase
    FOLDER = "folder"  # @folder path - include directory contents
    GIT = "git"  # @git - git status, log, diff summary
    DIFF = "diff"  # @diff [file] - git diff as context
    GREP = "grep"  # @grep pattern - text search in codebase
    RUN = "run"  # @run command - execute command, inject output
    CLEAR = "clear"  # @clear - clear context
    HELP = "help"  # @help - show available commands


@dataclass
class ParsedCommand:
    """A parsed command from user message."""

    type: CommandType
    argument: str = ""
    raw: str = ""


@dataclass
class ParsedMessage:
    """Parsed user message with commands extracted."""

    text: str  # Clean text without commands
    commands: list[ParsedCommand] = field(default_factory=list)
    has_commands: bool = False


# Command patterns
COMMAND_PATTERN = re.compile(
    r"@(web|code|file|rag|folder|git|diff|grep|run|clear|help)(?:\s+([^\n@]+))?",
    re.IGNORECASE,
)


def parse_message(message: str) -> ParsedMessage:
    """Parse message and extract @commands.

    Supported commands:
    - @web <query> - Search the web
    - @code <file> - Include code file
    - @file <path> - Read any file
    - @rag <query> - Search codebase with RAG
    - @clear - Clear conversation context
    - @help - Show available commands

    Example:
        "@web python asyncio tutorial how to use"
        "@code src/main.py what does this do?"
        "@rag authentication how is it implemented"

    """
    if not message:
        return ParsedMessage(text="")

    commands: list[ParsedCommand] = []

    # Find all commands
    for match in COMMAND_PATTERN.finditer(message):
        cmd_type = match.group(1).lower()
        argument = (match.group(2) or "").strip()
        raw = match.group(0)

        try:
            commands.append(
                ParsedCommand(
                    type=CommandType(cmd_type),
                    argument=argument,
                    raw=raw,
                )
            )
        except ValueError:
            # Unknown command type, skip
            continue

    # Remove commands from text
    clean_text = COMMAND_PATTERN.sub("", message).strip()
    # Clean up extra whitespace
    clean_text = re.sub(r"\s+", " ", clean_text).strip()

    return ParsedMessage(
        text=clean_text,
        commands=commands,
        has_commands=len(commands) > 0,
    )


def get_help_text() -> str:
    """Return help text for available commands."""
    return """## Quick Commands

| Command | Description | Example |
|---------|-------------|---------|
| `@web <query>` | Search the web | `@web python async tutorial` |
| `@code <file>` | Include code file | `@code src/main.py` |
| `@file <path>` | Read any file | `@file README.md` |
| `@folder <path>` | Include entire directory | `@folder src/api/routes` |
| `@rag <query>` | Semantic codebase search | `@rag how auth works` |
| `@grep <pattern>` | Text search in codebase | `@grep def authenticate` |
| `@git` | Git status, log, diff summary | `@git` or `@git status` |
| `@diff [file]` | Git diff (all or specific file) | `@diff` or `@diff src/main.py` |
| `@run <command>` | Execute command, show output | `@run pytest tests/ -v` |
| `@clear` | Clear context | `@clear` |
| `@help` | Show this help | `@help` |

**Tips:**
- Commands can be combined: `@web python @rag auth explain the difference`
- Commands are processed before the LLM sees your message
- `@rag` — semantic search (by meaning), `@grep` — exact text search (by pattern)
- `@git` shows overview, `@diff` shows full diff content
"""
