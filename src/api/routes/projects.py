"""Projects API - manage multiple project contexts."""

import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.api.dependencies import get_rag_adapter, limiter
from src.infrastructure.rag.chromadb_adapter import ChromaDBRAGAdapter

router = APIRouter(prefix="/projects", tags=["projects"])

# Store project configurations
PROJECTS_FILE = Path("output/projects.json")


class Project(BaseModel):
    """Project configuration."""
    id: str
    name: str
    path: str
    indexed: bool = False
    files_count: int = 0
    last_indexed: str | None = None


class ProjectCreate(BaseModel):
    """Request to add a project."""
    name: str
    path: str


class ProjectsStore:
    """Simple file-based project store."""
    
    def __init__(self):
        self._projects: dict[str, Project] = {}
        self._current_project: str | None = None
        self._load()
    
    def _load(self):
        if PROJECTS_FILE.exists():
            try:
                data = json.loads(PROJECTS_FILE.read_text())
                for p_data in data.get("projects", []):
                    proj = Project(**p_data)
                    self._projects[proj.id] = proj
                self._current_project = data.get("current")
            except Exception:
                pass
    
    def _save(self):
        PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "projects": [p.model_dump() for p in self._projects.values()],
            "current": self._current_project,
        }
        PROJECTS_FILE.write_text(json.dumps(data, indent=2))
    
    def list_projects(self) -> list[Project]:
        return list(self._projects.values())
    
    def get_project(self, project_id: str) -> Project | None:
        return self._projects.get(project_id)
    
    def add_project(self, name: str, path: str) -> Project:
        # Validate path exists
        p = Path(path)
        if not p.is_absolute():
            p = Path.cwd() / p
        p = p.resolve()
        
        if not p.exists():
            raise ValueError(f"Path does not exist: {p}")
        if not p.is_dir():
            raise ValueError(f"Path is not a directory: {p}")
        
        # Generate ID
        project_id = name.lower().replace(" ", "-")
        counter = 1
        while project_id in self._projects:
            project_id = f"{name.lower().replace(' ', '-')}-{counter}"
            counter += 1
        
        project = Project(
            id=project_id,
            name=name,
            path=str(p),
        )
        self._projects[project_id] = project
        self._save()
        return project
    
    def remove_project(self, project_id: str) -> bool:
        if project_id in self._projects:
            del self._projects[project_id]
            if self._current_project == project_id:
                self._current_project = None
            self._save()
            return True
        return False
    
    def set_current(self, project_id: str) -> bool:
        if project_id in self._projects:
            self._current_project = project_id
            self._save()
            return True
        return False
    
    def get_current(self) -> Project | None:
        if self._current_project:
            return self._projects.get(self._current_project)
        return None
    
    def update_project(self, project_id: str, **kwargs) -> Project | None:
        if project_id in self._projects:
            proj = self._projects[project_id]
            for k, v in kwargs.items():
                if hasattr(proj, k):
                    setattr(proj, k, v)
            self._save()
            return proj
        return None


# Singleton store
_store: ProjectsStore | None = None


def get_store() -> ProjectsStore:
    global _store
    if _store is None:
        _store = ProjectsStore()
    return _store


@router.get("")
@limiter.limit("60/minute")
async def list_projects(request: Request):
    """List all registered projects."""
    store = get_store()
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
):
    """Add a new project."""
    store = get_store()
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
):
    """Remove a project."""
    store = get_store()
    if store.remove_project(project_id):
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Project not found")


@router.post("/{project_id}/select")
@limiter.limit("30/minute")
async def select_project(
    request: Request,
    project_id: str,
):
    """Select a project as current."""
    store = get_store()
    if store.set_current(project_id):
        project = store.get_project(project_id)
        return {"status": "ok", "project": project.model_dump() if project else None}
    raise HTTPException(status_code=404, detail="Project not found")


@router.post("/{project_id}/index")
@limiter.limit("5/minute")
async def index_project(
    request: Request,
    project_id: str,
    rag: ChromaDBRAGAdapter = Depends(get_rag_adapter),
):
    """Index a project for RAG search."""
    store = get_store()
    project = store.get_project(project_id)
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Clear existing index and reindex
    rag.clear()
    
    # Change to project directory temporarily
    original_cwd = os.getcwd()
    try:
        os.chdir(project.path)
        stats = await rag.index_path(".")
        
        # Update project info
        from datetime import datetime
        store.update_project(
            project_id,
            indexed=True,
            files_count=stats.get("files_found", 0),
            last_indexed=datetime.now().isoformat(),
        )
        
        # Set as current
        store.set_current(project_id)
        
        return {
            "status": "ok",
            "project": project_id,
            "stats": stats,
        }
    finally:
        os.chdir(original_cwd)


@router.get("/current")
@limiter.limit("60/minute")
async def get_current_project(request: Request):
    """Get currently selected project."""
    store = get_store()
    current = store.get_current()
    if current:
        return {"project": current.model_dump()}
    return {"project": None}
