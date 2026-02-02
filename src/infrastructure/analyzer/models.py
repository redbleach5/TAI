"""Project analysis data models.

Dataclasses for analyzer results: FileMetrics, SecurityIssue,
ArchitectureInfo, ProjectAnalysis. Used by ProjectAnalyzer and ReportGenerator.
"""

from dataclasses import dataclass, field


@dataclass
class FileMetrics:
    """Метрики одного файла."""
    path: str
    lines_total: int = 0
    lines_code: int = 0
    lines_comment: int = 0
    lines_blank: int = 0
    functions: int = 0
    classes: int = 0
    complexity: int = 0  # Cyclomatic complexity estimate
    imports: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


@dataclass
class SecurityIssue:
    """Проблема безопасности."""
    severity: str  # critical, high, medium, low
    file: str
    line: int
    issue: str
    recommendation: str


@dataclass
class ArchitectureInfo:
    """Информация об архитектуре."""
    layers: dict[str, list[str]] = field(default_factory=dict)
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    entry_points: list[str] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)


@dataclass
class ProjectAnalysis:
    """Результат полного анализа проекта."""
    project_path: str
    project_name: str
    analyzed_at: str

    # Общая статистика
    total_files: int = 0
    total_lines: int = 0
    total_code_lines: int = 0
    languages: dict[str, int] = field(default_factory=dict)

    # Метрики по файлам
    file_metrics: list[FileMetrics] = field(default_factory=list)

    # Безопасность
    security_issues: list[SecurityIssue] = field(default_factory=list)
    security_score: int = 100  # 0-100

    # Архитектура
    architecture: ArchitectureInfo = field(default_factory=ArchitectureInfo)

    # Качество
    quality_score: int = 0  # 0-100
    code_smells: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    # Сильные и слабые стороны
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
