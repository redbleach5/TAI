"""Researcher agent - RAG search for relevant code context."""

from src.domain.entities.workflow_state import WorkflowState
from src.domain.ports.rag import RAGPort


async def researcher_node(
    state: WorkflowState,
    rag: RAGPort | None,
) -> WorkflowState:
    """Search RAG for relevant context. Updates state['context']."""
    if rag is None:
        return {**state, "context": "", "current_step": "researcher"}
    task = state.get("task", "")
    plan = state.get("plan", "")
    query = f"{task}\n{plan}".strip()
    if not query:
        return {**state, "context": "", "current_step": "researcher"}
    try:
        chunks = await rag.search(query, limit=5)
        context = "\n\n---\n\n".join(
            f"# {c.metadata.get('source', '')}\n{c.content}" for c in chunks
        )
    except Exception:
        context = ""
    return {**state, "context": context, "current_step": "researcher"}
