"""ChromaDB RAG adapter - implements RAGPort."""

import hashlib
from pathlib import Path

import chromadb

from src.domain.ports.config import RAGConfig
from src.domain.ports.embeddings import EmbeddingsPort
from src.domain.ports.rag import Chunk


def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks."""
    if not text or chunk_size <= 0:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end].strip())
        start = end - overlap if overlap < chunk_size else end
    return [c for c in chunks if c]


def _collect_code_files(path: Path) -> list[tuple[str, str]]:
    """Collect (relative_path, content) for Python files."""
    results: list[tuple[str, str]] = []
    path = path.resolve()
    if not path.is_dir():
        return results
    for p in path.rglob("*.py"):
        if p.is_file() and ".venv" not in str(p) and "__pycache__" not in str(p):
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
                rel = str(p.relative_to(path))
                results.append((rel, content))
            except OSError:
                continue
    return results


class ChromaDBRAGAdapter:
    """ChromaDB implementation of RAGPort. Uses EmbeddingsPort for vectors."""

    def __init__(
        self,
        config: RAGConfig,
        embeddings: EmbeddingsPort,
    ) -> None:
        self._config = config
        self._embeddings = embeddings
        self._client = chromadb.PersistentClient(path=config.chromadb_path)
        self._collection = self._client.get_or_create_collection(
            name=config.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    async def search(self, query: str, limit: int = 10) -> list[Chunk]:
        """Search for relevant chunks by query."""
        if not query.strip():
            return []
        count = self._collection.count()
        if count == 0:
            return []
        query_embedding = await self._embeddings.embed(query.strip())
        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(limit, count),
            include=["documents", "metadatas", "distances"],
        )
        documents = result.get("documents", [[]])[0] or []
        metadatas = result.get("metadatas", [[]])[0] or []
        distances = result.get("distances", [[]])[0] or []
        chunks: list[Chunk] = []
        for i, doc in enumerate(documents):
            if doc:
                meta = metadatas[i] if i < len(metadatas) else {}
                dist = distances[i] if i < len(distances) else 0.0
                # Cosine distance: 0 = identical, 2 = opposite. Convert to score (1 = best).
                score = max(0, 1 - (dist / 2)) if dist is not None else 1.0
                chunks.append(Chunk(content=doc, metadata=meta or {}, score=score))
        return chunks

    async def index_path(self, path: str) -> None:
        """Index a directory for RAG search."""
        base = Path(path)
        files = _collect_code_files(base)
        if not files:
            return
        all_chunks: list[str] = []
        all_ids: list[str] = []
        all_metadatas: list[dict] = []
        for rel_path, content in files:
            chunks = _chunk_text(
                content,
                self._config.chunk_size,
                self._config.chunk_overlap,
            )
            for j, chunk in enumerate(chunks):
                chunk_id = hashlib.sha256(f"{rel_path}:{j}:{chunk[:100]}".encode()).hexdigest()[:16]
                all_chunks.append(chunk)
                all_ids.append(chunk_id)
                all_metadatas.append({"source": rel_path, "chunk": j})
        if not all_chunks:
            return
        embeddings = await self._embeddings.embed_batch(all_chunks)
        self._collection.upsert(
            ids=all_ids,
            documents=all_chunks,
            embeddings=embeddings,
            metadatas=all_metadatas,
        )
