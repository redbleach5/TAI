"""Git API routes - uses GitService."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.api.dependencies import get_git_service, limiter
from src.infrastructure.services.git_service import GitService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/git", tags=["git"])


class CommitRequest(BaseModel):
    """Commit request."""

    message: str = Field(..., min_length=1, max_length=2000)
    files: list[str] | None = Field(None, max_length=500)


class CheckoutRequest(BaseModel):
    """Checkout request."""

    branch: str = Field(..., min_length=1, max_length=255)
    create: bool = False


@router.get("/status")
@limiter.limit("120/minute")
async def git_status(
    request: Request,
    service: GitService = Depends(get_git_service),
) -> dict:
    """Get Git status."""
    try:
        result = await service.status()
    except Exception:
        logger.exception("Failed to get git status")
        raise HTTPException(status_code=500, detail="Failed to get git status")

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error or "Failed to get git status")

    return {
        "success": True,
        "branch": result.data["branch"],
        "files": result.data["files"],
        "ahead": result.data["ahead"],
        "behind": result.data["behind"],
    }


@router.get("/diff")
@limiter.limit("60/minute")
async def git_diff(
    request: Request,
    path: str | None = None,
    service: GitService = Depends(get_git_service),
) -> dict:
    """Get Git diff."""
    try:
        result = await service.diff(path)
    except Exception:
        logger.exception("Failed to get git diff")
        raise HTTPException(status_code=500, detail="Failed to get git diff")

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error or "Failed to get git diff")

    return {"success": True, "diff": result.data["diff"]}


@router.get("/log")
@limiter.limit("60/minute")
async def git_log(
    request: Request,
    limit: int = 20,
    service: GitService = Depends(get_git_service),
) -> dict:
    """Get commit log."""
    try:
        result = await service.log(limit)
    except Exception:
        logger.exception("Failed to get git log")
        raise HTTPException(status_code=500, detail="Failed to get git log")

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error or "Failed to get git log")

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
async def git_commit(
    request: Request,
    body: CommitRequest,
    service: GitService = Depends(get_git_service),
) -> dict:
    """Create a commit."""
    try:
        result = await service.commit(body.message, body.files)
    except Exception:
        logger.exception("Failed to create git commit")
        raise HTTPException(status_code=500, detail="Failed to create git commit")

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error or "Failed to create commit")

    return {"success": True, "message": result.data["message"]}


@router.get("/branches")
@limiter.limit("60/minute")
async def git_branches(
    request: Request,
    service: GitService = Depends(get_git_service),
) -> dict:
    """List branches."""
    try:
        result = await service.branches()
    except Exception:
        logger.exception("Failed to list git branches")
        raise HTTPException(status_code=500, detail="Failed to list branches")

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error or "Failed to list branches")

    return {
        "success": True,
        "branches": result.data["branches"],
        "current": result.data["current"],
    }


@router.post("/checkout")
@limiter.limit("30/minute")
async def git_checkout(
    request: Request,
    body: CheckoutRequest,
    service: GitService = Depends(get_git_service),
) -> dict:
    """Checkout branch."""
    try:
        result = await service.checkout(body.branch, body.create)
    except Exception:
        logger.exception("Failed to checkout branch %s", body.branch)
        raise HTTPException(status_code=500, detail="Failed to checkout branch")

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error or "Failed to checkout branch")

    return {"success": True, "branch": result.data["branch"]}
