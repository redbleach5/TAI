"""Tests for extended RAG functionality."""

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)

# Skip RAG tests if embeddings not available (requires Ollama/LM Studio)
pytestmark = pytest.mark.skip(reason="RAG tests require embeddings (Ollama/LM Studio)")


class TestRAGIndex:
    """Test /rag/index endpoint."""

    def test_index_current_project(self):
        """Test indexing current project."""
        response = client.post("/rag/index?path=src")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "files_indexed" in data
        assert "chunks_created" in data
        assert data["files_indexed"] > 0

    def test_index_returns_file_types(self):
        """Test that indexing returns file type breakdown."""
        response = client.post("/rag/index?path=src")
        data = response.json()
        assert "files_by_type" in data
        assert ".py" in data["files_by_type"]


class TestRAGStatus:
    """Test /rag/status endpoint."""

    def test_status(self):
        """Test getting RAG status."""
        # Index first
        client.post("/rag/index?path=src")

        response = client.get("/rag/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "total_chunks" in data


class TestRAGSearch:
    """Test /rag/search endpoint."""

    def test_search(self):
        """Test RAG search."""
        # Index first
        client.post("/rag/index?path=src")

        response = client.post("/rag/search", json={"query": "FastAPI router", "limit": 5})
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "total_chars" in data

    def test_search_with_min_score(self):
        """Test search with minimum score filter."""
        client.post("/rag/index?path=src")

        response = client.post("/rag/search", json={"query": "FastAPI", "limit": 10, "min_score": 0.5})
        assert response.status_code == 200
        data = response.json()
        # All results should have score >= min_score
        for result in data["results"]:
            assert result["score"] >= 0.5

    def test_search_with_max_tokens(self):
        """Test search with token limit."""
        client.post("/rag/index?path=src")

        response = client.post("/rag/search", json={"query": "router", "limit": 100, "max_tokens": 500})
        assert response.status_code == 200
        data = response.json()
        # Total chars should be roughly limited (500 tokens * 4 chars)
        assert data["total_chars"] <= 500 * 4 + 1000  # Some buffer


class TestRAGFiles:
    """Test /rag/files endpoint."""

    def test_list_files(self):
        """Test listing indexed files."""
        client.post("/rag/index?path=src")

        response = client.get("/rag/files")
        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert "count" in data
        assert data["count"] > 0


class TestRAGProjectMap:
    """Test /rag/project-map endpoint."""

    def test_get_project_map(self):
        """Test getting project map."""
        # Index first to generate map
        client.post("/rag/index?path=src")

        response = client.get("/rag/project-map")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "project_map" in data
        assert "# Project Map" in data["project_map"]


class TestRAGClear:
    """Test /rag/clear endpoint."""

    def test_clear(self):
        """Test clearing index."""
        # Index first
        client.post("/rag/index?path=src")

        response = client.post("/rag/clear")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

        # Verify cleared
        status = client.get("/rag/status")
        assert status.json()["total_chunks"] == 0
