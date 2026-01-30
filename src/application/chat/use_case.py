"""Chat use case - orchestration layer."""

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from src.application.chat.dto import ChatRequest, ChatResponse
from src.application.chat.handlers import CommandRegistry, get_default_registry
from src.domain.ports.llm import LLMMessage, LLMPort
from src.domain.ports.rag import RAGPort
from src.domain.services.intent_detector import IntentDetector
from src.domain.services.model_router import ModelRouter
from src.infrastructure.llm.reasoning_parser import stream_reasoning_chunks
from src.infrastructure.services.command_parser import parse_message
from src.infrastructure.services.assistant_modes import get_mode

if TYPE_CHECKING:
    from src.infrastructure.persistence.conversation_memory import ConversationMemory


class ChatUseCase:
    """Orchestrates chat: intent detection + command processing + LLM call."""

    def __init__(
        self,
        llm: LLMPort,
        model_router: ModelRouter,
        max_context_messages: int = 20,
        memory: "ConversationMemory | None" = None,
        rag: "RAGPort | None" = None,
        command_registry: CommandRegistry | None = None,
    ) -> None:
        self._llm = llm
        self._model_router = model_router
        self._max_context = max_context_messages
        self._memory = memory
        self._rag = rag
        self._intent_detector = IntentDetector()
        self._command_registry = command_registry or get_default_registry()

    async def execute(self, request: ChatRequest) -> ChatResponse:
        """Process chat request: detect intent, process commands, call LLM."""
        request = self._resolve_history(request)
        
        # Check for template intent (greetings, help, etc.)
        intent = self._intent_detector.detect(request.message)
        if intent.response is not None:
            return self._create_response(request, intent.response, "template")

        # Build messages with command processing
        messages = await self._build_messages(request)
        
        # Generate LLM response
        model = self._model_router.select_model(request.message)
        temperature = self._get_temperature(request)
        llm_response = await self._generate_with_fallback(messages, model, temperature)
        
        return self._create_response(request, llm_response.content, llm_response.model)

    async def execute_stream(
        self, request: ChatRequest
    ) -> AsyncIterator[tuple[str, str]]:
        """Stream LLM response. Yields (kind, chunk)."""
        request = self._resolve_history(request)
        
        # Check for template intent
        intent = self._intent_detector.detect(request.message)
        if intent.response is not None:
            yield ("content", intent.response)
            return

        # Build messages with command processing
        messages = await self._build_messages(request)
        model = self._model_router.select_model(request.message)
        temperature = self._get_temperature(request)
        
        # Stream response
        full_content: list[str] = []
        raw_stream = self._stream_with_fallback(messages, model, temperature)
        async for kind, text in stream_reasoning_chunks(raw_stream):
            if kind == "content":
                full_content.append(text)
            yield (kind, text)

        # Save conversation
        if full_content:
            self._save_to_memory(request, "".join(full_content), model)

    async def _build_messages(self, request: ChatRequest) -> list[LLMMessage]:
        """Build messages for LLM from request, history, and commands."""
        # Get system prompt based on mode
        mode = get_mode(request.mode_id or "default")
        
        messages: list[LLMMessage] = [
            LLMMessage(role="system", content=mode.system_prompt)
        ]
        
        # Add history
        if request.history:
            messages.extend(request.history[-self._max_context:])
        
        # Parse and process commands
        parsed = parse_message(request.message)
        extra_context = await self._process_commands(parsed.commands)
        
        # Build user message
        user_content = parsed.text or request.message
        if extra_context:
            user_content = f"{extra_context}\n\n---\n\n{user_content}"
        
        messages.append(LLMMessage(role="user", content=user_content))
        return messages

    async def _process_commands(self, commands: list) -> str:
        """Process all commands and return combined context."""
        if not commands:
            return ""
        
        context_parts: list[str] = []
        
        for cmd in commands:
            # Map CommandType enum to string
            cmd_type = cmd.type.value if hasattr(cmd.type, "value") else str(cmd.type)
            
            # Skip clear command (handled separately)
            if cmd_type == "clear":
                continue
            
            # Execute command via registry
            result = await self._command_registry.execute(
                cmd_type,
                cmd.argument,
                rag=self._rag,
            )
            
            if result.content:
                context_parts.append(result.content)
        
        return "\n\n---\n\n".join(context_parts)

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
                history=loaded[-self._max_context:],
                conversation_id=request.conversation_id,
                mode_id=request.mode_id,
            )
        return request

    def _create_response(
        self,
        request: ChatRequest,
        content: str,
        model: str,
    ) -> ChatResponse:
        """Create response and save to memory."""
        conv_id = request.conversation_id or (
            self._memory.create_id() if self._memory else None
        )
        
        response = ChatResponse(
            content=content,
            model=model,
            conversation_id=conv_id,
        )
        
        self._save_to_memory(request, content, model)
        return response

    def _save_to_memory(
        self,
        request: ChatRequest,
        content: str,
        model: str,
    ) -> None:
        """Save conversation to memory."""
        if not self._memory:
            return
        
        conv_id = request.conversation_id or self._memory.create_id()
        history = list(request.history or [])
        history.append(LLMMessage(role="user", content=request.message))
        history.append(LLMMessage(role="assistant", content=content))
        self._memory.save(conv_id, history[-self._max_context:])

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
