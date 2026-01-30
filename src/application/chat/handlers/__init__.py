"""Chat command handlers package."""

from src.application.chat.handlers.base import CommandHandler, CommandResult
from src.application.chat.handlers.registry import (
    CommandRegistry,
    create_default_registry,
    get_default_registry,
)
from src.application.chat.handlers.web_search import WebSearchHandler
from src.application.chat.handlers.rag_search import RAGSearchHandler
from src.application.chat.handlers.file_reader import FileReaderHandler
from src.application.chat.handlers.help_handler import HelpHandler

__all__ = [
    "CommandHandler",
    "CommandResult",
    "CommandRegistry",
    "create_default_registry",
    "get_default_registry",
    "WebSearchHandler",
    "RAGSearchHandler",
    "FileReaderHandler",
    "HelpHandler",
]
