"""Formatting of web search results for LLM context."""

from typing import Protocol


class SearchResultLike(Protocol):
    """Protocol for search result objects (title, url, snippet)."""

    title: str
    url: str
    snippet: str


def format_search_results(results: list[SearchResultLike]) -> str:
    """Format search results for LLM context."""
    if not results:
        return "[No search results found]"

    lines = ["## Web Search Results\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"### {i}. {r.title}")
        if r.url:
            lines.append(f"URL: {r.url}")
        if r.snippet:
            lines.append(f"{r.snippet}")
        lines.append("")

    return "\n".join(lines)
