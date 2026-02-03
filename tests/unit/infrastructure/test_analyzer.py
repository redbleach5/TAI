"""Tests for CodeAnalyzer agent."""

import tempfile
from pathlib import Path

import pytest

from src.infrastructure.agents.analyzer import CodeAnalyzer


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def analyzer():
    """CodeAnalyzer without LLM."""
    return CodeAnalyzer(llm=None)


class TestCodeAnalyzer:
    """Tests for CodeAnalyzer."""

    def test_analyze_valid_file(self, analyzer, temp_dir):
        """Analyze valid Python file."""
        file_path = temp_dir / "valid.py"
        file_path.write_text('''
def hello():
    """Say hello."""
    print("hello")

class MyClass:
    """A class."""
    pass
''')
        result = analyzer.analyze_file(file_path)

        assert result.lines > 0
        assert result.functions == 1
        assert result.classes == 1

    def test_analyze_syntax_error(self, analyzer, temp_dir):
        """Analyze file with syntax error."""
        file_path = temp_dir / "invalid.py"
        file_path.write_text("def broken(:\n  pass")

        result = analyzer.analyze_file(file_path)

        assert len(result.issues) > 0
        assert result.issues[0].severity == "critical"
        assert result.issues[0].issue_type == "bug"

    def test_detect_high_complexity(self, analyzer, temp_dir):
        """Detect high complexity functions."""
        file_path = temp_dir / "complex.py"
        file_path.write_text('''
def complex_func(a, b, c, d, e, f):
    if a:
        if b:
            if c:
                if d:
                    if e:
                        if f:
                            for i in range(10):
                                while True:
                                    if i > 5:
                                        break
                                    try:
                                        pass
                                    except:
                                        pass
    return True
''')
        result = analyzer.analyze_file(file_path)

        complexity_issues = [i for i in result.issues if i.issue_type == "complexity"]
        assert len(complexity_issues) > 0

    def test_detect_too_many_params(self, analyzer, temp_dir):
        """Detect functions with too many parameters."""
        file_path = temp_dir / "many_params.py"
        file_path.write_text('''
def too_many(a, b, c, d, e, f, g):
    """Too many params."""
    pass
''')
        result = analyzer.analyze_file(file_path)

        param_issues = [i for i in result.issues if "parameters" in i.message]
        assert len(param_issues) > 0

    def test_detect_missing_docstring(self, analyzer, temp_dir):
        """Detect missing docstrings."""
        file_path = temp_dir / "no_docs.py"
        file_path.write_text('''
def public_func():
    pass

class PublicClass:
    pass
''')
        result = analyzer.analyze_file(file_path)

        docstring_issues = [i for i in result.issues if "docstring" in i.message.lower()]
        assert len(docstring_issues) >= 2

    def test_analyze_project(self, analyzer, temp_dir):
        """Analyze entire project."""
        (temp_dir / "module1.py").write_text('def func1(): pass')
        (temp_dir / "module2.py").write_text('def func2(): pass')

        result = analyzer.analyze_project(temp_dir)

        assert result.total_files >= 2
        assert result.total_functions >= 2

    def test_analyze_project_ignores_venv(self, analyzer, temp_dir):
        """Analyze ignores .venv directory."""
        venv = temp_dir / ".venv"
        venv.mkdir()
        (venv / "bad.py").write_text("syntax error here")
        (temp_dir / "good.py").write_text("def good(): pass")

        result = analyzer.analyze_project(temp_dir)

        # Should only find good.py
        assert result.total_files == 1

    def test_calculate_complexity(self, analyzer, temp_dir):
        """Calculate complexity correctly."""
        file_path = temp_dir / "complexity.py"
        file_path.write_text('''
def simple():
    return 1

def medium(x):
    if x > 0:
        return x
    else:
        return -x
''')
        result = analyzer.analyze_file(file_path)

        # Simple function has complexity 1, medium has higher
        assert result.complexity >= 2
