"""OpenAI-compatible embeddings - LM Studio, vLLM, LocalAI via POST /v1/embeddings.

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

from src.domain.ports.config import EmbeddingsConfig, OpenAICompatibleConfig

logger = logging.getLogger(__name__)


class OpenAICompatibleEmbeddingsAdapter:
    """LM Studio, vLLM, LocalAI embeddings via POST /v1/embeddings."""

    def __init__(
        self,
        config: OpenAICompatibleConfig,
        embeddings_config: EmbeddingsConfig,
    ) -> None:
        self._base_url = config.base_url.rstrip("/")
        self._model = embeddings_config.model
        self._timeout = config.timeout
        self._headers = {"Content-Type": "application/json"}
        if config.api_key:
            self._headers["Authorization"] = f"Bearer {config.api_key}"

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
        """Embed multiple texts. OpenAI API accepts array input.
        
        Retries up to 3 times with exponential backoff on network errors.
        Validates response structure.
        """
        if not texts:
            return []
        
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/embeddings",
                    json={"model": self._model, "input": texts},
                    headers=self._headers,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Embedding API error {e.response.status_code}: {e.response.text[:200]}")
            raise
        except httpx.TimeoutException:
            logger.warning(f"Embedding request timed out after {self._timeout}s")
            raise
        except httpx.NetworkError as e:
            logger.warning(f"Embedding network error: {e}")
            raise
        
        # Validate response structure
        items = data.get("data", [])
        if not items:
            logger.warning("Empty embedding response")
            return [[] for _ in texts]
        
        # OpenAI format: data[].embedding, sorted by index
        items = sorted(items, key=lambda x: x.get("index", 0))
        embeddings = [item.get("embedding", []) for item in items]
        
        # Validate count matches
        if len(embeddings) != len(texts):
            logger.warning(f"Embedding count mismatch: got {len(embeddings)}, expected {len(texts)}")
            # Pad or truncate
            while len(embeddings) < len(texts):
                embeddings.append([])
            embeddings = embeddings[:len(texts)]
        
        return embeddings
