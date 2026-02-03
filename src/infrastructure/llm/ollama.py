"""Ollama adapter - implements LLMPort with Circuit Breaker."""

import logging
from typing import Any, AsyncIterator

import httpx
from ollama import AsyncClient

from src.domain.ports.config import OllamaConfig

logger = logging.getLogger(__name__)
from src.domain.ports.llm import LLMMessage, LLMResponse
from src.infrastructure.resilience import (
    get_circuit_breaker,
    CircuitBreakerConfig,
    CircuitOpenError,
)

# Таймаут подключения — при недоступности быстрый фейл (старт не блокируется надолго)
DEFAULT_CONNECT_TIMEOUT = 5.0


class OllamaAdapter:
    """Ollama implementation of LLMPort with Circuit Breaker protection."""

    def __init__(self, config: OllamaConfig) -> None:
        self._config = config
        # Передаём timeout в ollama-клиент: connect — быстрый фейл при недоступности хоста,
        # read — полный таймаут на ответ (config.timeout в секундах). Все 4 параметра заданы явно (требование httpx).
        read_timeout = float(config.timeout) if config.timeout else 120.0
        timeout = httpx.Timeout(
            connect=DEFAULT_CONNECT_TIMEOUT,
            read=read_timeout,
            write=read_timeout,
            pool=30.0,
        )
        self._client = AsyncClient(host=config.host, timeout=timeout)
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

    def _ollama_options(self, temperature: float) -> dict:
        """Build options dict: temperature + optional num_ctx, num_predict from config."""
        opts: dict = {"temperature": temperature}
        if self._config.num_ctx is not None:
            opts["num_ctx"] = self._config.num_ctx
        if self._config.num_predict is not None:
            opts["num_predict"] = self._config.num_predict
        return opts

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Generate a single response with Circuit Breaker protection."""
        model = model or "llama2"
        msg_dicts = [{"role": m.role, "content": m.content} for m in messages]
        options = self._ollama_options(temperature)

        async def _call():
            response = await self._client.chat(
                model=model,
                messages=msg_dicts,
                options=options,
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
        options = self._ollama_options(temperature)
        stream = await self._client.chat(
            model=model,
            messages=msg_dicts,
            options=options,
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
        except Exception as e:
            logger.debug("Ollama availability check failed: %s", e)
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
        except (httpx.ConnectTimeout, httpx.ConnectError, ConnectionError) as e:
            logger.debug("Ollama list_models failed (unreachable): %s", e)
            return []
        except Exception as e:
            logger.warning("Ollama list_models failed: %s", e, exc_info=True)
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
        options = self._ollama_options(temperature)
        try:
            response = await self._client.chat(
                model=model,
                messages=messages,
                tools=tools,
                options=options,
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
        except Exception as e:
            logger.warning("Ollama chat_with_tools failed: %s", e, exc_info=True)
            return ("", [])

    async def chat_with_tools_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict],
        model: str | None = None,
        temperature: float = 0.3,
    ) -> AsyncIterator[tuple[str, str | list[dict] | None]]:
        """Stream chat with tools. Yields (kind, data): content chunks, then ("tool_calls", [...]) or ("done", None).
        Merges tool_calls by index (Ollama streams partial tool_calls per chunk).
        """
        import json as _json
        model = model or "llama2"
        options = self._ollama_options(temperature)
        try:
            stream = await self._client.chat(
                model=model,
                messages=messages,
                tools=tools,
                options=options,
                stream=True,
            )
            content_buf = ""
            # Merge by index: Ollama may send multiple chunks with same tool_call (partial args)
            tool_calls_acc: dict[int, dict[str, Any]] = {}
            async for chunk in stream:
                if chunk.message and chunk.message.content:
                    content_buf += chunk.message.content
                    yield ("content", chunk.message.content)
                tcs = getattr(chunk.message, "tool_calls", None) if chunk.message else None
                if tcs:
                    for i, tc in enumerate(tcs):
                        fn = getattr(tc, "function", tc) if hasattr(tc, "function") else tc
                        idx = getattr(fn, "index", i) if not isinstance(fn, dict) else fn.get("index", i)
                        name = getattr(fn, "name", "") if not isinstance(fn, dict) else fn.get("name", "")
                        args_raw = getattr(fn, "arguments", {}) if not isinstance(fn, dict) else fn.get("arguments", {})
                        if idx not in tool_calls_acc:
                            tool_calls_acc[idx] = {"name": "", "arguments": ""}
                        acc = tool_calls_acc[idx]
                        if name:
                            acc["name"] = name
                        if args_raw is not None and args_raw != "":
                            if isinstance(args_raw, dict):
                                acc["arguments"] = args_raw
                            elif isinstance(args_raw, str):
                                prev = acc.get("arguments", "")
                                acc["arguments"] = (prev if isinstance(prev, str) else "") + args_raw
            # Build final list and parse arguments (Ollama may send string or dict)
            tool_calls = []
            for idx in sorted(tool_calls_acc.keys()):
                acc = tool_calls_acc[idx]
                name = acc.get("name", "")
                args = acc.get("arguments", "") or ""
                if isinstance(args, str):
                    try:
                        args = _json.loads(args) if args.strip() else {}
                    except _json.JSONDecodeError:
                        args = {}
                elif not isinstance(args, dict):
                    args = {}
                tool_calls.append({"name": name, "arguments": args})
            if tool_calls:
                yield ("tool_calls", tool_calls)
            yield ("done", None)
        except Exception as e:
            logger.warning("Ollama chat_with_tools_stream failed: %s", e, exc_info=True)
            yield ("content", "*Ошибка при вызове модели.*")
            yield ("done", None)
