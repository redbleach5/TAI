"""Tests for architecture analysis — tmp_path only, zero mocks."""

from pathlib import Path

from src.infrastructure.analyzer.architecture import analyze_architecture


class TestAnalyzeArchitecture:
    """analyze_architecture: detect layers, entry points, config files, deps."""

    def test_empty_project(self, tmp_path: Path):
        arch = analyze_architecture(tmp_path, [])
        assert arch.layers == {}
        assert arch.entry_points == []
        assert arch.config_files == []
        assert arch.dependencies == {}

    def test_detects_layers(self, tmp_path: Path):
        src = tmp_path / "src"
        src.mkdir()
        f1 = src / "module.py"
        f1.write_text("x = 1")
        tests = tmp_path / "tests"
        tests.mkdir()
        f2 = tests / "test_module.py"
        f2.write_text("pass")

        arch = analyze_architecture(tmp_path, [f1, f2])
        assert "src" in arch.layers
        assert "tests" in arch.layers

    def test_detects_entry_points(self, tmp_path: Path):
        main = tmp_path / "main.py"
        main.write_text("print('main')")
        app = tmp_path / "app.py"
        app.write_text("print('app')")
        other = tmp_path / "utils.py"
        other.write_text("pass")

        arch = analyze_architecture(tmp_path, [main, app, other])
        assert "main.py" in arch.entry_points
        assert "app.py" in arch.entry_points
        assert "utils.py" not in arch.entry_points

    def test_detects_config_files(self, tmp_path: Path):
        toml = tmp_path / "pyproject.toml"
        toml.write_text("[project]\nname = 'test'")
        yaml = tmp_path / "config.yaml"
        yaml.write_text("key: value")
        py = tmp_path / "main.py"
        py.write_text("pass")

        arch = analyze_architecture(tmp_path, [toml, yaml, py])
        assert any("pyproject.toml" in c for c in arch.config_files)
        assert any("config.yaml" in c for c in arch.config_files)

    def test_detects_dependencies(self, tmp_path: Path):
        f = tmp_path / "src" / "app.py"
        f.parent.mkdir(parents=True)
        f.write_text("from mylib import helper\nimport json\n")

        arch = analyze_architecture(tmp_path, [f])
        # 'mylib' is not stdlib, should appear
        assert "src/app.py" in arch.dependencies
        deps = arch.dependencies["src/app.py"]
        assert any("mylib" in d for d in deps)

    def test_skips_stdlib_dependencies(self, tmp_path: Path):
        f = tmp_path / "src" / "app.py"
        f.parent.mkdir(parents=True)
        f.write_text("import os\nimport sys\nimport re\nimport json\n")

        arch = analyze_architecture(tmp_path, [f])
        # All stdlib — should not appear or be empty
        deps = arch.dependencies.get("src/app.py", [])
        for d in deps:
            assert d not in ("os", "sys", "re", "json")

    def test_syntax_error_skipped(self, tmp_path: Path):
        f = tmp_path / "src" / "bad.py"
        f.parent.mkdir(parents=True)
        f.write_text("def foo(:\n    pass")  # syntax error

        arch = analyze_architecture(tmp_path, [f])
        assert "src/bad.py" not in arch.dependencies

    def test_non_python_files_no_deps(self, tmp_path: Path):
        f = tmp_path / "src" / "readme.md"
        f.parent.mkdir(parents=True)
        f.write_text("# README")

        arch = analyze_architecture(tmp_path, [f])
        assert arch.dependencies == {}
