"""Web Search service - multi-engine search with fallback."""

import asyncio
import hashlib
import html
import re
import time
from dataclasses import dataclass, field

from src.infrastructure.services.http_pool import get_http_client


@dataclass
class SearchResult:
    """Single search result."""
    title: str
    url: str
    snippet: str
    source: str = ""  # Which engine returned this


@dataclass
class SearchCache:
    """Simple in-memory cache for search results."""
    _cache: dict = field(default_factory=dict)
    _ttl: int = 300  # 5 minutes
    
    def get(self, key: str) -> list[SearchResult] | None:
        if key in self._cache:
            results, timestamp = self._cache[key]
            if time.time() - timestamp < self._ttl:
                return results
            del self._cache[key]
        return None
    
    def set(self, key: str, results: list[SearchResult]) -> None:
        self._cache[key] = (results, time.time())
        # Cleanup old entries
        if len(self._cache) > 100:
            self._cleanup()
    
    def _cleanup(self) -> None:
        now = time.time()
        expired = [k for k, (_, t) in self._cache.items() if now - t > self._ttl]
        for k in expired:
            del self._cache[k]


# Global cache instance
_search_cache = SearchCache()


# SearXNG public instances (fallback list)
SEARXNG_INSTANCES = [
    "https://search.bus-hit.me",
    "https://searx.be",
    "https://search.sapti.me",
    "https://searx.tiekoetter.com",
]


async def multi_search(
    query: str,
    max_results: int = 8,
    timeout: float = 8.0,
    use_cache: bool = True,
) -> list[SearchResult]:
    """Search using multiple engines in parallel with fallback.
    
    Tries DuckDuckGo, SearXNG instances, and Brave (if key provided).
    Returns merged, deduplicated results.
    
    Args:
        query: Search query
        max_results: Maximum results to return
        timeout: Timeout per engine
        use_cache: Whether to use cache
    
    Returns:
        List of SearchResult from best available source
    """
    if not query.strip():
        return []
    
    # Check cache
    cache_key = hashlib.md5(f"{query}:{max_results}".encode()).hexdigest()
    if use_cache:
        cached = _search_cache.get(cache_key)
        if cached:
            return cached
    
    # Run searches in parallel
    results = await _parallel_search(query, max_results, timeout)
    
    # Cache results
    if use_cache and results:
        _search_cache.set(cache_key, results)
    
    return results


async def _parallel_search(
    query: str,
    max_results: int,
    timeout: float,
) -> list[SearchResult]:
    """Run multiple search engines in parallel."""
    
    async def safe_search(coro, name: str) -> tuple[str, list[SearchResult]]:
        try:
            results = await asyncio.wait_for(coro, timeout=timeout)
            return (name, results)
        except Exception:
            return (name, [])
    
    # Create search tasks
    tasks = [
        safe_search(search_duckduckgo(query, max_results, timeout), "duckduckgo"),
        safe_search(search_searxng(query, max_results, SEARXNG_INSTANCES[0]), "searxng"),
    ]
    
    # Run in parallel
    done = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Collect results
    all_results: list[SearchResult] = []
    seen_urls: set[str] = set()
    
    for item in done:
        if isinstance(item, Exception):
            continue
        name, results = item
        for r in results:
            if r.url and r.url not in seen_urls:
                r.source = name
                all_results.append(r)
                seen_urls.add(r.url)
    
    # If no results, try fallback SearXNG instances
    if not all_results:
        for instance in SEARXNG_INSTANCES[1:]:
            try:
                results = await asyncio.wait_for(
                    search_searxng(query, max_results, instance),
                    timeout=timeout,
                )
                if results:
                    for r in results:
                        r.source = "searxng"
                    return results[:max_results]
            except Exception:
                continue
    
    return all_results[:max_results]


async def search_duckduckgo(
    query: str,
    max_results: int = 5,
    timeout: float = 10.0,
) -> list[SearchResult]:
    """Search DuckDuckGo using HTML API (no API key required)."""
    if not query.strip():
        return []
    
    url = "https://lite.duckduckgo.com/lite/"
    data = {"q": query, "kl": "wt-wt"}
    
    try:
        async with get_http_client() as client:
            response = await client.post(url, data=data, timeout=timeout)
            response.raise_for_status()
            return _parse_ddg_lite(response.text, max_results)
    except Exception:
        return []


def _parse_ddg_lite(html_text: str, max_results: int) -> list[SearchResult]:
    """Parse DuckDuckGo lite HTML response."""
    results = []
    
    # Pattern for result links
    link_pattern = re.compile(
        r'<a rel="nofollow" href="([^"]+)"[^>]*>([^<]+)</a>',
        re.IGNORECASE
    )
    
    # Pattern for snippets
    snippet_pattern = re.compile(
        r'<td[^>]*class="result-snippet"[^>]*>([^<]+)</td>',
        re.IGNORECASE
    )
    
    links = link_pattern.findall(html_text)
    snippets = snippet_pattern.findall(html_text)
    
    for i, (url, title) in enumerate(links):
        if not url.startswith("http") or "duckduckgo.com" in url:
            continue
        
        snippet = snippets[len(results)] if len(results) < len(snippets) else ""
        title = _clean_html(title).strip()
        snippet = _clean_html(snippet).strip()
        
        if title:
            results.append(SearchResult(
                title=title,
                url=url,
                snippet=snippet[:300],
            ))
        
        if len(results) >= max_results:
            break
    
    return results


async def search_searxng(
    query: str,
    max_results: int = 5,
    instance: str = "https://search.bus-hit.me",
) -> list[SearchResult]:
    """Search using SearXNG public instance (JSON API)."""
    if not query.strip():
        return []
    
    url = f"{instance}/search"
    params = {
        "q": query,
        "format": "json",
        "categories": "general",
    }
    
    try:
        async with get_http_client() as client:
            response = await client.get(url, params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()
    except Exception:
        return []
    
    results = []
    for item in data.get("results", [])[:max_results]:
        results.append(SearchResult(
            title=item.get("title", ""),
            url=item.get("url", ""),
            snippet=item.get("content", "")[:300],
        ))
    
    return results


async def search_brave(
    query: str,
    max_results: int = 5,
    api_key: str | None = None,
) -> list[SearchResult]:
    """Search using Brave Search API (2000 free/month with key)."""
    if not query.strip() or not api_key:
        return []
    
    url = "https://api.search.brave.com/res/v1/web/search"
    params = {"q": query, "count": max_results}
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": api_key,
    }
    
    try:
        async with get_http_client() as client:
            response = await client.get(
                url,
                params=params,
                headers=headers,
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
    except Exception:
        return []
    
    results = []
    for item in data.get("web", {}).get("results", [])[:max_results]:
        results.append(SearchResult(
            title=item.get("title", ""),
            url=item.get("url", ""),
            snippet=item.get("description", "")[:300],
        ))
    
    return results


def _clean_html(text: str) -> str:
    """Remove HTML entities and tags."""
    text = html.unescape(text)
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
