"""HTTP Connection Pool - shared async HTTP client for better performance."""

import asyncio
import logging
from contextlib import asynccontextmanager

import httpx

logger = logging.getLogger(__name__)


class HTTPPool:
    """Shared HTTP connection pool for async requests.

    Reuses connections across requests for better performance.
    Thread-safe and handles connection lifecycle.
    """

    _instance: "HTTPPool | None" = None
    _lock: asyncio.Lock | None = None

    def __init__(self) -> None:
        """Initialize HTTP pool (client created on first use)."""
        self._client: httpx.AsyncClient | None = None
        self._timeout = httpx.Timeout(30.0, connect=10.0)
        self._limits = httpx.Limits(
            max_keepalive_connections=20,
            max_connections=50,
            keepalive_expiry=30.0,
        )

    @classmethod
    async def get_instance(cls) -> "HTTPPool":
        """Get singleton instance (async-safe)."""
        if cls._lock is None:
            cls._lock = asyncio.Lock()

        async with cls._lock:
            if cls._instance is None:
                cls._instance = HTTPPool()
            return cls._instance

    async def get_client(self) -> httpx.AsyncClient:
        """Get or create the shared HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                limits=self._limits,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                },
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @classmethod
    async def reset(cls) -> None:
        """Reset the singleton (for testing)."""
        if cls._instance:
            await cls._instance.close()
            cls._instance = None


@asynccontextmanager
async def get_http_client():
    """Context manager for getting HTTP client from pool.

    Usage:
        async with get_http_client() as client:
            response = await client.get(url)
    """
    pool = await HTTPPool.get_instance()
    client = await pool.get_client()
    yield client


async def fetch_url(
    url: str,
    method: str = "GET",
    params: dict | None = None,
    data: dict | None = None,
    headers: dict | None = None,
    timeout: float | None = None,
) -> httpx.Response:
    """Perform HTTP request using shared pool.

    Args:
        url: URL to fetch
        method: HTTP method (GET, POST, etc.)
        params: Query parameters
        data: Form data (for POST)
        headers: Additional headers
        timeout: Request timeout (overrides default)

    Returns:
        httpx.Response object

    """
    async with get_http_client() as client:
        kwargs = {"params": params, "headers": headers}
        if data:
            kwargs["data"] = data
        if timeout:
            kwargs["timeout"] = timeout

        if method.upper() == "GET":
            return await client.get(url, **kwargs)
        elif method.upper() == "POST":
            return await client.post(url, **kwargs)
        else:
            return await client.request(method, url, **kwargs)


async def fetch_json(
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
) -> dict:
    """Fetch JSON from URL using shared pool.

    Returns:
        Parsed JSON as dict, or empty dict on error

    """
    try:
        response = await fetch_url(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.debug("fetch_json failed for %s: %s", url, e)
        return {}
