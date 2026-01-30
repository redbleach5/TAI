"""Web Search service - multi-engine search with fallback.

Production-ready implementation with:
- Thread-safe LRU cache with configurable limits
- URL normalization for deduplication
- Parallel search with fallbacks
"""

import asyncio
import hashlib
import html
import logging
import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from urllib.parse import urlparse, urlunparse

from src.infrastructure.services.http_pool import get_http_client

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Single search result."""
    title: str
    url: str
    snippet: str
    source: str = ""  # Which engine returned this


class SearchCache:
    """Thread-safe LRU cache for search results.
    
    Features:
    - TTL-based expiration
    - LRU eviction when max_entries exceeded
    - Configurable limits
    """
    
    def __init__(self, ttl: int = 300, max_entries: int = 100):
        """Initialize cache.
        
        Args:
            ttl: Time-to-live in seconds (default 5 minutes)
            max_entries: Maximum cache entries (default 100)
        """
        self._cache: OrderedDict[str, tuple[list[SearchResult], float]] = OrderedDict()
        self._ttl = ttl
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> list[SearchResult] | None:
        """Get cached results (thread-safe, updates LRU order)."""
        with self._lock:
            if key in self._cache:
                results, timestamp = self._cache[key]
                if time.time() - timestamp < self._ttl:
                    # Move to end (most recently used)
                    self._cache.move_to_end(key)
                    self._hits += 1
                    return results
                # Expired
                del self._cache[key]
            self._misses += 1
            return None
    
    def set(self, key: str, results: list[SearchResult]) -> None:
        """Set cached results (thread-safe, with LRU eviction)."""
        with self._lock:
            # Remove old entry if exists
            if key in self._cache:
                del self._cache[key]
            
            # Evict oldest entries if at capacity
            while len(self._cache) >= self._max_entries:
                self._cache.popitem(last=False)  # Remove oldest (LRU)
            
            self._cache[key] = (results, time.time())
    
    def stats(self) -> dict:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._cache),
                "max_entries": self._max_entries,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total > 0 else 0.0,
            }
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()


# Global cache instance
_search_cache = SearchCache()


def normalize_url(url: str) -> str:
    """Normalize URL for deduplication.
    
    - Lowercase domain
    - Remove trailing slash
    - Remove www prefix
    - Remove fragment
    - Keep query params (may be significant)
    """
    try:
        parsed = urlparse(url)
        # Lowercase domain
        netloc = parsed.netloc.lower()
        # Remove www prefix
        if netloc.startswith("www."):
            netloc = netloc[4:]
        # Remove trailing slash from path
        path = parsed.path.rstrip("/") if parsed.path != "/" else ""
        # Reconstruct without fragment
        return urlunparse((
            parsed.scheme.lower(),
            netloc,
            path,
            parsed.params,
            parsed.query,
            "",  # Remove fragment
        ))
    except Exception:
        return url


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
    
    # Collect results with URL normalization for deduplication
    all_results: list[SearchResult] = []
    seen_urls: set[str] = set()
    
    for item in done:
        if isinstance(item, Exception):
            logger.debug(f"Search task failed: {item}")
            continue
        name, results = item
        for r in results:
            if r.url:
                normalized = normalize_url(r.url)
                if normalized not in seen_urls:
                    r.source = name
                    all_results.append(r)
                    seen_urls.add(normalized)
    
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
