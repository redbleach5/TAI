"""Tests for Terminal API."""

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


class TestTerminalExec:
    """Test /terminal/exec endpoint."""

    def test_exec_echo(self):
        """Test executing echo command."""
        response = client.post("/terminal/exec", json={"command": "echo hello"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "hello" in data["stdout"]
        assert data["exit_code"] == 0

    def test_exec_pwd(self):
        """Test executing pwd command."""
        response = client.post("/terminal/exec", json={"command": "pwd"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["stdout"]) > 0

    def test_exec_ls(self):
        """Test executing ls command."""
        response = client.post("/terminal/exec", json={"command": "ls"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "src" in data["stdout"] or "pyproject.toml" in data["stdout"]

    def test_exec_blocked_command(self):
        """Test that blocked commands are rejected."""
        response = client.post("/terminal/exec", json={"command": "curl http://example.com"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not allowed" in data["error"].lower()

    def test_exec_dangerous_pattern(self):
        """Test that dangerous patterns are blocked."""
        response = client.post("/terminal/exec", json={"command": "echo hello && rm -rf /"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        # Can be "blocked pattern" or "not allowed"
        assert "blocked" in data["error"].lower() or "not allowed" in data["error"].lower()

    def test_exec_pipe_blocked(self):
        """Test that pipes are blocked."""
        response = client.post("/terminal/exec", json={"command": "ls | grep py"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False

    def test_exec_python_version(self):
        """Test executing python version command (python3 for macOS compatibility)."""
        response = client.post("/terminal/exec", json={"command": "python3 --version"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Python" in data["stdout"] or "Python" in data["stderr"]

    def test_exec_with_cwd(self):
        """Test executing command in specific directory."""
        response = client.post("/terminal/exec", json={"command": "ls", "cwd": "src"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "main.py" in data["stdout"] or "api" in data["stdout"]

    def test_exec_empty_command(self):
        """Test executing empty command."""
        response = client.post("/terminal/exec", json={"command": ""})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "empty" in data["error"].lower()


class TestTerminalStream:
    """Test /terminal/stream endpoint."""

    def test_stream_echo(self):
        """Test streaming echo command."""
        response = client.get("/terminal/stream?command=echo%20streaming")
        assert response.status_code == 200
        # SSE response
        content = response.text
        assert "data:" in content
        assert "streaming" in content.lower() or "output" in content.lower()
