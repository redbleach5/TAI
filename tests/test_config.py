"""Tests for config API (Phase 6)."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_config_get_returns_editable_fields(client: AsyncClient):
    """GET /config returns llm, models, embeddings, logging."""
    resp = await client.get("/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "llm" in data
    assert "provider" in data["llm"]
    assert data["llm"]["provider"] in ("ollama", "lm_studio")
    assert "models" in data
    assert "defaults" in data["models"]
    assert "simple" in data["models"]["defaults"]
    assert "embeddings" in data
    assert "model" in data["embeddings"]
    assert "web_search" in data
    assert "searxng_url" in data["web_search"]
    assert "brave_api_key" in data["web_search"]
    assert "tavily_api_key" in data["web_search"]
    assert "google_api_key" in data["web_search"]
    assert "google_cx" in data["web_search"]
    assert "logging" in data
    assert "level" in data["logging"]


@pytest.mark.asyncio
async def test_config_patch_saves_and_returns_message(client: AsyncClient):
    """PATCH /config saves updates and returns success message."""
    resp = await client.patch(
        "/config",
        json={"logging": {"level": "DEBUG"}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("ok") is True
    assert "message" in data
