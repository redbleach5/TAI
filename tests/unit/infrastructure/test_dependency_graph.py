"""Tests for dependency graph (A2)."""

import tempfile
from pathlib import Path

import pytest

from src.infrastructure.analyzer.dependency_graph import (
    build_dependency_graph,
    format_dependency_graph_markdown,
)


class TestBuildDependencyGraph:
    """Tests for build_dependency_graph."""

    def test_empty_directory(self):
        """Empty directory returns empty result."""
        with tempfile.TemporaryDirectory() as d:
            result = build_dependency_graph(d)
        assert result.node_count == 0
        assert result.edge_count == 0
        assert result.cycles == []
        assert result.unused_imports == []

    def test_single_python_file_no_imports(self):
        """Single Python file with no imports."""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)
            (path / "main.py").write_text("print('hello')\n")
            result = build_dependency_graph(d)
        assert result.node_count == 0
        assert result.edge_count == 0

    def test_python_import_resolution(self):
        """Two Python files: a imports b."""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)
            (path / "b.py").write_text("x = 1\n")
            (path / "a.py").write_text("from b import x\nprint(x)\n")
            result = build_dependency_graph(d)
        assert result.edge_count >= 1
        from_files = {e.from_file for e in result.edges}
        to_files = {e.to_file for e in result.edges}
        assert "a.py" in from_files
        assert "b.py" in to_files

    def test_cycle_detection(self):
        """Cycle: a -> b -> a."""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)
            (path / "a.py").write_text("from b import x\n")
            (path / "b.py").write_text("from a import y\n")
            result = build_dependency_graph(d)
        assert len(result.cycles) >= 1
        flat = [n for cycle in result.cycles for n in cycle]
        assert "a.py" in flat
        assert "b.py" in flat

    def test_invalid_path_returns_empty(self):
        """Non-existent path returns empty result."""
        result = build_dependency_graph("/nonexistent/path/12345")
        assert result.node_count == 0
        assert result.edge_count == 0


class TestFormatDependencyGraphMarkdown:
    """Tests for format_dependency_graph_markdown."""

    def test_empty_result_returns_empty_string(self):
        """Empty result produces empty string."""
        from src.infrastructure.analyzer.dependency_graph import DependencyGraphResult
        result = DependencyGraphResult()
        assert format_dependency_graph_markdown(result) == ""

    def test_with_cycles_contains_section(self):
        """Result with cycles contains cycles section."""
        from src.infrastructure.analyzer.dependency_graph import DependencyGraphResult
        result = DependencyGraphResult(
            node_count=2,
            edge_count=2,
            cycles=[["a.py", "b.py", "a.py"]],
        )
        md = format_dependency_graph_markdown(result)
        assert "Граф зависимостей" in md
        assert "Циклы" in md
        assert "a.py" in md
        assert "b.py" in md
