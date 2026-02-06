"""Ollama embeddings adapter - POST /api/embed.

Production-ready with:
- Retry logic with exponential backoff
- Response validation
- Proper logging
"""

import logging

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.domain.ports.config import EmbeddingsConfig, OllamaConfig

logger = logging.getLogger(__name__)


class OllamaEmbeddingsAdapter:
    """Ollama embeddings via POST /api/embed."""

    def __init__(self, config: OllamaConfig, embeddings_config: EmbeddingsConfig) -> None:
        """Initialize with Ollama and embeddings config."""
        self._host = config.host.rstrip("/")
        self._model = embeddings_config.model
        self._timeout = config.timeout

    async def embed(self, text: str) -> list[float]:
        """Embed a single text."""
        result = await self.embed_batch([text])
        return result[0] if result else []

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts.

        Retries up to 3 times with exponential backoff on network errors.
        Validates response structure.
        """
        if not texts:
            return []

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._host}/api/embed",
                    json={"model": self._model, "input": texts},
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("Ollama embedding error %s: %s", e.response.status_code, e.response.text[:200])
            raise
        except httpx.TimeoutException:
            logger.warning("Ollama embedding timed out after %ss", self._timeout)
            raise
        except httpx.NetworkError as e:
            logger.warning("Ollama network error: %s", e)
            raise

        embeddings = data.get("embeddings", [])

        # Validate count matches
        if len(embeddings) != len(texts):
            logger.warning("Embedding count mismatch: got %d, expected %d", len(embeddings), len(texts))
            # Pad or truncate
            while len(embeddings) < len(texts):
                embeddings.append([])
            embeddings = embeddings[: len(texts)]

        return embeddings
