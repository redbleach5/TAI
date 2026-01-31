"""Ollama adapter - implements LLMPort with Circuit Breaker."""

from typing import AsyncIterator

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
