"""Researcher agent - RAG search for relevant code context."""

from src.domain.entities.workflow_state import WorkflowState
from src.domain.ports.rag import RAGPort


# Default context limits
DEFAULT_CHUNK_LIMIT = 20
DEFAULT_MAX_TOKENS = 6000  # ~24KB of context, safe for most models
DEFAULT_MIN_SCORE = 0.35


async def researcher_node(
    state: WorkflowState,
    rag: RAGPort | None,
    limit: int = DEFAULT_CHUNK_LIMIT,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    min_score: float = DEFAULT_MIN_SCORE,
) -> WorkflowState:
    """Search RAG for relevant context. Updates state['context'].
    
    Args:
        state: Current workflow state
        rag: RAG adapter (optional)
        limit: Max chunks to retrieve (default 20)
        max_tokens: Max tokens in context (default 6000)
        min_score: Minimum relevance score (default 0.35)
    """
    if rag is None:
        return {**state, "context": "", "current_step": "researcher"}
    
    task = state.get("task", "")
    plan = state.get("plan", "")
    query = f"{task}\n{plan}".strip()
    
    if not query:
        return {**state, "context": "", "current_step": "researcher"}
    
    try:
        chunks = await rag.search(
            query,
            limit=limit,
            min_score=min_score,
            max_tokens=max_tokens,
        )
        
        if not chunks:
            return {**state, "context": "", "current_step": "researcher"}
        
        # Group chunks by source file for better context
        files_context: dict[str, list[str]] = {}
        for c in chunks:
            source = c.metadata.get("source", "unknown")
            if source not in files_context:
                files_context[source] = []
            files_context[source].append(c.content)
        
        # Format context with file headers
        context_parts = []
        for source, contents in files_context.items():
            file_content = "\n\n".join(contents)
            context_parts.append(f"# File: {source}\n\n{file_content}")
        
        context = "\n\n---\n\n".join(context_parts)
        
        # Add summary of what was found
        summary = f"[RAG: {len(chunks)} chunks from {len(files_context)} files]"
        context = f"{summary}\n\n{context}"
        
    except Exception as e:
        context = f"[RAG error: {e}]"
    
    return {**state, "context": context, "current_step": "researcher"}
