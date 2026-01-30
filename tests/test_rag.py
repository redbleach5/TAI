"""RAG API integration test."""
import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_rag_status_returns_ok():
    """RAG status returns chunk count and stats."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/rag/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "total_chunks" in data
    assert data["status"] == "ok"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires Ollama/LM Studio for embeddings; run manually")
async def test_rag_index_returns_ok():
    """RAG index accepts path and returns ok. Requires embeddings backend."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post("/rag/index?path=.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "path" in data
