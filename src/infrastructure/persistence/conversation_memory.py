"""Conversation memory - save/load to output/conversations/."""

import json
import uuid
from pathlib import Path

from src.domain.ports.llm import LLMMessage


class ConversationMemory:
    """Save and load conversations to output/conversations/{id}.json."""

    def __init__(self, output_dir: str = "output") -> None:
        self._base = Path(output_dir) / "conversations"
        self._base.mkdir(parents=True, exist_ok=True)

    def create_id(self) -> str:
        """Generate new conversation ID."""
        return str(uuid.uuid4())

    def save(self, conversation_id: str, messages: list[LLMMessage]) -> None:
        """Save conversation to file."""
        path = self._base / f"{conversation_id}.json"
        data = [{"role": m.role, "content": m.content} for m in messages]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def load(self, conversation_id: str) -> list[LLMMessage]:
        """Load conversation from file. Returns empty list if not found."""
        path = self._base / f"{conversation_id}.json"
        if not path.exists():
            return []
        data = json.loads(path.read_text())
        return [LLMMessage(role=m["role"], content=m["content"]) for m in data]

    def list_ids(self) -> list[str]:
        """List saved conversation IDs."""
        if not self._base.exists():
            return []
        return [p.stem for p in self._base.glob("*.json")]
