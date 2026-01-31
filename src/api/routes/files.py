"""Files API routes - uses FileService."""

from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.api.dependencies import limiter
from src.api.routes.workspace import _get_workspace_path
from src.infrastructure.services.file_service import FileService

router = APIRouter(prefix="/files", tags=["files"])


class ReadRequest(BaseModel):
    """Read file request."""
    path: str


class WriteRequest(BaseModel):
    """Write file request."""
    path: str
    content: str


class CreateRequest(BaseModel):
    """Create file/directory request."""
    path: str
    is_directory: bool = False
    content: str = ""


class DeleteRequest(BaseModel):
    """Delete request."""
    path: str
    backup: bool = True


class RenameRequest(BaseModel):
    """Rename request."""
    old_path: str
    new_path: str


def _get_service() -> FileService:
    """Get FileService instance with workspace root."""
    root = _get_workspace_path()
    return FileService(root_path=root)


def _get_browse_roots() -> list[dict]:
    """Get roots for folder picker (home, cwd)."""
    roots = []
    home = Path.home()
    cwd = Path.cwd().resolve()
    roots.append({"path": str(home), "name": "Home"})
    if cwd != home:
        roots.append({"path": str(cwd), "name": cwd.name})
    return roots


@router.get("/browse")
async def browse_dirs(request: Request, path: str = ""):
    """List directories for folder picker. path='' returns roots."""
    if not path:
        return {"dirs": _get_browse_roots(), "parent": None}

    p = Path(path)
    if not p.is_absolute():
        p = Path.cwd() / p
    p = p.resolve()

    home = Path.home()
    if not str(p).startswith(str(home)) and p != Path.cwd():
        return {"dirs": [], "parent": None, "error": "Access denied"}

    if not p.exists() or not p.is_dir():
        return {"dirs": [], "parent": None, "error": "Path not found"}

    dirs = []
    try:
        for child in sorted(p.iterdir()):
            if child.is_dir() and not child.name.startswith("."):
                dirs.append({"path": str(child), "name": child.name})
    except PermissionError:
        pass

    parent = str(p.parent) if p.parent != p else None
    return {"dirs": dirs, "parent": parent}


@router.get("/tree")
@limiter.limit("60/minute")
async def get_tree(
    request: Request,
    path: str | None = None,
    depth: int = 10,
):
    """Get file tree."""
    service = _get_service()
    result = service.get_tree(path, depth)
    
    if not result.success:
        return {"success": False, "error": result.error}
    
    def node_to_dict(node):
        return {
            "name": node.name,
            "path": node.path,
            "type": "directory" if node.is_dir else "file",
            "size": node.size,
            "extension": node.path.split('.')[-1] if '.' in node.path and not node.is_dir else None,
            "children": [node_to_dict(c) for c in node.children] if node.children else None,
        }
    
    return {
        "success": True,
        "tree": node_to_dict(result.data["tree"]),
    }


@router.post("/read")
@limiter.limit("120/minute")
async def read_file(request: Request, body: ReadRequest):
    """Read file content."""
    service = _get_service()
    result = service.read(body.path)
    
    if not result.success:
        return {"success": False, "error": result.error}
    
    return {
        "success": True,
        "content": result.data["content"],
        "size": result.data["size"],
    }


@router.post("/write")
@limiter.limit("60/minute")
async def write_file(request: Request, body: WriteRequest):
    """Write file content."""
    service = _get_service()
    result = service.write(body.path, body.content)
    
    if not result.success:
        return {"success": False, "error": result.error}
    
    return {"success": True, "path": result.data["path"]}


@router.post("/create")
@limiter.limit("60/minute")
async def create_file(request: Request, body: CreateRequest):
    """Create file or directory."""
    service = _get_service()
    result = service.create(body.path, body.is_directory, body.content)
    
    if not result.success:
        return {"success": False, "error": result.error}
    
    return {"success": True, "path": result.data["path"]}


@router.delete("/delete")
@limiter.limit("30/minute")
async def delete_file(request: Request, path: str, backup: bool = True):
    """Delete file or directory."""
    service = _get_service()
    result = service.delete(path, backup)
    
    if not result.success:
        return {"success": False, "error": result.error}
    
    return {"success": True, "deleted": result.data["deleted"]}


@router.post("/rename")
@limiter.limit("30/minute")
async def rename_file(request: Request, body: RenameRequest):
    """Rename or move file/directory."""
    service = _get_service()
    result = service.rename(body.old_path, body.new_path)
    
    if not result.success:
        return {"success": False, "error": result.error}
    
    return {
        "success": True,
        "old": result.data["old"],
        "new": result.data["new"],
    }
