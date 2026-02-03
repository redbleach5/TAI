"""Models API integration test."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_models_returns_list():
    """Models endpoint returns list of model names."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/models")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # May be empty if Ollama/LM Studio not running
    assert all(isinstance(m, str) for m in data)
