"""Pytest configuration and shared fixtures."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.fixture
async def llm_available():
    """Return True if backend reports LLM (Ollama/LM Studio) available; use to skip tests that need a real model."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=5.0,
    ) as client:
        try:
            r = await client.get("/health")
            if r.status_code != 200:
                return False
            return r.json().get("llm_available", False)
        except Exception:
            return False
