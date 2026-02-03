"""Tests for coverage_collector (A4)."""

import tempfile
from pathlib import Path

from src.infrastructure.analyzer.coverage_collector import collect_coverage_for_analysis


class TestCollectCoverageForAnalysis:
    """Tests for collect_coverage_for_analysis."""

    def test_nonexistent_path(self):
        """Nonexistent path returns short message."""
        result = collect_coverage_for_analysis("/nonexistent/path/12345")
        assert "Путь" in result or "недоступен" in result

    def test_not_python_project(self):
        """Directory without pyproject/setup.py returns message about Python project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = collect_coverage_for_analysis(tmpdir)
        assert "Покрытие не измерено" in result
        assert "Python" in result or "tests" in result

    def test_python_project_without_tests_dir(self):
        """Python project without tests/ returns message about tests dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "pyproject.toml").write_text("[project]\nname = 'x'")
            result = collect_coverage_for_analysis(tmpdir)
        assert "Покрытие не измерено" in result
        assert "tests" in result.lower()
