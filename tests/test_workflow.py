"""Workflow API integration test."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_workflow_greeting_returns_template():
    """Greeting task returns template response without full workflow."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post("/workflow", json={"task": "привет"})
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert "content" in data
    assert data["intent_kind"] == "greeting"
    assert "CodeGen AI" in data["content"] or "привет" in data["content"].lower()
