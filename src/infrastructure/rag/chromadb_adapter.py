"""ChromaDB RAG adapter - implements RAGPort.

Production-ready with:
- Batch retry on embedding failures
- Progress logging for large indexing
- Configurable batch size
"""

import asyncio
import hashlib
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

import chromadb
from chromadb.config import Settings

from src.domain.ports.config import RAGConfig
from src.domain.ports.embeddings import EmbeddingsPort
from src.domain.ports.rag import Chunk
from src.infrastructure.agents.project_mapper import (
    build_project_map,
    load_project_map,
    save_project_map,
)
from src.infrastructure.rag.file_collector import (
    chunk_text,
    collect_code_files_with_stats,
)
from src.infrastructure.rag.index_state import IndexState

logger = logging.getLogger(__name__)


class ChromaDBRAGAdapter:
    """ChromaDB implementation of RAGPort."""

    def __init__(
        self,
        config: RAGConfig,
        embeddings: EmbeddingsPort,
    ) -> None:
        """Initialize with RAG config and embeddings port."""
        self._config = config
        self._embeddings = embeddings
        chromadb_path = Path(config.chromadb_path).resolve()
        chromadb_path.mkdir(parents=True, exist_ok=True)
        settings = Settings(anonymized_telemetry=False)
        self._client = chromadb.PersistentClient(path=str(chromadb_path), settings=settings)
        self._collection = self._client.get_or_create_collection(
            name=config.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._index_stats: dict = {}
        self._index_state = IndexState(str(chromadb_path))

    def close(self) -> None:
        """Release ChromaDB resources (call during app shutdown)."""
        try:
            # PersistentClient doesn't have explicit close, but we clear references
            self._collection = None  # type: ignore[assignment]
            self._client = None  # type: ignore[assignment]
            logger.debug("ChromaDB adapter closed")
        except Exception:
            logger.debug("ChromaDB close error (non-critical)", exc_info=True)

    async def search(
        self,
        query: str,
        limit: int = 20,
        min_score: float = 0.3,
        max_tokens: int | None = None,
    ) -> list[Chunk]:
        """Search for relevant chunks by query.

        Handles ChromaDB query failures gracefully.
        """
        if not query.strip():
            return []

        try:
            count = self._collection.count()
            if count == 0:
                return []
        except (ValueError, RuntimeError) as e:
            logger.error("Failed to get collection count: %s", e)
            return []

        try:
            query_embedding = await self._embeddings.embed(query.strip())
            if not query_embedding:
                logger.warning("Empty query embedding returned")
                return []
        except (ConnectionError, OSError, RuntimeError) as e:
            logger.error("Failed to embed query: %s", e)
            return []
        except Exception as e:
            logger.error("Unexpected embedding error: %s", e, exc_info=True)
            return []

        try:
            result = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=min(limit, count),
                include=["documents", "metadatas", "distances"],
            )
        except (ValueError, RuntimeError) as e:
            logger.error("ChromaDB query failed: %s", e)
            return []

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

    async def index_path(
        self,
        path: str,
        generate_map: bool = True,
        incremental: bool = True,
        on_progress: Callable[[int, int], Awaitable[None]] | None = None,
    ) -> dict:
        """Index a directory for RAG search.

        Args:
            path: Directory to index
            generate_map: Whether to build project map
            incremental: If True, only index new/changed files; if False, full reindex
            on_progress: Optional callback(batch_num, total_batches)

        """
        base = Path(path).resolve()
        base_str = str(base)

        stats = {
            "path": base_str,
            "files_found": 0,
            "files_added": 0,
            "files_updated": 0,
            "files_deleted": 0,
            "files_unchanged": 0,
            "files_by_type": {},
            "total_chunks": 0,
            "total_chars": 0,
            "project_map": None,
            "incremental": incremental,
        }

        files_with_stats = collect_code_files_with_stats(base, max_files=self._config.max_file_count)
        current_files: dict[str, dict[str, float | int]] = {
            rel: {"mtime": mtime, "size": size} for rel, _, mtime, size in files_with_stats
        }

        if incremental:
            indexed = self._index_state.get_indexed_files(base_str)
            new_paths, changed_paths, deleted_paths = IndexState.diff_files(current_files, indexed)
            unchanged_count = len(current_files) - len(new_paths) - len(changed_paths)
            stats["files_added"] = len(new_paths)
            stats["files_updated"] = len(changed_paths)
            stats["files_deleted"] = len(deleted_paths)
            stats["files_unchanged"] = unchanged_count

            # Delete chunks for removed and changed files
            to_delete = set(deleted_paths) | set(changed_paths)
            for rel_path in to_delete:
                self.delete_chunks_by_source(rel_path)

            # Only index new and changed files
            to_index = set(new_paths) | set(changed_paths)
            files_to_process = [
                (rel, content, mtime, size) for rel, content, mtime, size in files_with_stats if rel in to_index
            ]
        else:
            self.clear()
            self._index_state.clear_state(base_str)
            files_to_process = files_with_stats

        stats["files_found"] = len(files_with_stats)

        if not files_to_process:
            # Update project map even when no new files
            if generate_map and files_with_stats:
                files_for_map = [(r, c) for r, c, _, _ in files_with_stats]
                try:
                    project_map = build_project_map(base, files_for_map)
                    map_path = save_project_map(project_map)
                    stats["project_map"] = str(map_path)
                    stats["project_stats"] = project_map.stats
                except Exception as e:
                    logger.warning("Project map generation failed: %s", e)
                    stats["project_map_error"] = str(e)
            self._index_state.update_state(base_str, current_files)
            stats["total_chunks"] = self._collection.count()
            self._index_stats = stats
            return stats

        # Generate project map from all files
        if generate_map:
            files_for_map = [(r, c) for r, c, _, _ in files_with_stats]
            try:
                project_map = build_project_map(base, files_for_map)
                map_path = save_project_map(project_map)
                stats["project_map"] = str(map_path)
                stats["project_stats"] = project_map.stats
            except Exception as e:
                logger.warning("Project map generation failed: %s", e)
                stats["project_map_error"] = str(e)

        for rel_path, _, _, _ in files_to_process:
            ext = Path(rel_path).suffix.lower()
            stats["files_by_type"][ext] = stats["files_by_type"].get(ext, 0) + 1

        # Prepare chunks for files to process
        all_chunks: list[str] = []
        all_ids: list[str] = []
        all_metadatas: list[dict] = []

        for rel_path, content, _, _ in files_to_process:
            ext = Path(rel_path).suffix.lower()
            chunks = chunk_text(
                content,
                self._config.chunk_size,
                self._config.chunk_overlap,
            )
            for j, chunk in enumerate(chunks):
                chunk_id = hashlib.sha256(f"{rel_path}:{j}".encode()).hexdigest()[:16]
                all_chunks.append(chunk)
                all_ids.append(chunk_id)
                all_metadatas.append(
                    {
                        "source": rel_path,
                        "chunk": j,
                        "extension": ext,
                    }
                )
                stats["total_chars"] += len(chunk)

        if not all_chunks:
            self._index_state.update_state(base_str, current_files)
            stats["total_chunks"] = self._collection.count()
            self._index_stats = stats
            return stats

        batch_size = self._config.batch_size
        total_batches = (len(all_chunks) + batch_size - 1) // batch_size

        logger.info(
            f"Indexing {len(all_chunks)} chunks ({len(files_to_process)} files) "
            f"in {total_batches} batches (incremental={incremental})"
        )

        for batch_num, i in enumerate(range(0, len(all_chunks), batch_size), 1):
            batch_chunks = all_chunks[i : i + batch_size]
            batch_ids = all_ids[i : i + batch_size]
            batch_metas = all_metadatas[i : i + batch_size]

            embeddings = None
            last_error = None
            for attempt in range(3):
                try:
                    embeddings = await self._embeddings.embed_batch(batch_chunks)
                    if len(embeddings) != len(batch_chunks):
                        logger.warning(
                            f"Batch {batch_num}: embedding count mismatch "
                            f"(got {len(embeddings)}, expected {len(batch_chunks)})"
                        )
                        while len(embeddings) < len(batch_chunks):
                            embeddings.append([])
                        embeddings = embeddings[: len(batch_chunks)]
                    break
                except Exception as e:
                    last_error = e
                    if attempt < 2:
                        logger.warning("Batch %d embedding failed (attempt %d): %s", batch_num, attempt + 1, e)
                        await asyncio.sleep(2**attempt)
                    else:
                        logger.error("Batch %d embedding failed after 3 attempts: %s", batch_num, e)

            if embeddings is None:
                logger.error("Skipping batch %d due to embedding failure: %s", batch_num, last_error)
                continue

            try:
                self._collection.upsert(
                    ids=batch_ids,
                    documents=batch_chunks,
                    embeddings=embeddings,
                    metadatas=batch_metas,
                )
            except Exception as e:
                logger.error("Batch %d ChromaDB upsert failed: %s", batch_num, e)

            if on_progress:
                await on_progress(batch_num, total_batches)
            if total_batches > 5 and batch_num % max(1, total_batches // 10) == 0:
                progress_pct = round(batch_num / total_batches * 100)
                logger.info("Indexing progress: %d%% (%d/%d)", progress_pct, batch_num, total_batches)

        self._index_state.update_state(base_str, current_files)
        stats["total_chunks"] = self._collection.count()
        logger.info("Indexing complete: %d chunks, total in index: %d", len(all_chunks), stats["total_chunks"])
        self._index_stats = stats
        return stats

    def get_project_map_markdown(self) -> str | None:
        """Get project map as markdown."""
        project_map = load_project_map()
        if project_map:
            return project_map.to_markdown()
        return None

    def delete_chunks_by_source(self, source_path: str) -> int:
        """Delete all chunks for a given source file. Returns count deleted."""
        try:
            self._collection.delete(where={"source": {"$eq": source_path}})
            return 1
        except Exception as e:
            logger.warning("Failed to delete chunks for %s: %s", source_path, e)
            return 0

    def clear(self) -> None:
        """Clear all indexed data and index state."""
        self._client.delete_collection(self._config.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self._config.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._index_state.clear_state()
        self._index_stats = {}
