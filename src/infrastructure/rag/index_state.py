"""Index State - tracks indexed files for incremental indexing.

Persists file path -> (mtime, size) mapping to detect changes.
State is keyed by base path to support multiple projects.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

INDEX_STATE_FILENAME = "index_state.json"


class IndexState:
    """Tracks which files are indexed and their modification state."""

    def __init__(self, chromadb_path: str) -> None:
        self._chromadb_path = Path(chromadb_path)
        self._state_file = self._chromadb_path / INDEX_STATE_FILENAME
        self._state: dict[str, dict[str, dict[str, float | int]]] = {}
        self._load()

    def _load(self) -> None:
        """Load state from disk."""
        if not self._state_file.exists():
            self._state = {}
            return
        try:
            data = json.loads(self._state_file.read_text(encoding="utf-8"))
            self._state = data
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load index state: {e}, starting fresh")
            self._state = {}

    def _save(self) -> None:
        """Persist state to disk."""
        self._chromadb_path.mkdir(parents=True, exist_ok=True)
        try:
            self._state_file.write_text(
                json.dumps(self._state, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as e:
            logger.error(f"Failed to save index state: {e}")

    def get_indexed_files(self, base_path: str) -> dict[str, dict[str, float | int]]:
        """Get indexed files for a base path. Returns {rel_path: {mtime, size}}."""
        key = str(Path(base_path).resolve())
        return self._state.get(key, {})

    def update_state(
        self,
        base_path: str,
        files: dict[str, dict[str, float | int]],
    ) -> None:
        """Update state for base path with current file info."""
        key = str(Path(base_path).resolve())
        self._state[key] = files
        self._save()

    def clear_state(self, base_path: str | None = None) -> None:
        """Clear state for base path, or all if base_path is None."""
        if base_path is None:
            self._state = {}
        else:
            key = str(Path(base_path).resolve())
            self._state.pop(key, None)
        self._save()

    @staticmethod
    def diff_files(
        current: dict[str, dict[str, float | int]],
        indexed: dict[str, dict[str, float | int]],
    ) -> tuple[list[str], list[str], list[str]]:
        """Compare current files with indexed state.

        Returns:
            (new_files, changed_files, deleted_files)
        """
        current_paths = set(current)
        indexed_paths = set(indexed)

        new = list(current_paths - indexed_paths)
        deleted = list(indexed_paths - current_paths)

        changed: list[str] = []
        for path in current_paths & indexed_paths:
            cur = current[path]
            idx = indexed[path]
            if cur.get("mtime") != idx.get("mtime") or cur.get("size") != idx.get("size"):
                changed.append(path)

        return (new, changed, deleted)
