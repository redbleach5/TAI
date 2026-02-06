"""Conversation memory - save/load to output/conversations/."""

import json
import logging
import threading
import uuid
from pathlib import Path

from src.domain.ports.llm import LLMMessage

logger = logging.getLogger(__name__)


class ConversationMemory:
    """Save and load conversations to output/conversations/{id}.json.

    Thread-safe: file operations are protected by a reentrant lock.
    """

    def __init__(self, output_dir: str = "output") -> None:
        """Initialize with output directory for conversation files."""
        self._base = Path(output_dir) / "conversations"
        self._base.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def create_id(self) -> str:
        """Generate new conversation ID."""
        return str(uuid.uuid4())

    def save(self, conversation_id: str, messages: list[LLMMessage]) -> None:
        """Save conversation to file (thread-safe)."""
        path = self._base / f"{conversation_id}.json"
        try:
            data = [{"role": m.role, "content": m.content} for m in messages]
            with self._lock:
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception:
            logger.warning("Failed to save conversation %s", conversation_id, exc_info=True)

    def load(self, conversation_id: str) -> list[LLMMessage]:
        """Load conversation from file (thread-safe). Returns empty list if not found."""
        path = self._base / f"{conversation_id}.json"
        if not path.exists():
            return []
        try:
            with self._lock:
                data = json.loads(path.read_text())
            return [LLMMessage(role=m["role"], content=m["content"]) for m in data]
        except (json.JSONDecodeError, KeyError):
            logger.warning("Malformed conversation file: %s", path, exc_info=True)
            return []
        except Exception:
            logger.warning("Failed to load conversation %s", conversation_id, exc_info=True)
            return []

    def list_ids(self) -> list[str]:
        """List saved conversation IDs."""
        if not self._base.exists():
            return []
        return [p.stem for p in self._base.glob("*.json")]

    def list_with_titles(self, title_max_len: int = 50) -> list[dict]:
        """List conversations with title from first user message."""
        if not self._base.exists():
            return []
        result = []
        for path in self._base.glob("*.json"):
            cid = path.stem
            title = ""
            try:
                data = json.loads(path.read_text())
                for m in data:
                    if m.get("role") == "user" and m.get("content"):
                        title = (m["content"] or "").strip().replace("\n", " ")[:title_max_len]
                        break
            except Exception:
                logger.debug("Failed to read title from conversation %s", cid, exc_info=True)
            result.append({"id": cid, "title": title or "Без названия"})
        return result

    def delete(self, conversation_id: str) -> bool:
        """Delete conversation file (thread-safe). Returns True if deleted."""
        path = self._base / f"{conversation_id}.json"
        if not path.exists():
            return False
        try:
            with self._lock:
                path.unlink()
            return True
        except Exception:
            logger.warning("Failed to delete conversation %s", conversation_id, exc_info=True)
            return False
