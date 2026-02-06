"""Tests for code execution API."""

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
async def test_run_simple_code(client: AsyncClient):
    """Run simple Python code."""
    resp = await client.post(
        "/code/run",
        json={"code": "print('Hello, World!')"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "Hello, World!" in data["output"]


@pytest.mark.asyncio
async def test_run_code_with_error(client: AsyncClient):
    """Run code with syntax error."""
    resp = await client.post(
        "/code/run",
        json={"code": "print('Missing quote)"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False


@pytest.mark.asyncio
async def test_run_empty_code(client: AsyncClient):
    """Empty code is rejected by validation (min_length=1)."""
    resp = await client.post(
        "/code/run",
        json={"code": ""},
    )
    # Pydantic validation rejects empty code with 422
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_run_with_tests(client: AsyncClient):
    """Run code with tests."""
    code = """
def add(a, b):
    return a + b
"""
    tests = """
def test_add():
    assert add(1, 2) == 3
"""
    resp = await client.post(
        "/code/run",
        json={"code": code, "tests": tests},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "passed" in data["output"].lower()
