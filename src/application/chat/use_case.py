"""Chat use case - orchestration layer."""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING

from src.application.chat.dto import ChatRequest, ChatResponse
from src.domain.ports.llm import LLMMessage, LLMPort
from src.domain.ports.rag import RAGPort
from src.domain.services.intent_detector import IntentDetector
from src.domain.services.model_router import ModelRouter
from src.infrastructure.llm.reasoning_parser import stream_reasoning_chunks
from src.infrastructure.services.command_parser import (
    parse_message,
    CommandType,
    get_help_text,
)
from src.infrastructure.services.assistant_modes import get_mode
from src.infrastructure.services.web_search import search_duckduckgo, format_search_results

if TYPE_CHECKING:
    from src.infrastructure.persistence.conversation_memory import ConversationMemory


class ChatUseCase:
    """Orchestrates chat: intent detection + LLM call + command processing."""

    def __init__(
        self,
        llm: LLMPort,
        model_router: ModelRouter,
        max_context_messages: int = 20,
        memory: "ConversationMemory | None" = None,
        rag: "RAGPort | None" = None,
    ) -> None:
        self._llm = llm
        self._model_router = model_router
        self._max_context = max_context_messages
        self._memory = memory
        self._rag = rag
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

        messages = await self._build_messages(request)
        model = self._model_router.select_model(request.message)
        temperature = self._get_temperature(request)
        llm_response = await self._generate_with_fallback(messages, model, temperature)
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

        messages = await self._build_messages(request)
        model = self._model_router.select_model(request.message)
        temperature = self._get_temperature(request)
        full_content: list[str] = []
        raw_stream = self._stream_with_fallback(messages, model, temperature)
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

    async def _build_messages(self, request: ChatRequest) -> list[LLMMessage]:
        """Build messages for LLM from request, history, and commands."""
        # Get system prompt based on mode
        mode = get_mode(request.mode_id or "default")
        system_prompt = mode.system_prompt
        
        messages: list[LLMMessage] = [
            LLMMessage(role="system", content=system_prompt)
        ]
        
        if request.history:
            # Sliding window: keep last N messages
            history = request.history[-self._max_context :]
            messages.extend(history)
        
        # Parse commands from message
        parsed = parse_message(request.message)
        
        # Process commands and build context
        extra_context: list[str] = []
        
        for cmd in parsed.commands:
            if cmd.type == CommandType.HELP:
                # Return help immediately
                extra_context.append(get_help_text())
            
            elif cmd.type == CommandType.WEB and cmd.argument:
                # Web search
                try:
                    results = await search_duckduckgo(cmd.argument, max_results=5)
                    extra_context.append(format_search_results(results))
                except Exception as e:
                    extra_context.append(f"[Web search error: {e}]")
            
            elif cmd.type == CommandType.RAG and cmd.argument:
                # RAG search
                if self._rag:
                    try:
                        chunks = await self._rag.search(cmd.argument, limit=10)
                        if chunks:
                            context_parts = [f"## RAG Results for: {cmd.argument}\n"]
                            for c in chunks:
                                source = c.metadata.get("source", "unknown")
                                context_parts.append(f"### {source}\n```\n{c.content}\n```")
                            extra_context.append("\n".join(context_parts))
                    except Exception as e:
                        extra_context.append(f"[RAG error: {e}]")
            
            elif cmd.type in (CommandType.CODE, CommandType.FILE) and cmd.argument:
                # Read file
                try:
                    file_path = Path(cmd.argument)
                    if file_path.exists() and file_path.is_file():
                        content = file_path.read_text(encoding="utf-8", errors="replace")
                        if len(content) > 10000:
                            content = content[:10000] + "\n...[truncated]"
                        lang = file_path.suffix.lstrip(".") or "text"
                        extra_context.append(f"## File: {cmd.argument}\n```{lang}\n{content}\n```")
                    else:
                        extra_context.append(f"[File not found: {cmd.argument}]")
                except Exception as e:
                    extra_context.append(f"[File read error: {e}]")
        
        # Build user message with context
        user_content = parsed.text or request.message
        if extra_context:
            context_block = "\n\n---\n\n".join(extra_context)
            user_content = f"{context_block}\n\n---\n\n{user_content}"
        
        messages.append(LLMMessage(role="user", content=user_content))
        return messages
    
    def _get_temperature(self, request: ChatRequest) -> float:
        """Get temperature based on mode."""
        mode = get_mode(request.mode_id or "default")
        return mode.temperature

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

    async def _generate_with_fallback(
        self,
        messages: list[LLMMessage],
        model: str,
        temperature: float = 0.7,
    ):
        """Generate with fallback if model unavailable."""
        fallback_chain = [model, self._model_router.fallback_model]
        last_error: Exception | None = None
        for m in fallback_chain:
            try:
                return await self._llm.generate(
                    messages=messages,
                    model=m,
                    temperature=temperature,
                )
            except Exception as e:
                last_error = e
                continue
        raise last_error or RuntimeError("LLM generate failed")

    async def _stream_with_fallback(
        self,
        messages: list[LLMMessage],
        model: str,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Stream with fallback if model unavailable."""
        fallback_chain = [model, self._model_router.fallback_model]
        last_error: Exception | None = None
        for m in fallback_chain:
            try:
                async for chunk in self._llm.generate_stream(
                    messages=messages,
                    model=m,
                    temperature=temperature,
                ):
                    yield chunk
                return
            except Exception as e:
                last_error = e
                continue
        raise last_error or RuntimeError("LLM stream failed")
