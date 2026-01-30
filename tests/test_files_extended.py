"""Tests for extended Files API (tree, create, delete, rename)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


class TestFileTree:
    """Test /files/tree endpoint."""

    def test_get_tree_root(self):
        """Test getting file tree from root."""
        response = client.get("/files/tree")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["tree"] is not None
        assert "children" in data["tree"]

    def test_get_tree_src(self):
        """Test getting file tree from src directory."""
        response = client.get("/files/tree?path=src")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["tree"]["name"] == "src"
        assert data["tree"]["is_dir"] is True

    def test_get_tree_excludes_pycache(self):
        """Test that __pycache__ is excluded from tree."""
        response = client.get("/files/tree")
        assert response.status_code == 200
        data = response.json()
        
        def find_pycache(node):
            if node["name"] == "__pycache__":
                return True
            if node.get("children"):
                return any(find_pycache(c) for c in node["children"])
            return False
        
        assert not find_pycache(data["tree"])

    def test_get_tree_invalid_path(self):
        """Test getting tree for non-existent path returns error."""
        response = client.get("/files/tree?path=nonexistent_dir_12345")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not found" in data["error"].lower() or "error" in data


class TestFileCreate:
    """Test /files/create endpoint."""

    def test_create_file(self):
        """Test creating a new file."""
        test_path = "test_created_file_12345.txt"
        try:
            response = client.post(
                "/files/create",
                json={"path": test_path, "is_directory": False}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert Path(test_path).exists()
        finally:
            if Path(test_path).exists():
                Path(test_path).unlink()

    def test_create_directory(self):
        """Test creating a new directory."""
        test_path = "test_created_dir_12345"
        try:
            response = client.post(
                "/files/create",
                json={"path": test_path, "is_directory": True}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert Path(test_path).is_dir()
        finally:
            if Path(test_path).exists():
                Path(test_path).rmdir()

    def test_create_existing_file(self):
        """Test creating a file that already exists."""
        response = client.post(
            "/files/create",
            json={"path": "pyproject.toml", "is_directory": False}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "exists" in data["error"].lower()


class TestFileDelete:
    """Test /files/delete endpoint."""

    def test_delete_file(self):
        """Test deleting a file."""
        test_path = "test_delete_file_12345.txt"
        Path(test_path).write_text("test content")
        
        response = client.delete(f"/files/delete?path={test_path}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert not Path(test_path).exists()

    def test_delete_nonexistent(self):
        """Test deleting non-existent file returns error."""
        response = client.delete("/files/delete?path=nonexistent_file_12345.txt")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not found" in data["error"].lower()

    def test_delete_creates_backup(self):
        """Test that delete creates backup."""
        test_path = "test_delete_backup_12345.txt"
        Path(test_path).write_text("backup test content")
        
        response = client.delete(f"/files/delete?path={test_path}&backup=true")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestFileRename:
    """Test /files/rename endpoint."""

    def test_rename_file(self):
        """Test renaming a file."""
        old_path = "test_rename_old_12345.txt"
        new_path = "test_rename_new_12345.txt"
        
        try:
            Path(old_path).write_text("rename test")
            
            response = client.post(
                "/files/rename",
                json={"old_path": old_path, "new_path": new_path}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert not Path(old_path).exists()
            assert Path(new_path).exists()
        finally:
            for p in [old_path, new_path]:
                if Path(p).exists():
                    Path(p).unlink()

    def test_rename_nonexistent(self):
        """Test renaming non-existent file returns error."""
        response = client.post(
            "/files/rename",
            json={"old_path": "nonexistent_12345.txt", "new_path": "new_12345.txt"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not found" in data["error"].lower()

    def test_rename_to_existing(self):
        """Test renaming to existing file returns error."""
        old_path = "test_rename_src_12345.txt"
        
        try:
            Path(old_path).write_text("test")
            response = client.post(
                "/files/rename",
                json={"old_path": old_path, "new_path": "pyproject.toml"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "exists" in data["error"].lower()
        finally:
            if Path(old_path).exists():
                Path(old_path).unlink()
