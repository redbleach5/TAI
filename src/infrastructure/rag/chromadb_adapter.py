"""ChromaDB RAG adapter - implements RAGPort."""

import hashlib
import fnmatch
from pathlib import Path

import chromadb

from src.domain.ports.config import RAGConfig
from src.domain.ports.embeddings import EmbeddingsPort
from src.domain.ports.rag import Chunk
from src.infrastructure.agents.project_mapper import build_project_map, save_project_map, load_project_map


# Supported file extensions for indexing
SUPPORTED_EXTENSIONS = {
    # Python
    ".py",
    # JavaScript/TypeScript
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    # Config/Data
    ".json", ".toml", ".yaml", ".yml",
    # Documentation
    ".md", ".mdx", ".rst", ".txt",
    # Web
    ".html", ".css", ".scss", ".sass",
    # Other
    ".sh", ".bash", ".sql", ".graphql",
}

# Directories to always exclude
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "coverage",
    ".tox",
    "eggs",
    "*.egg-info",
}

# Default gitignore patterns
DEFAULT_IGNORES = [
    "*.pyc",
    "*.pyo",
    "*.egg",
    "*.egg-info",
    ".DS_Store",
    "Thumbs.db",
    "*.log",
    "*.bak",
    "*.swp",
    "*.lock",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
]


def _parse_gitignore(path: Path) -> list[str]:
    """Parse .gitignore file and return patterns."""
    gitignore = path / ".gitignore"
    patterns = list(DEFAULT_IGNORES)
    if gitignore.exists():
        try:
            for line in gitignore.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
        except OSError:
            pass
    return patterns


def _is_ignored(file_path: Path, base_path: Path, patterns: list[str]) -> bool:
    """Check if file matches any gitignore pattern."""
    try:
        rel_path = str(file_path.relative_to(base_path))
    except ValueError:
        return True
    
    # Check excluded directories
    parts = rel_path.split("/")
    for part in parts[:-1]:  # Check all parent directories
        if part in EXCLUDED_DIRS:
            return True
        for excluded in EXCLUDED_DIRS:
            if "*" in excluded and fnmatch.fnmatch(part, excluded):
                return True
    
    # Check gitignore patterns
    for pattern in patterns:
        # Handle directory patterns (ending with /)
        if pattern.endswith("/"):
            dir_pattern = pattern[:-1]
            for part in parts[:-1]:
                if fnmatch.fnmatch(part, dir_pattern):
                    return True
        # Handle file patterns
        elif fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(parts[-1], pattern):
            return True
    
    return False


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
    """Collect (relative_path, content) for all supported code files."""
    results: list[tuple[str, str]] = []
    path = path.resolve()
    if not path.is_dir():
        return results
    
    # Parse gitignore
    ignore_patterns = _parse_gitignore(path)
    
    # Collect all files with supported extensions
    for p in path.rglob("*"):
        if not p.is_file():
            continue
        
        # Check extension
        if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        
        # Check if ignored
        if _is_ignored(p, path, ignore_patterns):
            continue
        
        # Skip large files (>500KB likely not code)
        try:
            if p.stat().st_size > 500 * 1024:
                continue
        except OSError:
            continue
        
        # Read file
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
        self._index_stats: dict = {}

    async def search(
        self,
        query: str,
        limit: int = 20,
        min_score: float = 0.3,
        max_tokens: int | None = None,
    ) -> list[Chunk]:
        """Search for relevant chunks by query.
        
        Args:
            query: Search query
            limit: Max number of chunks to return (default 20)
            min_score: Minimum relevance score (0-1, default 0.3)
            max_tokens: If set, limit total tokens in results (approx 4 chars/token)
        """
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
            # Cosine distance: 0 = identical, 2 = opposite. Convert to score (1 = best).
            score = max(0, 1 - (dist / 2)) if dist is not None else 1.0
            
            # Filter by min score
            if score < min_score:
                continue
            
            # Check token limit
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
        """Index a directory for RAG search.
        
        Args:
            path: Directory path to index
            generate_map: Whether to generate project map (default True)
        
        Returns:
            Statistics about indexed files and chunks.
        """
        base = Path(path).resolve()
        files = _collect_code_files(base)
        
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
        
        all_chunks: list[str] = []
        all_ids: list[str] = []
        all_metadatas: list[dict] = []
        
        for rel_path, content in files:
            ext = Path(rel_path).suffix.lower()
            chunks = _chunk_text(
                content,
                self._config.chunk_size,
                self._config.chunk_overlap,
            )
            for j, chunk in enumerate(chunks):
                chunk_id = hashlib.sha256(f"{rel_path}:{j}:{chunk[:100]}".encode()).hexdigest()[:16]
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
        
        # Batch embeddings (in chunks to avoid memory issues)
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
        # Delete and recreate collection
        self._client.delete_collection(self._config.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self._config.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._index_stats = {}
