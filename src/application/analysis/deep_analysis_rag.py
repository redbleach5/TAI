"""RAG helpers for deep analysis: initial context and targeted (A1) context.

Used by DeepAnalyzer: gather_initial_rag(rag), targeted_rag(rag, modules).
"""

import logging

from src.domain.ports.rag import RAGPort

logger = logging.getLogger(__name__)

# RAG queries - expanded for better coverage
RAG_QUERIES = [
    "архитектура entry points main",
    "конфигурация настройки config",
    "API routes handlers endpoints",
    "сложные функции сложность complexity",
    "ошибки обработка exceptions error handling",
    "зависимости импорты imports dependencies",
    "тесты tests pytest",
    "модели данные models schema",
]
RAG_CHUNKS_PER_QUERY = 3
RAG_MAX_CHUNKS = 25
RAG_MIN_SCORE = 0.35

# Multi-step (A1): targeted RAG per module
A1_MAX_MODULES = 5
A1_CHUNKS_PER_MODULE = 5
A1_TARGETED_QUERY_TEMPLATE = "код логика проблемы рефакторинг {module}"
A1_MIN_SCORE = 0.35


async def gather_initial_rag(rag: RAGPort) -> str:
    """Gather initial RAG context from expanded queries.

    Args:
        rag: RAG adapter (implements RAGPort).

    Returns:
        Formatted context string or fallback message.

    """
    chunks_by_query: list[str] = []
    seen_sources: set[str] = set()
    for q in RAG_QUERIES:
        if len(chunks_by_query) >= RAG_MAX_CHUNKS:
            break
        results = await rag.search(q, limit=RAG_CHUNKS_PER_QUERY, min_score=RAG_MIN_SCORE)
        for c in results:
            src = c.metadata.get("source", "")
            if src not in seen_sources:
                seen_sources.add(src)
                content = getattr(c, "content", str(c))[:700]
                chunks_by_query.append(f"### {src}\n```\n{content}\n```")
                if len(chunks_by_query) >= RAG_MAX_CHUNKS:
                    break
    return "\n\n".join(chunks_by_query) if chunks_by_query else "Не найдено релевантных чанков."


async def targeted_rag(rag: RAGPort, modules: list[str]) -> str:
    """RAG search per module for deeper context (A1 step 2).

    Args:
        rag: RAG adapter (implements RAGPort).
        modules: List of module paths from step 1.

    Returns:
        Formatted context string or empty.

    """
    parts: list[str] = []
    seen: set[str] = set()
    for module in modules[:A1_MAX_MODULES]:
        for query in (
            A1_TARGETED_QUERY_TEMPLATE.format(module=module),
            module,
        ):
            try:
                results = await rag.search(
                    query,
                    limit=A1_CHUNKS_PER_MODULE,
                    min_score=A1_MIN_SCORE,
                )
                if not results:
                    continue
                for c in results:
                    src = c.metadata.get("source", "")
                    content = getattr(c, "content", str(c))[:600]
                    key = f"{src}:{content[:100]}"
                    if key not in seen:
                        seen.add(key)
                        parts.append(f"#### {module}\n```\n{content}\n```")
                break
            except Exception:
                logger.debug("Targeted RAG search failed for module=%s", module, exc_info=True)
                continue
    return "\n\n".join(parts) if parts else ""
