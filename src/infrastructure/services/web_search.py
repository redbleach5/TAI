"""Web Search service - DuckDuckGo integration."""

from dataclasses import dataclass

import httpx


@dataclass
class SearchResult:
    """Single search result."""
    title: str
    url: str
    snippet: str


async def search_duckduckgo(
    query: str,
    max_results: int = 5,
    timeout: float = 10.0,
) -> list[SearchResult]:
    """Search DuckDuckGo and return results.
    
    Uses DuckDuckGo HTML API (no API key required).
    
    Args:
        query: Search query
        max_results: Maximum results to return
        timeout: Request timeout in seconds
    
    Returns:
        List of SearchResult objects
    """
    if not query.strip():
        return []
    
    # Use DuckDuckGo lite HTML version
    url = "https://lite.duckduckgo.com/lite/"
    params = {"q": query, "kl": "wt-wt"}  # wt-wt = no region
    
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; TAi/1.0)",
    }
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, data=params, headers=headers)
            response.raise_for_status()
            html = response.text
    except Exception as e:
        return [SearchResult(
            title="Search Error",
            url="",
            snippet=f"Failed to search: {e}",
        )]
    
    # Simple HTML parsing (no external deps)
    results = _parse_ddg_lite(html, max_results)
    return results


def _parse_ddg_lite(html: str, max_results: int) -> list[SearchResult]:
    """Parse DuckDuckGo lite HTML response."""
    results = []
    
    # Find result links - they're in specific table structure
    # Format: <a rel="nofollow" href="URL">TITLE</a>
    import re
    
    # Pattern for result links
    link_pattern = re.compile(
        r'<a rel="nofollow" href="([^"]+)"[^>]*>([^<]+)</a>',
        re.IGNORECASE
    )
    
    # Find snippets - they follow the links in <td> tags
    snippet_pattern = re.compile(
        r'<td[^>]*class="result-snippet"[^>]*>([^<]+)</td>',
        re.IGNORECASE
    )
    
    links = link_pattern.findall(html)
    snippets = snippet_pattern.findall(html)
    
    # Filter out DuckDuckGo internal links
    for i, (url, title) in enumerate(links):
        if not url.startswith("http"):
            continue
        if "duckduckgo.com" in url:
            continue
        
        snippet = snippets[len(results)] if len(results) < len(snippets) else ""
        
        # Clean up
        title = _clean_html(title).strip()
        snippet = _clean_html(snippet).strip()
        
        if title:
            results.append(SearchResult(
                title=title,
                url=url,
                snippet=snippet[:200] if snippet else "",
            ))
        
        if len(results) >= max_results:
            break
    
    return results


def _clean_html(text: str) -> str:
    """Remove HTML entities and tags."""
    import html
    text = html.unescape(text)
    # Remove any remaining tags
    import re
    text = re.sub(r'<[^>]+>', '', text)
    return text


def format_search_results(results: list[SearchResult]) -> str:
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


# Alternative: use free API endpoints
async def search_searxng(
    query: str,
    max_results: int = 5,
    instance: str = "https://search.bus-hit.me",
) -> list[SearchResult]:
    """Search using SearXNG public instance.
    
    SearXNG is a privacy-respecting metasearch engine.
    """
    if not query.strip():
        return []
    
    url = f"{instance}/search"
    params = {
        "q": query,
        "format": "json",
        "categories": "general",
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        return [SearchResult(
            title="Search Error",
            url="",
            snippet=f"Failed to search: {e}",
        )]
    
    results = []
    for item in data.get("results", [])[:max_results]:
        results.append(SearchResult(
            title=item.get("title", ""),
            url=item.get("url", ""),
            snippet=item.get("content", "")[:200],
        ))
    
    return results
