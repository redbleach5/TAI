"""Files API - read/write files with backup support."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.api.dependencies import limiter
from src.infrastructure.agents.file_writer import FileWriter

router = APIRouter(prefix="/files", tags=["files"])

# Singleton file writer
_file_writer: FileWriter | None = None


def get_file_writer() -> FileWriter:
    """Get or create FileWriter instance."""
    global _file_writer
    if _file_writer is None:
        _file_writer = FileWriter()
    return _file_writer


# --- Request/Response Models ---


class WriteRequest(BaseModel):
    """Request to write file."""
    path: str
    content: str
    create_backup: bool = True


class WriteResponse(BaseModel):
    """Response from file write."""
    success: bool
    path: str
    backup_path: str | None = None
    created: bool = False
    error: str | None = None


class ReadResponse(BaseModel):
    """Response from file read."""
    success: bool
    path: str
    content: str | None = None
    error: str | None = None


class RestoreRequest(BaseModel):
    """Request to restore from backup."""
    backup_path: str
    original_path: str


class CreateRequest(BaseModel):
    """Request to create file or directory."""
    path: str
    is_directory: bool = False


class CreateResponse(BaseModel):
    """Response from create operation."""
    success: bool
    path: str
    type: Literal["file", "directory"]
    error: str | None = None


class DeleteResponse(BaseModel):
    """Response from delete operation."""
    success: bool
    path: str
    backup_path: str | None = None
    error: str | None = None


class RenameRequest(BaseModel):
    """Request to rename/move file."""
    old_path: str
    new_path: str


class RenameResponse(BaseModel):
    """Response from rename operation."""
    success: bool
    old_path: str
    new_path: str
    error: str | None = None


class FileNode(BaseModel):
    """File tree node."""
    name: str
    path: str
    type: Literal["file", "directory"]
    children: list["FileNode"] | None = None
    size: int | None = None
    extension: str | None = None


class TreeResponse(BaseModel):
    """Response from tree operation."""
    success: bool
    tree: FileNode | None = None
    error: str | None = None


@router.post("/write")
@limiter.limit("30/minute")
async def write_file(
    request: Request,
    body: WriteRequest,
    writer: FileWriter = Depends(get_file_writer),
) -> WriteResponse:
    """Write content to file with backup.
    
    Security: Only allows writing within project directory.
    """
    result = writer.write_file(
        path=body.path,
        content=body.content,
        create_backup=body.create_backup,
    )
    return WriteResponse(**result)


@router.get("/read")
@limiter.limit("60/minute")
async def read_file(
    request: Request,
    path: str,
    writer: FileWriter = Depends(get_file_writer),
) -> ReadResponse:
    """Read file content."""
    result = writer.read_file(path)
    return ReadResponse(**result)


@router.post("/restore")
@limiter.limit("10/minute")
async def restore_backup(
    request: Request,
    body: RestoreRequest,
    writer: FileWriter = Depends(get_file_writer),
):
    """Restore file from backup."""
    result = writer.restore_backup(body.backup_path, body.original_path)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/backups")
@limiter.limit("30/minute")
async def list_backups(
    request: Request,
    filename: str | None = None,
    writer: FileWriter = Depends(get_file_writer),
):
    """List available backups."""
    return {"backups": writer.list_backups(filename)}


@router.get("/tree")
@limiter.limit("30/minute")
async def get_file_tree(
    request: Request,
    path: str = ".",
    max_depth: int = 10,
    writer: FileWriter = Depends(get_file_writer),
) -> TreeResponse:
    """Get file tree structure.
    
    Returns hierarchical view of project files.
    Excludes: __pycache__, .git, node_modules, .venv, etc.
    """
    result = writer.get_file_tree(path, max_depth)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return TreeResponse(**result)


@router.post("/create")
@limiter.limit("20/minute")
async def create_file(
    request: Request,
    body: CreateRequest,
    writer: FileWriter = Depends(get_file_writer),
) -> CreateResponse:
    """Create a new file or directory.
    
    Security: Only allows creation within project directory.
    """
    result = writer.create_file(body.path, body.is_directory)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return CreateResponse(**result)


@router.delete("/delete")
@limiter.limit("10/minute")
async def delete_file(
    request: Request,
    path: str,
    create_backup: bool = True,
    writer: FileWriter = Depends(get_file_writer),
) -> DeleteResponse:
    """Delete a file or directory.
    
    Creates backup for files by default.
    Security: Only allows deletion within project directory.
    """
    result = writer.delete_file(path, create_backup)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return DeleteResponse(**result)


@router.post("/rename")
@limiter.limit("20/minute")
async def rename_file(
    request: Request,
    body: RenameRequest,
    writer: FileWriter = Depends(get_file_writer),
) -> RenameResponse:
    """Rename or move a file/directory.
    
    Security: Only allows operations within project directory.
    """
    result = writer.rename_file(body.old_path, body.new_path)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return RenameResponse(**result)
