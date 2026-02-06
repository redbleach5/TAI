"""Tests for file_metrics (compute_file_metrics, extract_imports, estimate_complexity)."""

import ast
from pathlib import Path

from src.infrastructure.analyzer.file_metrics import (
    compute_file_metrics,
    estimate_complexity,
    extract_imports,
)


class TestComputeFileMetrics:
    """Tests for compute_file_metrics."""

    def test_empty_file(self, tmp_path: Path):
        """Empty file returns zero metrics."""
        (tmp_path / "empty.py").write_text("")
        m = compute_file_metrics(tmp_path / "empty.py", tmp_path)
        assert m.path == "empty.py"
        assert m.lines_total == 1  # one empty line
        assert m.lines_code == 0
        assert m.functions == 0
        assert m.classes == 0

    def test_python_file_metrics(self, tmp_path: Path):
        """Python file: lines, functions, classes, complexity."""
        code = '''"""Doc."""
import os
def foo():
    pass
class Bar:
    def baz(self):
        if True:
            pass
'''
        (tmp_path / "m.py").write_text(code)
        m = compute_file_metrics(tmp_path / "m.py", tmp_path)
        assert m.lines_total > 0
        assert m.functions == 2  # foo, baz
        assert m.classes == 1
        assert m.complexity >= 1
        assert "os" in m.imports

    def test_non_python_no_ast(self, tmp_path: Path):
        """Non-Python file: no functions/classes/complexity."""
        (tmp_path / "readme.md").write_text("# Hello\n\nSome text.\n")
        m = compute_file_metrics(tmp_path / "readme.md", tmp_path)
        assert m.path == "readme.md"
        assert m.lines_total == 4  # "# Hello", "", "Some text.", ""
        assert m.functions == 0
        assert m.classes == 0
        assert m.imports == []

    def test_syntax_error_adds_issue(self, tmp_path: Path):
        """Python file with syntax error adds issue."""
        (tmp_path / "bad.py").write_text("def ( invalid\n")
        m = compute_file_metrics(tmp_path / "bad.py", tmp_path)
        assert any("Syntax" in i for i in m.issues)


class TestExtractImports:
    """Tests for extract_imports."""

    def test_import_names(self):
        """Extracts import names."""
        tree = ast.parse("import os\nimport foo.bar")
        assert extract_imports(tree) == ["os", "foo.bar"]

    def test_import_from_module(self):
        """Extracts from ... import module."""
        tree = ast.parse("from pathlib import Path")
        assert "pathlib" in extract_imports(tree)


class TestEstimateComplexity:
    """Tests for estimate_complexity."""

    def test_simple_module(self):
        """Simple module has base complexity 1."""
        tree = ast.parse("x = 1")
        assert estimate_complexity(tree) == 1

    def test_if_increases_complexity(self):
        """If statement adds to cyclomatic complexity."""
        tree = ast.parse("if x:\n    pass")
        assert estimate_complexity(tree) >= 2
