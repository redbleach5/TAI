"""Chat use case - orchestration layer."""

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from src.application.chat.dto import ChatRequest, ChatResponse
from src.domain.ports.llm import LLMMessage, LLMPort
from src.domain.services.intent_detector import IntentDetector
from src.domain.services.model_router import ModelRouter
from src.infrastructure.llm.reasoning_parser import stream_reasoning_chunks

if TYPE_CHECKING:
    from src.infrastructure.persistence.conversation_memory import ConversationMemory


class ChatUseCase:
    """Orchestrates chat: intent detection + LLM call."""

    def __init__(
        self,
        llm: LLMPort,
        model_router: ModelRouter,
        max_context_messages: int = 20,
        memory: "ConversationMemory | None" = None,
    ) -> None:
        self._llm = llm
        self._model_router = model_router
        self._max_context = max_context_messages
        self._memory = memory
        self._intent_detector = IntentDetector()

    async def execute(self, request: ChatRequest) -> ChatResponse:
        """Process chat request: detect intent, call LLM or return template."""
        request = self._resolve_history(request)
        intent = self._intent_detector.detect(request.message)
        if intent.response is not None:
            conv_id = request.conversation_id or (
                self._memory.create_id() if self._memory else None
            )
            resp = ChatResponse(
                content=intent.response,
                model="template",
                conversation_id=conv_id,
            )
            self._save_conversation(request, resp)
            return resp

        messages = self._build_messages(request)
        model = self._model_router.select_model(request.message)
        llm_response = await self._generate_with_fallback(messages, model)
        conv_id = request.conversation_id or (self._memory.create_id() if self._memory else None)
        resp = ChatResponse(
            content=llm_response.content,
            model=llm_response.model,
            conversation_id=conv_id,
        )
        self._save_conversation(request, resp)
        return resp

    async def execute_stream(
        self, request: ChatRequest
    ) -> AsyncIterator[tuple[str, str]]:
        """Stream LLM response. Yields (kind, chunk) where kind is 'content' or 'thinking'.

        For template intents, yields ('content', response) at once.
        For LLM, parses <think> blocks and yields ('thinking', ...) and ('content', ...).
        """
        request = self._resolve_history(request)
        intent = self._intent_detector.detect(request.message)
        if intent.response is not None:
            yield ("content", intent.response)
            return

        messages = self._build_messages(request)
        model = self._model_router.select_model(request.message)
        full_content: list[str] = []
        raw_stream = self._stream_with_fallback(messages, model)
        async for kind, text in stream_reasoning_chunks(raw_stream):
            if kind == "content":
                full_content.append(text)
            yield (kind, text)

        conv_id = request.conversation_id or (self._memory.create_id() if self._memory else None)
        if full_content and self._memory and conv_id:
            resp = ChatResponse(
                content="".join(full_content),
                model=model,
                conversation_id=conv_id,
            )
            self._save_conversation(request, resp)

    def _build_messages(self, request: ChatRequest) -> list[LLMMessage]:
        """Build messages for LLM from request and history."""
        messages: list[LLMMessage] = [
            LLMMessage(
                role="system",
                content="You are a helpful coding assistant. Answer concisely.",
            )
        ]
        if request.history:
            # Sliding window: keep last N messages
            history = request.history[-self._max_context :]
            messages.extend(history)
        messages.append(LLMMessage(role="user", content=request.message))
        return messages

    def _resolve_history(self, request: ChatRequest) -> ChatRequest:
        """Load history from memory if conversation_id provided."""
        if not self._memory or not request.conversation_id:
            return request
        loaded = self._memory.load(request.conversation_id)
        if loaded:
            return ChatRequest(
                message=request.message,
                history=loaded[-self._max_context :],
                conversation_id=request.conversation_id,
            )
        return request

    def _save_conversation(self, request: ChatRequest, response: ChatResponse) -> None:
        """Save conversation to memory."""
        if not self._memory:
            return
        conv_id = response.conversation_id or request.conversation_id
        if not conv_id:
            return
        history = list(request.history or [])
        history.append(LLMMessage(role="user", content=request.message))
        history.append(LLMMessage(role="assistant", content=response.content))
        self._memory.save(conv_id, history[-self._max_context :])

    async def _generate_with_fallback(self, messages: list[LLMMessage], model: str):
        """Generate with fallback if model unavailable."""
        fallback_chain = [model, self._model_router.fallback_model]
        last_error: Exception | None = None
        for m in fallback_chain:
            try:
                return await self._llm.generate(
                    messages=messages,
                    model=m,
                    temperature=0.7,
                )
            except Exception as e:
                last_error = e
                continue
        raise last_error or RuntimeError("LLM generate failed")

    async def _stream_with_fallback(
        self, messages: list[LLMMessage], model: str
    ) -> AsyncIterator[str]:
        """Stream with fallback if model unavailable."""
        fallback_chain = [model, self._model_router.fallback_model]
        last_error: Exception | None = None
        for m in fallback_chain:
            try:
                async for chunk in self._llm.generate_stream(
                    messages=messages,
                    model=m,
                    temperature=0.7,
                ):
                    yield chunk
                return
            except Exception as e:
                last_error = e
                continue
        raise last_error or RuntimeError("LLM stream failed")
