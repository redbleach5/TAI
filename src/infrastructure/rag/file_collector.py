"""File Collector - collects code files for RAG indexing.

Production-ready with:
- Semantic chunking at natural boundaries
- Gitignore support with negation patterns
- Binary file detection
- File count limits
- Proper logging
"""

import fnmatch
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Maximum files to collect to prevent memory issues
MAX_FILE_COUNT = 10000

# Supported file extensions for indexing
SUPPORTED_EXTENSIONS = {
    # Python
    ".py",
    # JavaScript/TypeScript
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
    # Config/Data
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    # Documentation
    ".md",
    ".mdx",
    ".rst",
    ".txt",
    # Web
    ".html",
    ".css",
    ".scss",
    ".sass",
    # Other
    ".sh",
    ".bash",
    ".sql",
    ".graphql",
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


def parse_gitignore(path: Path) -> tuple[list[str], list[str]]:
    """Parse .gitignore file and return (ignore_patterns, negated_patterns).

    Supports negated patterns (lines starting with !).
    Tries multiple encodings for compatibility.
    """
    gitignore = path / ".gitignore"
    patterns = list(DEFAULT_IGNORES)
    negated: list[str] = []

    if gitignore.exists():
        content = None
        # Try multiple encodings
        for encoding in ["utf-8", "latin-1", "cp1252"]:
            try:
                content = gitignore.read_text(encoding=encoding)
                break
            except (OSError, UnicodeDecodeError):
                continue

        if content:
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # Handle negated patterns
                if line.startswith("!"):
                    negated.append(line[1:])
                else:
                    patterns.append(line)

    return patterns, negated


def is_ignored(
    file_path: Path,
    base_path: Path,
    patterns: list[str],
    negated: list[str] | None = None,
) -> bool:
    """Check if file matches any gitignore pattern.

    Supports negated patterns (files to include even if matched).
    """
    try:
        rel_path = str(file_path.relative_to(base_path))
    except ValueError:
        return True

    parts = rel_path.split("/")
    filename = parts[-1]

    # Check excluded directories first
    for part in parts[:-1]:  # Check all parent directories
        if part in EXCLUDED_DIRS:
            return True
        for excluded in EXCLUDED_DIRS:
            if "*" in excluded and fnmatch.fnmatch(part, excluded):
                return True

    # Check if file matches any ignore pattern
    is_matched = False
    for pattern in patterns:
        # Handle directory patterns (ending with /)
        if pattern.endswith("/"):
            dir_pattern = pattern[:-1]
            for part in parts[:-1]:
                if fnmatch.fnmatch(part, dir_pattern):
                    is_matched = True
                    break
        # Handle file patterns
        elif fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(filename, pattern):
            is_matched = True
            break

    # Check negated patterns (override ignore)
    if is_matched and negated:
        for neg_pattern in negated:
            if fnmatch.fnmatch(rel_path, neg_pattern) or fnmatch.fnmatch(filename, neg_pattern):
                return False  # Negated = don't ignore

    return is_matched


def is_binary_file(file_path: Path, check_bytes: int = 8192) -> bool:
    """Check if file appears to be binary.

    Checks for null bytes in the first N bytes.
    """
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(check_bytes)
            # Check for null bytes (common in binary files)
            if b"\x00" in chunk:
                return True
            # Check for high ratio of non-text bytes
            non_text = sum(1 for b in chunk if b < 32 and b not in (9, 10, 13))
            if len(chunk) > 0 and non_text / len(chunk) > 0.3:
                return True
    except OSError:
        return True  # Assume binary if can't read
    return False


def collect_code_files_with_stats(
    path: Path,
    max_file_size: int = 500 * 1024,
    max_files: int = MAX_FILE_COUNT,
    follow_symlinks: bool = False,
) -> list[tuple[str, str, float, int]]:
    """Collect (relative_path, content, mtime, size) for supported code files.

    Same as collect_code_files but includes mtime and size for incremental indexing.
    """
    results: list[tuple[str, str, float, int]] = []
    path = path.resolve()

    if not path.is_dir():
        logger.warning("Path is not a directory: %s", path)
        return results

    ignore_patterns, negated_patterns = parse_gitignore(path)
    skipped_large = 0
    skipped_binary = 0
    skipped_error = 0

    for p in path.rglob("*"):
        if len(results) >= max_files:
            logger.warning("Reached max file limit (%d), stopping collection", max_files)
            break

        if p.is_symlink() and not follow_symlinks:
            continue

        if not p.is_file():
            continue

        if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        if is_ignored(p, path, ignore_patterns, negated_patterns):
            continue

        try:
            stat = p.stat()
            file_size = stat.st_size
            mtime = stat.st_mtime
            if file_size > max_file_size:
                skipped_large += 1
                continue
            if file_size == 0:
                continue
        except OSError:
            skipped_error += 1
            continue

        if is_binary_file(p):
            skipped_binary += 1
            continue

        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            rel = str(p.relative_to(path))
            results.append((rel, content, mtime, file_size))
        except OSError as e:
            logger.debug("Failed to read %s: %s", p, e)
            skipped_error += 1
            continue

    if skipped_large or skipped_binary or skipped_error:
        logger.debug("Skipped files: %d large, %d binary, %d errors", skipped_large, skipped_binary, skipped_error)

    return results


def collect_code_files(
    path: Path,
    max_file_size: int = 500 * 1024,
    max_files: int = MAX_FILE_COUNT,
    follow_symlinks: bool = False,
) -> list[tuple[str, str]]:
    """Collect (relative_path, content) for all supported code files.

    Args:
        path: Directory to scan
        max_file_size: Maximum file size in bytes (default 500KB)
        max_files: Maximum number of files to collect (default 10000)
        follow_symlinks: Whether to follow symlinks (default False for safety)

    Returns:
        List of (relative_path, content) tuples

    """
    results: list[tuple[str, str]] = []
    path = path.resolve()

    if not path.is_dir():
        logger.warning("Path is not a directory: %s", path)
        return results

    # Parse gitignore
    ignore_patterns, negated_patterns = parse_gitignore(path)

    skipped_large = 0
    skipped_binary = 0
    skipped_error = 0

    # Collect all files with supported extensions
    for p in path.rglob("*"):
        # Check file count limit
        if len(results) >= max_files:
            logger.warning("Reached max file limit (%d), stopping collection", max_files)
            break

        # Skip symlinks unless explicitly allowed
        if p.is_symlink() and not follow_symlinks:
            continue

        if not p.is_file():
            continue

        # Check extension
        if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        # Check if ignored
        if is_ignored(p, path, ignore_patterns, negated_patterns):
            continue

        # Skip large files
        try:
            file_size = p.stat().st_size
            if file_size > max_file_size:
                skipped_large += 1
                continue
            if file_size == 0:
                continue  # Skip empty files
        except OSError:
            skipped_error += 1
            continue

        # Check for binary content
        if is_binary_file(p):
            skipped_binary += 1
            continue

        # Read file
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            rel = str(p.relative_to(path))
            results.append((rel, content))
        except OSError as e:
            logger.debug("Failed to read %s: %s", p, e)
            skipped_error += 1
            continue

    if skipped_large or skipped_binary or skipped_error:
        logger.debug("Skipped files: %d large, %d binary, %d errors", skipped_large, skipped_binary, skipped_error)

    return results


def chunk_text(
    text: str,
    chunk_size: int,
    overlap: int,
    respect_boundaries: bool = True,
) -> list[str]:
    """Split text into overlapping chunks with semantic boundary detection.

    Args:
        text: Text to split
        chunk_size: Target size of each chunk in characters
        overlap: Overlap between chunks (must be < chunk_size)
        respect_boundaries: Try to split at natural boundaries (paragraphs, functions)

    Returns:
        List of text chunks

    Raises:
        ValueError: If parameters are invalid

    """
    # Input validation
    if not text:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0:
        raise ValueError("overlap must be non-negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be less than chunk_size")

    chunks: list[str] = []
    text_len = len(text)
    start = 0

    # Boundary patterns for semantic splitting (in priority order)
    boundaries = [
        "\n\ndef ",  # Python function
        "\n\nclass ",  # Python class
        "\nfunction ",  # JavaScript function
        "\n\n",  # Paragraph
        "\n",  # Line
    ]

    while start < text_len:
        # Calculate initial end position
        end = min(start + chunk_size, text_len)

        # If we're at the end of text, just take what's left
        if end >= text_len:
            chunk = text[start:].strip()
            if chunk:
                chunks.append(chunk)
            break

        # Try to find a natural boundary to split at
        if respect_boundaries:
            best_split = end
            # Look back from end to find a boundary
            search_start = max(start + chunk_size // 2, start)  # Don't look too far back
            search_text = text[search_start:end]

            for boundary in boundaries:
                # Find last occurrence of boundary in search region
                idx = search_text.rfind(boundary)
                if idx != -1:
                    # Found a boundary - split after it
                    best_split = search_start + idx + len(boundary)
                    break

            end = best_split

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Move start forward, accounting for overlap
        start = end - overlap

    return chunks


def chunk_code_file(content: str, chunk_size: int = 1500, overlap: int = 200) -> list[str]:
    """Chunk a code file intelligently.

    Specialized chunking for code that respects function/class boundaries.
    """
    return chunk_text(content, chunk_size, overlap, respect_boundaries=True)
