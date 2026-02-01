"""OpenAI-compatible adapter - LM Studio, vLLM, LocalAI."""

import json
import logging
from typing import Any, AsyncIterator

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

    def _chat_body(
        self,
        model: str,
        messages: list,
        temperature: float,
        stream: bool,
        tools: list | None = None,
    ) -> dict:
        """Build request body; optional max_tokens from config."""
        body: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        if self._config.max_tokens is not None:
            body["max_tokens"] = self._config.max_tokens
        if tools is not None:
            body["tools"] = tools
        return body

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Generate a single response (non-streaming)."""
        model = model or "default"
        body = self._chat_body(
            model,
            [{"role": m.role, "content": m.content} for m in messages],
            temperature,
            stream=False,
        )
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
        body = self._chat_body(
            model,
            [{"role": m.role, "content": m.content} for m in messages],
            temperature,
            stream=True,
        )
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

    def _messages_to_openai(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert internal messages (with tool_call_id, tool_calls) to OpenAI API format."""
        out: list[dict[str, Any]] = []
        for m in messages:
            role = m.get("role", "")
            if role == "tool":
                out.append({
                    "role": "tool",
                    "content": m.get("content", ""),
                    "tool_call_id": m.get("tool_call_id", ""),
                })
            elif role == "assistant" and m.get("tool_calls"):
                tcs = m["tool_calls"]
                openai_tcs = []
                for tc in tcs:
                    fn = tc.get("function", tc) if isinstance(tc.get("function"), dict) else {"name": tc.get("name", ""), "arguments": tc.get("arguments", {})}
                    name = fn.get("name", "") if isinstance(fn, dict) else getattr(fn, "name", "")
                    args = fn.get("arguments", {}) if isinstance(fn, dict) else getattr(fn, "arguments", {})
                    if isinstance(args, dict):
                        args = json.dumps(args) if args else "{}"
                    openai_tcs.append({
                        "id": tc.get("id", ""),
                        "type": "function",
                        "function": {"name": name, "arguments": args},
                    })
                out.append({"role": "assistant", "content": m.get("content") or "", "tool_calls": openai_tcs})
            else:
                out.append({"role": role, "content": m.get("content", "")})
        return out

    async def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict],
        model: str | None = None,
        temperature: float = 0.3,
    ) -> tuple[str, list[dict]]:
        """Chat with tools (OpenAI / LM Studio tool use). Returns (content, tool_calls with id)."""
        model = model or "default"
        body = self._chat_body(
            model,
            self._messages_to_openai(messages),
            temperature,
            stream=False,
            tools=tools,
        )
        try:
            async with httpx.AsyncClient(timeout=self._config.timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    json=body,
                    headers=self._headers,
                )
                if resp.status_code >= 400:
                    logger.warning("LM Studio tool call API error %s: %s", resp.status_code, resp.text[:300])
                    return ("", [])
                data = resp.json()
        except Exception as e:
            logger.warning("LM Studio chat_with_tools failed: %s", e)
            return ("", [])
        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        content = msg.get("content") or ""
        raw_tcs = msg.get("tool_calls") or []
        calls = []
        for tc in raw_tcs:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments", "{}")
            if isinstance(args, str):
                try:
                    args = json.loads(args) if args.strip() else {}
                except json.JSONDecodeError:
                    args = {}
            calls.append({
                "name": name,
                "arguments": args or {},
                "id": tc.get("id", ""),
            })
        return (content, calls)

    async def chat_with_tools_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict],
        model: str | None = None,
        temperature: float = 0.3,
    ) -> AsyncIterator[tuple[str, str | list[dict] | None]]:
        """Stream chat with tools. Yields (kind, data): content chunks, then ('tool_calls', [...]) or ('done', None)."""
        model = model or "default"
        body = self._chat_body(
            model,
            self._messages_to_openai(messages),
            temperature,
            stream=True,
            tools=tools,
        )
        try:
            async with httpx.AsyncClient(timeout=self._config.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self._base_url}/chat/completions",
                    json=body,
                    headers=self._headers,
                ) as resp:
                    if resp.status_code >= 400:
                        err = await resp.aread()
                        logger.warning("LM Studio stream tool API error %s: %s", resp.status_code, err[:300])
                        yield ("content", "")
                        yield ("done", None)
                        return
                    content_buf = ""
                    tool_calls_acc: list[dict[str, Any]] = []
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        chunk = line[6:]
                        if chunk.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(chunk)
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            if delta.get("content"):
                                content_buf += delta["content"]
                                yield ("content", delta["content"])
                            for tc_delta in delta.get("tool_calls") or []:
                                idx = tc_delta.get("index", 0)
                                while len(tool_calls_acc) <= idx:
                                    tool_calls_acc.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                                acc = tool_calls_acc[idx]
                                acc["id"] = acc.get("id", "") or tc_delta.get("id", "")
                                fn = acc.setdefault("function", {"name": "", "arguments": ""})
                                fn["name"] = fn.get("name", "") or (tc_delta.get("function") or {}).get("name", "")
                                fn["arguments"] = (fn.get("arguments") or "") + (tc_delta.get("function") or {}).get("arguments", "")
                        except json.JSONDecodeError:
                            pass
                    calls = []
                    for acc in tool_calls_acc:
                        fn = acc.get("function", {})
                        args = fn.get("arguments", "{}")
                        if isinstance(args, str):
                            try:
                                args = json.loads(args) if args.strip() else {}
                            except json.JSONDecodeError:
                                args = {}
                        calls.append({
                            "name": fn.get("name", ""),
                            "arguments": args or {},
                            "id": acc.get("id", ""),
                        })
                    if calls:
                        yield ("tool_calls", calls)
                    yield ("done", None)
        except Exception as e:
            logger.warning("LM Studio chat_with_tools_stream failed: %s", e)
            yield ("content", "")
            yield ("done", None)
