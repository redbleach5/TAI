"""Self-improvement use case - orchestrates analysis and improvement."""

import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from src.application.improvement.dto import (
    AnalyzeRequest,
    AnalyzeResponse,
    ImprovementRequest,
    ImprovementResponse,
    ImprovementTask,
    IssueDTO,
    QueueStatus,
    TaskStatus,
)
from src.domain.ports.llm import LLMPort
from src.domain.ports.rag import RAGPort
from src.domain.services.model_selector import ModelSelector
from src.infrastructure.agents.analyzer import CodeAnalyzer, CodeIssue, ProjectAnalysis
from src.infrastructure.agents.file_writer import FileWriter
from src.infrastructure.workflow.improvement_graph import (
    ImprovementState,
    build_improvement_graph,
    compile_improvement_graph,
)


def _issue_to_dto(issue: CodeIssue) -> IssueDTO:
    """Convert CodeIssue to IssueDTO."""
    return IssueDTO(
        file=issue.file,
        line=issue.line,
        issue_type=issue.issue_type,
        severity=issue.severity,
        message=issue.message,
        suggestion=issue.suggestion,
    )


class SelfImprovementUseCase:
    """Orchestrates self-improvement: analysis → planning → coding → validation → writing."""

    def __init__(
        self,
        llm: LLMPort,
        model_selector: ModelSelector,
        file_writer: FileWriter | None = None,
        rag: RAGPort | None = None,
        checkpointer: MemorySaver | None = None,
        workspace_path_getter: Callable[[], str] | None = None,
    ) -> None:
        self._llm = llm
        self._model_selector = model_selector
        self._file_writer = file_writer or FileWriter()
        self._rag = rag
        self._checkpointer = checkpointer or MemorySaver()
        self._analyzer = CodeAnalyzer(llm)
        self._workspace_path_getter = workspace_path_getter or (
            lambda: str(Path.cwd().resolve())
        )
        self._workspace_lock = asyncio.Lock()
        
        # Task queue
        self._tasks: dict[str, ImprovementTask] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None
        self._running = False

    async def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        """Analyze project and return issues with suggestions.
        
        Uses workspace path from getter; chdirs to workspace for analysis.
        """
        workspace_path = self._workspace_path_getter()
        original_cwd = os.getcwd()
        async with self._workspace_lock:
            try:
                os.chdir(workspace_path)
                # Static analysis
                analysis = self._analyzer.analyze_project(request.path)
                
                # Add linter issues
                if request.include_linter:
                    linter_issues = self._analyzer.run_linter(request.path)
                    analysis.issues.extend(linter_issues)
                
                # Get LLM suggestions
                suggestions = []
                if request.use_llm:
                    suggestions = await self._analyzer.suggest_improvements(analysis)
                else:
                    # Basic suggestions based on analysis
                    suggestions = self._generate_basic_suggestions(analysis)
                
                return AnalyzeResponse(
                    total_files=analysis.total_files,
                    total_lines=analysis.total_lines,
                    total_functions=analysis.total_functions,
                    total_classes=analysis.total_classes,
                    avg_complexity=analysis.avg_complexity,
                    issues=[_issue_to_dto(i) for i in analysis.issues],
                    suggestions=suggestions,
                )
            finally:
                os.chdir(original_cwd)

    def _generate_basic_suggestions(self, analysis: ProjectAnalysis) -> list[dict]:
        """Generate basic suggestions without LLM."""
        suggestions = []
        
        critical = [i for i in analysis.issues if i.severity == "critical"]
        high = [i for i in analysis.issues if i.severity == "high"]
        complexity_issues = [i for i in analysis.issues if i.issue_type == "complexity"]
        refactor_issues = [i for i in analysis.issues if i.issue_type == "refactor"]
        
        if critical:
            suggestions.append({
                "priority": 1,
                "title": "Fix Critical Issues",
                "description": f"Found {len(critical)} critical issues requiring immediate attention",
                "estimated_effort": "high",
                "files": list(set(i.file for i in critical))[:5],
            })
        
        if high:
            suggestions.append({
                "priority": 2,
                "title": "Address High Severity Issues",
                "description": f"Found {len(high)} high severity issues that should be fixed",
                "estimated_effort": "medium",
                "files": list(set(i.file for i in high))[:5],
            })
        
        if complexity_issues:
            suggestions.append({
                "priority": 3,
                "title": "Reduce Code Complexity",
                "description": f"Found {len(complexity_issues)} functions with high complexity",
                "estimated_effort": "medium",
                "files": list(set(i.file for i in complexity_issues))[:5],
            })
        
        if refactor_issues:
            suggestions.append({
                "priority": 4,
                "title": "Refactoring Opportunities",
                "description": f"Found {len(refactor_issues)} opportunities for refactoring",
                "estimated_effort": "low",
                "files": list(set(i.file for i in refactor_issues))[:5],
            })
        
        if analysis.avg_complexity > 8:
            suggestions.append({
                "priority": 5,
                "title": "Overall Complexity Reduction",
                "description": f"Average complexity is {analysis.avg_complexity:.1f}, target is below 8",
                "estimated_effort": "high",
            })
        
        return suggestions

    async def improve_file(
        self,
        request: ImprovementRequest,
        on_chunk: Any = None,
    ) -> ImprovementResponse:
        """Improve single file using LLM workflow.
        
        Uses workspace path from getter; chdirs to workspace for file ops.
        """
        workspace_path = self._workspace_path_getter()
        original_cwd = os.getcwd()
        async with self._workspace_lock:
            try:
                os.chdir(workspace_path)
                # For improvements, prefer complex model (largest available)
                model, _ = await self._model_selector.select_model(
                    request.issue.get("message", "") if request.issue else "complex refactoring"
                )
                
                builder = build_improvement_graph(
                    llm=self._llm,
                    model=model,
                    file_writer=self._file_writer,
                    on_chunk=on_chunk,
                    rag=self._rag,
                )
                graph = compile_improvement_graph(builder, self._checkpointer)
                
                session_id = str(uuid.uuid4())
                config = {"configurable": {"thread_id": session_id}, "recursion_limit": 20}
                
                initial: ImprovementState = {
                    "file_path": request.file_path,
                    "issue": request.issue or {
                        "message": "General code improvement",
                        "severity": "medium",
                        "issue_type": "refactor",
                    },
                    "max_retries": request.max_retries,
                    "related_files": request.related_files,
                    "auto_write": request.auto_write,
                }
                if request.selection_start_line is not None and request.selection_end_line is not None:
                    initial["selection_start_line"] = request.selection_start_line
                    initial["selection_end_line"] = request.selection_end_line
                
                final = await graph.ainvoke(initial, config=config)
                
                write_result = final.get("write_result", {})
                success = final.get("validation_passed", False) and write_result.get("success", False)
                
                return ImprovementResponse(
                    success=success,
                    file_path=request.file_path,
                    backup_path=write_result.get("backup_path"),
                    improved_code=final.get("improved_code"),
                    validation_output=final.get("validation_output"),
                    error=final.get("error"),
                    retries=final.get("retry_count", 0),
                    proposed_full_content=write_result.get("proposed_full_content"),
                    selection_start_line=final.get("selection_start_line"),
                    selection_end_line=final.get("selection_end_line"),
                )
            finally:
                os.chdir(original_cwd)

    async def improve_file_stream(
        self,
        request: ImprovementRequest,
    ) -> AsyncIterator[dict]:
        """Improve file with streaming updates."""
        queue: asyncio.Queue[dict] = asyncio.Queue()
        
        def on_chunk(event_type: str, chunk: str) -> None:
            queue.put_nowait({"event": event_type, "chunk": chunk})
        
        async def run_improvement() -> None:
            try:
                result = await self.improve_file(request, on_chunk=on_chunk)
                queue.put_nowait({"event": "done", "result": result.__dict__})
            except Exception as e:
                queue.put_nowait({"event": "error", "error": str(e)})
        
        task = asyncio.create_task(run_improvement())
        
        try:
            while True:
                event = await queue.get()
                yield event
                if event.get("event") in ("done", "error"):
                    break
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    # Task Queue Management
    
    def add_task(self, request: ImprovementRequest) -> str:
        """Add task to improvement queue."""
        task_id = str(uuid.uuid4())
        task = ImprovementTask(
            id=task_id,
            file_path=request.file_path,
            issue=request.issue,
            status=TaskStatus.PENDING,
        )
        self._tasks[task_id] = task
        self._queue.put_nowait(task_id)
        return task_id

    def get_task(self, task_id: str) -> ImprovementTask | None:
        """Get task by ID."""
        return self._tasks.get(task_id)

    def get_queue_status(self) -> QueueStatus:
        """Get current queue status."""
        tasks = list(self._tasks.values())
        completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in tasks if t.status == TaskStatus.FAILED)
        pending = sum(1 for t in tasks if t.status == TaskStatus.PENDING)
        
        current = None
        for t in tasks:
            if t.status not in (TaskStatus.PENDING, TaskStatus.COMPLETED, TaskStatus.FAILED):
                current = t
                break
        
        return QueueStatus(
            total_tasks=len(tasks),
            completed=completed,
            failed=failed,
            pending=pending,
            current_task=current,
            tasks=tasks,
        )

    async def start_worker(self) -> None:
        """Start background worker to process queue."""
        if self._running:
            return
        
        self._running = True
        self._worker_task = asyncio.create_task(self._process_queue())

    async def stop_worker(self) -> None:
        """Stop background worker."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    async def _process_queue(self) -> None:
        """Process tasks from queue."""
        while self._running:
            try:
                task_id = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            
            task = self._tasks.get(task_id)
            if not task:
                continue
            
            # Update status
            task.status = TaskStatus.ANALYZING
            task.progress = 0.1
            
            try:
                request = ImprovementRequest(
                    file_path=task.file_path,
                    issue=task.issue,
                )
                
                def update_progress(event: str, _: str) -> None:
                    if event == "plan":
                        task.status = TaskStatus.PLANNING
                        task.progress = 0.3
                    elif event == "code":
                        task.status = TaskStatus.CODING
                        task.progress = 0.6
                    elif event == "validate":
                        task.status = TaskStatus.VALIDATING
                        task.progress = 0.8
                
                result = await self.improve_file(request, on_chunk=update_progress)
                
                task.result = result
                task.status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
                task.progress = 1.0
                task.error = result.error
                
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.progress = 1.0

    def clear_completed_tasks(self) -> int:
        """Clear completed and failed tasks from queue."""
        to_remove = [
            tid for tid, t in self._tasks.items()
            if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
        ]
        for tid in to_remove:
            del self._tasks[tid]
        return len(to_remove)
