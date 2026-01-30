"""Web search command handler (@web)."""

from src.application.chat.handlers.base import CommandHandler, CommandResult
from src.infrastructure.services.web_search import (
    multi_search,
    format_search_results,
)


class WebSearchHandler(CommandHandler):
    """Handles @web command - searches the internet using multiple engines."""
    
    @property
    def command_type(self) -> str:
        return "web"
    
    async def execute(self, argument: str, **context) -> CommandResult:
        """Execute web search using multiple engines in parallel.
        
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
            # Use multi-engine parallel search with caching
            results = await multi_search(
                argument,
                max_results=8,
                timeout=8.0,
                use_cache=True,
            )
            content = format_search_results(results)
            return CommandResult(content=content)
        except Exception as e:
            return CommandResult(
                content=f"[Web search error: {e}]",
                success=False,
                error=str(e),
            )
