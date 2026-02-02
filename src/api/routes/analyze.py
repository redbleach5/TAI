"""Project Analysis API - анализ любого проекта."""

import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from src.api.dependencies import get_analyzer, get_llm_adapter, get_model_selector, get_rag_adapter, get_store, limiter
from src.api.store import ProjectsStore
from src.application.analysis.deep_analyzer import DeepAnalyzer, summary_from_report
from src.domain.ports.llm import LLMPort
from src.domain.services.model_selector import ModelSelector
from src.infrastructure.analyzer.project_analyzer import ProjectAnalysis, ProjectAnalyzer
from src.infrastructure.analyzer.report_generator import ReportGenerator
from src.infrastructure.rag.chromadb_adapter import ChromaDBRAGAdapter


router = APIRouter(prefix="/analyze", tags=["analyze"])


class AnalyzeRequest(BaseModel):
    """Запрос на анализ проекта."""
    path: str
    generate_report: bool = True


class AnalyzeResponse(BaseModel):
    """Ответ с результатами анализа."""
    project_name: str
    project_path: str
    analyzed_at: str
    
    # Scores
    security_score: int
    quality_score: int
    overall_score: int
    
    # Statistics
    total_files: int
    total_lines: int
    total_code_lines: int
    languages: dict[str, int]
    
    # Issues
    security_issues_count: int
    code_smells_count: int
    
    # Summary
    strengths: list[str]
    weaknesses: list[str]
    recommendations: list[str]
    
    # Report path (if generated)
    report_path: str | None = None


class SecurityIssueDTO(BaseModel):
    """Security issue DTO."""
    severity: str
    file: str
    line: int
    issue: str
    recommendation: str


class DetailedAnalyzeResponse(AnalyzeResponse):
    """Детальный ответ с полными данными."""
    security_issues: list[SecurityIssueDTO]
    code_smells: list[str]
    architecture_layers: dict[str, int]
    entry_points: list[str]
    config_files: list[str]


def _analysis_to_response(
    analysis: ProjectAnalysis,
    report_path: str | None = None
) -> AnalyzeResponse:
    """Конвертирует анализ в ответ API."""
    return AnalyzeResponse(
        project_name=analysis.project_name,
        project_path=analysis.project_path,
        analyzed_at=analysis.analyzed_at,
        security_score=analysis.security_score,
        quality_score=analysis.quality_score,
        overall_score=(analysis.security_score + analysis.quality_score) // 2,
        total_files=analysis.total_files,
        total_lines=analysis.total_lines,
        total_code_lines=analysis.total_code_lines,
        languages=analysis.languages,
        security_issues_count=len(analysis.security_issues),
        code_smells_count=len(analysis.code_smells),
        strengths=analysis.strengths,
        weaknesses=analysis.weaknesses,
        recommendations=analysis.recommendations,
        report_path=report_path,
    )


def _analysis_to_detailed_response(
    analysis: ProjectAnalysis,
    report_path: str | None = None
) -> DetailedAnalyzeResponse:
    """Конвертирует анализ в детальный ответ."""
    return DetailedAnalyzeResponse(
        project_name=analysis.project_name,
        project_path=analysis.project_path,
        analyzed_at=analysis.analyzed_at,
        security_score=analysis.security_score,
        quality_score=analysis.quality_score,
        overall_score=(analysis.security_score + analysis.quality_score) // 2,
        total_files=analysis.total_files,
        total_lines=analysis.total_lines,
        total_code_lines=analysis.total_code_lines,
        languages=analysis.languages,
        security_issues_count=len(analysis.security_issues),
        code_smells_count=len(analysis.code_smells),
        strengths=analysis.strengths,
        weaknesses=analysis.weaknesses,
        recommendations=analysis.recommendations,
        report_path=report_path,
        security_issues=[
            SecurityIssueDTO(
                severity=i.severity,
                file=i.file,
                line=i.line,
                issue=i.issue,
                recommendation=i.recommendation,
            )
            for i in analysis.security_issues
        ],
        code_smells=analysis.code_smells,
        architecture_layers={
            layer: len(files)
            for layer, files in analysis.architecture.layers.items()
        },
        entry_points=analysis.architecture.entry_points,
        config_files=analysis.architecture.config_files,
    )


def _resolve_path_allowed(path_str: str, store: ProjectsStore) -> Path:
    """Resolve path and ensure it is under workspace or cwd (security)."""
    root_str = None
    current = store.get_current()
    if current:
        root_str = current.path
    if not root_str:
        root_str = str(Path.cwd().resolve())
    root = Path(root_str).resolve()
    path = Path(path_str).expanduser().resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise HTTPException(
            status_code=403,
            detail=f"Path must be inside workspace: {root_str}",
        )
    return path


@router.post("/project")
@limiter.limit("10/minute")
async def analyze_project(
    request: Request,
    body: AnalyzeRequest,
    store: ProjectsStore = Depends(get_store),
    analyzer: ProjectAnalyzer = Depends(get_analyzer),
) -> AnalyzeResponse:
    """Анализирует проект и возвращает результаты.
    
    Path must be inside current workspace (or cwd if no workspace set).
    
    Args:
        body: Путь к проекту и опции
        
    Returns:
        Результаты анализа с scores и recommendations
    """
    path = _resolve_path_allowed(body.path, store)
    
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {body.path}")
    
    if not path.is_dir():
        raise HTTPException(status_code=400, detail="Path must be a directory")
    
    # Запускаем анализ в фоне
    analysis = await asyncio.to_thread(analyzer.analyze, str(path))
    
    # Генерируем отчёт если нужно
    report_path = None
    if body.generate_report:
        generator = ReportGenerator()
        report_file = Path("output") / "reports" / f"{analysis.project_name}_analysis.md"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        generator.save_report(analysis, report_file)
        report_path = str(report_file)
    
    return _analysis_to_response(analysis, report_path)


@router.post("/project/detailed")
@limiter.limit("20/minute")
async def analyze_project_detailed(
    request: Request,
    body: AnalyzeRequest,
    store: ProjectsStore = Depends(get_store),
    analyzer: ProjectAnalyzer = Depends(get_analyzer),
) -> DetailedAnalyzeResponse:
    """Детальный анализ проекта со всеми данными.
    
    Включает полный список security issues, code smells и архитектуру.
    Path must be inside current workspace.
    """
    path = _resolve_path_allowed(body.path, store)
    
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {body.path}")
    
    if not path.is_dir():
        raise HTTPException(status_code=400, detail="Path must be a directory")
    
    analysis = await asyncio.to_thread(analyzer.analyze, str(path))
    
    report_path = None
    if body.generate_report:
        generator = ReportGenerator()
        report_file = Path("output") / "reports" / f"{analysis.project_name}_analysis.md"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        generator.save_report(analysis, report_file)
        report_path = str(report_file)
    
    return _analysis_to_detailed_response(analysis, report_path)


@router.post("/project/report", response_class=PlainTextResponse)
@limiter.limit("10/minute")
async def get_project_report(
    request: Request,
    body: AnalyzeRequest,
    store: ProjectsStore = Depends(get_store),
    analyzer: ProjectAnalyzer = Depends(get_analyzer),
) -> str:
    """Генерирует и возвращает Markdown отчёт напрямую.
    
    Path must be inside current workspace.
    Returns:
        Markdown отчёт как текст
    """
    path = _resolve_path_allowed(body.path, store)
    
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {body.path}")
    
    analysis = await asyncio.to_thread(analyzer.analyze, str(path))
    
    generator = ReportGenerator()
    return generator.generate_markdown(analysis)


class DeepAnalyzeRequest(BaseModel):
    """Запрос на глубокий анализ (Cursor-like)."""
    path: str


class DeepAnalyzeResponse(BaseModel):
    """Ответ глубокого анализа: полный отчёт в файле проекта, в чат — краткая сводка (как Cursor)."""
    report_path: str  # относительный путь в проекте, например docs/ANALYSIS_REPORT.md
    summary: str      # краткая сводка для чата




@router.post("/project/deep")
@limiter.limit("15/minute")  # 3/min слишком жёстко для одного пользователя
async def get_project_deep_report(
    request: Request,
    body: DeepAnalyzeRequest,
    store: ProjectsStore = Depends(get_store),
    llm: LLMPort = Depends(get_llm_adapter),
    model_selector: ModelSelector = Depends(get_model_selector),
    rag: ChromaDBRAGAdapter = Depends(get_rag_adapter),
    analyzer: ProjectAnalyzer = Depends(get_analyzer),
) -> DeepAnalyzeResponse:
    """Глубокий анализ уровня Cursor AI: статика + RAG + LLM.
    
    Полный отчёт сохраняется в проекте (docs/ANALYSIS_REPORT.md).
    В ответе — краткая сводка для чата (как в Cursor).
    Path must be inside current workspace.
    Требует: LLM (Ollama/LM Studio), опционально RAG (индексация workspace).
    """
    path = _resolve_path_allowed(body.path, store)
    
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {body.path}")
    
    if not path.is_dir():
        raise HTTPException(status_code=400, detail="Path must be a directory")
    
    deep_analyzer = DeepAnalyzer(
        llm=llm,
        model_selector=model_selector,
        rag=rag,
        analyzer=analyzer,
    )
    full_md = await deep_analyzer.analyze(str(path))
    
    # Сохраняем полный отчёт в проекте (как Cursor)
    report_rel = "docs/ANALYSIS_REPORT.md"
    report_file = path / report_rel
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(full_md, encoding="utf-8")
    
    summary = summary_from_report(full_md, report_rel)
    return DeepAnalyzeResponse(report_path=report_rel, summary=summary)


@router.post("/security")
@limiter.limit("20/minute")
async def check_security(
    request: Request,
    body: AnalyzeRequest,
    store: ProjectsStore = Depends(get_store),
    analyzer: ProjectAnalyzer = Depends(get_analyzer),
):
    """Быстрая проверка безопасности проекта.
    
    Path must be inside current workspace.
    Returns:
        Только security-related данные
    """
    path = _resolve_path_allowed(body.path, store)
    
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {body.path}")
    
    analysis = await asyncio.to_thread(analyzer.analyze, str(path))
    
    # Группируем по severity
    by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for issue in analysis.security_issues:
        by_severity[issue.severity] += 1
    
    return {
        "project": analysis.project_name,
        "security_score": analysis.security_score,
        "total_issues": len(analysis.security_issues),
        "by_severity": by_severity,
        "critical_issues": [
            {
                "file": i.file,
                "line": i.line,
                "issue": i.issue,
                "recommendation": i.recommendation,
            }
            for i in analysis.security_issues
            if i.severity == "critical"
        ],
        "high_issues": [
            {
                "file": i.file,
                "line": i.line,
                "issue": i.issue,
                "recommendation": i.recommendation,
            }
            for i in analysis.security_issues
            if i.severity == "high"
        ][:10],  # Limit
    }


@router.get("/compare")
@limiter.limit("20/minute")
async def compare_projects(
    request: Request,
    path1: str,
    path2: str,
    analyzer: ProjectAnalyzer = Depends(get_analyzer),
):
    """Сравнивает два проекта.
    
    Returns:
        Сравнительный анализ двух проектов
    """
    p1 = Path(path1).expanduser().resolve()
    p2 = Path(path2).expanduser().resolve()
    
    if not p1.exists() or not p2.exists():
        raise HTTPException(status_code=404, detail="One or both paths not found")
    
    # Анализируем параллельно
    analysis1, analysis2 = await asyncio.gather(
        asyncio.to_thread(analyzer.analyze, str(p1)),
        asyncio.to_thread(analyzer.analyze, str(p2)),
    )
    
    return {
        "comparison": {
            "project1": {
                "name": analysis1.project_name,
                "security_score": analysis1.security_score,
                "quality_score": analysis1.quality_score,
                "total_files": analysis1.total_files,
                "total_lines": analysis1.total_lines,
                "languages": analysis1.languages,
            },
            "project2": {
                "name": analysis2.project_name,
                "security_score": analysis2.security_score,
                "quality_score": analysis2.quality_score,
                "total_files": analysis2.total_files,
                "total_lines": analysis2.total_lines,
                "languages": analysis2.languages,
            },
        },
        "winner": {
            "security": analysis1.project_name if analysis1.security_score > analysis2.security_score else analysis2.project_name,
            "quality": analysis1.project_name if analysis1.quality_score > analysis2.quality_score else analysis2.project_name,
            "overall": analysis1.project_name if (analysis1.security_score + analysis1.quality_score) > (analysis2.security_score + analysis2.quality_score) else analysis2.project_name,
        },
    }
