"""RAG API routes - index project for context retrieval."""

from fastapi import APIRouter, Depends, Request

from src.api.dependencies import get_rag_adapter, limiter
from src.infrastructure.rag.chromadb_adapter import ChromaDBRAGAdapter

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/index")
@limiter.limit("10/minute")
async def index_path(
    request: Request,
    path: str = ".",
    rag: ChromaDBRAGAdapter = Depends(get_rag_adapter),
):
    """Index a directory for RAG search. Path relative to project root or absolute."""
    await rag.index_path(path)
    return {"status": "ok", "path": path}


@router.get("/status")
@limiter.limit("60/minute")
async def rag_status(
    request: Request,
    rag: ChromaDBRAGAdapter = Depends(get_rag_adapter),
):
    """Get RAG index status (document count)."""
    count = rag._collection.count()
    return {"status": "ok", "documents": count}
