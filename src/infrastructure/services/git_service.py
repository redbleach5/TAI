"""Git Service - handles Git operations."""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GitStatus:
    """Git repository status."""
    branch: str
    files: list[dict] = field(default_factory=list)
    ahead: int = 0
    behind: int = 0


@dataclass
class GitCommit:
    """Git commit info."""
    hash: str
    message: str
    author: str
    date: str


@dataclass
class GitResult:
    """Result of Git operation."""
    success: bool
    data: dict | None = None
    error: str | None = None


class GitService:
    """Service for Git operations."""
    
    def __init__(self, cwd: str | None = None):
        """Initialize with working directory."""
        self._cwd = cwd or str(Path.cwd())
    
    async def _run(self, args: list[str]) -> tuple[int, str, str]:
        """Run git command and return (code, stdout, stderr)."""
        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            cwd=self._cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return (
            proc.returncode or 0,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )
    
    async def is_repo(self) -> bool:
        """Check if current directory is a Git repo."""
        code, _, _ = await self._run(["rev-parse", "--git-dir"])
        return code == 0
    
    async def status(self) -> GitResult:
        """Get repository status."""
        # Get current branch
        code, branch, _ = await self._run(["rev-parse", "--abbrev-ref", "HEAD"])
        if code != 0:
            return GitResult(success=False, error="Not a Git repository")
        branch = branch.strip()
        
        # Get status
        code, out, _ = await self._run(["status", "--porcelain"])
        files = []
        for line in out.strip().split("\n"):
            if line:
                status = line[:2].strip()
                filepath = line[3:]
                files.append({"status": status, "path": filepath})
        
        # Get ahead/behind
        ahead, behind = 0, 0
        code, out, _ = await self._run([
            "rev-list", "--left-right", "--count", f"{branch}...@{{u}}"
        ])
        if code == 0:
            parts = out.strip().split()
            if len(parts) == 2:
                ahead, behind = int(parts[0]), int(parts[1])
        
        return GitResult(
            success=True,
            data={
                "branch": branch,
                "files": files,
                "ahead": ahead,
                "behind": behind,
            },
        )
    
    async def diff(self, path: str | None = None) -> GitResult:
        """Get diff for file or all changes."""
        args = ["diff"]
        if path:
            args.append(path)
        
        code, out, err = await self._run(args)
        if code != 0:
            return GitResult(success=False, error=err)
        
        return GitResult(success=True, data={"diff": out})
    
    async def log(self, limit: int = 20) -> GitResult:
        """Get commit log."""
        code, out, err = await self._run([
            "log",
            f"-{limit}",
            "--pretty=format:%H|%s|%an|%ad",
            "--date=iso",
        ])
        if code != 0:
            return GitResult(success=False, error=err)
        
        entries = []
        for line in out.strip().split("\n"):
            if line:
                parts = line.split("|", 3)
                if len(parts) == 4:
                    entries.append(GitCommit(
                        hash=parts[0],
                        message=parts[1],
                        author=parts[2],
                        date=parts[3],
                    ))
        
        return GitResult(success=True, data={"entries": entries})
    
    async def commit(
        self,
        message: str,
        files: list[str] | None = None,
    ) -> GitResult:
        """Create a commit."""
        if not message.strip():
            return GitResult(success=False, error="Commit message required")
        
        # Stage files
        if files:
            for f in files:
                await self._run(["add", f])
        else:
            await self._run(["add", "-A"])
        
        # Commit
        code, out, err = await self._run(["commit", "-m", message])
        if code != 0:
            if "nothing to commit" in err or "nothing to commit" in out:
                return GitResult(success=False, error="Nothing to commit")
            return GitResult(success=False, error=err)
        
        return GitResult(success=True, data={"message": message})
    
    async def branches(self) -> GitResult:
        """List branches."""
        code, out, err = await self._run(["branch", "--list"])
        if code != 0:
            return GitResult(success=False, error=err)
        
        branches = []
        current = None
        for line in out.strip().split("\n"):
            if line:
                is_current = line.startswith("*")
                name = line.lstrip("* ").strip()
                if is_current:
                    current = name
                branches.append(name)
        
        return GitResult(
            success=True,
            data={"branches": branches, "current": current},
        )
    
    async def checkout(
        self,
        branch: str,
        create: bool = False,
    ) -> GitResult:
        """Checkout branch."""
        args = ["checkout"]
        if create:
            args.append("-b")
        args.append(branch)
        
        code, _, err = await self._run(args)
        if code != 0:
            return GitResult(success=False, error=err)
        
        return GitResult(success=True, data={"branch": branch})
