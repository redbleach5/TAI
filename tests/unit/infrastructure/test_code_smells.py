"""Tests for code_smells — pattern detection with tmp_path, zero mocks."""

from pathlib import Path

from src.infrastructure.analyzer.code_smells import MAX_SMELLS, find_code_smells


class TestFindCodeSmells:
    """find_code_smells: regex pattern detection in Python files."""

    def test_no_files(self, tmp_path: Path):
        assert find_code_smells([], tmp_path) == []

    def test_clean_code_no_smells(self, tmp_path: Path):
        f = tmp_path / "clean.py"
        f.write_text("def foo(x, y):\n    return x + y\n")
        result = find_code_smells([f], tmp_path)
        assert result == []

    def test_detects_bare_except(self, tmp_path: Path):
        f = tmp_path / "bad.py"
        f.write_text("try:\n    pass\nexcept:\n    pass\n")
        result = find_code_smells([f], tmp_path)
        assert any("except" in s.lower() for s in result)

    def test_detects_star_import(self, tmp_path: Path):
        f = tmp_path / "star.py"
        f.write_text("from os import *\n")
        result = find_code_smells([f], tmp_path)
        assert any("*" in s for s in result)

    def test_detects_global(self, tmp_path: Path):
        f = tmp_path / "glob.py"
        f.write_text("x = 0\ndef foo():\n    global x\n    x = 1\n")
        result = find_code_smells([f], tmp_path)
        assert any("global" in s for s in result)

    def test_detects_long_params(self, tmp_path: Path):
        f = tmp_path / "long.py"
        # Create a function with a very long parameter list
        params = ", ".join(f"param_{i}: int" for i in range(15))
        f.write_text(f"def func({params}):\n    pass\n")
        result = find_code_smells([f], tmp_path)
        assert any("параметр" in s.lower() for s in result)

    def test_detects_deep_nesting(self, tmp_path: Path):
        f = tmp_path / "nested.py"
        f.write_text(
            "if True:\n"
            "    if True:\n"
            "        if True:\n"
            "            pass\n"
        )
        result = find_code_smells([f], tmp_path)
        assert any("вложенност" in s.lower() for s in result)

    def test_detects_type_ignore(self, tmp_path: Path):
        f = tmp_path / "ignore.py"
        f.write_text("x: int = 'hello'  # type: ignore\n")
        result = find_code_smells([f], tmp_path)
        assert any("type: ignore" in s for s in result)

    def test_skips_non_python_files(self, tmp_path: Path):
        f = tmp_path / "script.sh"
        f.write_text("#!/bin/bash\nexcept:\nfrom os import *\n")
        result = find_code_smells([f], tmp_path)
        assert result == []

    def test_multiple_smells_per_file(self, tmp_path: Path):
        f = tmp_path / "multi.py"
        f.write_text(
            "from os import *\n"
            "try:\n    pass\nexcept:\n    pass\n"
            "x = 0\ndef foo():\n    global x\n    x = 1\n"
        )
        result = find_code_smells([f], tmp_path)
        assert len(result) >= 3

    def test_occurrence_count(self, tmp_path: Path):
        f = tmp_path / "many.py"
        f.write_text("try:\n    pass\nexcept:\n    pass\ntry:\n    pass\nexcept:\n    pass\n")
        result = find_code_smells([f], tmp_path)
        assert any("2 occurrences" in s for s in result)

    def test_max_smells_limit(self, tmp_path: Path):
        # Create many files each with a smell
        files = []
        for i in range(MAX_SMELLS + 10):
            f = tmp_path / f"file_{i}.py"
            f.write_text("from os import *\ntry:\n    pass\nexcept:\n    pass\n")
            files.append(f)
        result = find_code_smells(files, tmp_path)
        assert len(result) <= MAX_SMELLS

    def test_unreadable_file_skipped(self, tmp_path: Path):
        good = tmp_path / "good.py"
        good.write_text("from os import *\n")
        bad = tmp_path / "nonexistent.py"
        result = find_code_smells([good, bad], tmp_path)
        assert len(result) >= 1  # At least the good file smells
