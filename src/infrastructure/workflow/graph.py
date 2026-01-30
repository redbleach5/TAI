"""LangGraph workflow - intent → planner → researcher → tests → coder → validator."""

from collections.abc import Callable
from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.domain.entities.workflow_state import WorkflowState
from src.domain.ports.llm import LLMPort
from src.domain.ports.rag import RAGPort
from src.domain.services.intent_detector import IntentDetector
from src.domain.services.model_router import ModelRouter
from src.infrastructure.agents.coder import coder_node
from src.infrastructure.agents.planner import planner_node
from src.infrastructure.agents.researcher import researcher_node
from src.infrastructure.agents.tests_writer import tests_writer_node
from src.infrastructure.agents.validator import validator_node


def _should_skip_greeting(state: WorkflowState) -> Literal["end", "planner"]:
    """Route: greeting/help → END, else → planner."""
    kind = state.get("intent_kind", "chat")
    if kind in ("greeting", "help"):
        return "end"
    return "planner"


def build_workflow_graph(
    llm: LLMPort,
    model_router: ModelRouter,
    on_chunk: Callable[[str, str], None] | None = None,
    rag: RAGPort | None = None,
) -> StateGraph:
    """Build workflow graph with injected dependencies."""
    intent_detector = IntentDetector()

    async def intent_node(state: WorkflowState) -> WorkflowState:
        """Detect intent, set template_response for greeting/help."""
        task = state.get("task", "")
        intent = intent_detector.detect(task)
        model = model_router.select_model(task)
        return {
            **state,
            "intent_kind": intent.kind,
            "template_response": intent.response,
            "model": model,
        }

    async def planner_wrapper(state: WorkflowState) -> WorkflowState:
        return await planner_node(
            state,
            llm,
            state.get("model", "qwen2.5-coder:7b"),
            on_chunk=on_chunk,
        )

    async def researcher_wrapper(state: WorkflowState) -> WorkflowState:
        """RAG search for relevant context."""
        return await researcher_node(state, rag)

    async def tests_wrapper(state: WorkflowState) -> WorkflowState:
        return await tests_writer_node(
            state,
            llm,
            state.get("model", "qwen2.5-coder:7b"),
            on_chunk=on_chunk,
        )

    async def coder_wrapper(state: WorkflowState) -> WorkflowState:
        return await coder_node(
            state,
            llm,
            state.get("model", "qwen2.5-coder:7b"),
            on_chunk=on_chunk,
        )

    builder = StateGraph(WorkflowState)
    builder.add_node("intent", intent_node)
    builder.add_node("planner", planner_wrapper)
    builder.add_node("researcher", researcher_wrapper)
    builder.add_node("tests", tests_wrapper)
    builder.add_node("coder", coder_wrapper)
    builder.add_node("validator", validator_node)

    builder.add_edge(START, "intent")
    builder.add_conditional_edges(
        "intent",
        _should_skip_greeting,
        path_map={"end": END, "planner": "planner"},
    )
    builder.add_edge("planner", "researcher")
    builder.add_edge("researcher", "tests")
    builder.add_edge("tests", "coder")
    builder.add_edge("coder", "validator")
    builder.add_edge("validator", END)

    return builder


def compile_workflow_graph(
    builder: StateGraph,
    *,
    checkpointer: MemorySaver | None = None,
):
    """Compile graph with MemorySaver for checkpointing. Thread-safe for concurrent use."""
    return builder.compile(checkpointer=checkpointer or MemorySaver())
