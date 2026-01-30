"""OpenAI-compatible adapter - LM Studio, vLLM, LocalAI."""

import json
import logging
from typing import AsyncIterator

import httpx

from src.domain.ports.config import OpenAICompatibleConfig
from src.domain.ports.llm import LLMMessage, LLMResponse

logger = logging.getLogger(__name__)


class OpenAICompatibleAdapter:
    """LM Studio, vLLM, LocalAI - implements LLMPort via /v1/chat/completions."""

    def __init__(self, config: OpenAICompatibleConfig) -> None:
        self._config = config
        self._base_url = config.base_url.rstrip("/")
        self._headers = {"Content-Type": "application/json"}
        if config.api_key:
            self._headers["Authorization"] = f"Bearer {config.api_key}"

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Generate a single response (non-streaming)."""
        model = model or "default"
        body = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=self._config.timeout) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions",
                json=body,
                headers=self._headers,
            )
            if resp.status_code >= 400:
                err_text = resp.text
                logger.error(
                    "LLM API error %s: %s",
                    resp.status_code,
                    err_text[:500],
                    extra={"request_body": body},
                )
            resp.raise_for_status()
            data = resp.json()
        choice = data.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content", "")
        return LLMResponse(content=content, model=model, done=True)

    async def generate_stream(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Generate response with streaming."""
        model = model or "default"
        body = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=self._config.timeout) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                json=body,
                headers=self._headers,
            ) as resp:
                if resp.status_code >= 400:
                    try:
                        err_body = await resp.aread()
                        err_text = err_body.decode("utf-8", errors="replace")
                        logger.error(
                            "LLM API error %s: %s",
                            resp.status_code,
                            err_text[:500],
                            extra={"request_body": body},
                        )
                        raise httpx.HTTPStatusError(
                            f"LLM API error {resp.status_code}: {err_text[:200]}",
                            request=resp.request,
                            response=resp,
                        )
                    except httpx.HTTPStatusError:
                        raise
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        chunk = line[6:]
                        if chunk.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(chunk)
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            if content := delta.get("content"):
                                yield content
                        except json.JSONDecodeError:
                            pass

    async def is_available(self) -> bool:
        """Check if LM Studio / vLLM / LocalAI is available."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base_url}/models", headers=self._headers)
                return resp.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """List available models from /v1/models."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base_url}/models", headers=self._headers)
                resp.raise_for_status()
                data = resp.json()
                models = data.get("data", [])
                return [m.get("id", "") for m in models if m.get("id")]
        except Exception:
            return []
