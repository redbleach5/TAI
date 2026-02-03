"""RAG API routes - index project for context retrieval."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from src.api.dependencies import get_rag_adapter, limiter
from src.infrastructure.rag.chromadb_adapter import ChromaDBRAGAdapter

router = APIRouter(prefix="/rag", tags=["rag"])


class SearchRequest(BaseModel):
    """Request for RAG search."""

    query: str
    limit: int = 20
    min_score: float = 0.3
    max_tokens: int | None = None


class ChunkResult(BaseModel):
    """Single search result."""

    content: str
    source: str
    score: float


class SearchResponse(BaseModel):
    """Response from RAG search."""

    results: list[ChunkResult]
    total_chars: int


@router.post("/index")
@limiter.limit("10/minute")
async def index_path(
    request: Request,
    path: str = ".",
    incremental: bool = True,
    rag: ChromaDBRAGAdapter = Depends(get_rag_adapter),
):
    """Index a directory for RAG search.

    Indexes all code files (.py, .ts, .tsx, .js, .json, .md, .toml, etc.)
    Respects .gitignore patterns.

    incremental: If True (default), only index new/changed files. If False, full reindex.
    """
    stats = await rag.index_path(path, incremental=incremental)
    return {
        "status": "ok",
        "path": stats.get("path", path),
        "files_indexed": stats.get("files_found", 0),
        "files_by_type": stats.get("files_by_type", {}),
        "chunks_created": stats.get("total_chunks", 0),
    }


@router.get("/status")
@limiter.limit("60/minute")
async def rag_status(
    request: Request,
    rag: ChromaDBRAGAdapter = Depends(get_rag_adapter),
):
    """Get RAG index status with statistics."""
    stats = rag.get_stats()
    return {
        "status": "ok",
        "total_chunks": stats.get("total_chunks", 0),
        "files_indexed": stats.get("files_found", 0),
        "files_by_type": stats.get("files_by_type", {}),
        "path": stats.get("path"),
    }


@router.get("/files")
@limiter.limit("30/minute")
async def list_indexed_files(
    request: Request,
    rag: ChromaDBRAGAdapter = Depends(get_rag_adapter),
):
    """Get list of all indexed files."""
    files = rag.get_indexed_files()
    return {"files": files, "count": len(files)}


@router.post("/search")
@limiter.limit("60/minute")
async def search_rag(
    request: Request,
    body: SearchRequest,
    rag: ChromaDBRAGAdapter = Depends(get_rag_adapter),
) -> SearchResponse:
    """Search RAG index for relevant code chunks.

    Args:
        query: Search query
        limit: Max results (default 20)
        min_score: Minimum relevance 0-1 (default 0.3)
        max_tokens: Limit total tokens in response
    """
    chunks = await rag.search(
        query=body.query,
        limit=body.limit,
        min_score=body.min_score,
        max_tokens=body.max_tokens,
    )

    results = []
    total_chars = 0
    for chunk in chunks:
        results.append(
            ChunkResult(
                content=chunk.content,
                source=chunk.metadata.get("source", "unknown"),
                score=chunk.score,
            )
        )
        total_chars += len(chunk.content)

    return SearchResponse(results=results, total_chars=total_chars)


@router.post("/clear")
@limiter.limit("5/minute")
async def clear_index(
    request: Request,
    rag: ChromaDBRAGAdapter = Depends(get_rag_adapter),
):
    """Clear all indexed data."""
    rag.clear()
    return {"status": "ok", "message": "Index cleared"}


@router.get("/project-map")
@limiter.limit("30/minute")
async def get_project_map(
    request: Request,
    rag: ChromaDBRAGAdapter = Depends(get_rag_adapter),
):
    """Get project map (structure overview).

    Returns markdown description of project structure including:
    - File tree
    - Classes and their methods
    - Functions with signatures
    - Imports and dependencies
    """
    map_md = rag.get_project_map_markdown()
    if not map_md:
        return {
            "status": "error",
            "error": "Project map not found. Run /rag/index first.",
        }
    return {
        "status": "ok",
        "project_map": map_md,
    }
