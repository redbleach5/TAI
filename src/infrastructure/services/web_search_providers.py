"""URL, params and headers builders for web search providers."""


def build_ddg_url() -> str:
    """DuckDuckGo Lite HTML API base URL."""
    return "https://lite.duckduckgo.com/lite/"


def build_ddg_data(query: str) -> dict:
    """POST body for DuckDuckGo."""
    return {"q": query, "kl": "wt-wt"}


def build_searxng_url(instance: str) -> str:
    """SearXNG search URL (instance base without trailing slash)."""
    base = (instance or "").rstrip("/")
    return f"{base}/search" if base else ""


def build_searxng_params(query: str) -> dict:
    """Query params for SearXNG JSON API."""
    return {
        "q": query,
        "format": "json",
        "categories": "general",
    }


def build_brave_url() -> str:
    """Brave Search API URL."""
    return "https://api.search.brave.com/res/v1/web/search"


def build_brave_params(query: str, max_results: int) -> dict:
    """Query params for Brave Search API."""
    return {"q": query, "count": max_results}


def build_brave_headers(api_key: str) -> dict:
    """Headers for Brave Search API."""
    return {
        "Accept": "application/json",
        "X-Subscription-Token": api_key,
    }


def build_tavily_url() -> str:
    """Tavily Search API URL."""
    return "https://api.tavily.com/search"


def build_tavily_payload(query: str, max_results: int) -> dict:
    """JSON body for Tavily API."""
    return {
        "query": query,
        "max_results": min(max_results, 20),
        "search_depth": "basic",
    }


def build_tavily_headers(api_key: str) -> dict:
    """Headers for Tavily API."""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }


def build_google_url() -> str:
    """Google Custom Search JSON API URL."""
    return "https://customsearch.googleapis.com/customsearch/v1"


def build_google_params(
    query: str,
    max_results: int,
    api_key: str,
    cx: str,
) -> dict:
    """Query params for Google Custom Search API."""
    return {
        "key": api_key,
        "cx": cx,
        "q": query,
        "num": min(max_results, 10),
    }
