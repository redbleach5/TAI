"""Chat use case - orchestration layer."""

import json
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from src.application.chat.dto import ChatRequest, ChatResponse
from src.application.chat.handlers import CommandRegistry, get_default_registry
from src.domain.ports.llm import LLMMessage, LLMPort
from src.domain.ports.rag import RAGPort
from src.domain.services.intent_detector import IntentDetector
from src.domain.services.model_selector import ModelSelector
from src.infrastructure.llm.reasoning_parser import stream_reasoning_chunks
from src.infrastructure.services.command_parser import parse_message
from src.infrastructure.services.assistant_modes import get_mode

if TYPE_CHECKING:
    from src.application.agent.use_case import AgentUseCase
    from src.infrastructure.persistence.conversation_memory import ConversationMemory


class ChatUseCase:
    """Orchestrates chat: intent detection + command processing + LLM call."""

    def __init__(
        self,
        llm: LLMPort,
        model_selector: ModelSelector,
        max_context_messages: int = 20,
        memory: "ConversationMemory | None" = None,
        rag: "RAGPort | None" = None,
        command_registry: CommandRegistry | None = None,
        agent_use_case: "AgentUseCase | None" = None,
    ) -> None:
        self._llm = llm
        self._model_selector = model_selector
        self._max_context = max_context_messages
        self._memory = memory
        self._rag = rag
        self._intent_detector = IntentDetector()
        self._command_registry = command_registry or get_default_registry()
        self._agent_use_case = agent_use_case

    async def execute(self, request: ChatRequest) -> ChatResponse:
        """Process chat request: detect intent, process commands, call LLM."""
        request = self._resolve_history(request)

        # Agent mode: delegate to AgentUseCase
        if request.mode_id == "agent" and self._agent_use_case:
            return await self._agent_use_case.execute(request)
        
        # Check for template intent (greetings, help, etc.)
        intent = self._intent_detector.detect(request.message)
        if intent.response is not None:
            return self._create_response(request, intent.response, "template")

        # Build messages with command processing
        messages = await self._build_messages(request)
        
        # Generate LLM response
        model, fallback = await self._model_selector.select_model(request.message)
        temperature = self._get_temperature(request)
        llm_response = await self._generate_with_fallback(messages, model, fallback, temperature)
        
        return self._create_response(request, llm_response.content, llm_response.model)

    async def execute_stream(
        self, request: ChatRequest
    ) -> AsyncIterator[tuple[str, str]]:
        """Stream LLM response. Yields (kind, chunk)."""
        request = self._resolve_history(request)

        # Agent mode: delegate to AgentUseCase
        if request.mode_id == "agent" and self._agent_use_case:
            model = request.model or (await self._model_selector.select_model(request.message))[0]
            req_with_model = request.model_copy(update={"model": model}) if not request.model else request
            async for kind, chunk in self._agent_use_case.execute_stream(req_with_model):
                yield (kind, chunk)
            yield ("done", json.dumps({"conversation_id": request.conversation_id or "", "model": model}))
            return
        
        # Check for template intent
        intent = self._intent_detector.detect(request.message)
        if intent.response is not None:
            yield ("content", intent.response)
            conv_id = self._save_to_memory(request, intent.response, "template") if self._memory else None
            yield ("done", json.dumps({"conversation_id": conv_id or request.conversation_id or "", "model": "template"}))
            return

        # Build messages with command processing
        messages = await self._build_messages(request)
        model, fallback = await self._model_selector.select_model(request.message)
        temperature = self._get_temperature(request)
        
        # Stream response
        full_content: list[str] = []
        raw_stream = self._stream_with_fallback(messages, model, fallback, temperature)
        async for kind, text in stream_reasoning_chunks(raw_stream):
            if kind == "content":
                full_content.append(text)
            yield (kind, text)

        # Save conversation and send conversation_id in done event
        conv_id: str | None = None
        if full_content:
            conv_id = self._save_to_memory(request, "".join(full_content), model)
        # done event: JSON with conversation_id and model for watermark
        done_data = conv_id or ""
        if model:
            done_data = json.dumps({"conversation_id": conv_id or "", "model": model})
        yield ("done", done_data)

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
        
        # B4: Auto-RAG — if no @rag command, inject relevant chunks
        has_rag_cmd = any(
            getattr(c, "type", None) and str(getattr(c.type, "value", c.type)) == "rag"
            for c in parsed.commands
        )
        if not has_rag_cmd and self._rag and (parsed.text or request.message).strip():
            auto_rag = await self._auto_rag_search((parsed.text or request.message).strip())
            if auto_rag:
                extra_context = f"{auto_rag}\n\n---\n\n{extra_context}" if extra_context else auto_rag
        
        # Build user message
        user_content = parsed.text or request.message
        # Prepend context: open files (Cursor-like) first, then commands
        if request.context_files:
            file_context = "\n\n".join(
                f"[file: {f.path}]\n```\n{f.content}\n```"
                for f in request.context_files
            )
            user_content = f"[Context - open files in IDE]\n\n{file_context}\n\n---\n\n{user_content}"
        if extra_context:
            user_content = f"{extra_context}\n\n---\n\n{user_content}"
        
        messages.append(LLMMessage(role="user", content=user_content))
        return messages

    async def _auto_rag_search(self, query: str) -> str:
        """B4: Auto RAG search when user doesn't use @rag."""
        if not query or len(query) < 5:
            return ""
        try:
            chunks = await self._rag.search(query, limit=5, min_score=0.4)
            if not chunks:
                return ""
            parts = []
            for c in chunks[:5]:
                src = c.metadata.get("source", "unknown")
                parts.append(f"### {src}\n```\n{c.content[:400]}\n```")
            return f"[Relevant code from project]\n\n" + "\n\n".join(parts)
        except Exception:
            return ""

    async def _process_commands(self, commands: list) -> str:
        """Process all commands in PARALLEL and return combined context."""
        if not commands:
            return ""
        
        import asyncio
        
        # Prepare command execution tasks
        async def execute_cmd(cmd):
            cmd_type = cmd.type.value if hasattr(cmd.type, "value") else str(cmd.type)
            if cmd_type == "clear":
                return None
            result = await self._command_registry.execute(
                cmd_type,
                cmd.argument,
                rag=self._rag,
            )
            return result.content if result.content else None
        
        # Execute ALL commands in parallel
        tasks = [execute_cmd(cmd) for cmd in commands]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect successful results
        context_parts = [r for r in results if r and not isinstance(r, Exception)]
        
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
    ) -> str | None:
        """Save conversation to memory. Returns conversation_id used."""
        if not self._memory:
            return None
        
        conv_id = request.conversation_id or self._memory.create_id()
        history = list(request.history or [])
        history.append(LLMMessage(role="user", content=request.message))
        history.append(LLMMessage(role="assistant", content=content))
        self._memory.save(conv_id, history[-self._max_context:])
        return conv_id

    async def _generate_with_fallback(
        self,
        messages: list[LLMMessage],
        model: str,
        fallback: str,
        temperature: float = 0.7,
    ):
        """Generate with fallback if model unavailable."""
        fallback_chain = [model, fallback]
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
        fallback: str,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Stream with fallback if model unavailable."""
        fallback_chain = [model, fallback]
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
