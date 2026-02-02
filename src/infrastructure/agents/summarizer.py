"""Summarizer agent - LLM-based context summarization."""

import hashlib
import threading
from pathlib import Path

from src.domain.ports.llm import LLMMessage, LLMPort


# Cache for summaries (in-memory, persisted to file); lock for thread safety
_summary_cache: dict[str, str] = {}
_cache_lock = threading.Lock()
_cache_file = Path("output/summary_cache.json")


def _load_cache() -> None:
    """Load summary cache from file. Caller must hold _cache_lock when modifying cache."""
    global _summary_cache
    if _cache_file.exists():
        try:
            import json
            _summary_cache = json.loads(_cache_file.read_text())
        except Exception:
            _summary_cache = {}
    else:
        _summary_cache = {}


def _save_cache() -> None:
    """Save summary cache to file. Caller must hold _cache_lock."""
    try:
        import json
        _cache_file.parent.mkdir(parents=True, exist_ok=True)
        _cache_file.write_text(json.dumps(_summary_cache))
    except Exception:
        pass


def _content_hash(content: str) -> str:
    """Generate hash for content."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


SUMMARIZE_SYSTEM = """You are a code summarizer. Your task is to create concise summaries of code files and context that preserve the most important information for a developer.

Rules:
1. Focus on: function signatures, class definitions, key logic, imports, dependencies
2. Preserve: function names, class names, important variables, API endpoints
3. Remove: implementation details, comments, docstrings (unless critical)
4. Keep structure: maintain the logical organization of the code
5. Be concise: aim for 30-50% of original length while keeping essential info
6. Output format: use markdown with code blocks for signatures

Example summary:
```
## file.py
- Imports: fastapi, pydantic
- Classes: `UserService(BaseService)` - handles user CRUD
- Functions:
  - `get_user(id: int) -> User` - fetch by ID
  - `create_user(data: UserCreate) -> User` - create new
- Key logic: Uses repository pattern, async DB calls
```"""


SUMMARIZE_USER = """Summarize the following code/context. Keep function signatures, class definitions, and key logic. Be concise.

---
{content}
---

Provide a structured summary:"""


async def summarize_content(
    content: str,
    llm: LLMPort,
    model: str,
    max_output_tokens: int = 2000,
    use_cache: bool = True,
) -> str:
    """Summarize content using LLM.
    
    Args:
        content: Content to summarize
        llm: LLM adapter
        model: Model to use
        max_output_tokens: Max tokens in summary
        use_cache: Whether to use/store in cache
    
    Returns:
        Summarized content
    """
    if not content.strip():
        return ""
    
    # Check cache
    content_hash = _content_hash(content)
    if use_cache:
        with _cache_lock:
            _load_cache()
            if content_hash in _summary_cache:
                return _summary_cache[content_hash]

    # Generate summary
    messages = [
        LLMMessage(role="system", content=SUMMARIZE_SYSTEM),
        LLMMessage(role="user", content=SUMMARIZE_USER.format(content=content[:50000])),  # Limit input
    ]
    
    try:
        response = await llm.generate(
            messages=messages,
            model=model,
            max_tokens=max_output_tokens,
            temperature=0.3,
        )
        summary = response.content.strip()
        
        # Cache result
        if use_cache and summary:
            with _cache_lock:
                _summary_cache[content_hash] = summary
                _save_cache()
        
        return summary
    except Exception as e:
        return f"[Summary error: {e}]\n\n{content[:1000]}..."


async def summarize_chunks(
    chunks: list[dict],
    llm: LLMPort,
    model: str,
    max_total_tokens: int = 4000,
) -> str:
    """Summarize multiple code chunks into a coherent context.
    
    Args:
        chunks: List of {content, source, score} dicts
        llm: LLM adapter
        model: Model to use
        max_total_tokens: Target size for final summary
    
    Returns:
        Combined summary
    """
    if not chunks:
        return ""
    
    # Group by source file
    by_file: dict[str, list[str]] = {}
    for chunk in chunks:
        source = chunk.get("source", "unknown")
        content = chunk.get("content", "")
        if source not in by_file:
            by_file[source] = []
        by_file[source].append(content)
    
    # Summarize each file
    file_summaries = []
    tokens_per_file = max_total_tokens // len(by_file) if by_file else max_total_tokens
    
    for source, contents in by_file.items():
        full_content = f"# {source}\n\n" + "\n\n".join(contents)
        summary = await summarize_content(
            full_content,
            llm,
            model,
            max_output_tokens=tokens_per_file,
        )
        file_summaries.append(f"## {source}\n{summary}")
    
    return "\n\n---\n\n".join(file_summaries)


async def summarize_conversation(
    messages: list[dict],
    llm: LLMPort,
    model: str,
    max_tokens: int = 1000,
) -> str:
    """Summarize conversation history.
    
    Args:
        messages: List of {role, content} messages
        llm: LLM adapter
        model: Model to use
        max_tokens: Max tokens in summary
    
    Returns:
        Conversation summary
    """
    if not messages:
        return ""
    
    # Format conversation
    conversation = "\n".join(
        f"{m.get('role', 'user')}: {m.get('content', '')[:500]}"
        for m in messages
    )
    
    prompt = f"""Summarize this conversation, focusing on:
1. What the user wanted to accomplish
2. What was discussed/decided
3. Any code or technical details mentioned

Conversation:
{conversation}

Summary:"""
    
    try:
        response = await llm.generate(
            messages=[
                LLMMessage(role="system", content="You are a conversation summarizer. Be concise but preserve key technical details."),
                LLMMessage(role="user", content=prompt),
            ],
            model=model,
            max_tokens=max_tokens,
            temperature=0.3,
        )
        return response.content.strip()
    except Exception as e:
        return f"[Summary error: {e}]"


def estimate_tokens(text: str) -> int:
    """Estimate token count (rough: 4 chars per token)."""
    return len(text) // 4


def should_summarize(content: str, max_tokens: int) -> bool:
    """Check if content should be summarized."""
    return estimate_tokens(content) > max_tokens
