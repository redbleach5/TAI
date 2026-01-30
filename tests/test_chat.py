"""Chat API integration test."""
import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_chat_greeting_returns_template():
    """Greeting intent returns template response without LLM."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post("/chat", json={"message": "hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert "content" in data
    assert "model" in data
    assert data["model"] == "template"
    assert "CodeGen AI" in data["content"] or "привет" in data["content"].lower()


@pytest.mark.asyncio
async def test_chat_code_returns_template():
    """Code intent returns template response."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post("/chat", json={"message": "write a function"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] == "template"
    assert "Workflow" in data["content"] or "Phase" in data["content"]


@pytest.mark.asyncio
async def test_chat_help_returns_template():
    """Help intent returns template response."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post("/chat", json={"message": "help"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] == "template"
    assert len(data["content"]) > 0


@pytest.mark.asyncio
async def test_chat_stream_greeting_emits_content_event():
    """Stream endpoint emits content event for greeting (no thinking)."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        async with client.stream(
            "GET", "/chat/stream", params={"message": "hello"}
        ) as resp:
            assert resp.status_code == 200
            events = []
            async for line in resp.aiter_lines():
                if line.startswith("event:"):
                    events.append(("event", line[6:].strip()))
                elif line.startswith("data:"):
                    events.append(("data", line[5:].strip()))
    # Should have event: content, data: <template>, event: done
    event_types = [v for k, v in events if k == "event"]
    assert "content" in event_types
    assert "done" in event_types
