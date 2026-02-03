"""Health endpoint integration test."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_health_returns_ok():
    """Health endpoint returns status and LLM availability."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "codegen-ai"
    assert data["llm_provider"] in ("ollama", "lm_studio")
    assert isinstance(data["llm_available"], bool)
