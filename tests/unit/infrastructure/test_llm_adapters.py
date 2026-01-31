"""Tests for LLM adapters (Ollama, OpenAI-compatible)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from src.domain.ports.config import OllamaConfig, OpenAICompatibleConfig
from src.domain.ports.llm import LLMMessage
from src.infrastructure.llm.ollama import OllamaAdapter
from src.infrastructure.llm.openai_compatible import OpenAICompatibleAdapter


class TestOllamaAdapter:
    """Tests for OllamaAdapter."""

    @pytest.fixture
    def config(self):
        return OllamaConfig(host="http://localhost:11434", timeout=30, pool_size=2)

    @pytest.fixture
    def adapter(self, config):
        return OllamaAdapter(config)

    @pytest.mark.asyncio
    async def test_generate_calls_client(self, adapter):
        """Generate calls ollama client with correct params."""
        mock_response = MagicMock()
        mock_response.message = MagicMock(content="Hello!")
        mock_response.model = "llama2"

        adapter._client.chat = AsyncMock(return_value=mock_response)

        messages = [LLMMessage(role="user", content="Hi")]
        result = await adapter.generate(messages, model="llama2")

        assert result.content == "Hello!"
        assert result.model == "llama2"
        adapter._client.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_default_model(self, adapter):
        """Generate uses default model if not specified."""
        mock_response = MagicMock()
        mock_response.message = MagicMock(content="Response")
        mock_response.model = "llama2"

        adapter._client.chat = AsyncMock(return_value=mock_response)

        messages = [LLMMessage(role="user", content="Hi")]
        await adapter.generate(messages)

        call_kwargs = adapter._client.chat.call_args
        assert call_kwargs.kwargs["model"] == "llama2"

    @pytest.mark.asyncio
    async def test_generate_stream(self, adapter):
        """Generate stream yields content chunks."""
        async def mock_stream():
            for text in ["Hello", " ", "world"]:
                chunk = MagicMock()
                chunk.message = MagicMock(content=text)
                yield chunk

        adapter._client.chat = AsyncMock(return_value=mock_stream())

        messages = [LLMMessage(role="user", content="Hi")]
        chunks = []
        async for chunk in adapter.generate_stream(messages, model="llama2"):
            chunks.append(chunk)

        assert chunks == ["Hello", " ", "world"]

    @pytest.mark.asyncio
    async def test_is_available_true(self, adapter, config):
        """is_available returns True when server responds."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            result = await adapter.is_available()

        assert result is True
        assert adapter._available is True

    @pytest.mark.asyncio
    async def test_is_available_false_on_error(self, adapter):
        """is_available returns False on connection error."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            result = await adapter.is_available()

        assert result is False
        assert adapter._available is False

    @pytest.mark.asyncio
    async def test_list_models(self, adapter):
        """list_models returns model names."""
        # ollama package uses 'model' attr (newer) or 'name' (legacy)
        model1 = MagicMock()
        model1.model = "llama2"
        model1.name = "llama2"
        model2 = MagicMock()
        model2.model = "codellama"
        model2.name = "codellama"
        mock_response = MagicMock()
        mock_response.models = [model1, model2]

        adapter._client.list = AsyncMock(return_value=mock_response)

        result = await adapter.list_models()
        assert result == ["llama2", "codellama"]

    @pytest.mark.asyncio
    async def test_list_models_empty_on_error(self, adapter):
        """list_models returns empty list on error."""
        adapter._client.list = AsyncMock(side_effect=Exception("Error"))

        result = await adapter.list_models()
        assert result == []


class TestOpenAICompatibleAdapter:
    """Tests for OpenAICompatibleAdapter."""

    @pytest.fixture
    def config(self):
        return OpenAICompatibleConfig(
            base_url="http://localhost:1234/v1",
            api_key="test-key",
            timeout=30,
        )

    @pytest.fixture
    def adapter(self, config):
        return OpenAICompatibleAdapter(config)

    def test_init_sets_headers(self, adapter):
        """Init sets authorization header if api_key provided."""
        assert adapter._headers["Authorization"] == "Bearer test-key"

    def test_init_no_auth_header_without_key(self):
        """No auth header if api_key is empty."""
        config = OpenAICompatibleConfig(base_url="http://localhost:1234/v1")
        adapter = OpenAICompatibleAdapter(config)
        assert "Authorization" not in adapter._headers

    @pytest.mark.asyncio
    async def test_generate_calls_api(self, adapter):
        """Generate calls OpenAI-compatible API."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello!"}}]
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            messages = [LLMMessage(role="user", content="Hi")]
            result = await adapter.generate(messages, model="local")

        assert result.content == "Hello!"
        assert result.model == "local"

    @pytest.mark.asyncio
    async def test_generate_default_model(self, adapter):
        """Generate uses 'default' model if not specified."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}]
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = mock_client.return_value.__aenter__.return_value
            mock_instance.post = AsyncMock(return_value=mock_response)

            messages = [LLMMessage(role="user", content="Hi")]
            result = await adapter.generate(messages)

            call_args = mock_instance.post.call_args
            assert call_args.kwargs["json"]["model"] == "default"

    @pytest.mark.asyncio
    async def test_generate_handles_error(self, adapter):
        """Generate raises on API error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Error", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            messages = [LLMMessage(role="user", content="Hi")]
            with pytest.raises(httpx.HTTPStatusError):
                await adapter.generate(messages)

    @pytest.mark.asyncio
    async def test_is_available_true(self, adapter):
        """is_available returns True when server responds."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            result = await adapter.is_available()

        assert result is True

    @pytest.mark.asyncio
    async def test_is_available_false_on_error(self, adapter):
        """is_available returns False on connection error."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("Connection refused")
            )
            result = await adapter.is_available()

        assert result is False

    @pytest.mark.asyncio
    async def test_list_models(self, adapter):
        """list_models returns model IDs."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"id": "model-1"}, {"id": "model-2"}]
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            result = await adapter.list_models()

        assert result == ["model-1", "model-2"]

    @pytest.mark.asyncio
    async def test_list_models_empty_on_error(self, adapter):
        """list_models returns empty list on error."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("Error")
            )
            result = await adapter.list_models()

        assert result == []
