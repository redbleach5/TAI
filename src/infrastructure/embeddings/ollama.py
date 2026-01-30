"""Ollama embeddings adapter - POST /api/embed."""

import httpx

from src.domain.ports.config import EmbeddingsConfig, OllamaConfig


class OllamaEmbeddingsAdapter:
    """Ollama embeddings via POST /api/embed."""

    def __init__(self, config: OllamaConfig, embeddings_config: EmbeddingsConfig) -> None:
        self._host = config.host.rstrip("/")
        self._model = embeddings_config.model
        self._timeout = config.timeout

    async def embed(self, text: str) -> list[float]:
        """Embed a single text."""
        result = await self.embed_batch([text])
        return result[0] if result else []

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts."""
        if not texts:
            return []
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._host}/api/embed",
                json={"model": self._model, "input": texts},
            )
            resp.raise_for_status()
            data = resp.json()
        return data.get("embeddings", [])
