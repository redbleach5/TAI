"""File Collector - collects code files for RAG indexing."""

import fnmatch
from pathlib import Path


# Supported file extensions for indexing
SUPPORTED_EXTENSIONS = {
    # Python
    ".py",
    # JavaScript/TypeScript
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    # Config/Data
    ".json", ".toml", ".yaml", ".yml",
    # Documentation
    ".md", ".mdx", ".rst", ".txt",
    # Web
    ".html", ".css", ".scss", ".sass",
    # Other
    ".sh", ".bash", ".sql", ".graphql",
}

# Directories to always exclude
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "coverage",
    ".tox",
    "eggs",
    "*.egg-info",
}

# Default gitignore patterns
DEFAULT_IGNORES = [
    "*.pyc",
    "*.pyo",
    "*.egg",
    "*.egg-info",
    ".DS_Store",
    "Thumbs.db",
    "*.log",
    "*.bak",
    "*.swp",
    "*.lock",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
]


def parse_gitignore(path: Path) -> list[str]:
    """Parse .gitignore file and return patterns."""
    gitignore = path / ".gitignore"
    patterns = list(DEFAULT_IGNORES)
    if gitignore.exists():
        try:
            for line in gitignore.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
        except OSError:
            pass
    return patterns


def is_ignored(file_path: Path, base_path: Path, patterns: list[str]) -> bool:
    """Check if file matches any gitignore pattern."""
    try:
        rel_path = str(file_path.relative_to(base_path))
    except ValueError:
        return True
    
    # Check excluded directories
    parts = rel_path.split("/")
    for part in parts[:-1]:  # Check all parent directories
        if part in EXCLUDED_DIRS:
            return True
        for excluded in EXCLUDED_DIRS:
            if "*" in excluded and fnmatch.fnmatch(part, excluded):
                return True
    
    # Check gitignore patterns
    for pattern in patterns:
        # Handle directory patterns (ending with /)
        if pattern.endswith("/"):
            dir_pattern = pattern[:-1]
            for part in parts[:-1]:
                if fnmatch.fnmatch(part, dir_pattern):
                    return True
        # Handle file patterns
        elif fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(parts[-1], pattern):
            return True
    
    return False


def collect_code_files(
    path: Path,
    max_file_size: int = 500 * 1024,
) -> list[tuple[str, str]]:
    """Collect (relative_path, content) for all supported code files.
    
    Args:
        path: Directory to scan
        max_file_size: Maximum file size in bytes (default 500KB)
    
    Returns:
        List of (relative_path, content) tuples
    """
    results: list[tuple[str, str]] = []
    path = path.resolve()
    
    if not path.is_dir():
        return results
    
    # Parse gitignore
    ignore_patterns = parse_gitignore(path)
    
    # Collect all files with supported extensions
    for p in path.rglob("*"):
        if not p.is_file():
            continue
        
        # Check extension
        if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        
        # Check if ignored
        if is_ignored(p, path, ignore_patterns):
            continue
        
        # Skip large files
        try:
            if p.stat().st_size > max_file_size:
                continue
        except OSError:
            continue
        
        # Read file
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            rel = str(p.relative_to(path))
            results.append((rel, content))
        except OSError:
            continue
    
    return results


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks.
    
    Args:
        text: Text to split
        chunk_size: Size of each chunk in characters
        overlap: Overlap between chunks
    
    Returns:
        List of text chunks
    """
    if not text or chunk_size <= 0:
        return []
    
    chunks: list[str] = []
    start = 0
    
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end].strip())
        start = end - overlap if overlap < chunk_size else end
    
    return [c for c in chunks if c]
