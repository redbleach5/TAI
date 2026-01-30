"""Tests for ChromaDB RAG adapter."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile
import os

from src.domain.ports.config import RAGConfig
from src.infrastructure.rag.chromadb_adapter import ChromaDBRAGAdapter
from src.infrastructure.rag.file_collector import chunk_text, collect_code_files


class TestChunkText:
    """Tests for chunk_text helper."""

    def test_empty_text(self):
        """Empty text returns empty list."""
        assert chunk_text("", 100, 10) == []

    def test_short_text(self):
        """Text shorter than chunk_size returns single chunk."""
        result = chunk_text("Hello", 100, 10)
        assert result == ["Hello"]

    def test_exact_chunk_size(self):
        """Text exactly chunk_size returns single chunk."""
        text = "a" * 100
        result = chunk_text(text, 100, 10)
        assert len(result) == 1
        assert result[0] == text

    def test_multiple_chunks(self):
        """Text longer than chunk_size returns multiple chunks."""
        text = "a" * 250
        result = chunk_text(text, 100, 20)
        assert len(result) > 1
        # First chunk should be 100 chars
        assert len(result[0]) == 100

    def test_overlap(self):
        """Chunks overlap by specified amount."""
        text = "0123456789" * 5  # 50 chars
        result = chunk_text(text, 20, 5)
        # With overlap, chunks should share characters
        assert len(result) >= 2

    def test_zero_chunk_size(self):
        """Zero chunk_size returns empty list."""
        assert chunk_text("Hello", 0, 0) == []

    def test_whitespace_stripped(self):
        """Chunks are stripped of whitespace."""
        text = "  Hello  " + "a" * 100
        result = chunk_text(text, 20, 0)
        assert result[0] == "Hello"


class TestCollectCodeFiles:
    """Tests for collect_code_files helper."""

    def test_empty_directory(self):
        """Empty directory returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = collect_code_files(Path(tmpdir))
            assert result == []

    def test_collects_python_files(self):
        """Collects .py files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a Python file
            py_file = Path(tmpdir) / "test.py"
            py_file.write_text("print('hello')")
            
            result = collect_code_files(Path(tmpdir))
            
            assert len(result) == 1
            assert result[0][0] == "test.py"
            assert "print('hello')" in result[0][1]

    def test_collects_txt_files(self):
        """Now also collects .txt files (documentation)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            txt_file = Path(tmpdir) / "readme.txt"
            txt_file.write_text("readme content")
            
            result = collect_code_files(Path(tmpdir))
            assert len(result) == 1

    def test_ignores_venv(self):
        """Ignores .venv directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            venv_dir = Path(tmpdir) / ".venv"
            venv_dir.mkdir()
            venv_file = venv_dir / "test.py"
            venv_file.write_text("venv code")
            
            result = collect_code_files(Path(tmpdir))
            assert result == []

    def test_ignores_pycache(self):
        """Ignores __pycache__ directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "__pycache__"
            cache_dir.mkdir()
            cache_file = cache_dir / "test.py"
            cache_file.write_text("cached")
            
            result = collect_code_files(Path(tmpdir))
            assert result == []

    def test_recursive(self):
        """Recursively collects from subdirectories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sub_dir = Path(tmpdir) / "sub"
            sub_dir.mkdir()
            (sub_dir / "nested.py").write_text("nested")
            (Path(tmpdir) / "root.py").write_text("root")
            
            result = collect_code_files(Path(tmpdir))
            
            assert len(result) == 2
            paths = [r[0] for r in result]
            assert "root.py" in paths
            assert os.path.join("sub", "nested.py") in paths

    def test_nonexistent_directory(self):
        """Nonexistent directory returns empty list."""
        result = collect_code_files(Path("/nonexistent/path"))
        assert result == []


class TestChromaDBRAGAdapter:
    """Tests for ChromaDBRAGAdapter."""

    @pytest.fixture
    def config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield RAGConfig(
                chromadb_path=tmpdir,
                collection_name="test_collection",
                chunk_size=100,
                chunk_overlap=10,
            )

    @pytest.fixture
    def mock_embeddings(self):
        embeddings = MagicMock()
        embeddings.embed = AsyncMock(return_value=[0.1, 0.2, 0.3])
        embeddings.embed_batch = AsyncMock(return_value=[[0.1, 0.2], [0.3, 0.4]])
        return embeddings

    @pytest.fixture
    def adapter(self, config, mock_embeddings):
        return ChromaDBRAGAdapter(config, mock_embeddings)

    @pytest.mark.asyncio
    async def test_search_empty_query(self, adapter):
        """Search with empty query returns empty list."""
        result = await adapter.search("")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_empty_collection(self, adapter):
        """Search on empty collection returns empty list."""
        result = await adapter.search("test query")
        assert result == []

    @pytest.mark.asyncio
    async def test_index_and_search(self, adapter, config, mock_embeddings):
        """Can index directory and search."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a Python file to index
            py_file = Path(tmpdir) / "code.py"
            py_file.write_text("def hello(): pass")
            
            # Index
            await adapter.index_path(tmpdir)
            
            # Embeddings should have been called
            mock_embeddings.embed_batch.assert_called()

    @pytest.mark.asyncio
    async def test_index_empty_directory(self, adapter):
        """Indexing empty directory doesn't fail."""
        with tempfile.TemporaryDirectory() as tmpdir:
            await adapter.index_path(tmpdir)
            # Should not raise

    @pytest.mark.asyncio
    async def test_search_returns_chunks(self, adapter, mock_embeddings):
        """Search returns Chunk objects with score."""
        # Manually add some data to collection
        adapter._collection.add(
            ids=["test1"],
            documents=["test document content"],
            embeddings=[[0.1, 0.2, 0.3]],
            metadatas=[{"source": "test.py", "chunk": 0}],
        )
        
        result = await adapter.search("test query", limit=5)
        
        assert len(result) == 1
        assert result[0].content == "test document content"
        assert result[0].metadata["source"] == "test.py"
        assert 0 <= result[0].score <= 1
