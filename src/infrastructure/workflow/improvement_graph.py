"""Self-Improvement Workflow - analyze → rag → plan → code → validate → write with retry."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.domain.ports.llm import LLMMessage, LLMPort
from src.infrastructure.agents.file_writer import FileWriter

if TYPE_CHECKING:
    from src.domain.ports.rag import RAGPort


class ImprovementState(TypedDict, total=False):
    """State for improvement workflow."""
    
    # Input
    file_path: str
    issue: dict  # CodeIssue as dict
    original_code: str
    related_files: list[str]  # B3: paths for context (imports, tests)
    related_files_context: str  # B3: content of related files
    
    # RAG context (B1) + project map (B2)
    rag_context: str
    project_map: str
    
    # Processing
    plan: str
    improved_code: str
    tests: str
    
    # Validation
    validation_passed: bool
    validation_output: str
    retry_count: int
    max_retries: int
    # B5: RAG by error on retry
    error_rag_context: str

    # Output
    write_result: dict
    error: str | None
    current_step: str


@dataclass
class ImprovementResult:
    """Result of improvement attempt."""
    
    success: bool
    file_path: str
    original_code: str
    improved_code: str | None
    backup_path: str | None
    validation_output: str | None
    error: str | None
    retries: int


async def _analyze_node(
    state: ImprovementState,
    file_writer: FileWriter,
) -> ImprovementState:
    """Read original file and related files (B3) for improvement."""
    file_path = state.get("file_path", "")
    result = file_writer.read_file(file_path)
    
    if not result["success"]:
        return {
            **state,
            "error": result["error"],
            "current_step": "error",
        }
    
    # B3: Read related files (imports, tests) for context
    related_files_context = ""
    related_files = state.get("related_files") or []
    for rel_path in related_files[:5]:  # Limit to 5 files
        if not rel_path or rel_path == file_path:
            continue
        r = file_writer.read_file(rel_path)
        if r.get("success") and r.get("content"):
            related_files_context += f"\n### {rel_path}\n```\n{r['content'][:1500]}\n```\n"
    
    return {
        **state,
        "original_code": result["content"],
        "related_files_context": related_files_context[:6000] if related_files_context else "",
        "retry_count": 0,
        "max_retries": state.get("max_retries", 3),
        "current_step": "rag",
    }


async def _rag_node(
    state: ImprovementState,
    rag: "RAGPort | None",
) -> ImprovementState:
    """RAG search + project map (B1, B2 - Cursor-like)."""
    if not rag:
        return {**state, "rag_context": "", "project_map": "", "current_step": "plan"}
    
    file_path = state.get("file_path", "")
    issue = state.get("issue", {})
    original_code = state.get("original_code", "")[:500]
    
    query = f"{file_path} {issue.get('message', '')} {issue.get('suggestion', '')}".strip()
    if not query:
        return {**state, "rag_context": "", "project_map": "", "current_step": "plan"}
    
    try:
        chunks = await rag.search(query, limit=8, min_score=0.35)
        if not chunks:
            rag_context = ""
        else:
            parts = []
            seen: set[str] = set()
            for c in chunks:
                src = c.metadata.get("source", "")
                if src not in seen and src != file_path:
                    seen.add(src)
                    parts.append(f"### {src}\n```\n{c.content[:500]}\n```")
                if len(parts) >= 5:
                    break
            rag_context = "\n\n".join(parts) if parts else ""
    except Exception:
        rag_context = ""
    
    # B2: Project map
    project_map = ""
    if rag and hasattr(rag, "get_project_map_markdown"):
        try:
            map_md = rag.get_project_map_markdown()
            if map_md:
                project_map = map_md[:2500]
        except Exception:
            pass
    
    return {**state, "rag_context": rag_context, "project_map": project_map, "current_step": "plan"}


async def _plan_node(
    state: ImprovementState,
    llm: LLMPort,
    model: str,
    on_chunk: Callable[[str, str], None] | None = None,
) -> ImprovementState:
    """Generate improvement plan."""
    issue = state.get("issue", {})
    original_code = state.get("original_code", "")
    rag_context = state.get("rag_context", "")
    project_map = state.get("project_map", "")
    related_files_context = state.get("related_files_context", "")
    
    rag_section = ""
    if project_map:
        rag_section += f"\nProject structure:\n{project_map[:1500]}\n\n"
    if rag_context:
        rag_section += f"""
Relevant code from project (follow similar patterns):
{rag_context}

"""
    if related_files_context:
        rag_section += f"""
Related files (imports, tests - consider when planning):
{related_files_context}

"""
    
    prompt = f"""You need to improve this code to fix the following issue:

Issue: {issue.get('message', 'General improvement')}
Severity: {issue.get('severity', 'medium')}
Type: {issue.get('issue_type', 'refactor')}
Suggestion: {issue.get('suggestion', 'Improve code quality')}
{rag_section}
Original code:
```python
{original_code}
```

Create a brief step-by-step plan to fix this issue. Be specific about what changes to make.
"""

    messages = [
        LLMMessage(role="system", content="You are a senior Python developer. Create concise improvement plans."),
        LLMMessage(role="user", content=prompt),
    ]
    
    if on_chunk:
        content_parts = []
        async for chunk in llm.generate_stream(messages=messages, model=model):
            content_parts.append(chunk)
            on_chunk("plan", chunk)
        plan = "".join(content_parts)
    else:
        response = await llm.generate(messages=messages, model=model)
        plan = response.content
    
    return {
        **state,
        "plan": plan,
        "current_step": "code",
    }


async def _code_node(
    state: ImprovementState,
    llm: LLMPort,
    model: str,
    on_chunk: Callable[[str, str], None] | None = None,
) -> ImprovementState:
    """Generate improved code."""
    issue = state.get("issue", {})
    original_code = state.get("original_code", "")
    plan = state.get("plan", "")
    rag_context = state.get("rag_context", "")
    project_map = state.get("project_map", "")
    related_files_context = state.get("related_files_context", "")
    validation_output = state.get("validation_output", "")
    retry_count = state.get("retry_count", 0)
    error_rag_context = state.get("error_rag_context", "")

    # B5: retry with full stack trace + RAG «похожий код»
    retry_context = ""
    if retry_count > 0 and validation_output:
        retry_context = f"""

PREVIOUS ATTEMPT FAILED. Full error / stack trace:
```
{validation_output}
```
Fix the issues and try again.
"""
        if error_rag_context:
            retry_context += f"""

Similar code from codebase (may help fix this error):
{error_rag_context}
"""

    rag_section = ""
    if project_map:
        rag_section += f"\nProject structure:\n{project_map[:1200]}\n\n"
    if rag_context:
        rag_section += f"""
Project context (follow similar patterns):
{rag_context[:2000]}

"""
    if related_files_context:
        rag_section += f"""
Related files (preserve imports, consider callers/tests):
{related_files_context[:2000]}

"""
    
    prompt = f"""Improve this Python code following the plan below.

Issue to fix: {issue.get('message', 'General improvement')}

Plan:
{plan}
{rag_section}
Original code:
```python
{original_code}
```
{retry_context}
Output ONLY the improved Python code. No markdown, no explanations.
Preserve the overall structure and imports. Make minimal necessary changes.
"""

    messages = [
        LLMMessage(role="system", content="You are a Python expert. Output only valid Python code."),
        LLMMessage(role="user", content=prompt),
    ]
    
    if on_chunk:
        content_parts = []
        async for chunk in llm.generate_stream(messages=messages, model=model):
            content_parts.append(chunk)
            on_chunk("code", chunk)
        improved_code = "".join(content_parts)
    else:
        response = await llm.generate(messages=messages, model=model)
        improved_code = response.content
    
    # Clean up markdown if present
    if improved_code.startswith("```"):
        lines = improved_code.split("\n")
        improved_code = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    
    return {
        **state,
        "improved_code": improved_code,
        "current_step": "validate",
    }


async def _validate_node(state: ImprovementState) -> ImprovementState:
    """Validate improved code (syntax check + basic tests). B5: full stack trace in validation_output."""
    import ast
    import subprocess
    import tempfile
    import traceback
    from pathlib import Path

    improved_code = state.get("improved_code", "")

    # Syntax check — B5: include line content when available
    try:
        ast.parse(improved_code)
    except SyntaxError as e:
        line_preview = ""
        if e.text:
            line_preview = f" Line content: {e.text.strip()!r}"
        return {
            **state,
            "validation_passed": False,
            "validation_output": f"Syntax error at line {e.lineno}: {e.msg}{line_preview}",
            "current_step": "check_retry",
        }

    # Try to run basic import check — B5: full stderr (stack trace)
    with tempfile.TemporaryDirectory() as tmpdir:
        code_file = Path(tmpdir) / "improved.py"
        code_file.write_text(improved_code, encoding="utf-8")

        try:
            result = subprocess.run(
                ["python", "-m", "py_compile", str(code_file)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                full_output = (result.stderr or "").strip()
                if result.stdout:
                    full_output = f"{result.stdout.strip()}\n{full_output}"
                return {
                    **state,
                    "validation_passed": False,
                    "validation_output": full_output or "Compilation failed (no output)",
                    "current_step": "check_retry",
                }
        except Exception as e:
            return {
                **state,
                "validation_passed": False,
                "validation_output": traceback.format_exc(),
                "current_step": "check_retry",
            }

    return {
        **state,
        "validation_passed": True,
        "validation_output": "Syntax and compilation check passed",
        "current_step": "write",
    }


def _should_retry(state: ImprovementState) -> Literal["retry", "write", "error"]:
    """Check if should retry after validation failure."""
    if state.get("validation_passed"):
        return "write"
    
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)
    
    if retry_count < max_retries:
        return "retry"
    
    return "error"


async def _retry_node(
    state: ImprovementState,
    rag: "RAGPort | None",
) -> ImprovementState:
    """B5: Increment retry, run RAG by error text for «похожий код» context."""
    retry_count = state.get("retry_count", 0) + 1
    validation_output = state.get("validation_output", "")
    error_rag_context = ""

    if rag and validation_output:
        try:
            # RAG по ошибке: ищем похожий код по тексту ошибки
            query = validation_output[:600].replace("\n", " ")
            chunks = await rag.search(query, limit=5, min_score=0.3)
            if chunks:
                parts = []
                seen: set[str] = set()
                for c in chunks:
                    src = c.metadata.get("source", "")
                    if src not in seen:
                        seen.add(src)
                        parts.append(f"### {src}\n```\n{c.content[:400]}\n```")
                error_rag_context = "\n\n".join(parts)
        except Exception:
            pass

    return {
        **state,
        "retry_count": retry_count,
        "error_rag_context": error_rag_context,
        "current_step": "code",
    }


async def _write_node(
    state: ImprovementState,
    file_writer: FileWriter,
) -> ImprovementState:
    """Write improved code to file."""
    file_path = state.get("file_path", "")
    improved_code = state.get("improved_code", "")
    
    result = file_writer.write_file(
        path=file_path,
        content=improved_code,
        create_backup=True,
    )
    
    return {
        **state,
        "write_result": result,
        "current_step": "done" if result["success"] else "error",
        "error": result.get("error"),
    }


async def _error_node(state: ImprovementState) -> ImprovementState:
    """Handle error state."""
    error = state.get("error") or state.get("validation_output") or "Unknown error"
    return {
        **state,
        "error": error,
        "current_step": "error",
    }


def build_improvement_graph(
    llm: LLMPort,
    model: str = "qwen2.5-coder:32b",
    file_writer: FileWriter | None = None,
    on_chunk: Callable[[str, str], None] | None = None,
    rag: "RAGPort | None" = None,
) -> StateGraph:
    """Build improvement workflow graph."""
    writer = file_writer or FileWriter()
    
    async def analyze_wrapper(state: ImprovementState) -> ImprovementState:
        return await _analyze_node(state, writer)
    
    async def rag_wrapper(state: ImprovementState) -> ImprovementState:
        return await _rag_node(state, rag)

    async def retry_wrapper(state: ImprovementState) -> ImprovementState:
        return await _retry_node(state, rag)

    async def plan_wrapper(state: ImprovementState) -> ImprovementState:
        return await _plan_node(state, llm, model, on_chunk)
    
    async def code_wrapper(state: ImprovementState) -> ImprovementState:
        return await _code_node(state, llm, model, on_chunk)
    
    async def write_wrapper(state: ImprovementState) -> ImprovementState:
        return await _write_node(state, writer)
    
    builder = StateGraph(ImprovementState)
    
    builder.add_node("analyze", analyze_wrapper)
    builder.add_node("rag", rag_wrapper)
    builder.add_node("plan", plan_wrapper)
    builder.add_node("code", code_wrapper)
    builder.add_node("validate", _validate_node)
    builder.add_node("retry", retry_wrapper)
    builder.add_node("write", write_wrapper)
    builder.add_node("error", _error_node)
    
    # Flow
    builder.add_edge(START, "analyze")
    builder.add_edge("analyze", "rag")
    builder.add_edge("rag", "plan")
    builder.add_edge("plan", "code")
    builder.add_edge("code", "validate")
    
    # Retry loop
    builder.add_conditional_edges(
        "validate",
        _should_retry,
        path_map={"retry": "retry", "write": "write", "error": "error"},
    )
    builder.add_edge("retry", "code")
    
    # End states
    builder.add_edge("write", END)
    builder.add_edge("error", END)
    
    return builder


def compile_improvement_graph(
    builder: StateGraph,
    checkpointer: MemorySaver | None = None,
):
    """Compile improvement graph."""
    return builder.compile(checkpointer=checkpointer or MemorySaver())
