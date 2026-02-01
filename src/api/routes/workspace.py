"""Workspace API - open folder, get current workspace."""

import asyncio
import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from src.api.dependencies import get_rag_adapter, limiter
from src.api.routes.projects import get_store
from src.infrastructure.rag.chromadb_adapter import ChromaDBRAGAdapter

router = APIRouter(prefix="/workspace", tags=["workspace"])


class WorkspaceSet(BaseModel):
    """Set workspace (open folder) request."""
    path: str


class WorkspaceCreate(BaseModel):
    """Create new project folder and set as workspace."""
    path: str
    name: str | None = None


def _get_workspace_path() -> str:
    """Get current workspace path (current project or cwd)."""
    store = get_store()
    current = store.get_current()
    return current.path if current else str(Path.cwd().resolve())


@router.get("")
@limiter.limit("60/minute")
async def get_workspace(request: Request):
    """Get current workspace path and name."""
    store = get_store()
    current = store.get_current()
    if current:
        return {"path": current.path, "name": current.name}
    path = Path.cwd().resolve()
    return {"path": str(path), "name": path.name}


def _ensure_path_allowed(path: Path) -> None:
    """Raise if path is not under home or cwd (safety for create)."""
    path = path.resolve()
    home = Path.home().resolve()
    cwd = Path.cwd().resolve()
    try:
        path.relative_to(home)
        return
    except ValueError:
        pass
    try:
        path.relative_to(cwd)
        return
    except ValueError:
        pass
    raise HTTPException(
        status_code=400,
        detail="Path must be under your home directory or current working directory",
    )


@router.post("")
@limiter.limit("30/minute")
async def set_workspace(request: Request, body: WorkspaceSet):
    """Open folder - set as current workspace (add project and select)."""
    store = get_store()
    p = Path(body.path)
    if not p.is_absolute():
        p = Path.cwd() / p
    p = p.resolve()

    if not p.exists():
        raise HTTPException(status_code=400, detail="Path does not exist")
    if not p.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    name = p.name
    # Add or get existing project
    existing = next((pr for pr in store.list_projects() if pr.path == str(p)), None)
    if existing:
        store.set_current(existing.id)
        return {"path": str(p), "name": name, "project_id": existing.id}
    project = store.add_project(name, str(p))
    store.set_current(project.id)
    return {"path": str(p), "name": name, "project_id": project.id}


@router.post("/create")
@limiter.limit("20/minute")
async def create_workspace(request: Request, body: WorkspaceCreate):
    """Create project folder if missing, then set as current workspace (Cursor-like: new project)."""
    store = get_store()
    raw = body.path.strip()
    raw = os.path.expanduser(raw)
    p = Path(raw)
    if not p.is_absolute():
        p = Path.cwd() / p
    p = p.resolve()

    _ensure_path_allowed(p)

    if p.exists():
        if not p.is_dir():
            raise HTTPException(status_code=400, detail="Path exists and is not a directory")
    else:
        try:
            p.mkdir(parents=True, exist_ok=False)
        except OSError as e:
            raise HTTPException(status_code=400, detail=f"Cannot create directory: {e}") from e

    name = (body.name or "").strip() or p.name
    existing = next((pr for pr in store.list_projects() if pr.path == str(p)), None)
    if existing:
        store.set_current(existing.id)
        return {"path": str(p), "name": name, "project_id": existing.id}
    project = store.add_project(name, str(p))
    store.set_current(project.id)
    return {"path": str(p), "name": name, "project_id": project.id}


@router.post("/index")
@limiter.limit("5/minute")
async def index_workspace(
    request: Request,
    incremental: bool = True,
    rag: ChromaDBRAGAdapter = Depends(get_rag_adapter),
):
    """Index current workspace for RAG search.

    incremental: If True (default), only index new/changed files. If False, full reindex.
    """
    store = get_store()
    current = store.get_current()
    path = current.path if current else str(Path.cwd().resolve())
    project_id = current.id if current else None

    original_cwd = os.getcwd()
    try:
        os.chdir(path)
        stats = await rag.index_path(".", incremental=incremental)

        if current:
            from datetime import datetime
            store.update_project(
                current.id,
                indexed=True,
                files_count=stats.get("files_found", 0),
                last_indexed=datetime.now().isoformat(),
            )

        return {
            "status": "ok",
            "project": project_id,
            "stats": stats,
        }
    finally:
        os.chdir(original_cwd)


@router.post("/index/stream")
@limiter.limit("5/minute")
async def index_workspace_stream(
    request: Request,
    incremental: bool = True,
    rag: ChromaDBRAGAdapter = Depends(get_rag_adapter),
):
    """Index current workspace for RAG search, stream progress via SSE.

    incremental: If True (default), only index new/changed files. If False, full reindex.
    """
    store = get_store()
    current = store.get_current()
    path = current.path if current else str(Path.cwd().resolve())
    project_id = current.id if current else None

    async def event_generator():
        queue: asyncio.Queue[dict | None] = asyncio.Queue()

        async def on_progress(batch_num: int, total_batches: int) -> None:
            pct = round(batch_num / total_batches * 100) if total_batches else 0
            await queue.put({
                "event": "progress",
                "data": json.dumps({"progress": pct, "batch": batch_num, "total": total_batches}),
            })

        async def run_index() -> None:
            original_cwd = os.getcwd()
            try:
                os.chdir(path)
                await queue.put({
                    "event": "progress",
                    "data": json.dumps({"progress": 0, "batch": 0, "total": 1}),
                })
                stats = await rag.index_path(
                    ".",
                    incremental=incremental,
                    on_progress=on_progress,
                )

                if current:
                    from datetime import datetime
                    store.update_project(
                        current.id,
                        indexed=True,
                        files_count=stats.get("files_found", 0),
                        last_indexed=datetime.now().isoformat(),
                    )

                await queue.put({
                    "event": "done",
                    "data": json.dumps({"status": "ok", "project": project_id, "stats": stats}),
                })
            except Exception as e:
                await queue.put({
                    "event": "error",
                    "data": json.dumps({"detail": str(e)}),
                })
            finally:
                os.chdir(original_cwd)
                await queue.put(None)

        asyncio.create_task(run_index())

        while True:
            msg = await queue.get()
            if msg is None:
                break
            yield msg

    return EventSourceResponse(event_generator())
