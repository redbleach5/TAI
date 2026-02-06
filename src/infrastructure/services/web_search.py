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
import os
import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

from src.infrastructure.services.http_pool import get_http_client
from src.infrastructure.services.web_search_formatters import format_search_results
from src.infrastructure.services.web_search_providers import (
    build_brave_headers,
    build_brave_params,
    build_brave_url,
    build_ddg_data,
    build_ddg_url,
    build_google_params,
    build_google_url,
    build_searxng_params,
    build_searxng_url,
    build_tavily_headers,
    build_tavily_payload,
    build_tavily_url,
)

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
        return urlunparse(
            (
                parsed.scheme.lower(),
                netloc,
                path,
                parsed.params,
                parsed.query,
                "",  # Remove fragment
            )
        )
    except Exception:
        logger.debug("URL normalization failed for %s", url, exc_info=True)
        return url


# SearXNG public instances (fallback list)
SEARXNG_INSTANCES = [
    "https://search.bus-hit.me",
    "https://searx.be",
    "https://search.sapti.me",
    "https://searx.tiekoetter.com",
]


def _resolve_web_search_options(
    searxng_url: str | None = None,
    brave_api_key: str | None = None,
    tavily_api_key: str | None = None,
    google_api_key: str | None = None,
    google_cx: str | None = None,
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    """Resolve options from args or env (config overrides env when passed)."""
    return (
        (searxng_url or os.environ.get("SEARXNG_URL", "") or "").strip() or None,
        (brave_api_key if brave_api_key is not None else os.environ.get("BRAVE_API_KEY", "") or "").strip() or None,
        (tavily_api_key if tavily_api_key is not None else os.environ.get("TAVILY_API_KEY", "") or "").strip() or None,
        (google_api_key if google_api_key is not None else os.environ.get("GOOGLE_API_KEY", "") or "").strip() or None,
        (google_cx if google_cx is not None else os.environ.get("GOOGLE_CX", "") or "").strip() or None,
    )


async def multi_search(
    query: str,
    max_results: int = 10,
    timeout: float = 12.0,
    use_cache: bool = True,
    *,
    searxng_url: str | None = None,
    brave_api_key: str | None = None,
    tavily_api_key: str | None = None,
    google_api_key: str | None = None,
    google_cx: str | None = None,
) -> list[SearchResult]:
    """Search using multiple engines in parallel with fallback (Cherry Studio–style).

    Tries DuckDuckGo, SearXNG (custom URL or public instances), Brave, Tavily, and Google Custom Search when keys set.
    Returns merged, deduplicated results.

    Args:
        query: Search query
        max_results: Maximum results to return
        timeout: Timeout per engine
        use_cache: Whether to use cache
        searxng_url: Optional custom SearXNG instance URL (e.g. http://localhost:8080)
        brave_api_key: Optional Brave Search API key
        tavily_api_key: Optional Tavily API key
        google_api_key: Optional Google Custom Search API key (100 free/day)
        google_cx: Optional Google Programmable Search Engine ID (required with google_api_key)

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

    s_url, b_key, t_key, g_key, g_cx = _resolve_web_search_options(
        searxng_url, brave_api_key, tavily_api_key, google_api_key, google_cx
    )
    results = await _parallel_search(
        query,
        max_results,
        timeout,
        searxng_url=s_url,
        brave_api_key=b_key,
        tavily_api_key=t_key,
        google_api_key=g_key,
        google_cx=g_cx,
    )

    # Cache results
    if use_cache and results:
        _search_cache.set(cache_key, results)

    return results


async def _parallel_search(
    query: str,
    max_results: int,
    timeout: float,
    *,
    searxng_url: str | None = None,
    brave_api_key: str | None = None,
    tavily_api_key: str | None = None,
    google_api_key: str | None = None,
    google_cx: str | None = None,
) -> list[SearchResult]:
    """Run multiple search engines in parallel (Cherry Studio–style).

    Uses custom SearXNG URL if set, else first public instance. Adds Brave/Tavily/Google when keys set.
    Falls back to additional SearXNG instances in parallel if no results.
    """

    async def safe_search(coro, name: str) -> tuple[str, list[SearchResult]]:
        try:
            results = await asyncio.wait_for(coro, timeout=timeout + 5)  # Extra buffer
            return (name, results)
        except asyncio.TimeoutError:
            logger.debug("Search '%s' timed out", name)
            return (name, [])
        except Exception as e:
            logger.debug("Search '%s' failed: %s", name, e)
            return (name, [])

    searxng_base = (searxng_url or "").strip()
    if not searxng_base:
        searxng_base = SEARXNG_INSTANCES[0]
    else:
        # Ensure no trailing slash for consistency
        searxng_base = searxng_base.rstrip("/")

    tasks = [
        safe_search(search_duckduckgo(query, max_results, timeout), "duckduckgo"),
        safe_search(search_searxng(query, max_results, searxng_base, timeout), "searxng"),
    ]
    if brave_api_key:
        tasks.append(safe_search(search_brave(query, max_results, brave_api_key), "brave"))
    if tavily_api_key:
        tasks.append(safe_search(search_tavily(query, max_results, tavily_api_key, timeout), "tavily"))
    if google_api_key and google_cx:
        tasks.append(safe_search(search_google(query, max_results, google_api_key, google_cx, timeout), "google"))

    done = await asyncio.gather(*tasks, return_exceptions=True)

    all_results: list[SearchResult] = []
    seen_urls: set[str] = set()

    for item in done:
        if isinstance(item, Exception):
            logger.debug("Search task exception: %s", item)
            continue
        name, results = item
        for r in results:
            if r.url:
                normalized = normalize_url(r.url)
                if normalized not in seen_urls:
                    r.source = name
                    all_results.append(r)
                    seen_urls.add(normalized)

    # If no results, try remaining SearXNG instances only when not using custom URL
    if not all_results and not (searxng_url or "").strip() and len(SEARXNG_INSTANCES) > 1:
        logger.debug("Primary search failed, trying fallback instances in parallel")
        fallback_tasks = [
            safe_search(search_searxng(query, max_results, inst, timeout), f"searxng-{i}")
            for i, inst in enumerate(SEARXNG_INSTANCES[1:], 1)
        ]
        fallback_done = await asyncio.gather(*fallback_tasks, return_exceptions=True)

        for item in fallback_done:
            if isinstance(item, Exception):
                continue
            name, results = item
            if results:
                for r in results:
                    r.source = "searxng"
                    normalized = normalize_url(r.url)
                    if normalized not in seen_urls:
                        all_results.append(r)
                        seen_urls.add(normalized)
                if len(all_results) >= max_results:
                    break

    return all_results[:max_results]


async def search_duckduckgo(
    query: str,
    max_results: int = 5,
    timeout: float = 10.0,
    retries: int = 2,
) -> list[SearchResult]:
    """Search DuckDuckGo using HTML API (no API key required).

    Retries on transient errors with exponential backoff.
    """
    if not query.strip():
        return []

    url = build_ddg_url()
    data = build_ddg_data(query)

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            async with get_http_client() as client:
                response = await client.post(url, data=data, timeout=timeout)
                response.raise_for_status()
                return _parse_ddg_lite(response.text, max_results)
        except Exception as e:
            last_error = e
            if attempt < retries:
                wait_time = 2**attempt  # Exponential backoff: 1, 2, 4...
                logger.debug("DuckDuckGo retry %d after %ds: %s", attempt + 1, wait_time, e)
                await asyncio.sleep(wait_time)

    logger.warning("DuckDuckGo search failed after %d attempts: %s", retries + 1, last_error)
    return []


def _parse_ddg_lite(html_text: str, max_results: int) -> list[SearchResult]:
    """Parse DuckDuckGo lite HTML response."""
    results = []

    # Pattern for result links
    link_pattern = re.compile(r'<a rel="nofollow" href="([^"]+)"[^>]*>([^<]+)</a>', re.IGNORECASE)

    # Pattern for snippets
    snippet_pattern = re.compile(r'<td[^>]*class="result-snippet"[^>]*>([^<]+)</td>', re.IGNORECASE)

    links = link_pattern.findall(html_text)
    snippets = snippet_pattern.findall(html_text)

    for i, (url, title) in enumerate(links):
        if not url.startswith("http") or "duckduckgo.com" in url:
            continue

        snippet = snippets[len(results)] if len(results) < len(snippets) else ""
        title = _clean_html(title).strip()
        snippet = _clean_html(snippet).strip()

        if title:
            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet[:300],
                )
            )

        if len(results) >= max_results:
            break

    return results


async def search_searxng(
    query: str,
    max_results: int = 5,
    instance: str = "https://search.bus-hit.me",
    timeout: float = 10.0,
    retries: int = 1,
) -> list[SearchResult]:
    """Search using SearXNG public instance (JSON API).

    Retries on transient errors.
    """
    if not query.strip():
        return []

    url = build_searxng_url(instance)
    if not url:
        return []
    params = build_searxng_params(query)

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            async with get_http_client() as client:
                response = await client.get(url, params=params, timeout=timeout)
                response.raise_for_status()
                data = response.json()

            results = []
            for item in data.get("results", [])[:max_results]:
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        snippet=item.get("content", "")[:300],
                    )
                )
            return results
        except Exception as e:
            last_error = e
            if attempt < retries:
                wait_time = 2**attempt
                logger.debug("SearXNG retry %d: %s", attempt + 1, e)
                await asyncio.sleep(wait_time)

    logger.debug("SearXNG %s failed: %s", instance, last_error)
    return []


async def search_tavily(
    query: str,
    max_results: int = 5,
    api_key: str | None = None,
    timeout: float = 10.0,
    retries: int = 2,
) -> list[SearchResult]:
    """Search using Tavily API (Cherry Studio–style; app.tavily.com).

    POST https://api.tavily.com/search, Bearer token. Retries on transient errors.
    """
    if not query.strip() or not api_key:
        return []

    url = build_tavily_url()
    payload = build_tavily_payload(query, max_results)
    headers = build_tavily_headers(api_key)

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            async with get_http_client() as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=timeout,
                )
                response.raise_for_status()
                data = response.json()

            results = []
            for item in data.get("results", [])[:max_results]:
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        snippet=(item.get("content") or "")[:300],
                    )
                )
            return results
        except Exception as e:
            last_error = e
            if attempt < retries:
                wait_time = 2**attempt
                logger.debug("Tavily retry %d: %s", attempt + 1, e)
                await asyncio.sleep(wait_time)

    logger.debug("Tavily search failed: %s", last_error)
    return []


async def search_google(
    query: str,
    max_results: int = 5,
    api_key: str | None = None,
    cx: str | None = None,
    timeout: float = 10.0,
    retries: int = 2,
) -> list[SearchResult]:
    """Search using Google Custom Search JSON API (Cherry Studio–style).

    Requires API key (Google Cloud) and Programmable Search Engine ID (cx).
    Free tier: 100 queries/day. Create engine at programmablesearchengine.google.com.
    """
    if not query.strip() or not api_key or not cx:
        return []

    url = build_google_url()
    params = build_google_params(query, max_results, api_key, cx)

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            async with get_http_client() as client:
                response = await client.get(url, params=params, timeout=timeout)
                response.raise_for_status()
                data = response.json()

            results = []
            for item in data.get("items", [])[:max_results]:
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("link", ""),
                        snippet=item.get("snippet", "")[:300],
                    )
                )
            return results
        except Exception as e:
            last_error = e
            if attempt < retries:
                wait_time = 2**attempt
                logger.debug("Google retry %d: %s", attempt + 1, e)
                await asyncio.sleep(wait_time)

    logger.debug("Google search failed: %s", last_error)
    return []


async def search_brave(
    query: str,
    max_results: int = 5,
    api_key: str | None = None,
    timeout: float = 10.0,
    retries: int = 2,
) -> list[SearchResult]:
    """Search using Brave Search API (2000 free/month with key).

    Retries on transient errors with exponential backoff.
    """
    if not query.strip() or not api_key:
        return []

    url = build_brave_url()
    params = build_brave_params(query, max_results)
    headers = build_brave_headers(api_key)

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            async with get_http_client() as client:
                response = await client.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=timeout,
                )
                response.raise_for_status()
                data = response.json()

            results = []
            for item in data.get("web", {}).get("results", [])[:max_results]:
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        snippet=item.get("description", "")[:300],
                    )
                )
            return results
        except Exception as e:
            last_error = e
            if attempt < retries:
                wait_time = 2**attempt
                logger.debug("Brave retry %d: %s", attempt + 1, e)
                await asyncio.sleep(wait_time)

    logger.debug("Brave search failed: %s", last_error)
    return []


def _clean_html(text: str) -> str:
    """Remove HTML entities and tags."""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    return text


# Re-export for backward compatibility (format_search_results from web_search_formatters)
__all__ = [
    "SearchResult",
    "SearchCache",
    "multi_search",
    "search_duckduckgo",
    "search_searxng",
    "search_brave",
    "search_tavily",
    "search_google",
    "format_search_results",
]
