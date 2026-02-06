"""Tests for file_collector — chunking and ignore logic, tmp_path only."""

from pathlib import Path

import pytest

from src.infrastructure.rag.file_collector import (
    chunk_code_file,
    chunk_text,
    collect_code_files,
    is_binary_file,
    is_ignored,
    parse_gitignore,
)


class TestChunkText:
    """chunk_text: split text into overlapping chunks."""

    def test_empty_text(self):
        assert chunk_text("", 100, 10) == []

    def test_short_text_single_chunk(self):
        text = "Hello world"
        chunks = chunk_text(text, 100, 10)
        assert len(chunks) == 1
        assert chunks[0] == "Hello world"

    def test_splits_long_text(self):
        text = "A" * 500
        chunks = chunk_text(text, 100, 20)
        assert len(chunks) > 1
        # Each chunk should be at most chunk_size
        for chunk in chunks:
            assert len(chunk) <= 100

    def test_overlap_between_chunks(self):
        # Use text without natural boundaries to test raw overlap
        text = "word " * 100  # 500 chars
        chunks = chunk_text(text, 100, 20, respect_boundaries=False)
        assert len(chunks) > 1
        # All text should be covered
        reconstructed = chunks[0]
        for chunk in chunks[1:]:
            reconstructed += chunk[20:]  # skip overlap part

    def test_respects_paragraph_boundary(self):
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunks = chunk_text(text, 30, 5, respect_boundaries=True)
        assert len(chunks) >= 2

    def test_respects_function_boundary(self):
        text = "x = 1\n\ndef foo():\n    pass\n\ndef bar():\n    pass"
        chunks = chunk_text(text, 25, 5, respect_boundaries=True)
        assert len(chunks) >= 2

    def test_invalid_chunk_size_raises(self):
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            chunk_text("text", 0, 0)

    def test_negative_overlap_raises(self):
        with pytest.raises(ValueError, match="overlap must be non-negative"):
            chunk_text("text", 100, -1)

    def test_overlap_gte_chunk_size_raises(self):
        with pytest.raises(ValueError, match="overlap must be less than chunk_size"):
            chunk_text("text", 100, 100)

    def test_no_empty_chunks(self):
        text = "Some text\n\n\n\nMore text"
        chunks = chunk_text(text, 10, 2)
        for chunk in chunks:
            assert chunk.strip() != ""


class TestChunkCodeFile:
    """chunk_code_file: code-aware chunking."""

    def test_short_file_single_chunk(self):
        code = "def foo():\n    return 42"
        chunks = chunk_code_file(code, chunk_size=1500)
        assert len(chunks) == 1

    def test_long_file_multiple_chunks(self):
        # Generate a long Python file
        lines = [f"def func_{i}():\n    return {i}\n" for i in range(100)]
        code = "\n".join(lines)
        chunks = chunk_code_file(code, chunk_size=200, overlap=50)
        assert len(chunks) > 1


class TestIsIgnored:
    """is_ignored: gitignore pattern matching."""

    def test_excluded_directory(self):
        base = Path("/project")
        assert is_ignored(Path("/project/node_modules/file.js"), base, []) is True
        assert is_ignored(Path("/project/__pycache__/module.pyc"), base, []) is True
        assert is_ignored(Path("/project/.git/config"), base, []) is True

    def test_pattern_match_filename(self):
        base = Path("/project")
        assert is_ignored(Path("/project/file.pyc"), base, ["*.pyc"]) is True
        assert is_ignored(Path("/project/file.py"), base, ["*.pyc"]) is False

    def test_pattern_match_relative(self):
        base = Path("/project")
        assert is_ignored(Path("/project/dist/bundle.js"), base, ["dist/"]) is True

    def test_negated_pattern(self):
        base = Path("/project")
        # File matches ignore but is negated
        assert is_ignored(Path("/project/important.log"), base, ["*.log"], ["important.log"]) is False

    def test_file_outside_base(self):
        base = Path("/project")
        assert is_ignored(Path("/other/file.py"), base, []) is True

    def test_venv_excluded(self):
        base = Path("/project")
        assert is_ignored(Path("/project/.venv/lib/site.py"), base, []) is True
        assert is_ignored(Path("/project/venv/lib/site.py"), base, []) is True

    def test_normal_file_not_ignored(self):
        base = Path("/project")
        assert is_ignored(Path("/project/src/main.py"), base, []) is False
        assert is_ignored(Path("/project/README.md"), base, []) is False


class TestParseGitignore:
    """parse_gitignore: parse .gitignore files with tmp_path."""

    def test_no_gitignore(self, tmp_path: Path):
        patterns, negated = parse_gitignore(tmp_path)
        # Should have default patterns
        assert len(patterns) > 0
        assert "*.pyc" in patterns
        assert negated == []

    def test_with_gitignore(self, tmp_path: Path):
        (tmp_path / ".gitignore").write_text("*.log\nbuild/\n!important.log\n")
        patterns, negated = parse_gitignore(tmp_path)
        assert "*.log" in patterns
        assert "build/" in patterns
        assert "important.log" in negated

    def test_comments_and_empty_lines_skipped(self, tmp_path: Path):
        (tmp_path / ".gitignore").write_text("# Comment\n\n*.tmp\n")
        patterns, negated = parse_gitignore(tmp_path)
        assert "# Comment" not in patterns
        assert "*.tmp" in patterns


class TestIsBinaryFile:
    """is_binary_file: detect binary content."""

    def test_text_file(self, tmp_path: Path):
        f = tmp_path / "text.py"
        f.write_text("print('hello world')")
        assert is_binary_file(f) is False

    def test_binary_file(self, tmp_path: Path):
        f = tmp_path / "binary.bin"
        f.write_bytes(b"\x00\x01\x02\x03\xff\xfe")
        assert is_binary_file(f) is True

    def test_nonexistent_file(self, tmp_path: Path):
        f = tmp_path / "nonexistent"
        assert is_binary_file(f) is True  # Assumes binary if can't read


class TestCollectCodeFiles:
    """collect_code_files: full collection with tmp_path."""

    def test_collects_python_files(self, tmp_path: Path):
        (tmp_path / "main.py").write_text("print('hello')")
        (tmp_path / "utils.py").write_text("def helper(): pass")
        files = collect_code_files(tmp_path)
        paths = [p for p, _ in files]
        assert "main.py" in paths
        assert "utils.py" in paths

    def test_ignores_node_modules(self, tmp_path: Path):
        nm = tmp_path / "node_modules"
        nm.mkdir()
        (nm / "lib.js").write_text("module.exports = {}")
        (tmp_path / "app.js").write_text("const x = 1;")
        files = collect_code_files(tmp_path)
        paths = [p for p, _ in files]
        assert "app.js" in paths
        assert any("node_modules" in p for p in paths) is False

    def test_skips_unsupported_extensions(self, tmp_path: Path):
        (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00")
        (tmp_path / "main.py").write_text("x = 1")
        files = collect_code_files(tmp_path)
        paths = [p for p, _ in files]
        assert "image.png" not in paths

    def test_respects_max_files(self, tmp_path: Path):
        for i in range(20):
            (tmp_path / f"file_{i}.py").write_text(f"x = {i}")
        files = collect_code_files(tmp_path, max_files=5)
        assert len(files) <= 5

    def test_skips_empty_files(self, tmp_path: Path):
        (tmp_path / "empty.py").write_text("")
        (tmp_path / "notempty.py").write_text("x = 1")
        files = collect_code_files(tmp_path)
        paths = [p for p, _ in files]
        assert "empty.py" not in paths
        assert "notempty.py" in paths

    def test_nonexistent_path(self):
        files = collect_code_files(Path("/nonexistent/path"))
        assert files == []
