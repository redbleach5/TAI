"""RAG API routes - index project for context retrieval."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.api.dependencies import get_rag_adapter, limiter
from src.infrastructure.rag.chromadb_adapter import ChromaDBRAGAdapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["rag"])


class SearchRequest(BaseModel):
    """Request for RAG search."""

    query: str = Field(..., min_length=1, max_length=2000)
    limit: int = Field(20, ge=1, le=100)
    min_score: float = Field(0.3, ge=0.0, le=1.0)
    max_tokens: int | None = Field(None, ge=1, le=100_000)


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
) -> dict:
    """Index a directory for RAG search.

    Indexes all code files (.py, .ts, .tsx, .js, .json, .md, .toml, etc.)
    Respects .gitignore patterns.

    incremental: If True (default), only index new/changed files. If False, full reindex.
    """
    try:
        stats = await rag.index_path(path, incremental=incremental)
    except Exception:
        logger.exception("Failed to index path: %s", path)
        raise HTTPException(status_code=500, detail="Failed to index path")

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
) -> dict:
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
) -> dict:
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
        request: FastAPI request.
        body: Search request (query, limit, min_score, max_tokens).
        rag: RAG adapter (injected).

    Returns:
        Search response with chunks.

    """
    try:
        chunks = await rag.search(
            query=body.query,
            limit=body.limit,
            min_score=body.min_score,
            max_tokens=body.max_tokens,
        )
    except Exception:
        logger.exception("RAG search failed for query: %s", body.query)
        raise HTTPException(status_code=500, detail="RAG search failed")

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
) -> dict:
    """Clear all indexed data."""
    try:
        rag.clear()
    except Exception:
        logger.exception("Failed to clear RAG index")
        raise HTTPException(status_code=500, detail="Failed to clear index")
    return {"status": "ok", "message": "Index cleared"}


@router.get("/project-map")
@limiter.limit("30/minute")
async def get_project_map(
    request: Request,
    rag: ChromaDBRAGAdapter = Depends(get_rag_adapter),
) -> dict:
    """Get project map (structure overview).

    Returns markdown description of project structure including:
    - File tree
    - Classes and their methods
    - Functions with signatures
    - Imports and dependencies
    """
    map_md = rag.get_project_map_markdown()
    if not map_md:
        raise HTTPException(
            status_code=404,
            detail="Project map not found. Run /rag/index first.",
        )
    return {
        "status": "ok",
        "project_map": map_md,
    }
