"""Ollama adapter - implements LLMPort with Circuit Breaker."""

from typing import Any, AsyncIterator

import httpx
from ollama import AsyncClient

from src.domain.ports.config import OllamaConfig
from src.domain.ports.llm import LLMMessage, LLMResponse
from src.infrastructure.resilience import (
    get_circuit_breaker,
    CircuitBreakerConfig,
    CircuitOpenError,
)


class OllamaAdapter:
    """Ollama implementation of LLMPort with Circuit Breaker protection."""

    def __init__(self, config: OllamaConfig) -> None:
        self._config = config
        self._client = AsyncClient(host=config.host)
        self._available: bool | None = None
        
        # Circuit Breaker для защиты от каскадных сбоев
        self._breaker = get_circuit_breaker(
            "ollama",
            CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=30.0,
                success_threshold=2,
            ),
        )

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Generate a single response with Circuit Breaker protection."""
        model = model or "llama2"
        msg_dicts = [{"role": m.role, "content": m.content} for m in messages]
        
        async def _call():
            response = await self._client.chat(
                model=model,
                messages=msg_dicts,
                options={"temperature": temperature},
            )
            content = response.message.content if response.message else ""
            return LLMResponse(content=content, model=response.model, done=True)
        
        try:
            return await self._breaker.call(_call)
        except CircuitOpenError:
            # Возвращаем ошибку, но не падаем
            return LLMResponse(
                content="[LLM temporarily unavailable - circuit breaker open]",
                model=model,
                done=True,
            )

    async def generate_stream(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Generate response with streaming (yields content chunks)."""
        model = model or "llama2"
        msg_dicts = [{"role": m.role, "content": m.content} for m in messages]
        stream = await self._client.chat(
            model=model,
            messages=msg_dicts,
            options={"temperature": temperature},
            stream=True,
        )
        async for chunk in stream:
            if chunk.message and chunk.message.content:
                yield chunk.message.content

    async def is_available(self) -> bool:
        """Check if Ollama server is available. Fail-fast, no stale cache."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._config.host.rstrip('/')}/api/tags")
                if resp.status_code == 200:
                    self._available = True
                    return True
        except Exception:
            pass
        self._available = False
        return False

    async def list_models(self) -> list[str]:
        """List available models from Ollama."""
        try:
            resp = await self._client.list()
            if not resp.models:
                return []
            # ollama package: Model has 'model' attr (newer) or 'name' (legacy)
            return [getattr(m, "model", getattr(m, "name", "")) for m in resp.models if getattr(m, "model", getattr(m, "name", ""))]
        except Exception:
            return []

    async def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict],
        model: str | None = None,
        temperature: float = 0.3,
    ) -> tuple[str, list[dict]]:
        """Chat with native tool calling. Returns (content, tool_calls)."""
        model = model or "llama2"
        try:
            response = await self._client.chat(
                model=model,
                messages=messages,
                tools=tools,
                options={"temperature": temperature},
            )
            content = response.message.content if response.message else ""
            tool_calls = getattr(response.message, "tool_calls", None) or []
            # Convert to dict format: [{"name": "...", "arguments": {...}}]
            calls = []
            for tc in tool_calls:
                fn = getattr(tc, "function", tc) if hasattr(tc, "function") else tc
                name = getattr(fn, "name", fn.get("name", "")) if isinstance(fn, dict) else getattr(fn, "name", "")
                args = getattr(fn, "arguments", fn.get("arguments", {})) if isinstance(fn, dict) else getattr(fn, "arguments", {})
                if isinstance(args, str):
                    import json
                    try:
                        args = json.loads(args) if args else {}
                    except json.JSONDecodeError:
                        args = {}
                calls.append({"name": name, "arguments": args or {}})
            return (content, calls)
        except Exception:
            return ("", [])

    async def chat_with_tools_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict],
        model: str | None = None,
        temperature: float = 0.3,
    ) -> AsyncIterator[tuple[str, str | list[dict] | None]]:
        """Stream chat with tools. Yields (kind, data): content chunks, then ("tool_calls", [...]) or ("done", None)."""
        model = model or "llama2"
        try:
            stream = await self._client.chat(
                model=model,
                messages=messages,
                tools=tools,
                options={"temperature": temperature},
                stream=True,
            )
            content_buf = ""
            tool_calls: list[dict] = []
            async for chunk in stream:
                if chunk.message and chunk.message.content:
                    content_buf += chunk.message.content
                    yield ("content", chunk.message.content)
                tcs = getattr(chunk.message, "tool_calls", None) if chunk.message else None
                if tcs:
                    for tc in tcs:
                        fn = getattr(tc, "function", tc) if hasattr(tc, "function") else tc
                        name = getattr(fn, "name", "") if not isinstance(fn, dict) else fn.get("name", "")
                        args = getattr(fn, "arguments", {}) if not isinstance(fn, dict) else fn.get("arguments", {})
                        if isinstance(args, str):
                            import json
                            try:
                                args = json.loads(args) if args else {}
                            except json.JSONDecodeError:
                                args = {}
                        tool_calls.append({"name": name, "arguments": args or {}})
            if tool_calls:
                yield ("tool_calls", tool_calls)
            yield ("done", None)
        except Exception:
            yield ("content", "*Ошибка при вызове модели.*")
            yield ("done", None)
