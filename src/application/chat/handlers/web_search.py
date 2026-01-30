"""Web search command handler (@web)."""

from src.application.chat.handlers.base import CommandHandler, CommandResult
from src.infrastructure.services.web_search import (
    search_duckduckgo,
    format_search_results,
)


class WebSearchHandler(CommandHandler):
    """Handles @web command - searches the internet."""
    
    @property
    def command_type(self) -> str:
        return "web"
    
    async def execute(self, argument: str, **context) -> CommandResult:
        """Execute web search.
        
        Args:
            argument: Search query
        """
        if not argument.strip():
            return CommandResult(
                content="",
                success=False,
                error="Web search requires a query. Example: @web python async tutorial",
            )
        
        try:
            results = await search_duckduckgo(argument, max_results=5)
            content = format_search_results(results)
            return CommandResult(content=content)
        except Exception as e:
            return CommandResult(
                content=f"[Web search error: {e}]",
                success=False,
                error=str(e),
            )
