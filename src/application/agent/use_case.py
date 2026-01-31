"""Agent Use Case - ReAct-style agent loop with tool execution."""

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

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

    async def execute(self, request: ChatRequest) -> ChatResponse:
        """Run agent loop until done or max iterations."""
        model = request.model or self._model_router.select_model(request.message)
        messages = self._build_initial_messages(request)
        executor = ToolExecutor(workspace_path=None, rag=self._rag)
        full_content: list[str] = []

        for _ in range(self._max_iterations):
            response = await self._generate(messages, model)
            content = response.content
            full_content.append(content)

            tool_call = parse_tool_call(content)
            if not tool_call:
                # No tool call - final answer
                text = strip_tool_call_from_content(content)
                if text:
                    full_content[-1] = text
                break

            # Execute tool
            result = await executor.execute(tool_call.tool, tool_call.args)
            obs = result.content if result.success else f"Error: {result.error}"

            # Add assistant message (with tool call) and observation
            messages.append(LLMMessage(role="assistant", content=content))
            messages.append(LLMMessage(role="user", content=f"Observation:\n{obs}"))

        final_content = "\n\n".join(full_content)
        return ChatResponse(content=final_content, model=model, conversation_id=request.conversation_id)

    async def execute_stream(
        self, request: ChatRequest
    ) -> AsyncIterator[tuple[str, str]]:
        """Stream agent response with tool_call and tool_result events."""
        model = request.model or self._model_router.select_model(request.message)
        messages = self._build_initial_messages(request)
        executor = ToolExecutor(workspace_path=None, rag=self._rag)
        full_content: list[str] = []

        for iteration in range(self._max_iterations):
            # Stream LLM response
            chunk_buffer: list[str] = []
            async for chunk in self._stream(messages, model):
                chunk_buffer.append(chunk)
                yield ("content", chunk)

            content = "".join(chunk_buffer)
            full_content.append(content)

            tool_call = parse_tool_call(content)
            if not tool_call:
                # Пустой ответ — показываем подсказку
                if not content.strip():
                    fallback = "*Модель не вернула ответ. Для режима Агент нужна модель с поддержкой tool-calling (Qwen 2.5, Llama 3.1+).*"
                    full_content[-1] = fallback
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
