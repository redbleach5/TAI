"""Tests for embeddings adapters."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.ports.config import EmbeddingsConfig, OllamaConfig, OpenAICompatibleConfig
from src.infrastructure.embeddings.ollama import OllamaEmbeddingsAdapter
from src.infrastructure.embeddings.openai_compatible import OpenAICompatibleEmbeddingsAdapter


class TestOllamaEmbeddingsAdapter:
    """Tests for OllamaEmbeddingsAdapter."""

    @pytest.fixture
    def config(self):
        return OllamaConfig(host="http://localhost:11434", timeout=30, pool_size=2)

    @pytest.fixture
    def embeddings_config(self):
        return EmbeddingsConfig(model="nomic-embed-text")

    @pytest.fixture
    def adapter(self, config, embeddings_config):
        return OllamaEmbeddingsAdapter(config, embeddings_config)

    @pytest.mark.asyncio
    async def test_embed_single_text(self, adapter):
        """embed returns embedding for single text."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embeddings": [[0.1, 0.2, 0.3]]}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            result = await adapter.embed("Hello world")

        assert result == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_embed_batch(self, adapter):
        """embed_batch returns embeddings for multiple texts."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embeddings": [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            result = await adapter.embed_batch(["text1", "text2", "text3"])

        assert len(result) == 3
        assert result[0] == [0.1, 0.2]

    @pytest.mark.asyncio
    async def test_embed_batch_empty(self, adapter):
        """embed_batch returns empty list for empty input."""
        result = await adapter.embed_batch([])
        assert result == []

    @pytest.mark.asyncio
    async def test_embed_returns_empty_on_no_result(self, adapter):
        """embed returns empty list if no embeddings returned."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embeddings": []}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            result = await adapter.embed("text")

        assert result == []


class TestOpenAICompatibleEmbeddingsAdapter:
    """Tests for OpenAICompatibleEmbeddingsAdapter."""

    @pytest.fixture
    def config(self):
        return OpenAICompatibleConfig(
            base_url="http://localhost:1234/v1",
            api_key="test-key",
            timeout=30,
        )

    @pytest.fixture
    def embeddings_config(self):
        return EmbeddingsConfig(model="text-embedding")

    @pytest.fixture
    def adapter(self, config, embeddings_config):
        return OpenAICompatibleEmbeddingsAdapter(config, embeddings_config)

    @pytest.mark.asyncio
    async def test_embed_single(self, adapter):
        """embed returns embedding via OpenAI-compatible API."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3]}]}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            result = await adapter.embed("Hello")

        assert result == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_embed_batch(self, adapter):
        """embed_batch returns embeddings for multiple texts."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"embedding": [0.1, 0.2]},
                {"embedding": [0.3, 0.4]},
            ]
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            result = await adapter.embed_batch(["text1", "text2"])

        assert len(result) == 2
        assert result[0] == [0.1, 0.2]

    @pytest.mark.asyncio
    async def test_embed_batch_empty(self, adapter):
        """embed_batch returns empty list for empty input."""
        result = await adapter.embed_batch([])
        assert result == []
