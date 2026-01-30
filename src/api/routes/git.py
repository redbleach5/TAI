"""Git API - repository status, diff, log, and commit operations."""

import asyncio
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.api.dependencies import limiter

router = APIRouter(prefix="/git", tags=["git"])


class GitStatus(BaseModel):
    """Git file status."""
    path: str
    status: str  # M, A, D, ?, U, etc.
    staged: bool


class StatusResponse(BaseModel):
    """Git status response."""
    success: bool
    branch: str | None = None
    files: list[GitStatus] = []
    ahead: int = 0
    behind: int = 0
    error: str | None = None


class DiffResponse(BaseModel):
    """Git diff response."""
    success: bool
    path: str | None = None
    diff: str = ""
    error: str | None = None


class LogEntry(BaseModel):
    """Git log entry."""
    hash: str
    short_hash: str
    author: str
    date: str
    message: str


class LogResponse(BaseModel):
    """Git log response."""
    success: bool
    entries: list[LogEntry] = []
    error: str | None = None


class CommitRequest(BaseModel):
    """Request to create commit."""
    message: str
    files: list[str] | None = None  # None = commit all staged


class CommitResponse(BaseModel):
    """Commit response."""
    success: bool
    hash: str | None = None
    message: str = ""
    error: str | None = None


class BranchResponse(BaseModel):
    """Branch list response."""
    success: bool
    current: str | None = None
    branches: list[str] = []
    error: str | None = None


class CheckoutRequest(BaseModel):
    """Request to checkout branch."""
    branch: str
    create: bool = False


async def _run_git(args: list[str], cwd: str | None = None) -> tuple[bool, str, str]:
    """Run git command and return (success, stdout, stderr)."""
    work_dir = cwd or os.getcwd()
    
    try:
        process = await asyncio.create_subprocess_exec(
            "git", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=work_dir,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
        success = process.returncode == 0
        return success, stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")
    except asyncio.TimeoutError:
        return False, "", "Git command timed out"
    except FileNotFoundError:
        return False, "", "Git not found"
    except Exception as e:
        return False, "", str(e)


def _parse_status_line(line: str) -> GitStatus | None:
    """Parse git status --porcelain line."""
    if len(line) < 3:
        return None
    
    index_status = line[0]
    worktree_status = line[1]
    path = line[3:].strip()
    
    # Remove quotes if present
    if path.startswith('"') and path.endswith('"'):
        path = path[1:-1]
    
    # Determine overall status
    if index_status == "?" and worktree_status == "?":
        status = "?"  # Untracked
    elif index_status == "A":
        status = "A"  # Added
    elif index_status == "D" or worktree_status == "D":
        status = "D"  # Deleted
    elif index_status == "M" or worktree_status == "M":
        status = "M"  # Modified
    elif index_status == "R":
        status = "R"  # Renamed
    elif index_status == "U" or worktree_status == "U":
        status = "U"  # Unmerged
    else:
        status = index_status or worktree_status
    
    staged = index_status not in (" ", "?")
    
    return GitStatus(path=path, status=status, staged=staged)


@router.get("/status")
@limiter.limit("60/minute")
async def get_status(request: Request) -> StatusResponse:
    """Get git repository status.
    
    Returns current branch, changed files, and ahead/behind counts.
    """
    # Check if git repo exists
    if not Path(".git").exists():
        return StatusResponse(
            success=False,
            error="Not a git repository",
        )
    
    # Get branch name
    success, branch, _ = await _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    branch = branch.strip() if success else None
    
    # Get status
    success, stdout, stderr = await _run_git(["status", "--porcelain"])
    if not success:
        return StatusResponse(success=False, branch=branch, error=stderr)
    
    files = []
    for line in stdout.splitlines():
        status = _parse_status_line(line)
        if status:
            files.append(status)
    
    # Get ahead/behind
    ahead, behind = 0, 0
    if branch and branch != "HEAD":
        success, stdout, _ = await _run_git([
            "rev-list", "--left-right", "--count",
            f"{branch}...origin/{branch}"
        ])
        if success:
            parts = stdout.strip().split()
            if len(parts) == 2:
                ahead, behind = int(parts[0]), int(parts[1])
    
    return StatusResponse(
        success=True,
        branch=branch,
        files=files,
        ahead=ahead,
        behind=behind,
    )


@router.get("/diff")
@limiter.limit("30/minute")
async def get_diff(
    request: Request,
    path: str | None = None,
    staged: bool = False,
) -> DiffResponse:
    """Get git diff for a file or all changes.
    
    Args:
        path: Specific file path (optional)
        staged: If True, show staged changes (--cached)
    """
    args = ["diff"]
    if staged:
        args.append("--cached")
    if path:
        args.append("--")
        args.append(path)
    
    success, stdout, stderr = await _run_git(args)
    
    if not success:
        return DiffResponse(success=False, path=path, error=stderr)
    
    return DiffResponse(success=True, path=path, diff=stdout)


@router.get("/log")
@limiter.limit("30/minute")
async def get_log(
    request: Request,
    limit: int = 20,
    path: str | None = None,
) -> LogResponse:
    """Get git log entries.
    
    Args:
        limit: Max number of entries (default 20)
        path: Filter by file path (optional)
    """
    limit = min(limit, 100)  # Cap at 100
    
    # Format: hash|short_hash|author|date|message
    format_str = "%H|%h|%an|%ci|%s"
    args = ["log", f"--pretty=format:{format_str}", f"-{limit}"]
    
    if path:
        args.extend(["--", path])
    
    success, stdout, stderr = await _run_git(args)
    
    if not success:
        return LogResponse(success=False, error=stderr)
    
    entries = []
    for line in stdout.splitlines():
        parts = line.split("|", 4)
        if len(parts) == 5:
            entries.append(LogEntry(
                hash=parts[0],
                short_hash=parts[1],
                author=parts[2],
                date=parts[3],
                message=parts[4],
            ))
    
    return LogResponse(success=True, entries=entries)


@router.post("/commit")
@limiter.limit("10/minute")
async def create_commit(
    request: Request,
    body: CommitRequest,
) -> CommitResponse:
    """Create a git commit.
    
    Args:
        message: Commit message
        files: Specific files to stage (optional, defaults to all)
    """
    if not body.message.strip():
        return CommitResponse(success=False, error="Commit message is required")
    
    # Stage files
    if body.files:
        for file in body.files:
            success, _, stderr = await _run_git(["add", file])
            if not success:
                return CommitResponse(success=False, error=f"Failed to stage {file}: {stderr}")
    else:
        # Stage all changes
        success, _, stderr = await _run_git(["add", "-A"])
        if not success:
            return CommitResponse(success=False, error=f"Failed to stage: {stderr}")
    
    # Commit
    success, stdout, stderr = await _run_git(["commit", "-m", body.message])
    
    if not success:
        if "nothing to commit" in stderr.lower() or "nothing to commit" in stdout.lower():
            return CommitResponse(success=False, error="Nothing to commit")
        return CommitResponse(success=False, error=stderr or stdout)
    
    # Get commit hash
    success, hash_out, _ = await _run_git(["rev-parse", "HEAD"])
    commit_hash = hash_out.strip()[:8] if success else None
    
    return CommitResponse(
        success=True,
        hash=commit_hash,
        message=body.message,
    )


@router.get("/branches")
@limiter.limit("30/minute")
async def get_branches(request: Request) -> BranchResponse:
    """Get list of git branches."""
    # Get current branch
    success, current, _ = await _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    current = current.strip() if success else None
    
    # Get all branches
    success, stdout, stderr = await _run_git(["branch", "--list"])
    
    if not success:
        return BranchResponse(success=False, current=current, error=stderr)
    
    branches = []
    for line in stdout.splitlines():
        branch = line.strip().lstrip("* ").strip()
        if branch:
            branches.append(branch)
    
    return BranchResponse(success=True, current=current, branches=branches)


@router.post("/checkout")
@limiter.limit("10/minute")
async def checkout_branch(
    request: Request,
    body: CheckoutRequest,
) -> BranchResponse:
    """Checkout or create a git branch.
    
    Args:
        branch: Branch name to checkout
        create: If True, create the branch
    """
    args = ["checkout"]
    if body.create:
        args.append("-b")
    args.append(body.branch)
    
    success, stdout, stderr = await _run_git(args)
    
    if not success:
        return BranchResponse(
            success=False,
            error=stderr or stdout,
        )
    
    # Return updated branch info
    return await get_branches(request)
