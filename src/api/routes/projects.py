"""Projects API - manage multiple project contexts."""

import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.api.dependencies import get_rag_adapter, get_store, limiter
from src.api.store import ProjectsStore
from src.infrastructure.rag.chromadb_adapter import ChromaDBRAGAdapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    """Request to add a project."""

    name: str = Field(..., min_length=1, max_length=255)
    path: str = Field(..., min_length=1, max_length=1024)


@router.get("")
@limiter.limit("60/minute")
async def list_projects(
    request: Request,
    store: ProjectsStore = Depends(get_store),
) -> dict:
    """List all registered projects."""
    projects = store.list_projects()
    current = store.get_current()
    return {
        "projects": [p.model_dump() for p in projects],
        "current": current.model_dump() if current else None,
    }


@router.post("")
@limiter.limit("10/minute")
async def add_project(
    request: Request,
    body: ProjectCreate,
    store: ProjectsStore = Depends(get_store),
) -> dict:
    """Add a new project."""
    try:
        project = store.add_project(body.name, body.path)
        return {"status": "ok", "project": project.model_dump()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{project_id}")
@limiter.limit("10/minute")
async def remove_project(
    request: Request,
    project_id: str,
    store: ProjectsStore = Depends(get_store),
) -> dict:
    """Remove a project."""
    if store.remove_project(project_id):
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Project not found")


@router.post("/{project_id}/select")
@limiter.limit("30/minute")
async def select_project(
    request: Request,
    project_id: str,
    store: ProjectsStore = Depends(get_store),
) -> dict:
    """Select a project as current."""
    if store.set_current(project_id):
        project = store.get_project(project_id)
        return {"status": "ok", "project": project.model_dump() if project else None}
    raise HTTPException(status_code=404, detail="Project not found")


@router.post("/{project_id}/index")
@limiter.limit("5/minute")
async def index_project(
    request: Request,
    project_id: str,
    incremental: bool = True,
    rag: ChromaDBRAGAdapter = Depends(get_rag_adapter),
    store: ProjectsStore = Depends(get_store),
) -> dict:
    """Index a project for RAG search.

    incremental: If True (default), only index new/changed files. If False, full reindex.
    """
    project = store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    original_cwd = os.getcwd()
    try:
        os.chdir(project.path)
        stats = await rag.index_path(".", incremental=incremental)
        from datetime import datetime

        store.update_project(
            project_id,
            indexed=True,
            files_count=stats.get("files_found", 0),
            last_indexed=datetime.now().isoformat(),
        )
        store.set_current(project_id)
        return {
            "status": "ok",
            "project": project_id,
            "stats": stats,
        }
    except Exception:
        logger.exception("Failed to index project %s at %s", project_id, project.path)
        raise HTTPException(status_code=500, detail="Failed to index project")
    finally:
        os.chdir(original_cwd)


@router.get("/current")
@limiter.limit("60/minute")
async def get_current_project(
    request: Request,
    store: ProjectsStore = Depends(get_store),
) -> dict:
    """Get currently selected project."""
    current = store.get_current()
    if current:
        return {"project": current.model_dump()}
    return {"project": None}
