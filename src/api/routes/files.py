"""Files API routes - uses FileService."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.api.dependencies import limiter
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
    """Get FileService instance."""
    return FileService()


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
            "is_dir": node.is_dir,
            "size": node.size,
            "children": [node_to_dict(c) for c in node.children],
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
