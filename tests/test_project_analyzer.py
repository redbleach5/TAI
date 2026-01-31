"""Tests for Project Analyzer."""

import tempfile
from pathlib import Path

import pytest

from src.infrastructure.analyzer.project_analyzer import (
    ProjectAnalyzer,
    ProjectAnalysis,
    FileMetrics,
    SecurityIssue,
    get_analyzer,
)
from src.infrastructure.analyzer.report_generator import ReportGenerator


class TestProjectAnalyzer:
    """Tests for ProjectAnalyzer."""

    def test_analyze_empty_directory(self):
        """Empty directory should return minimal analysis."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = ProjectAnalyzer()
            analysis = analyzer.analyze(tmpdir)
            
            assert analysis.total_files == 0
            assert analysis.total_lines == 0
            assert analysis.security_score == 100
            assert analysis.quality_score >= 0

    def test_analyze_python_project(self):
        """Should analyze Python files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create sample Python file
            py_file = Path(tmpdir) / "main.py"
            py_file.write_text("""
def hello():
    '''Say hello.'''
    print("Hello, World!")

class Greeter:
    def greet(self, name):
        return f"Hello, {name}!"
""")
            
            analyzer = ProjectAnalyzer()
            analysis = analyzer.analyze(tmpdir)
            
            assert analysis.total_files == 1
            assert analysis.total_lines > 0
            assert "Python" in analysis.languages
            assert len(analysis.file_metrics) == 1
            assert analysis.file_metrics[0].functions >= 1
            assert analysis.file_metrics[0].classes >= 1

    def test_detect_security_issues(self):
        """Should detect security issues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create file with security issues
            py_file = Path(tmpdir) / "vulnerable.py"
            py_file.write_text("""
import os
os.system("rm -rf /")  # Critical
eval(user_input)  # Critical
password = "secret123"  # High
DEBUG = True  # Medium
print("debug")  # Low
""")
            
            analyzer = ProjectAnalyzer()
            analysis = analyzer.analyze(tmpdir)
            
            assert len(analysis.security_issues) > 0
            assert analysis.security_score < 100
            
            severities = {i.severity for i in analysis.security_issues}
            assert "critical" in severities

    def test_detect_code_smells(self):
        """Should detect code smells."""
        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "smelly.py"
            py_file.write_text("""
from module import *  # Star import

def long_params(a, b, c, d, e, f, g, h, i, j):
    pass

try:
    risky()
except:  # Bare except
    pass

global x  # Global
""")
            
            analyzer = ProjectAnalyzer()
            analysis = analyzer.analyze(tmpdir)
            
            assert len(analysis.code_smells) > 0

    def test_analyze_architecture(self):
        """Should analyze architecture."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create directory structure
            (Path(tmpdir) / "src").mkdir()
            (Path(tmpdir) / "tests").mkdir()
            (Path(tmpdir) / "src" / "main.py").write_text("print('main')")
            (Path(tmpdir) / "tests" / "test_main.py").write_text("def test(): pass")
            (Path(tmpdir) / "config.toml").write_text("[app]")
            
            analyzer = ProjectAnalyzer()
            analysis = analyzer.analyze(tmpdir)
            
            assert "src" in analysis.architecture.layers
            assert "tests" in analysis.architecture.layers
            assert any("config" in f for f in analysis.architecture.config_files)

    def test_multiple_languages(self):
        """Should detect multiple languages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "main.py").write_text("print('python')")
            (Path(tmpdir) / "app.js").write_text("console.log('js');")
            (Path(tmpdir) / "style.css").write_text("body { color: red; }")
            
            analyzer = ProjectAnalyzer()
            analysis = analyzer.analyze(tmpdir)
            
            assert len(analysis.languages) >= 3
            assert "Python" in analysis.languages
            assert "JavaScript" in analysis.languages
            assert "CSS" in analysis.languages

    def test_ignores_excluded_directories(self):
        """Should ignore .venv, node_modules, etc."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create excluded directories
            venv = Path(tmpdir) / ".venv"
            venv.mkdir()
            (venv / "lib.py").write_text("venv code")
            
            node = Path(tmpdir) / "node_modules"
            node.mkdir()
            (node / "lib.js").write_text("node code")
            
            # Create included file
            (Path(tmpdir) / "main.py").write_text("main code")
            
            analyzer = ProjectAnalyzer()
            analysis = analyzer.analyze(tmpdir)
            
            assert analysis.total_files == 1
            assert not any(".venv" in f.path for f in analysis.file_metrics)
            assert not any("node_modules" in f.path for f in analysis.file_metrics)

    def test_complexity_calculation(self):
        """Should calculate complexity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "complex.py"
            py_file.write_text("""
def complex_func(x):
    if x > 0:
        if x > 10:
            for i in range(x):
                if i % 2 == 0:
                    print(i)
        else:
            while x > 0:
                x -= 1
    else:
        try:
            raise ValueError()
        except ValueError:
            pass
""")
            
            analyzer = ProjectAnalyzer()
            analysis = analyzer.analyze(tmpdir)
            
            assert len(analysis.file_metrics) == 1
            assert analysis.file_metrics[0].complexity > 1

    def test_get_analyzer_singleton(self):
        """get_analyzer should return singleton."""
        analyzer1 = get_analyzer()
        analyzer2 = get_analyzer()
        assert analyzer1 is analyzer2


class TestReportGenerator:
    """Tests for ReportGenerator."""

    def test_generate_markdown(self):
        """Should generate valid Markdown report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "main.py").write_text("print('hello')")
            
            analyzer = ProjectAnalyzer()
            analysis = analyzer.analyze(tmpdir)
            
            generator = ReportGenerator()
            report = generator.generate_markdown(analysis)
            
            assert "# 📊 Отчёт анализа проекта" in report
            assert "Краткое резюме" in report
            assert "Безопасность" in report
            assert "Качество" in report
            assert analysis.project_name in report

    def test_save_report(self):
        """Should save report to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()
            (project_dir / "main.py").write_text("print('hello')")
            
            analyzer = ProjectAnalyzer()
            analysis = analyzer.analyze(str(project_dir))
            
            generator = ReportGenerator()
            output_file = Path(tmpdir) / "report.md"
            result = generator.save_report(analysis, output_file)
            
            assert result.exists()
            content = result.read_text()
            assert "Отчёт анализа проекта" in content

    def test_report_contains_scores(self):
        """Report should contain scores."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "main.py").write_text("print('hello')")
            
            analyzer = ProjectAnalyzer()
            analysis = analyzer.analyze(tmpdir)
            
            generator = ReportGenerator()
            report = generator.generate_markdown(analysis)
            
            assert "Безопасность" in report
            assert "Качество" in report
            assert "/100" in report

    def test_report_handles_empty_project(self):
        """Report should handle empty project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = ProjectAnalyzer()
            analysis = analyzer.analyze(tmpdir)
            
            generator = ReportGenerator()
            report = generator.generate_markdown(analysis)
            
            # Should not crash
            assert "Отчёт анализа проекта" in report


class TestFileMetrics:
    """Tests for FileMetrics dataclass."""

    def test_file_metrics_defaults(self):
        """FileMetrics should have correct defaults."""
        metrics = FileMetrics(path="test.py")
        
        assert metrics.lines_total == 0
        assert metrics.lines_code == 0
        assert metrics.functions == 0
        assert metrics.classes == 0
        assert metrics.imports == []
        assert metrics.issues == []


class TestSecurityIssue:
    """Tests for SecurityIssue dataclass."""

    def test_security_issue_creation(self):
        """Should create SecurityIssue."""
        issue = SecurityIssue(
            severity="critical",
            file="main.py",
            line=10,
            issue="eval() detected",
            recommendation="Use ast.literal_eval()",
        )
        
        assert issue.severity == "critical"
        assert issue.line == 10
