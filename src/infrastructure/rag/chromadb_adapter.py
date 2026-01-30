"""ChromaDB RAG adapter - implements RAGPort."""

import hashlib
from pathlib import Path

import chromadb

from src.domain.ports.config import RAGConfig
from src.domain.ports.embeddings import EmbeddingsPort
from src.domain.ports.rag import Chunk
from src.infrastructure.rag.file_collector import collect_code_files, chunk_text
from src.infrastructure.agents.project_mapper import (
    build_project_map,
    save_project_map,
    load_project_map,
)


class ChromaDBRAGAdapter:
    """ChromaDB implementation of RAGPort."""

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
        self._index_stats: dict = {}

    async def search(
        self,
        query: str,
        limit: int = 20,
        min_score: float = 0.3,
        max_tokens: int | None = None,
    ) -> list[Chunk]:
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
        total_chars = 0
        max_chars = max_tokens * 4 if max_tokens else None
        
        for i, doc in enumerate(documents):
            if not doc:
                continue
            
            meta = metadatas[i] if i < len(metadatas) else {}
            dist = distances[i] if i < len(distances) else 0.0
            score = max(0.0, min(1.0, 1 - (dist / 2))) if dist is not None else 1.0
            
            if score < min_score:
                continue
            
            if max_chars and total_chars + len(doc) > max_chars:
                break
            
            total_chars += len(doc)
            chunks.append(Chunk(content=doc, metadata=meta or {}, score=score))
        
        return chunks

    async def search_by_file(self, filename: str, limit: int = 10) -> list[Chunk]:
        """Search for chunks from a specific file."""
        count = self._collection.count()
        if count == 0:
            return []
        
        result = self._collection.get(
            where={"source": {"$eq": filename}},
            limit=limit,
            include=["documents", "metadatas"],
        )
        
        documents = result.get("documents", []) or []
        metadatas = result.get("metadatas", []) or []
        
        chunks: list[Chunk] = []
        for i, doc in enumerate(documents):
            if doc:
                meta = metadatas[i] if i < len(metadatas) else {}
                chunks.append(Chunk(content=doc, metadata=meta or {}, score=1.0))
        
        return chunks

    def get_stats(self) -> dict:
        """Get indexing statistics."""
        return {
            "total_chunks": self._collection.count(),
            **self._index_stats,
        }

    def get_indexed_files(self) -> list[str]:
        """Get list of indexed files."""
        result = self._collection.get(
            limit=10000,
            include=["metadatas"],
        )
        metadatas = result.get("metadatas", []) or []
        files = set()
        for meta in metadatas:
            if meta and "source" in meta:
                files.add(meta["source"])
        return sorted(files)

    async def index_path(self, path: str, generate_map: bool = True) -> dict:
        """Index a directory for RAG search."""
        base = Path(path).resolve()
        files = collect_code_files(base)
        
        stats = {
            "path": str(base),
            "files_found": len(files),
            "files_by_type": {},
            "total_chunks": 0,
            "total_chars": 0,
            "project_map": None,
        }
        
        if not files:
            self._index_stats = stats
            return stats
        
        # Generate project map
        if generate_map:
            try:
                project_map = build_project_map(base, files)
                map_path = save_project_map(project_map)
                stats["project_map"] = str(map_path)
                stats["project_stats"] = project_map.stats
            except Exception as e:
                stats["project_map_error"] = str(e)
        
        # Count files by extension
        for rel_path, _ in files:
            ext = Path(rel_path).suffix.lower()
            stats["files_by_type"][ext] = stats["files_by_type"].get(ext, 0) + 1
        
        # Prepare chunks
        all_chunks: list[str] = []
        all_ids: list[str] = []
        all_metadatas: list[dict] = []
        
        for rel_path, content in files:
            ext = Path(rel_path).suffix.lower()
            chunks = chunk_text(
                content,
                self._config.chunk_size,
                self._config.chunk_overlap,
            )
            for j, chunk in enumerate(chunks):
                chunk_id = hashlib.sha256(
                    f"{rel_path}:{j}:{chunk[:100]}".encode()
                ).hexdigest()[:16]
                all_chunks.append(chunk)
                all_ids.append(chunk_id)
                all_metadatas.append({
                    "source": rel_path,
                    "chunk": j,
                    "extension": ext,
                })
                stats["total_chars"] += len(chunk)
        
        stats["total_chunks"] = len(all_chunks)
        
        if not all_chunks:
            self._index_stats = stats
            return stats
        
        # Batch embeddings
        batch_size = 100
        for i in range(0, len(all_chunks), batch_size):
            batch_chunks = all_chunks[i:i + batch_size]
            batch_ids = all_ids[i:i + batch_size]
            batch_metas = all_metadatas[i:i + batch_size]
            
            embeddings = await self._embeddings.embed_batch(batch_chunks)
            self._collection.upsert(
                ids=batch_ids,
                documents=batch_chunks,
                embeddings=embeddings,
                metadatas=batch_metas,
            )
        
        self._index_stats = stats
        return stats

    def get_project_map_markdown(self) -> str | None:
        """Get project map as markdown."""
        project_map = load_project_map()
        if project_map:
            return project_map.to_markdown()
        return None

    def clear(self) -> None:
        """Clear all indexed data."""
        self._client.delete_collection(self._config.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self._config.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._index_stats = {}
