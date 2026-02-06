"""Files API routes - uses FileService."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.api.dependencies import get_file_service, limiter
from src.infrastructure.services.file_service import FileService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["files"])


class ReadRequest(BaseModel):
    """Read file request."""

    path: str = Field(..., min_length=1, max_length=1024)


class WriteRequest(BaseModel):
    """Write file request."""

    path: str = Field(..., min_length=1, max_length=1024)
    content: str = Field(..., max_length=10_000_000)  # 10 MB limit


class CreateRequest(BaseModel):
    """Create file/directory request."""

    path: str = Field(..., min_length=1, max_length=1024)
    is_directory: bool = False
    content: str = Field("", max_length=10_000_000)


class DeleteRequest(BaseModel):
    """Delete request."""

    path: str = Field(..., min_length=1, max_length=1024)
    backup: bool = True


class RenameRequest(BaseModel):
    """Rename request."""

    old_path: str = Field(..., min_length=1, max_length=1024)
    new_path: str = Field(..., min_length=1, max_length=1024)


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
async def browse_dirs(request: Request, path: str = "") -> dict:
    """List directories for folder picker. path='' returns roots."""
    if not path:
        return {"dirs": _get_browse_roots(), "parent": None}

    p = Path(path)
    if not p.is_absolute():
        p = Path.cwd() / p
    p = p.resolve()

    home = Path.home()
    if not str(p).startswith(str(home)) and p != Path.cwd():
        raise HTTPException(status_code=403, detail="Access denied")

    if not p.exists() or not p.is_dir():
        raise HTTPException(status_code=404, detail="Path not found")

    dirs = []
    try:
        for child in sorted(p.iterdir()):
            if child.is_dir() and not child.name.startswith("."):
                dirs.append({"path": str(child), "name": child.name})
    except PermissionError:
        logger.warning("Permission denied browsing %s", p)

    parent = str(p.parent) if p.parent != p else None
    return {"dirs": dirs, "parent": parent}


@router.get("/tree")
@limiter.limit("60/minute")
async def get_tree(
    request: Request,
    path: str | None = None,
    depth: int = 10,
    service: FileService = Depends(get_file_service),
) -> dict:
    """Get file tree."""
    try:
        result = service.get_tree(path, depth)
    except Exception:
        logger.exception("Failed to get file tree for path=%s", path)
        raise HTTPException(status_code=500, detail="Failed to get file tree")

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error or "Failed to get file tree")

    def node_to_dict(node):
        return {
            "name": node.name,
            "path": node.path,
            "type": "directory" if node.is_dir else "file",
            "size": node.size,
            "extension": node.path.split(".")[-1] if "." in node.path and not node.is_dir else None,
            "children": [node_to_dict(c) for c in node.children] if node.children else None,
        }

    return {
        "success": True,
        "tree": node_to_dict(result.data["tree"]),
    }


@router.post("/read")
@limiter.limit("120/minute")
async def read_file(
    request: Request,
    body: ReadRequest,
    service: FileService = Depends(get_file_service),
) -> dict:
    """Read file content."""
    try:
        result = service.read(body.path)
    except Exception:
        logger.exception("Failed to read file %s", body.path)
        raise HTTPException(status_code=500, detail="Failed to read file")

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error or "Failed to read file")

    return {
        "success": True,
        "content": result.data["content"],
        "size": result.data["size"],
    }


@router.post("/write")
@limiter.limit("60/minute")
async def write_file(
    request: Request,
    body: WriteRequest,
    service: FileService = Depends(get_file_service),
) -> dict:
    """Write file content."""
    try:
        result = service.write(body.path, body.content)
    except Exception:
        logger.exception("Failed to write file %s", body.path)
        raise HTTPException(status_code=500, detail="Failed to write file")

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error or "Failed to write file")

    return {"success": True, "path": result.data["path"]}


@router.post("/create")
@limiter.limit("60/minute")
async def create_file(
    request: Request,
    body: CreateRequest,
    service: FileService = Depends(get_file_service),
) -> dict:
    """Create file or directory."""
    try:
        result = service.create(body.path, body.is_directory, body.content)
    except Exception:
        logger.exception("Failed to create %s", body.path)
        raise HTTPException(status_code=500, detail="Failed to create file/directory")

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error or "Failed to create")

    return {"success": True, "path": result.data["path"]}


@router.delete("/delete")
@limiter.limit("30/minute")
async def delete_file(
    request: Request,
    path: str,
    backup: bool = True,
    service: FileService = Depends(get_file_service),
) -> dict:
    """Delete file or directory."""
    try:
        result = service.delete(path, backup)
    except Exception:
        logger.exception("Failed to delete %s", path)
        raise HTTPException(status_code=500, detail="Failed to delete")

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error or "Failed to delete")

    return {"success": True, "deleted": result.data["deleted"]}


@router.post("/rename")
@limiter.limit("30/minute")
async def rename_file(
    request: Request,
    body: RenameRequest,
    service: FileService = Depends(get_file_service),
) -> dict:
    """Rename or move file/directory."""
    try:
        result = service.rename(body.old_path, body.new_path)
    except Exception:
        logger.exception("Failed to rename %s -> %s", body.old_path, body.new_path)
        raise HTTPException(status_code=500, detail="Failed to rename")

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error or "Failed to rename")

    return {
        "success": True,
        "old": result.data["old"],
        "new": result.data["new"],
    }
