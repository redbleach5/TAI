"""Tests for GitContextHandler and DiffHandler — uses tmp_path + real git."""

import pytest

from src.application.chat.handlers.git_handler import DiffHandler, GitContextHandler, _run_git


@pytest.fixture()
def git_repo(tmp_path):
    """Create a real git repo with a commit."""
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path, capture_output=True, check=True,
    )
    (tmp_path / "file.py").write_text("print('hello')\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=tmp_path, capture_output=True, check=True,
    )
    return tmp_path


class TestRunGit:
    """Tests for _run_git helper."""

    @pytest.mark.asyncio()
    async def test_run_git_status(self, git_repo):
        code, out = await _run_git(["status", "--short"], str(git_repo))
        assert code == 0

    @pytest.mark.asyncio()
    async def test_run_git_bad_dir(self, tmp_path):
        code, out = await _run_git(["status"], str(tmp_path / "nonexistent"))
        assert code != 0 or out == ""


class TestGitContextHandler:
    """Tests for @git handler."""

    @pytest.fixture()
    def handler(self):
        return GitContextHandler()

    @pytest.mark.asyncio()
    async def test_command_type(self, handler):
        assert handler.command_type == "git"

    @pytest.mark.asyncio()
    async def test_git_context_in_repo(self, handler, git_repo):
        result = await handler.execute("", workspace_path=str(git_repo))
        assert result.success
        assert "Git Status" in result.content or "Recent Commits" in result.content

    @pytest.mark.asyncio()
    async def test_git_status_subcommand(self, handler, git_repo):
        result = await handler.execute("status", workspace_path=str(git_repo))
        assert result.success

    @pytest.mark.asyncio()
    async def test_git_log_subcommand(self, handler, git_repo):
        result = await handler.execute("log", workspace_path=str(git_repo))
        assert result.success
        assert "Recent Commits" in result.content
        assert "Initial commit" in result.content

    @pytest.mark.asyncio()
    async def test_git_with_changes(self, handler, git_repo):
        (git_repo / "file.py").write_text("print('changed')\n")
        result = await handler.execute("", workspace_path=str(git_repo))
        assert result.success
        assert "Git" in result.content

    @pytest.mark.asyncio()
    async def test_not_a_repo(self, handler, tmp_path):
        result = await handler.execute("", workspace_path=str(tmp_path))
        assert not result.success


class TestDiffHandler:
    """Tests for @diff handler."""

    @pytest.fixture()
    def handler(self):
        return DiffHandler()

    @pytest.mark.asyncio()
    async def test_command_type(self, handler):
        assert handler.command_type == "diff"

    @pytest.mark.asyncio()
    async def test_no_changes(self, handler, git_repo):
        result = await handler.execute("", workspace_path=str(git_repo))
        assert result.success
        assert "No changes" in result.content

    @pytest.mark.asyncio()
    async def test_diff_with_changes(self, handler, git_repo):
        (git_repo / "file.py").write_text("print('changed')\n")
        result = await handler.execute("", workspace_path=str(git_repo))
        assert result.success
        assert "diff" in result.content.lower() or "Changes" in result.content

    @pytest.mark.asyncio()
    async def test_diff_specific_file(self, handler, git_repo):
        (git_repo / "file.py").write_text("print('changed')\n")
        result = await handler.execute("file.py", workspace_path=str(git_repo))
        assert result.success
        assert "file.py" in result.content

    @pytest.mark.asyncio()
    async def test_diff_staged(self, handler, git_repo):
        import subprocess
        (git_repo / "file.py").write_text("print('staged')\n")
        subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True, check=True)
        result = await handler.execute("--staged", workspace_path=str(git_repo))
        assert result.success
        assert "Staged" in result.content or "diff" in result.content.lower()
