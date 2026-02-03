"""Base command handler interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CommandResult:
    """Result of command execution."""

    content: str
    success: bool = True
    error: str | None = None


class CommandHandler(ABC):
    """Base class for chat command handlers."""

    @property
    @abstractmethod
    def command_type(self) -> str:
        """Return command type this handler processes (e.g., 'web', 'rag')."""
        ...

    @abstractmethod
    async def execute(self, argument: str, **context) -> CommandResult:
        """Execute command with given argument.

        Args:
            argument: Command argument (text after @command)
            **context: Additional context (rag adapter, etc.)

        Returns:
            CommandResult with content or error
        """
        ...

    def can_handle(self, command_type: str) -> bool:
        """Check if this handler can process given command type."""
        return command_type.lower() == self.command_type.lower()
