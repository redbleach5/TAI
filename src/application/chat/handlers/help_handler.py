"""Help command handler (@help)."""

from src.application.chat.handlers.base import CommandHandler, CommandResult
from src.infrastructure.services.command_parser import get_help_text


class HelpHandler(CommandHandler):
    """Handles @help command - shows available commands."""
    
    @property
    def command_type(self) -> str:
        return "help"
    
    async def execute(self, argument: str, **context) -> CommandResult:
        """Return help text."""
        return CommandResult(content=get_help_text())
