"""Project Analyzer - комплексный анализ любого проекта.

Анализирует структуру, качество кода, безопасность и архитектуру.
Генерирует детальный отчёт с рекомендациями.

Production-ready with:
- Pre-compiled regex patterns
- Proper input validation
- Logging for debugging
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

from src.infrastructure.analyzer.models import (
    ArchitectureInfo,
    FileMetrics,
    ProjectAnalysis,
    SecurityIssue,
)
from src.infrastructure.analyzer.architecture import analyze_architecture
from src.infrastructure.analyzer.code_smells import find_code_smells
from src.infrastructure.analyzer.file_metrics import compute_file_metrics
from src.infrastructure.analyzer.security_scanner import check_file_security

logger = logging.getLogger(__name__)

# Number of workers for parallel file processing
MAX_WORKERS = 8


class ProjectAnalyzer:
    """Анализатор проектов.
    
    Проводит комплексный анализ:
    - Структура и размер
    - Качество кода (метрики)
    - Безопасность (уязвимости)
    - Архитектура (зависимости)
    """
    
    # Расширения по языкам
    LANGUAGE_EXTENSIONS = {
        "Python": [".py"],
        "JavaScript": [".js", ".jsx", ".mjs"],
        "TypeScript": [".ts", ".tsx"],
        "HTML": [".html", ".htm"],
        "CSS": [".css", ".scss", ".sass"],
        "JSON": [".json"],
        "YAML": [".yaml", ".yml"],
        "Markdown": [".md", ".mdx"],
        "Shell": [".sh", ".bash"],
        "SQL": [".sql"],
        "TOML": [".toml"],
    }
    
    # Директории для игнорирования
    IGNORE_DIRS = {
        ".git", ".venv", "venv", "node_modules", "__pycache__",
        ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist",
        "build", ".next", "coverage", ".tox", "eggs",
    }

    def __init__(self, max_file_size: int = 1024 * 1024):
        """Инициализация анализатора.

        Args:
            max_file_size: Максимальный размер файла для анализа (байты)
        """
        if max_file_size <= 0:
            raise ValueError("max_file_size must be positive")
        self.max_file_size = max_file_size

    def analyze(self, project_path: str) -> ProjectAnalysis:
        """Полный анализ проекта.
        
        Args:
            project_path: Путь к проекту
            
        Returns:
            ProjectAnalysis с результатами
            
        Raises:
            ValueError: If path is invalid or inaccessible
        """
        if not project_path:
            raise ValueError("Project path cannot be empty")
        
        path = Path(project_path).resolve()
        
        if not path.exists():
            raise ValueError(f"Project path does not exist: {project_path}")
        
        if not path.is_dir():
            raise ValueError(f"Project path is not a directory: {project_path}")
        
        # Check read permission
        if not os.access(path, os.R_OK):
            raise ValueError(f"No read permission for: {project_path}")
        
        logger.info(f"Analyzing project: {path}")
        
        analysis = ProjectAnalysis(
            project_path=str(path),
            project_name=path.name,
            analyzed_at=datetime.now().isoformat(),
        )
        
        # Собираем файлы
        files = self._collect_files(path)
        analysis.total_files = len(files)
        
        # File content cache to avoid reading files multiple times
        file_cache: dict[Path, str] = {}
        
        # Анализируем файлы параллельно для производительности
        def analyze_single_file(file_path: Path) -> tuple[FileMetrics | None, list[SecurityIssue], str | None]:
            """Analyze a single file and return results."""
            try:
                metrics = compute_file_metrics(file_path, path)
                security_issues = check_file_security(file_path, path)
                lang = self._detect_language(file_path)
                return metrics, security_issues, lang
            except Exception as e:
                logger.debug(f"Error analyzing {file_path}: {e}")
                return None, [], None
        
        # Use ThreadPoolExecutor for I/O-bound file operations
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_file = {
                executor.submit(analyze_single_file, file_path): file_path
                for file_path in files
            }
            
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    metrics, security_issues, lang = future.result()
                    
                    if metrics:
                        analysis.file_metrics.append(metrics)
                        analysis.total_lines += metrics.lines_total
                        analysis.total_code_lines += metrics.lines_code
                    
                    if lang:
                        analysis.languages[lang] = analysis.languages.get(lang, 0) + 1
                    
                    analysis.security_issues.extend(security_issues)
                    
                except Exception as e:
                    logger.debug(f"Failed to get result for {file_path}: {e}")
        
        # Анализ архитектуры
        analysis.architecture = analyze_architecture(path, files)

        # Подсчёт code smells
        analysis.code_smells = find_code_smells(files, path)
        
        # Расчёт scores
        analysis.security_score = self._calculate_security_score(analysis.security_issues)
        analysis.quality_score = self._calculate_quality_score(analysis)
        
        # Генерация рекомендаций
        analysis.recommendations = self._generate_recommendations(analysis)
        analysis.strengths = self._identify_strengths(analysis)
        analysis.weaknesses = self._identify_weaknesses(analysis)
        
        return analysis
    
    def _collect_files(self, path: Path) -> list[Path]:
        """Собирает все релевантные файлы."""
        files = []
        
        for p in path.rglob("*"):
            if not p.is_file():
                continue
            
            # Проверяем игнорируемые директории
            if any(ignored in p.parts for ignored in self.IGNORE_DIRS):
                continue
            
            # Проверяем размер
            try:
                if p.stat().st_size > self.max_file_size:
                    continue
            except OSError:
                continue
            
            # Проверяем расширение
            if self._detect_language(p):
                files.append(p)
        
        return files
    
    def _detect_language(self, file_path: Path) -> str | None:
        """Определяет язык по расширению."""
        suffix = file_path.suffix.lower()
        for lang, extensions in self.LANGUAGE_EXTENSIONS.items():
            if suffix in extensions:
                return lang
        return None
    
    def _calculate_security_score(self, issues: list[SecurityIssue]) -> int:
        """Рассчитывает security score."""
        score = 100
        
        # Считаем по категориям с лимитами
        critical_count = sum(1 for i in issues if i.severity == "critical")
        high_count = sum(1 for i in issues if i.severity == "high")
        medium_count = sum(1 for i in issues if i.severity == "medium")
        low_count = sum(1 for i in issues if i.severity == "low")
        
        # Critical/High влияют сильно
        score -= min(critical_count * 10, 50)  # Max -50 for criticals
        score -= min(high_count * 5, 25)  # Max -25 for high
        
        # Medium/Low влияют слабо (с лимитом)
        score -= min(medium_count * 0.5, 15)  # Max -15 for medium
        score -= min(low_count * 0.1, 5)  # Max -5 for low
        
        return max(0, int(score))
    
    def _calculate_quality_score(self, analysis: ProjectAnalysis) -> int:
        """Рассчитывает quality score."""
        score = 70  # Начинаем с 70 (neutral)
        
        # Штрафы за code smells (с лимитом)
        smells_penalty = min(len(analysis.code_smells) * 2, 15)
        score -= smells_penalty
        
        # Большие файлы (лимит)
        large_files = [f for f in analysis.file_metrics if f.lines_code > 500]
        score -= min(len(large_files) * 3, 15)
        
        # Высокая сложность (лимит)
        complex_files = [f for f in analysis.file_metrics if f.complexity > 20]
        score -= min(len(complex_files) * 3, 10)
        
        # Бонусы
        if analysis.total_files > 10:
            score += 10  # Modular structure
        
        if any("test" in f.path.lower() for f in analysis.file_metrics):
            score += 15  # Has tests
        
        if len(analysis.architecture.entry_points) > 0:
            score += 5  # Clear entry points
        
        if len(analysis.languages) > 1:
            score += 5  # Multi-language (full-stack)
        
        # Ratio of comments
        total_comments = sum(f.lines_comment for f in analysis.file_metrics)
        if analysis.total_code_lines > 0:
            comment_ratio = total_comments / analysis.total_code_lines
            if comment_ratio > 0.1:
                score += 5  # Good documentation
        
        return max(0, min(100, score))
    
    def _generate_recommendations(self, analysis: ProjectAnalysis) -> list[str]:
        """Генерирует рекомендации."""
        recs = []
        
        # Security
        critical_issues = [i for i in analysis.security_issues if i.severity == "critical"]
        if critical_issues:
            recs.append(f"🔴 КРИТИЧНО: Исправить {len(critical_issues)} критических проблем безопасности")
        
        high_issues = [i for i in analysis.security_issues if i.severity == "high"]
        if high_issues:
            recs.append(f"🟠 ВЫСОКИЙ: Устранить {len(high_issues)} проблем безопасности высокой степени")
        
        # Quality
        if len(analysis.code_smells) > 5:
            recs.append(f"♻️ Рефакторинг: Обнаружено {len(analysis.code_smells)} code smells")
        
        # Structure
        large_files = [f for f in analysis.file_metrics if f.lines_code > 500]
        if large_files:
            recs.append(f"📦 Разбить большие файлы: {len(large_files)} файлов превышают 500 строк")
        
        # Tests
        test_files = [f for f in analysis.file_metrics if "test" in f.path.lower()]
        if not test_files:
            recs.append("🧪 Добавить тесты: Тестовые файлы не найдены")
        
        # Documentation
        doc_files = [f for f in analysis.file_metrics if f.path.endswith(".md")]
        if not doc_files:
            recs.append("📝 Добавить документацию: Markdown-файлы не найдены")
        
        return recs[:10]
    
    def _identify_strengths(self, analysis: ProjectAnalysis) -> list[str]:
        """Определяет сильные стороны."""
        strengths = []
        
        if analysis.security_score >= 80:
            strengths.append("✅ Хорошие практики безопасности")
        
        if analysis.quality_score >= 70:
            strengths.append("✅ Приемлемое качество кода")
        
        if len(analysis.languages) > 1:
            strengths.append(f"✅ Мультиязычный проект ({', '.join(analysis.languages.keys())})")
        
        if "tests" in str(analysis.architecture.layers.keys()):
            strengths.append("✅ Есть отдельная директория для тестов")
        
        if len(analysis.architecture.entry_points) > 0:
            strengths.append("✅ Определены точки входа")
        
        avg_complexity = sum(f.complexity for f in analysis.file_metrics) / max(1, len(analysis.file_metrics))
        if avg_complexity < 10:
            strengths.append("✅ Низкая средняя сложность")
        
        return strengths
    
    def _identify_weaknesses(self, analysis: ProjectAnalysis) -> list[str]:
        """Определяет слабые стороны."""
        weaknesses = []
        
        if analysis.security_score < 50:
            weaknesses.append("❌ Критические проблемы безопасности")
        elif analysis.security_score < 80:
            weaknesses.append("⚠️ Безопасность требует улучшения")
        
        if analysis.quality_score < 50:
            weaknesses.append("❌ Низкое качество кода")
        elif analysis.quality_score < 70:
            weaknesses.append("⚠️ Качество требует улучшения")
        
        if len(analysis.code_smells) > 10:
            weaknesses.append("⚠️ Обнаружено много code smells")
        
        large_files = [f for f in analysis.file_metrics if f.lines_code > 500]
        if large_files:
            weaknesses.append(f"⚠️ {len(large_files)} файлов слишком большие")
        
        if not analysis.architecture.entry_points:
            weaknesses.append("⚠️ Нет явных точек входа")
        
        return weaknesses
