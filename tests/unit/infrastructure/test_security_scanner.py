"""Tests for security_scanner (check_file_security)."""

from pathlib import Path

import pytest

from src.infrastructure.analyzer.security_scanner import (
    SECURITY_PATTERNS,
    check_file_security,
)


class TestCheckFileSecurity:
    """Tests for check_file_security."""

    def test_detects_eval(self, tmp_path: Path):
        """Detects eval() in Python file."""
        (tmp_path / "bad.py").write_text("x = eval('1+1')\n")
        issues = check_file_security(tmp_path / "bad.py", tmp_path)
        assert len(issues) >= 1
        assert any(i.issue == "Вызов eval()" for i in issues)

    def test_skips_markdown(self, tmp_path: Path):
        """Skips .md files."""
        (tmp_path / "readme.md").write_text("eval() is dangerous\n")
        issues = check_file_security(tmp_path / "readme.md", tmp_path)
        assert len(issues) == 0

    def test_skips_test_files(self, tmp_path: Path):
        """Skips test_*.py and tests/ dir."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_foo.py").write_text("eval('bad')\n")
        issues = check_file_security(tests_dir / "test_foo.py", tmp_path)
        assert len(issues) == 0

    def test_empty_file_returns_empty(self, tmp_path: Path):
        """Empty Python file returns no issues."""
        (tmp_path / "empty.py").write_text("")
        issues = check_file_security(tmp_path / "empty.py", tmp_path)
        assert issues == []

    def test_patterns_compiled(self):
        """SECURITY_PATTERNS is non-empty."""
        assert len(SECURITY_PATTERNS) > 0
        for item in SECURITY_PATTERNS:
            assert len(item) == 4  # pattern, severity, issue, recommendation
