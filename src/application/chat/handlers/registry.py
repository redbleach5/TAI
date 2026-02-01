"""Command handler registry - manages all command handlers."""

from src.application.chat.handlers.base import CommandHandler, CommandResult
from src.application.chat.handlers.web_search import WebSearchHandler
from src.application.chat.handlers.rag_search import RAGSearchHandler
from src.application.chat.handlers.file_reader import FileReaderHandler
from src.application.chat.handlers.help_handler import HelpHandler


class CommandRegistry:
    """Registry for command handlers."""
    
    def __init__(self):
        self._handlers: dict[str, CommandHandler] = {}
    
    def register(self, handler: CommandHandler) -> None:
        """Register a command handler."""
        self._handlers[handler.command_type.lower()] = handler
    
    def get(self, command_type: str) -> CommandHandler | None:
        """Get handler for command type."""
        return self._handlers.get(command_type.lower())
    
    def has(self, command_type: str) -> bool:
        """Check if handler exists for command type."""
        return command_type.lower() in self._handlers
    
    async def execute(
        self,
        command_type: str,
        argument: str,
        **context,
    ) -> CommandResult:
        """Execute command using appropriate handler.
        
        Args:
            command_type: Type of command (web, rag, code, etc.)
            argument: Command argument
            **context: Additional context for handlers
        
        Returns:
            CommandResult from handler or error result
        """
        handler = self.get(command_type)
        if not handler:
            return CommandResult(
                content=f"[Unknown command: @{command_type}]",
                success=False,
                error=f"No handler for command: {command_type}",
            )
        
        return await handler.execute(argument, **context)
    
    def list_commands(self) -> list[str]:
        """List all registered command types."""
        return list(self._handlers.keys())


def create_default_registry() -> CommandRegistry:
    """Create registry with all default handlers."""
    registry = CommandRegistry()
    
    # Register all handlers
    registry.register(WebSearchHandler())
    registry.register(RAGSearchHandler())
    registry.register(FileReaderHandler("code"))
    registry.register(FileReaderHandler("file"))
    registry.register(HelpHandler())
    
    return registry


def get_default_registry() -> CommandRegistry:
    """Get default command registry from container (for backward compatibility)."""
    from src.api.container import get_container
    return get_container().command_registry
