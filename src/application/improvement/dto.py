"""DTOs for self-improvement use case."""

from dataclasses import dataclass, field
from enum import Enum


class TaskStatus(str, Enum):
    """Status of improvement task."""
    
    PENDING = "pending"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    CODING = "coding"
    VALIDATING = "validating"
    WRITING = "writing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AnalyzeRequest:
    """Request to analyze project or file."""
    
    path: str = "."
    include_linter: bool = True
    use_llm: bool = False


@dataclass
class IssueDTO:
    """Code issue DTO."""
    
    file: str
    line: int | None
    issue_type: str
    severity: str
    message: str
    suggestion: str | None = None


@dataclass
class FileAnalysisDTO:
    """File analysis DTO."""
    
    path: str
    lines: int
    functions: int
    classes: int
    complexity: int
    issues: list[IssueDTO] = field(default_factory=list)


@dataclass
class AnalyzeResponse:
    """Response from project analysis."""
    
    total_files: int
    total_lines: int
    total_functions: int
    total_classes: int
    avg_complexity: float
    issues: list[IssueDTO] = field(default_factory=list)
    suggestions: list[dict] = field(default_factory=list)


@dataclass
class ImprovementRequest:
    """Request to improve specific file/issue."""
    
    file_path: str
    issue: dict | None = None  # If None, general improvement
    auto_write: bool = True
    max_retries: int = 3
    related_files: list[str] = field(default_factory=list)  # B3: imports, tests for context
    # B6: inline selection (1-based inclusive); when set, only that range is improved
    selection_start_line: int | None = None
    selection_end_line: int | None = None


@dataclass
class ImprovementResponse:
    """Response from improvement attempt."""
    
    success: bool
    file_path: str
    backup_path: str | None = None
    improved_code: str | None = None
    validation_output: str | None = None
    error: str | None = None
    retries: int = 0
    # B6: full file content after edit (for diff preview / apply in UI)
    proposed_full_content: str | None = None
    selection_start_line: int | None = None
    selection_end_line: int | None = None


@dataclass
class ImprovementTask:
    """Task in improvement queue."""
    
    id: str
    file_path: str
    issue: dict | None
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    result: ImprovementResponse | None = None
    error: str | None = None


@dataclass
class QueueStatus:
    """Status of task queue."""
    
    total_tasks: int
    completed: int
    failed: int
    pending: int
    current_task: ImprovementTask | None = None
    tasks: list[ImprovementTask] = field(default_factory=list)
