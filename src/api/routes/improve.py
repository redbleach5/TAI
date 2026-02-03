"""Self-improvement API routes."""

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.api.dependencies import get_improvement_use_case, limiter
from src.application.improvement import (
    AnalyzeRequest,
    ImprovementRequest,
    SelfImprovementUseCase,
)

router = APIRouter(prefix="/improve", tags=["improve"])


# Request/Response models


class AnalyzeRequestModel(BaseModel):
    """Request to analyze project."""

    path: str = "."
    include_linter: bool = True
    use_llm: bool = False


class ImprovementRequestModel(BaseModel):
    """Request to improve file."""

    file_path: str
    issue: dict | None = None
    auto_write: bool = True
    max_retries: int = 3
    related_files: list[str] = []  # B3: imports, tests for context
    # B6: inline selection (1-based inclusive); when set, only that range is improved
    selection_start_line: int | None = None
    selection_end_line: int | None = None


class AddTaskRequestModel(BaseModel):
    """Request to add task to queue."""

    file_path: str
    issue: dict | None = None


# Endpoints


@router.post("/analyze")
@limiter.limit("25/minute")
async def analyze_project(
    request: Request,
    body: AnalyzeRequestModel,
    use_case: SelfImprovementUseCase = Depends(get_improvement_use_case),
):
    """Analyze project for issues and improvement suggestions.

    Uses current workspace path. Runs analysis in workspace directory.

    Returns:
        - total_files, total_lines, total_functions, total_classes
        - avg_complexity
        - issues: list of found issues
        - suggestions: prioritized improvement suggestions
    """
    req = AnalyzeRequest(
        path=body.path,
        include_linter=body.include_linter,
        use_llm=body.use_llm,
    )
    result = await use_case.analyze(req)

    return {
        "total_files": result.total_files,
        "total_lines": result.total_lines,
        "total_functions": result.total_functions,
        "total_classes": result.total_classes,
        "avg_complexity": result.avg_complexity,
        "issues": [
            {
                "file": i.file,
                "line": i.line,
                "type": i.issue_type,
                "severity": i.severity,
                "message": i.message,
                "suggestion": i.suggestion,
            }
            for i in result.issues
        ],
        "suggestions": result.suggestions,
    }


@router.post("/run")
@limiter.limit("25/minute")  # 5/min слишком жёстко для одного пользователя
async def run_improvement(
    request: Request,
    body: ImprovementRequestModel,
    use_case: SelfImprovementUseCase = Depends(get_improvement_use_case),
):
    """Run improvement on single file.

    Uses current workspace path. Runs improvement in workspace directory.

    This endpoint runs the full improvement workflow:
    1. Read original file
    2. Generate improvement plan
    3. Generate improved code
    4. Validate (syntax check)
    5. Write to file (with backup)
    6. Retry if validation fails (up to max_retries)
    """
    req = ImprovementRequest(
        file_path=body.file_path,
        issue=body.issue,
        auto_write=body.auto_write,
        max_retries=body.max_retries,
        related_files=body.related_files,
        selection_start_line=body.selection_start_line,
        selection_end_line=body.selection_end_line,
    )
    result = await use_case.improve_file(req)

    return {
        "success": result.success,
        "file_path": result.file_path,
        "backup_path": result.backup_path,
        "validation_output": result.validation_output,
        "error": result.error,
        "retries": result.retries,
        "proposed_full_content": result.proposed_full_content,
        "selection_start_line": result.selection_start_line,
        "selection_end_line": result.selection_end_line,
    }


@router.post("/run/stream")
@limiter.limit("25/minute")
async def run_improvement_stream(
    request: Request,
    body: ImprovementRequestModel,
    use_case: SelfImprovementUseCase = Depends(get_improvement_use_case),
):
    """Run improvement with streaming output via SSE."""
    req = ImprovementRequest(
        file_path=body.file_path,
        issue=body.issue,
        auto_write=body.auto_write,
        max_retries=body.max_retries,
        related_files=body.related_files,
        selection_start_line=body.selection_start_line,
        selection_end_line=body.selection_end_line,
    )

    async def generate() -> AsyncIterator[str]:
        async for event in use_case.improve_file_stream(req):
            import json

            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# Task Queue Endpoints


@router.post("/queue/add")
@limiter.limit("30/minute")
async def add_to_queue(
    request: Request,
    body: AddTaskRequestModel,
    use_case: SelfImprovementUseCase = Depends(get_improvement_use_case),
):
    """Add improvement task to queue."""
    req = ImprovementRequest(
        file_path=body.file_path,
        issue=body.issue,
    )
    task_id = use_case.add_task(req)
    return {"task_id": task_id}


@router.get("/queue/status")
@limiter.limit("60/minute")
async def get_queue_status(
    request: Request,
    use_case: SelfImprovementUseCase = Depends(get_improvement_use_case),
):
    """Get queue status."""
    status = use_case.get_queue_status()
    return {
        "total_tasks": status.total_tasks,
        "completed": status.completed,
        "failed": status.failed,
        "pending": status.pending,
        "current_task": {
            "id": status.current_task.id,
            "file_path": status.current_task.file_path,
            "status": status.current_task.status.value,
            "progress": status.current_task.progress,
        }
        if status.current_task
        else None,
        "tasks": [
            {
                "id": t.id,
                "file_path": t.file_path,
                "status": t.status.value,
                "progress": t.progress,
                "error": t.error,
            }
            for t in status.tasks
        ],
    }


@router.get("/queue/task/{task_id}")
@limiter.limit("60/minute")
async def get_task(
    request: Request,
    task_id: str,
    use_case: SelfImprovementUseCase = Depends(get_improvement_use_case),
):
    """Get specific task status."""
    task = use_case.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "id": task.id,
        "file_path": task.file_path,
        "status": task.status.value,
        "progress": task.progress,
        "error": task.error,
        "result": {
            "success": task.result.success,
            "backup_path": task.result.backup_path,
            "validation_output": task.result.validation_output,
            "error": task.result.error,
            "retries": task.result.retries,
        }
        if task.result
        else None,
    }


@router.post("/queue/start")
@limiter.limit("25/minute")
async def start_worker(
    request: Request,
    use_case: SelfImprovementUseCase = Depends(get_improvement_use_case),
):
    """Start background worker to process queue."""
    await use_case.start_worker()
    return {"status": "worker_started"}


@router.post("/queue/stop")
@limiter.limit("25/minute")
async def stop_worker(
    request: Request,
    use_case: SelfImprovementUseCase = Depends(get_improvement_use_case),
):
    """Stop background worker."""
    await use_case.stop_worker()
    return {"status": "worker_stopped"}


@router.post("/queue/clear")
@limiter.limit("25/minute")
async def clear_completed(
    request: Request,
    use_case: SelfImprovementUseCase = Depends(get_improvement_use_case),
):
    """Clear completed and failed tasks from queue."""
    count = use_case.clear_completed_tasks()
    return {"cleared": count}
