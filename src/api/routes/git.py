"""Git API routes - uses GitService."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.api.dependencies import limiter
from src.infrastructure.services.git_service import GitService

router = APIRouter(prefix="/git", tags=["git"])


class CommitRequest(BaseModel):
    """Commit request."""
    message: str
    files: list[str] | None = None


class CheckoutRequest(BaseModel):
    """Checkout request."""
    branch: str
    create: bool = False


def _get_service() -> GitService:
    """Get GitService instance."""
    return GitService()


@router.get("/status")
@limiter.limit("120/minute")
async def git_status(request: Request):
    """Get Git status."""
    service = _get_service()
    result = await service.status()
    
    if not result.success:
        return {"success": False, "error": result.error}
    
    return {
        "success": True,
        "branch": result.data["branch"],
        "files": result.data["files"],
        "ahead": result.data["ahead"],
        "behind": result.data["behind"],
    }


@router.get("/diff")
@limiter.limit("60/minute")
async def git_diff(request: Request, path: str | None = None):
    """Get Git diff."""
    service = _get_service()
    result = await service.diff(path)
    
    if not result.success:
        return {"success": False, "error": result.error}
    
    return {"success": True, "diff": result.data["diff"]}


@router.get("/log")
@limiter.limit("60/minute")
async def git_log(request: Request, limit: int = 20):
    """Get commit log."""
    service = _get_service()
    result = await service.log(limit)
    
    if not result.success:
        return {"success": False, "error": result.error}
    
    entries = [
        {
            "hash": c.hash,
            "message": c.message,
            "author": c.author,
            "date": c.date,
        }
        for c in result.data["entries"]
    ]
    
    return {"success": True, "entries": entries}


@router.post("/commit")
@limiter.limit("30/minute")
async def git_commit(request: Request, body: CommitRequest):
    """Create a commit."""
    service = _get_service()
    result = await service.commit(body.message, body.files)
    
    if not result.success:
        return {"success": False, "error": result.error}
    
    return {"success": True, "message": result.data["message"]}


@router.get("/branches")
@limiter.limit("60/minute")
async def git_branches(request: Request):
    """List branches."""
    service = _get_service()
    result = await service.branches()
    
    if not result.success:
        return {"success": False, "error": result.error}
    
    return {
        "success": True,
        "branches": result.data["branches"],
        "current": result.data["current"],
    }


@router.post("/checkout")
@limiter.limit("30/minute")
async def git_checkout(request: Request, body: CheckoutRequest):
    """Checkout branch."""
    service = _get_service()
    result = await service.checkout(body.branch, body.create)
    
    if not result.success:
        return {"success": False, "error": result.error}
    
    return {"success": True, "branch": result.data["branch"]}
