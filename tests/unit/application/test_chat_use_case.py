"""Tests for ChatUseCase."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.application.chat.dto import ChatRequest, ChatResponse
from src.application.chat.use_case import ChatUseCase
from src.domain.ports.config import ModelConfig
from src.domain.ports.llm import LLMMessage, LLMResponse
from src.domain.services.model_router import ModelRouter


@pytest.fixture
def mock_llm():
    """Mock LLM adapter."""
    llm = MagicMock()
    llm.generate = AsyncMock(
        return_value=LLMResponse(content="LLM response", model="test-model", done=True)
    )
    return llm


@pytest.fixture
def mock_llm_stream():
    """Mock LLM adapter with streaming."""
    llm = MagicMock()

    async def stream_gen(*args, **kwargs):
        for chunk in ["Hello", " ", "world"]:
            yield chunk

    llm.generate_stream = stream_gen
    llm.generate = AsyncMock(
        return_value=LLMResponse(content="LLM response", model="test-model", done=True)
    )
    return llm


@pytest.fixture
def model_router():
    """Model router with default config."""
    config = ModelConfig(
        simple="simple-model",
        medium="medium-model",
        complex="complex-model",
        fallback="fallback-model",
    )
    return ModelRouter(config, provider="ollama")


@pytest.fixture
def mock_memory():
    """Mock conversation memory."""
    memory = MagicMock()
    memory.create_id.return_value = "test-conv-id"
    memory.load.return_value = None
    return memory


@pytest.fixture
def use_case(mock_llm, model_router, mock_memory):
    """ChatUseCase with mocked dependencies."""
    return ChatUseCase(
        llm=mock_llm,
        model_router=model_router,
        max_context_messages=10,
        memory=mock_memory,
    )


class TestChatUseCaseExecute:
    """Tests for ChatUseCase.execute method."""

    @pytest.mark.asyncio
    async def test_greeting_returns_template(self, use_case, mock_llm):
        """Greeting intent returns template without LLM call."""
        request = ChatRequest(message="привет")
        response = await use_case.execute(request)

        assert response.content  # Template response
        assert response.model == "template"
        mock_llm.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_help_returns_template(self, use_case, mock_llm):
        """Help intent returns template without LLM call."""
        request = ChatRequest(message="помощь")
        response = await use_case.execute(request)

        assert response.content
        assert response.model == "template"
        mock_llm.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_regular_message_calls_llm(self, use_case, mock_llm):
        """Regular message calls LLM."""
        request = ChatRequest(message="Объясни что такое Python")
        response = await use_case.execute(request)

        assert response.content == "LLM response"
        mock_llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_builds_messages_with_history(self, use_case, mock_llm):
        """Includes history in messages to LLM."""
        history = [
            LLMMessage(role="user", content="prev question"),
            LLMMessage(role="assistant", content="prev answer"),
        ]
        request = ChatRequest(message="follow up", history=history)

        await use_case.execute(request)

        call_args = mock_llm.generate.call_args
        messages = call_args.kwargs["messages"]
        # Should have system + history + current message
        assert len(messages) == 4  # system + 2 history + 1 current

    @pytest.mark.asyncio
    async def test_respects_max_context(self, mock_llm, model_router, mock_memory):
        """Truncates history to max_context_messages."""
        use_case = ChatUseCase(
            llm=mock_llm,
            model_router=model_router,
            max_context_messages=2,
            memory=mock_memory,
        )
        history = [
            LLMMessage(role="user", content="msg1"),
            LLMMessage(role="assistant", content="ans1"),
            LLMMessage(role="user", content="msg2"),
            LLMMessage(role="assistant", content="ans2"),
            LLMMessage(role="user", content="msg3"),
            LLMMessage(role="assistant", content="ans3"),
        ]
        request = ChatRequest(message="final", history=history)

        await use_case.execute(request)

        call_args = mock_llm.generate.call_args
        messages = call_args.kwargs["messages"]
        # system + last 2 from history + current
        assert len(messages) == 4

    @pytest.mark.asyncio
    async def test_saves_conversation(self, use_case, mock_memory):
        """Saves conversation to memory."""
        request = ChatRequest(message="test message")
        await use_case.execute(request)

        mock_memory.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_loads_history_from_memory(self, use_case, mock_memory):
        """Loads history from memory if conversation_id provided."""
        stored_history = [
            LLMMessage(role="user", content="stored question"),
            LLMMessage(role="assistant", content="stored answer"),
        ]
        mock_memory.load.return_value = stored_history

        request = ChatRequest(message="new message", conversation_id="existing-id")
        await use_case.execute(request)

        mock_memory.load.assert_called_with("existing-id")


class TestChatUseCaseExecuteStream:
    """Tests for ChatUseCase.execute_stream method."""

    @pytest.mark.asyncio
    async def test_greeting_yields_template(self, use_case):
        """Greeting intent yields template at once."""
        request = ChatRequest(message="привет")
        chunks = []
        async for kind, text in use_case.execute_stream(request):
            chunks.append((kind, text))

        assert len(chunks) >= 2  # content + done
        assert chunks[0][0] == "content"
        assert chunks[0][1]  # Template text
        assert chunks[-1][0] == "done"

    @pytest.mark.asyncio
    async def test_regular_message_streams(self, mock_llm_stream, model_router, mock_memory):
        """Regular message streams chunks from LLM."""
        use_case = ChatUseCase(
            llm=mock_llm_stream,
            model_router=model_router,
            max_context_messages=10,
            memory=mock_memory,
        )
        request = ChatRequest(message="explain something")

        chunks = []
        async for kind, text in use_case.execute_stream(request):
            chunks.append((kind, text))

        # Should have content chunks + done event
        assert len(chunks) >= 2
        content_chunks = [(k, t) for k, t in chunks if k == "content"]
        assert len(content_chunks) >= 1
        assert chunks[-1][0] == "done"


class TestChatUseCaseFallback:
    """Tests for fallback behavior."""

    @pytest.mark.asyncio
    async def test_fallback_on_error(self, model_router, mock_memory):
        """Falls back to fallback model on error."""
        mock_llm = MagicMock()
        call_count = 0

        async def generate_with_error(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Model unavailable")
            return LLMResponse(content="fallback response", model="fallback", done=True)

        mock_llm.generate = generate_with_error

        use_case = ChatUseCase(
            llm=mock_llm,
            model_router=model_router,
            memory=mock_memory,
        )
        request = ChatRequest(message="test message")

        response = await use_case.execute(request)

        assert response.content == "fallback response"
        assert call_count == 2  # First failed, second succeeded

    @pytest.mark.asyncio
    async def test_raises_if_all_fail(self, model_router, mock_memory):
        """Raises if all models fail."""
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(side_effect=Exception("All failed"))

        use_case = ChatUseCase(
            llm=mock_llm,
            model_router=model_router,
            memory=mock_memory,
        )
        request = ChatRequest(message="test message")

        with pytest.raises(Exception, match="All failed"):
            await use_case.execute(request)
