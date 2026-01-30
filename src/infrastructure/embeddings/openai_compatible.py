"""OpenAI-compatible embeddings - LM Studio, vLLM, LocalAI via POST /v1/embeddings."""

import httpx

from src.domain.ports.config import EmbeddingsConfig, OpenAICompatibleConfig


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

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts. OpenAI API accepts array input."""
        if not texts:
            return []
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/embeddings",
                json={"model": self._model, "input": texts},
                headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json()
        # OpenAI format: data[].embedding, sorted by index
        items = sorted(data.get("data", []), key=lambda x: x.get("index", 0))
        return [item.get("embedding", []) for item in items]
