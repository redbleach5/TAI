"""Tests for Git API."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


# Check if we're in a git repo
IS_GIT_REPO = Path(".git").exists()


@pytest.mark.skipif(not IS_GIT_REPO, reason="Not a git repository")
class TestGitStatus:
    """Test /git/status endpoint."""

    def test_get_status(self):
        """Test getting git status."""
        response = client.get("/git/status")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "branch" in data
        assert "files" in data
        assert isinstance(data["files"], list)

    def test_status_has_branch(self):
        """Test that status includes branch info."""
        response = client.get("/git/status")
        data = response.json()
        assert data["branch"] is None or isinstance(data["branch"], str)


@pytest.mark.skipif(not IS_GIT_REPO, reason="Not a git repository")
class TestGitDiff:
    """Test /git/diff endpoint."""

    def test_get_diff_all(self):
        """Test getting diff for all changes."""
        response = client.get("/git/diff")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "diff" in data

    def test_get_diff_specific_file(self):
        """Test getting diff for specific file."""
        response = client.get("/git/diff?path=pyproject.toml")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # diff key should be present
        assert "diff" in data


@pytest.mark.skipif(not IS_GIT_REPO, reason="Not a git repository")
class TestGitLog:
    """Test /git/log endpoint."""

    def test_get_log(self):
        """Test getting git log."""
        response = client.get("/git/log?limit=5")
        assert response.status_code == 200
        data = response.json()
        # success can be False if no commits yet
        assert "entries" in data or "error" in data
        if data["success"]:
            assert isinstance(data["entries"], list)

    def test_log_entry_structure(self):
        """Test log entry has correct structure."""
        response = client.get("/git/log?limit=1")
        data = response.json()

        if data.get("entries"):
            entry = data["entries"][0]
            assert "hash" in entry
            assert "author" in entry
            assert "date" in entry
            assert "message" in entry

    def test_log_limit(self):
        """Test log respects limit."""
        response = client.get("/git/log?limit=3")
        data = response.json()
        if data["success"]:
            assert len(data["entries"]) <= 3


@pytest.mark.skipif(not IS_GIT_REPO, reason="Not a git repository")
class TestGitBranches:
    """Test /git/branches endpoint."""

    def test_get_branches(self):
        """Test getting branch list."""
        response = client.get("/git/branches")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "current" in data
        assert "branches" in data
        assert isinstance(data["branches"], list)


@pytest.mark.skipif(not IS_GIT_REPO, reason="Not a git repository")
class TestGitCommit:
    """Test /git/commit endpoint."""

    def test_commit_empty_message(self):
        """Test commit with empty message fails."""
        response = client.post("/git/commit", json={"message": ""})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "required" in data["error"].lower()

    def test_commit_nothing_to_commit(self):
        """Test commit when nothing staged."""
        response = client.post("/git/commit", json={"message": "test commit", "files": []})
        # May succeed or fail depending on repo state
        assert response.status_code == 200
