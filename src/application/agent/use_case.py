"""Agent Use Case - native Ollama tools or ReAct-style fallback."""

import json
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from src.application.agent.ollama_tools import AGENT_SYSTEM_PROMPT_NATIVE, OLLAMA_TOOLS
from src.application.agent.tool_parser import parse_all_tool_calls, parse_tool_call, strip_tool_call_from_content
from src.application.agent.tools import AGENT_TOOLS_PROMPT, ToolExecutor
from src.application.chat.dto import ChatRequest, ChatResponse
from src.domain.ports.llm import LLMMessage, LLMPort
from src.domain.services.model_selector import ModelSelector

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
        model_selector: ModelSelector,
        rag: "RAGPort | None" = None,
        max_iterations: int = 15,
    ) -> None:
        self._llm = llm
        self._model_selector = model_selector
        self._rag = rag
        self._max_iterations = max_iterations

    def _use_native_tools(self) -> bool:
        """Check if LLM supports native tool calling (Ollama)."""
        return hasattr(self._llm, "chat_with_tools") and callable(getattr(self._llm, "chat_with_tools"))

    async def _get_agent_context(self, message: str) -> tuple[str, str]:
        """C1: RAG search + project map for agent context."""
        rag_context = ""
        project_map = ""
        if not self._rag or not message.strip():
            return rag_context, project_map
        try:
            chunks = await self._rag.search(message.strip(), limit=6, min_score=0.4)
            if chunks:
                parts = [f"### {c.metadata.get('source', '?')}\n```\n{c.content[:500]}\n```" for c in chunks[:5]]
                rag_context = "[Relevant code]\n\n" + "\n\n".join(parts)
        except Exception:
            pass
        if self._rag and hasattr(self._rag, "get_project_map_markdown"):
            try:
                map_md = self._rag.get_project_map_markdown()
                if map_md:
                    project_map = map_md[:2000]
            except Exception:
                pass
        return rag_context, project_map

    def _build_ollama_messages(
        self,
        request: ChatRequest,
        rag_context: str = "",
        project_map: str = "",
    ) -> list[dict[str, Any]]:
        """Build messages in Ollama format for native tools."""
        system = AGENT_SYSTEM_PROMPT_NATIVE
        if project_map:
            system = f"[Project structure]\n{project_map}\n\n---\n\n{system}"
        msgs: list[dict[str, Any]] = [{"role": "system", "content": system}]
        if request.history:
            for m in request.history[-15:]:
                msgs.append({"role": m.role, "content": m.content})
        user_content = request.message
        if request.active_file_path:
            user_content = f"Current file (user focused): {request.active_file_path}\n\n---\n\n{user_content}"
        if rag_context:
            user_content = f"{rag_context}\n\n---\n\n{user_content}"
        if request.context_files:
            file_ctx = "\n\n".join(
                f"[file: {f.path}]\n```\n{f.content[:2000]}\n```"
                for f in request.context_files
            )
            user_content = f"[Open files]\n{file_ctx}\n\n---\n\n{user_content}"
        msgs.append({"role": "user", "content": user_content})
        return msgs

    async def execute(self, request: ChatRequest) -> ChatResponse:
        """Run agent loop until done or max iterations (sync: writes to disk, no proposed_edits)."""
        model, fallback = await self._model_selector.select_model(request.message)
        model = request.model or model
        executor = ToolExecutor(workspace_path=None, rag=self._rag, propose_edits=False)

        if self._use_native_tools():
            return await self._execute_native(request, model, executor)
        return await self._execute_prompt_based(request, model, fallback, executor)

    async def _execute_native(
        self, request: ChatRequest, model: str, executor: ToolExecutor
    ) -> ChatResponse:
        """Native Ollama tool calling."""
        rag_context, project_map = await self._get_agent_context(request.message)
        messages = self._build_ollama_messages(request, rag_context=rag_context, project_map=project_map)
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

            # Assistant message with tool_calls (include id for OpenAI/LM Studio)
            tool_calls_for_msg = [
                {
                    **({"id": tc["id"]} if tc.get("id") else {}),
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc.get("arguments", {}) or {}},
                }
                for tc in tool_calls
            ]
            messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls_for_msg})

            for tc in tool_calls:
                name = tc.get("name", "")
                args = tc.get("arguments", {}) or {}
                result = await executor.execute(name, args)
                obs = result.content if result.success else f"Error: {result.error}"
                msg = {"role": "tool", "content": obs}
                if tc.get("id"):
                    msg["tool_call_id"] = tc["id"]
                messages.append(msg)

        final = "\n\n".join(full_content).strip()
        if not final:
            final = "*Модель не вернула ответ. Проверь, что модель поддерживает tool calling (GLM 4.7, Qwen, Llama 3.1+).*"
        return ChatResponse(content=final, model=model, conversation_id=request.conversation_id)

    async def _execute_prompt_based(
        self, request: ChatRequest, model: str, fallback: str, executor: ToolExecutor
    ) -> ChatResponse:
        """Prompt-based ReAct fallback."""
        rag_context, project_map = await self._get_agent_context(request.message)
        messages = self._build_initial_messages(request, rag_context=rag_context, project_map=project_map)
        full_content: list[str] = []

        for _ in range(self._max_iterations):
            response = await self._generate(messages, model, fallback)
            content = response.content
            full_content.append(content)

            tool_calls = parse_all_tool_calls(content)
            if not tool_calls:
                text = strip_tool_call_from_content(content)
                if text:
                    full_content[-1] = text
                break

            # B3: Execute all tool calls (multi-file write support)
            obs_parts: list[str] = []
            for i, tc in enumerate(tool_calls, 1):
                result = await executor.execute(tc.tool, tc.args)
                obs_parts.append(f"[{i}] {tc.tool}: {result.content if result.success else f'Error: {result.error}'}")
            obs = "\n".join(obs_parts)
            messages.append(LLMMessage(role="assistant", content=content))
            messages.append(LLMMessage(role="user", content=f"Observation:\n{obs}"))

        final_content = "\n\n".join(full_content)
        return ChatResponse(content=final_content, model=model, conversation_id=request.conversation_id)

    async def execute_stream(
        self, request: ChatRequest
    ) -> AsyncIterator[tuple[str, str]]:
        """Stream agent response with tool_call, tool_result, and proposed_edit events (Cursor-like apply/reject)."""
        model, fallback = await self._model_selector.select_model(request.message)
        model = request.model or model
        propose_edits = getattr(request, "apply_edits_required", True)
        executor = ToolExecutor(workspace_path=None, rag=self._rag, propose_edits=propose_edits)

        if self._use_native_tools():
            async for evt in self._execute_stream_native(request, model, executor):
                yield evt
        else:
            async for evt in self._execute_stream_prompt_based(request, model, fallback, executor):
                yield evt

    async def _execute_stream_native(
        self, request: ChatRequest, model: str, executor: ToolExecutor
    ) -> AsyncIterator[tuple[str, str]]:
        """Stream with native Ollama tools."""
        rag_context, project_map = await self._get_agent_context(request.message)
        messages = self._build_ollama_messages(request, rag_context=rag_context, project_map=project_map)

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

            tool_calls_for_msg = [
                {
                    **({"id": tc["id"]} if tc.get("id") else {}),
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc.get("arguments", {}) or {}},
                }
                for tc in tool_calls
            ]
            messages.append({"role": "assistant", "content": content_buf, "tool_calls": tool_calls_for_msg})

            for tc in tool_calls:
                name = tc.get("name", "")
                args = tc.get("arguments", {}) or {}
                yield ("tool_call", f"{name}: {args}")
                result = await executor.execute(name, args)
                if result.proposed_edit:
                    yield ("proposed_edit", json.dumps(result.proposed_edit))
                obs = result.content if result.success else f"Error: {result.error}"
                yield ("tool_result", obs[:500] + ("..." if len(obs) > 500 else ""))
                msg = {"role": "tool", "content": obs}
                if tc.get("id"):
                    msg["tool_call_id"] = tc["id"]
                messages.append(msg)

    async def _execute_stream_prompt_based(
        self, request: ChatRequest, model: str, fallback: str, executor: ToolExecutor
    ) -> AsyncIterator[tuple[str, str]]:
        """Stream with prompt-based ReAct fallback."""
        rag_context, project_map = await self._get_agent_context(request.message)
        messages = self._build_initial_messages(request, rag_context=rag_context, project_map=project_map)

        for _ in range(self._max_iterations):
            chunk_buffer: list[str] = []
            async for chunk in self._stream(messages, model, fallback):
                chunk_buffer.append(chunk)
                yield ("content", chunk)

            content = "".join(chunk_buffer)
            tool_calls = parse_all_tool_calls(content)
            if not tool_calls:
                if not content.strip():
                    fallback = "*Модель не вернула ответ. Для режима Агент нужна модель с поддержкой tool-calling (Qwen 2.5, Llama 3.1+).*"
                    yield ("content", fallback)
                break

            # B3: Execute all tool calls (multi-file write support)
            obs_parts: list[str] = []
            for tc in tool_calls:
                yield ("tool_call", f"{tc.tool}: {tc.args}")
                result = await executor.execute(tc.tool, tc.args)
                if result.proposed_edit:
                    yield ("proposed_edit", json.dumps(result.proposed_edit))
                obs_text = result.content if result.success else f"Error: {result.error}"
                obs_parts.append(obs_text)
                yield ("tool_result", obs_text[:500] + ("..." if len(obs_text) > 500 else ""))
            obs = "\n".join(obs_parts)

            messages.append(LLMMessage(role="assistant", content=content))
            messages.append(LLMMessage(role="user", content=f"Observation:\n{obs}"))


    def _build_initial_messages(
        self,
        request: ChatRequest,
        rag_context: str = "",
        project_map: str = "",
    ) -> list[LLMMessage]:
        system = AGENT_SYSTEM_PROMPT
        if project_map:
            system = f"[Project structure]\n{project_map}\n\n---\n\n{system}"
        messages: list[LLMMessage] = [LLMMessage(role="system", content=system)]
        if request.history:
            messages.extend(request.history[-15:])
        user_content = request.message
        if request.active_file_path:
            user_content = f"Current file (user focused): {request.active_file_path}\n\n---\n\n{user_content}"
        if rag_context:
            user_content = f"{rag_context}\n\n---\n\n{user_content}"
        if request.context_files:
            file_ctx = "\n\n".join(
                f"[file: {f.path}]\n```\n{f.content[:2000]}\n```"
                for f in request.context_files
            )
            user_content = f"[Open files]\n{file_ctx}\n\n---\n\n{user_content}"
        messages.append(LLMMessage(role="user", content=user_content))
        return messages

    async def _generate(
        self, messages: list[LLMMessage], model: str, fallback: str
    ):
        fallback_chain = [model, fallback]
        last_err: Exception | None = None
        for m in fallback_chain:
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
        self, messages: list[LLMMessage], model: str, fallback: str
    ) -> AsyncIterator[str]:
        fallback_chain = [model, fallback]
        last_err: Exception | None = None
        for m in fallback_chain:
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
