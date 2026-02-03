"""Web search command handler (@web)."""

from src.application.chat.handlers.base import CommandHandler, CommandResult
from src.infrastructure.services.web_search import (
    format_search_results,
    multi_search,
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
            # Use multi-engine parallel search (config/context or env for keys)
            searxng_url = context.get("web_search_searxng_url")
            brave_api_key = context.get("web_search_brave_api_key")
            tavily_api_key = context.get("web_search_tavily_api_key")
            google_api_key = context.get("web_search_google_api_key")
            google_cx = context.get("web_search_google_cx")
            results = await multi_search(
                argument,
                max_results=10,
                timeout=12.0,
                use_cache=True,
                searxng_url=searxng_url,
                brave_api_key=brave_api_key,
                tavily_api_key=tavily_api_key,
                google_api_key=google_api_key,
                google_cx=google_cx,
            )
            content = format_search_results(results)
            return CommandResult(content=content)
        except Exception as e:
            return CommandResult(
                content=f"[Web search error: {e}]",
                success=False,
                error=str(e),
            )
