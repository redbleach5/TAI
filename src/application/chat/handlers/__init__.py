"""Chat command handlers package."""

from src.application.chat.handlers.base import CommandHandler, CommandResult
from src.application.chat.handlers.file_reader import FileReaderHandler
from src.application.chat.handlers.folder_reader import FolderReaderHandler
from src.application.chat.handlers.git_handler import DiffHandler, GitContextHandler
from src.application.chat.handlers.grep_handler import GrepHandler
from src.application.chat.handlers.help_handler import HelpHandler
from src.application.chat.handlers.rag_search import RAGSearchHandler
from src.application.chat.handlers.registry import (
    CommandRegistry,
    create_default_registry,
    get_default_registry,
)
from src.application.chat.handlers.terminal_handler import TerminalHandler
from src.application.chat.handlers.web_search import WebSearchHandler

__all__ = [
    "CommandHandler",
    "CommandResult",
    "CommandRegistry",
    "create_default_registry",
    "get_default_registry",
    "WebSearchHandler",
    "RAGSearchHandler",
    "FileReaderHandler",
    "FolderReaderHandler",
    "GitContextHandler",
    "DiffHandler",
    "GrepHandler",
    "TerminalHandler",
    "HelpHandler",
]
