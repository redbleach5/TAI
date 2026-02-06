"""Chat use case - orchestration layer."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from typing import TYPE_CHECKING

from src.application.chat.dto import ChatRequest, ChatResponse
from src.application.chat.handlers import CommandRegistry, get_default_registry
from src.application.shared.llm_fallback import generate_with_fallback, stream_with_fallback
from src.domain.ports.llm import LLMMessage, LLMPort
from src.domain.ports.rag import RAGPort
from src.domain.services.intent_detector import IntentDetector
from src.domain.services.model_selector import ModelSelector
from src.infrastructure.llm.reasoning_parser import stream_reasoning_chunks
from src.infrastructure.services.assistant_modes import get_mode
from src.infrastructure.services.command_parser import CommandType, parse_message

logger = logging.getLogger(__name__)

# When @web was requested but search failed — we return this in context and then short-circuit (no LLM)
WEB_FAILED_MARKER = "Web search was requested but could not be performed"
WEB_FAILED_USER_MESSAGE = (
    "Веб-поиск не выполнен: сервис недоступен или нет результатов. "
    "Проверьте подключение к интернету и попробуйте позже. "
    "Для надёжного поиска можно настроить API-ключ Brave (переменная BRAVE_API_KEY, см. документацию)."
)

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
        workspace_path_getter: "Callable[[], str] | None" = None,
        is_indexed_getter: "Callable[[], bool] | None" = None,
        web_search_searxng_url: str | None = None,
        web_search_brave_api_key: str | None = None,
        web_search_tavily_api_key: str | None = None,
        web_search_google_api_key: str | None = None,
        web_search_google_cx: str | None = None,
    ) -> None:
        """Initialize chat use case with LLM, selector, optional memory/RAG/agent."""
        self._llm = llm
        self._model_selector = model_selector
        self._max_context = max_context_messages
        self._memory = memory
        self._rag = rag
        self._intent_detector = IntentDetector()
        self._command_registry = command_registry or get_default_registry()
        self._agent_use_case = agent_use_case
        self._workspace_path_getter = workspace_path_getter
        self._is_indexed_getter = is_indexed_getter
        self._web_search_searxng_url = (web_search_searxng_url or "").strip() or None
        self._web_search_brave_api_key = (web_search_brave_api_key or "").strip() or None
        self._web_search_tavily_api_key = (web_search_tavily_api_key or "").strip() or None
        self._web_search_google_api_key = (web_search_google_api_key or "").strip() or None
        self._web_search_google_cx = (web_search_google_cx or "").strip() or None

    async def execute(self, request: ChatRequest) -> ChatResponse:
        """Process chat request: detect intent, process commands, call LLM."""
        logger.debug("Chat execute: message=%s, mode=%s", request.message[:80], request.mode_id)
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
        user_content = messages[-1].content if messages else ""
        if "@web" in request.message.lower() and WEB_FAILED_MARKER in user_content:
            return self._create_response(request, WEB_FAILED_USER_MESSAGE, "system")

        # Generate LLM response (use request.model if user selected one in UI)
        if request.model and request.model.strip():
            model, fallback = request.model.strip(), request.model.strip()
        else:
            model, fallback = await self._model_selector.select_model(request.message)
        temperature = self._get_temperature(request)
        llm_response = await self._generate_with_fallback(messages, model, fallback, temperature)

        return self._create_response(request, llm_response.content, llm_response.model)

    async def execute_stream(self, request: ChatRequest) -> AsyncIterator[tuple[str, str]]:
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
            yield (
                "done",
                json.dumps({"conversation_id": conv_id or request.conversation_id or "", "model": "template"}),
            )
            return

        # Build messages with command processing
        messages = await self._build_messages(request)
        user_content = messages[-1].content if messages else ""
        if "@web" in request.message.lower() and WEB_FAILED_MARKER in user_content:
            yield ("content", WEB_FAILED_USER_MESSAGE)
            conv_id = self._save_to_memory(request, WEB_FAILED_USER_MESSAGE, "system") if self._memory else None
            yield ("done", json.dumps({"conversation_id": conv_id or request.conversation_id or "", "model": "system"}))
            return

        # Use request.model if user selected one in UI
        if request.model and request.model.strip():
            model, fallback = request.model.strip(), request.model.strip()
        else:
            model, fallback = await self._model_selector.select_model(request.message)
        temperature = self._get_temperature(request)

        # Stream response
        full_content: list[str] = []
        raw_stream = self._stream_with_fallback(messages, model, fallback, temperature)
        async for kind, text in stream_reasoning_chunks(raw_stream):
            if kind == "content":
                full_content.append(text)
            yield (kind, text)

        # Save conversation and send conversation_id + model in done event (always JSON for watermark)
        conv_id: str | None = None
        if full_content:
            conv_id = self._save_to_memory(request, "".join(full_content), model)
        done_data = json.dumps({"conversation_id": conv_id or "", "model": model or ""})
        yield ("done", done_data)

    async def _build_messages(self, request: ChatRequest) -> list[LLMMessage]:
        """Build messages for LLM from request, history, and commands.

        Orchestrates sub-methods for each context section:
        1. System prompt + history
        2. Command processing + auto-RAG
        3. Project map, git context, open files, indexing hint
        """
        mode = get_mode(request.mode_id or "default")
        messages: list[LLMMessage] = [LLMMessage(role="system", content=mode.system_prompt)]

        if request.history:
            messages.extend(request.history[-self._max_context :])

        # Parse and process commands
        parsed = parse_message(request.message)
        extra_context = await self._process_commands(parsed.commands)
        extra_context = await self._maybe_add_auto_rag(parsed, request.message, extra_context)

        # Build user content through sub-methods
        user_content = parsed.text or request.message
        user_content = self._prepend_project_map(user_content)
        user_content = await self._prepend_auto_git(user_content, parsed.commands)
        user_content = self._prepend_open_files(user_content, request)
        user_content = self._prepend_extra_context(user_content, extra_context, parsed.commands)
        user_content = self._append_indexing_hint(user_content, parsed.text or request.message)

        messages.append(LLMMessage(role="user", content=user_content))
        return messages

    async def _maybe_add_auto_rag(self, parsed, raw_message: str, extra_context: str) -> str:
        """Auto-RAG: inject relevant codebase chunks if no explicit @rag command."""
        has_rag_cmd = any(
            getattr(c, "type", None) and str(getattr(c.type, "value", c.type)) == "rag" for c in parsed.commands
        )
        if not has_rag_cmd and self._rag and (parsed.text or raw_message).strip():
            auto_rag = await self._auto_rag_search((parsed.text or raw_message).strip())
            if auto_rag:
                return f"{auto_rag}\n\n---\n\n{extra_context}" if extra_context else auto_rag
        return extra_context

    def _prepend_project_map(self, user_content: str) -> str:
        """Prepend short project structure so model sees layout."""
        if not self._rag or not hasattr(self._rag, "get_project_map_markdown"):
            return user_content
        try:
            map_md = self._rag.get_project_map_markdown()
            if map_md:
                return f"[Project structure]\n{map_md[:1500]}\n\n---\n\n{user_content}"
        except Exception:
            logger.debug("Failed to get project map for chat context", exc_info=True)
        return user_content

    async def _prepend_auto_git(self, user_content: str, commands: list) -> str:
        """Auto-inject git status when no explicit @git/@diff command."""
        has_git_cmd = any(
            getattr(c, "type", None) and str(getattr(c.type, "value", c.type)) in ("git", "diff")
            for c in commands
        )
        if not has_git_cmd:
            git_hint = await self._auto_git_context()
            if git_hint:
                return f"{git_hint}\n\n---\n\n{user_content}"
        return user_content

    def _prepend_open_files(self, user_content: str, request: ChatRequest) -> str:
        """Prepend open editor files and active file hint (Cursor-like)."""
        current_file_hint = ""
        if request.active_file_path:
            current_file_hint = f"Current file (user is focused on): {request.active_file_path}\n\n"
        if request.context_files:
            file_context = "\n\n".join(f"[file: {f.path}]\n```\n{f.content}\n```" for f in request.context_files)
            return f"{current_file_hint}[Open files in editor — use these for context]\n\n{file_context}\n\n---\n\n{user_content}"
        if current_file_hint:
            return f"{current_file_hint}---\n\n{user_content}"
        return user_content

    def _prepend_extra_context(self, user_content: str, extra_context: str, commands: list) -> str:
        """Prepend command results (web search, RAG, etc.) to user content."""
        if not extra_context:
            return user_content
        if any(c.type == CommandType.WEB for c in commands) and WEB_FAILED_MARKER not in extra_context:
            extra_context = (
                "Результаты веб-поиска (обязательно используй их для ответа на вопрос пользователя):\n\n"
                + extra_context
            )
        return f"{extra_context}\n\n---\n\n{user_content}"

    def _append_indexing_hint(self, user_content: str, query: str) -> str:
        """Append indexing hint when project is not indexed."""
        if (
            self._rag
            and self._is_indexed_getter
            and not self._is_indexed_getter()
            and query.strip()
        ):
            user_content += (
                "\n\n[Note: Project not indexed. To search the codebase, user can run Index in the UI "
                "or switch to Agent mode and ask to index the project.]"
            )
        return user_content

    async def _auto_git_context(self) -> str:
        """Auto-inject short git status so model knows what files changed (Cursor-like)."""
        workspace_path = self._workspace_path_getter() if self._workspace_path_getter else None
        if not workspace_path:
            return ""
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "status", "--short", "--branch",
                cwd=workspace_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            if proc.returncode != 0:
                return ""
            status = stdout.decode("utf-8", errors="replace").strip()
            if not status:
                return ""
            # Limit to first 30 lines to avoid huge context
            lines = status.splitlines()
            if len(lines) > 30:
                status = "\n".join(lines[:30]) + f"\n... and {len(lines) - 30} more files"
            return f"[Git status — recent changes in project]\n```\n{status}\n```"
        except Exception:
            logger.debug("Auto git-context failed", exc_info=True)
            return ""

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
            return "[Relevant code from project]\n\n" + "\n\n".join(parts)
        except Exception:
            logger.debug("Auto-RAG search failed", exc_info=True)
            return ""

    async def _process_commands(self, commands: list) -> str:
        """Process all @ commands in parallel and return combined context.

        Each command (@web, @rag, @code, @file) is executed concurrently.
        Results are joined as context sections separated by '---'.
        When @web fails, a special marker is injected to short-circuit the response.
        """
        if not commands:
            return ""

        import asyncio

        # Prepare command execution tasks
        workspace_path = self._workspace_path_getter() if self._workspace_path_getter else None

        async def execute_cmd(cmd):
            cmd_type = cmd.type.value if hasattr(cmd.type, "value") else str(cmd.type)
            if cmd_type == "clear":
                return None
            result = await self._command_registry.execute(
                cmd_type,
                cmd.argument,
                rag=self._rag,
                workspace_path=workspace_path,
                web_search_searxng_url=self._web_search_searxng_url,
                web_search_brave_api_key=self._web_search_brave_api_key,
                web_search_tavily_api_key=self._web_search_tavily_api_key,
                web_search_google_api_key=self._web_search_google_api_key,
                web_search_google_cx=self._web_search_google_cx,
            )
            return result.content if result.content else None

        # Execute ALL commands in parallel
        tasks = [execute_cmd(cmd) for cmd in commands]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect successful results; when @web was requested but failed, add a note so we
        # short-circuit and show "web search unavailable" instead of calling the LLM with "[No search results found]"
        web_failed_note = (
            f"[{WEB_FAILED_MARKER} (temporarily unavailable or no results). "
            "Do not claim you have no internet. Tell the user that web search is temporarily unavailable.]"
        )
        no_results_placeholder = "[No search results found]"
        context_parts = []
        for cmd, r in zip(commands, results):
            if cmd.type == CommandType.WEB and (
                r is None
                or isinstance(r, Exception)
                or (isinstance(r, str) and (not r.strip() or r.strip() == no_results_placeholder))
            ):
                context_parts.append(web_failed_note)
            elif r and not isinstance(r, Exception) and (r.strip() != no_results_placeholder):
                context_parts.append(r)

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
                history=loaded[-self._max_context :],
                conversation_id=request.conversation_id,
                mode_id=request.mode_id,
                model=request.model,
                context_files=request.context_files,
                active_file_path=request.active_file_path,
                apply_edits_required=request.apply_edits_required,
            )
        return request

    def _create_response(
        self,
        request: ChatRequest,
        content: str,
        model: str,
    ) -> ChatResponse:
        """Create response and save to memory."""
        conv_id = request.conversation_id or (self._memory.create_id() if self._memory else None)

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
        self._memory.save(conv_id, history[-self._max_context :])
        return conv_id

    async def _generate_with_fallback(
        self,
        messages: list[LLMMessage],
        model: str,
        fallback: str,
        temperature: float = 0.7,
    ):
        """Generate with fallback if model unavailable."""
        return await generate_with_fallback(self._llm, messages, [model, fallback], temperature=temperature)

    async def _stream_with_fallback(
        self,
        messages: list[LLMMessage],
        model: str,
        fallback: str,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Stream with fallback if model unavailable."""
        async for chunk in stream_with_fallback(self._llm, messages, [model, fallback], temperature=temperature):
            yield chunk
