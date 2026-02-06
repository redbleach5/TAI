"""RAG search command handler (@rag)."""

import logging

from src.application.chat.handlers.base import CommandHandler, CommandResult
from src.domain.ports.rag import RAGPort

logger = logging.getLogger(__name__)


class RAGSearchHandler(CommandHandler):
    """Handles @rag command - searches codebase via RAG."""

    @property
    def command_type(self) -> str:
        """Return command type ('rag')."""
        return "rag"

    async def execute(self, argument: str, **context) -> CommandResult:
        """Execute RAG search.

        Args:
            argument: Search query
            **context: Must contain 'rag' - RAGPort instance

        """
        if not argument.strip():
            return CommandResult(
                content="",
                success=False,
                error="RAG search requires a query. Example: @rag how auth works",
            )

        rag: RAGPort | None = context.get("rag")
        if not rag:
            return CommandResult(
                content="[RAG not available - index project first]",
                success=False,
                error="RAG adapter not configured",
            )

        try:
            chunks = await rag.search(argument, limit=10)
            if not chunks:
                return CommandResult(
                    content=f"[No results found for: {argument}]",
                    success=True,
                )

            # Format results
            context_parts = [f"## RAG Results for: {argument}\n"]
            for c in chunks:
                source = c.metadata.get("source", "unknown")
                context_parts.append(f"### {source}\n```\n{c.content}\n```")

            return CommandResult(content="\n".join(context_parts))
        except Exception as e:
            logger.warning("RAG search failed for query=%s: %s", argument, e, exc_info=True)
            return CommandResult(
                content=f"[RAG error: {e}]",
                success=False,
                error=str(e),
            )
