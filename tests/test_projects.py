"""Tests for Projects API."""


import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.api.container import reset_container
from src.api.store import PROJECTS_FILE

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_projects():
    """Clean projects store before each test (reset container so store is fresh)."""
    if PROJECTS_FILE.exists():
        PROJECTS_FILE.unlink()
    reset_container()
    yield
    if PROJECTS_FILE.exists():
        PROJECTS_FILE.unlink()
    reset_container()


class TestProjectsList:
    """Test GET /projects endpoint."""

    def test_list_empty(self):
        """Test listing when no projects."""
        response = client.get("/projects")
        assert response.status_code == 200
        data = response.json()
        assert data["projects"] == []
        assert data["current"] is None


class TestProjectsAdd:
    """Test POST /projects endpoint."""

    def test_add_project(self):
        """Test adding a project."""
        # Use current directory as test path
        response = client.post(
            "/projects",
            json={"name": "Test Project", "path": "."}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["project"]["name"] == "Test Project"
        assert data["project"]["id"] == "test-project"

    def test_add_project_invalid_path(self):
        """Test adding project with invalid path."""
        response = client.post(
            "/projects",
            json={"name": "Invalid", "path": "/nonexistent/path/12345"}
        )
        assert response.status_code == 400
        assert "does not exist" in response.json()["detail"]

    def test_add_duplicate_name(self):
        """Test adding project with duplicate name creates unique ID."""
        client.post("/projects", json={"name": "Test", "path": "."})
        response = client.post("/projects", json={"name": "Test", "path": "."})
        
        assert response.status_code == 200
        data = response.json()
        # Should have suffix like test-1
        assert data["project"]["id"].startswith("test")
        assert data["project"]["id"] != "test"


class TestProjectsSelect:
    """Test POST /projects/{id}/select endpoint."""

    def test_select_project(self):
        """Test selecting a project."""
        # Add project first
        add_res = client.post("/projects", json={"name": "My Project", "path": "."})
        project_id = add_res.json()["project"]["id"]
        
        # Select it
        response = client.post(f"/projects/{project_id}/select")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["project"]["id"] == project_id

    def test_select_nonexistent(self):
        """Test selecting non-existent project."""
        response = client.post("/projects/nonexistent-12345/select")
        assert response.status_code == 404


class TestProjectsRemove:
    """Test DELETE /projects/{id} endpoint."""

    def test_remove_project(self):
        """Test removing a project."""
        # Add project first
        add_res = client.post("/projects", json={"name": "To Remove", "path": "."})
        project_id = add_res.json()["project"]["id"]
        
        # Remove it
        response = client.delete(f"/projects/{project_id}")
        assert response.status_code == 200
        
        # Verify removed
        list_res = client.get("/projects")
        ids = [p["id"] for p in list_res.json()["projects"]]
        assert project_id not in ids

    def test_remove_nonexistent(self):
        """Test removing non-existent project."""
        response = client.delete("/projects/nonexistent-12345")
        assert response.status_code == 404


class TestProjectsCurrent:
    """Test GET /projects/current endpoint."""

    def test_get_current_none(self):
        """Test getting current when none selected."""
        response = client.get("/projects/current")
        assert response.status_code == 200
        data = response.json()
        assert data["project"] is None

    def test_get_current_after_select(self):
        """Test getting current after selection."""
        # Add and select
        add_res = client.post("/projects", json={"name": "Current", "path": "."})
        project_id = add_res.json()["project"]["id"]
        client.post(f"/projects/{project_id}/select")
        
        # Get current
        response = client.get("/projects/current")
        assert response.status_code == 200
        data = response.json()
        assert data["project"]["id"] == project_id
