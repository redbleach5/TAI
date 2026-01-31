"""Agent Use Case - native Ollama tools or ReAct-style fallback."""

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from src.application.agent.ollama_tools import AGENT_SYSTEM_PROMPT_NATIVE, OLLAMA_TOOLS
from src.application.agent.tool_parser import parse_tool_call, strip_tool_call_from_content
from src.application.agent.tools import AGENT_TOOLS_PROMPT, ToolExecutor
from src.application.chat.dto import ChatRequest, ChatResponse
from src.domain.ports.llm import LLMMessage, LLMPort
from src.domain.services.model_router import ModelRouter

if TYPE_CHECKING:
    from src.domain.ports.rag import RAGPort


AGENT_SYSTEM_PROMPT = """You are an autonomous coding agent. You can read files, write files, search the codebase, run terminal commands, and list directories.

Your goal: accomplish the user's task step by step. Use tools when needed. Think before acting.

""" + AGENT_TOOLS_PROMPT


class AgentUseCase:
    """Orchestrates agent loop: LLM → tool call → execute → Observation → LLM."""

    def __init__(
        self,
        llm: LLMPort,
        model_router: ModelRouter,
        rag: "RAGPort | None" = None,
        max_iterations: int = 10,
    ) -> None:
        self._llm = llm
        self._model_router = model_router
        self._rag = rag
        self._max_iterations = max_iterations

    def _use_native_tools(self) -> bool:
        """Check if LLM supports native tool calling (Ollama)."""
        return hasattr(self._llm, "chat_with_tools") and callable(getattr(self._llm, "chat_with_tools"))

    def _build_ollama_messages(self, request: ChatRequest) -> list[dict[str, Any]]:
        """Build messages in Ollama format for native tools."""
        msgs: list[dict[str, Any]] = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT_NATIVE},
        ]
        if request.history:
            for m in request.history[-15:]:
                msgs.append({"role": m.role, "content": m.content})
        user_content = request.message
        if request.context_files:
            file_ctx = "\n\n".join(
                f"[file: {f.path}]\n```\n{f.content[:2000]}\n```"
                for f in request.context_files
            )
            user_content = f"[Open files]\n{file_ctx}\n\n---\n\n{user_content}"
        msgs.append({"role": "user", "content": user_content})
        return msgs

    async def execute(self, request: ChatRequest) -> ChatResponse:
        """Run agent loop until done or max iterations."""
        model = request.model or self._model_router.select_model(request.message)
        executor = ToolExecutor(workspace_path=None, rag=self._rag)

        if self._use_native_tools():
            return await self._execute_native(request, model, executor)
        return await self._execute_prompt_based(request, model, executor)

    async def _execute_native(
        self, request: ChatRequest, model: str, executor: ToolExecutor
    ) -> ChatResponse:
        """Native Ollama tool calling."""
        messages = self._build_ollama_messages(request)
        full_content: list[str] = []

        for _ in range(self._max_iterations):
            content, tool_calls = await self._llm.chat_with_tools(
                messages=messages,
                tools=OLLAMA_TOOLS,
                model=model,
                temperature=0.3,
            )
            full_content.append(content)

            if not tool_calls:
                break

            # Ollama format: assistant with tool_calls, then one tool message per call
            ollama_tool_calls = [
                {"type": "function", "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                for tc in tool_calls
            ]
            messages.append({"role": "assistant", "content": content, "tool_calls": ollama_tool_calls})

            for tc in tool_calls:
                name = tc.get("name", "")
                args = tc.get("arguments", {}) or {}
                result = await executor.execute(name, args)
                obs = result.content if result.success else f"Error: {result.error}"
                messages.append({"role": "tool", "tool_name": name, "content": obs})

        final = "\n\n".join(full_content).strip()
        if not final:
            final = "*Модель не вернула ответ. Проверь, что модель поддерживает tool calling (GLM 4.7, Qwen, Llama 3.1+).*"
        return ChatResponse(content=final, model=model, conversation_id=request.conversation_id)

    async def _execute_prompt_based(
        self, request: ChatRequest, model: str, executor: ToolExecutor
    ) -> ChatResponse:
        """Prompt-based ReAct fallback."""
        messages = self._build_initial_messages(request)
        full_content: list[str] = []

        for _ in range(self._max_iterations):
            response = await self._generate(messages, model)
            content = response.content
            full_content.append(content)

            tool_call = parse_tool_call(content)
            if not tool_call:
                text = strip_tool_call_from_content(content)
                if text:
                    full_content[-1] = text
                break

            result = await executor.execute(tool_call.tool, tool_call.args)
            obs = result.content if result.success else f"Error: {result.error}"
            messages.append(LLMMessage(role="assistant", content=content))
            messages.append(LLMMessage(role="user", content=f"Observation:\n{obs}"))

        final_content = "\n\n".join(full_content)
        return ChatResponse(content=final_content, model=model, conversation_id=request.conversation_id)

    async def execute_stream(
        self, request: ChatRequest
    ) -> AsyncIterator[tuple[str, str]]:
        """Stream agent response with tool_call and tool_result events."""
        model = request.model or self._model_router.select_model(request.message)
        executor = ToolExecutor(workspace_path=None, rag=self._rag)

        if self._use_native_tools():
            async for evt in self._execute_stream_native(request, model, executor):
                yield evt
        else:
            async for evt in self._execute_stream_prompt_based(request, model, executor):
                yield evt

    async def _execute_stream_native(
        self, request: ChatRequest, model: str, executor: ToolExecutor
    ) -> AsyncIterator[tuple[str, str]]:
        """Stream with native Ollama tools."""
        messages = self._build_ollama_messages(request)

        for _ in range(self._max_iterations):
            content_buf = ""
            tool_calls: list[dict] = []
            async for kind, data in self._llm.chat_with_tools_stream(
                messages=messages, tools=OLLAMA_TOOLS, model=model, temperature=0.3
            ):
                if kind == "content" and data:
                    content_buf += data
                    yield ("content", data)
                elif kind == "tool_calls" and data:
                    tool_calls = data

            if not tool_calls:
                break

            ollama_tool_calls = [
                {"type": "function", "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                for tc in tool_calls
            ]
            messages.append({"role": "assistant", "content": content_buf, "tool_calls": ollama_tool_calls})

            for tc in tool_calls:
                name = tc.get("name", "")
                args = tc.get("arguments", {}) or {}
                yield ("tool_call", f"{name}: {args}")
                result = await executor.execute(name, args)
                obs = result.content if result.success else f"Error: {result.error}"
                yield ("tool_result", obs[:500] + ("..." if len(obs) > 500 else ""))
                messages.append({"role": "tool", "tool_name": name, "content": obs})

    async def _execute_stream_prompt_based(
        self, request: ChatRequest, model: str, executor: ToolExecutor
    ) -> AsyncIterator[tuple[str, str]]:
        """Stream with prompt-based ReAct fallback."""
        messages = self._build_initial_messages(request)

        for _ in range(self._max_iterations):
            chunk_buffer: list[str] = []
            async for chunk in self._stream(messages, model):
                chunk_buffer.append(chunk)
                yield ("content", chunk)

            content = "".join(chunk_buffer)
            tool_call = parse_tool_call(content)
            if not tool_call:
                if not content.strip():
                    fallback = "*Модель не вернула ответ. Для режима Агент нужна модель с поддержкой tool-calling (Qwen 2.5, Llama 3.1+).*"
                    yield ("content", fallback)
                break

            yield ("tool_call", f"{tool_call.tool}: {tool_call.args}")
            result = await executor.execute(tool_call.tool, tool_call.args)
            obs = result.content if result.success else f"Error: {result.error}"
            yield ("tool_result", obs[:500] + ("..." if len(obs) > 500 else ""))

            messages.append(LLMMessage(role="assistant", content=content))
            messages.append(LLMMessage(role="user", content=f"Observation:\n{obs}"))


    def _build_initial_messages(self, request: ChatRequest) -> list[LLMMessage]:
        messages: list[LLMMessage] = [
            LLMMessage(role="system", content=AGENT_SYSTEM_PROMPT),
        ]
        if request.history:
            messages.extend(request.history[-15:])
        user_content = request.message
        if request.context_files:
            file_ctx = "\n\n".join(
                f"[file: {f.path}]\n```\n{f.content[:2000]}\n```"
                for f in request.context_files
            )
            user_content = f"[Open files]\n{file_ctx}\n\n---\n\n{user_content}"
        messages.append(LLMMessage(role="user", content=user_content))
        return messages

    async def _generate(
        self, messages: list[LLMMessage], model: str
    ):
        fallback = [model, self._model_router.fallback_model]
        last_err: Exception | None = None
        for m in fallback:
            try:
                return await self._llm.generate(
                    messages=messages,
                    model=m,
                    temperature=0.3,
                )
            except Exception as e:
                last_err = e
        raise last_err or RuntimeError("LLM failed")

    async def _stream(
        self, messages: list[LLMMessage], model: str
    ) -> AsyncIterator[str]:
        fallback = [model, self._model_router.fallback_model]
        last_err: Exception | None = None
        for m in fallback:
            try:
                async for chunk in self._llm.generate_stream(
                    messages=messages,
                    model=m,
                    temperature=0.3,
                ):
                    yield chunk
                return
            except Exception as e:
                last_err = e
        raise last_err or RuntimeError("LLM stream failed")
