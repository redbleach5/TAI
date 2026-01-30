"""Tests for Terminal API."""

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


class TestTerminalExec:
    """Test /terminal/exec endpoint."""

    def test_exec_echo(self):
        """Test executing echo command."""
        response = client.post(
            "/terminal/exec",
            json={"command": "echo hello", "timeout": 5}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "hello" in data["stdout"]
        assert data["exit_code"] == 0

    def test_exec_pwd(self):
        """Test executing pwd command."""
        response = client.post(
            "/terminal/exec",
            json={"command": "pwd", "timeout": 5}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["stdout"]) > 0

    def test_exec_ls(self):
        """Test executing ls command."""
        response = client.post(
            "/terminal/exec",
            json={"command": "ls", "timeout": 5}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "src" in data["stdout"] or "pyproject.toml" in data["stdout"]

    def test_exec_blocked_command(self):
        """Test that blocked commands are rejected."""
        response = client.post(
            "/terminal/exec",
            json={"command": "curl http://example.com", "timeout": 5}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not allowed" in data["error"].lower()

    def test_exec_dangerous_pattern(self):
        """Test that dangerous patterns are blocked."""
        response = client.post(
            "/terminal/exec",
            json={"command": "echo hello && rm -rf /", "timeout": 5}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "dangerous" in data["error"].lower() or "not allowed" in data["error"].lower()

    def test_exec_pipe_blocked(self):
        """Test that pipes are blocked."""
        response = client.post(
            "/terminal/exec",
            json={"command": "ls | grep py", "timeout": 5}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False

    def test_exec_python_version(self):
        """Test executing python command."""
        response = client.post(
            "/terminal/exec",
            json={"command": "python --version", "timeout": 5}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Python" in data["stdout"] or "Python" in data["stderr"]

    def test_exec_with_cwd(self):
        """Test executing command in specific directory."""
        response = client.post(
            "/terminal/exec",
            json={"command": "ls", "cwd": "src", "timeout": 5}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "main.py" in data["stdout"] or "api" in data["stdout"]

    def test_exec_empty_command(self):
        """Test executing empty command."""
        response = client.post(
            "/terminal/exec",
            json={"command": "", "timeout": 5}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "empty" in data["error"].lower()


class TestTerminalStream:
    """Test /terminal/stream endpoint."""

    def test_stream_echo(self):
        """Test streaming echo command."""
        response = client.get(
            "/terminal/stream?command=echo%20streaming&timeout=5"
        )
        assert response.status_code == 200
        # SSE response
        content = response.text
        assert "data:" in content
        assert "streaming" in content or "start" in content
