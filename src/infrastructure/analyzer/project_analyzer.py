"""Project Analyzer - комплексный анализ любого проекта.

Анализирует структуру, качество кода, безопасность и архитектуру.
Генерирует детальный отчёт с рекомендациями.

Production-ready with:
- Pre-compiled regex patterns
- Proper input validation
- Logging for debugging
"""

import ast
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Number of workers for parallel file processing
MAX_WORKERS = 8


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
    
    # Паттерны безопасности (используем word boundaries для точности)
    SECURITY_PATTERNS = [
        # Critical - только реальные вызовы функций, не строки/комментарии
        (r"(?<!['\"\w])eval\s*\([^)]+\)", "critical", "Вызов eval()", "Использовать ast.literal_eval() или безопасные альтернативы"),
        (r"(?<![\w.])exec\s*\([^)]+\)", "critical", "Вызов exec()", "Переструктурировать код, избегать динамического выполнения"),
        (r"subprocess\.(call|run|Popen).*shell\s*=\s*True", "critical", "Риск shell injection", "Использовать shell=False и передавать аргументы списком"),
        (r"os\.system\s*\([^)]+\)", "critical", "Выполнение OS-команд", "Использовать subprocess с shell=False"),
        
        # High
        (r"pickle\.loads?\s*\(", "high", "Десериализация pickle", "Использовать JSON или безопасный формат"),
        (r"yaml\.load\s*\([^)]*Loader\s*=\s*None", "high", "Небезопасная загрузка YAML", "Использовать yaml.safe_load()"),
        (r"(?<!['\"\w])__import__\s*\(", "high", "Динамический импорт", "Использовать статические импорты"),
        (r"password\s*=\s*['\"][a-zA-Z0-9]{8,}['\"]", "high", "Пароль в коде", "Использовать переменные окружения или secrets manager"),
        (r"api[_-]?key\s*=\s*['\"][a-zA-Z0-9]{16,}['\"]", "high", "API-ключ в коде", "Использовать переменные окружения"),
        
        # Medium - отключаем слишком шумные паттерны
        (r"verify\s*=\s*False", "medium", "Отключена проверка SSL", "Включить проверку SSL"),
        
        # Low
        (r"\b(TODO|FIXME|HACK|XXX)\b:", "low", "Маркер TODO/FIXME", "Исправить отложенные задачи"),
    ]
    
    # Code smells
    CODE_SMELL_PATTERNS = [
        (r"def\s+\w+\([^)]{100,}\)", "Длинный список параметров (>5)"),
        (r"if\s+.*:\s*\n\s+if\s+.*:\s*\n\s+if", "Глубокая вложенность (3+ уровня)"),
        (r"except\s*:", "Пустой except"),
        (r"from\s+\w+\s+import\s+\*", "Импорт через *"),
        (r"global\s+\w+", "Использование global"),
        (r"#.*type:\s*ignore", "Комментарий type: ignore"),
    ]
    
    def __init__(self, max_file_size: int = 1024 * 1024):
        """Инициализация анализатора.
        
        Args:
            max_file_size: Максимальный размер файла для анализа (байты)
        """
        if max_file_size <= 0:
            raise ValueError("max_file_size must be positive")
        self.max_file_size = max_file_size
        
        # Pre-compile security patterns for performance
        self._compiled_security_patterns = [
            (re.compile(pattern, re.IGNORECASE), severity, issue, rec)
            for pattern, severity, issue, rec in self.SECURITY_PATTERNS
        ]
        
        # Pre-compile code smell patterns
        self._compiled_smell_patterns = [
            (re.compile(pattern, re.MULTILINE), desc)
            for pattern, desc in self.CODE_SMELL_PATTERNS
        ]
    
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
                metrics = self._analyze_file(file_path, path)
                security_issues = self._check_security(file_path, path)
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
        analysis.architecture = self._analyze_architecture(path, files)
        
        # Подсчёт code smells
        analysis.code_smells = self._find_code_smells(files, path)
        
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
    
    def _analyze_file(self, file_path: Path, base_path: Path) -> FileMetrics:
        """Анализирует один файл."""
        rel_path = str(file_path.relative_to(base_path))
        metrics = FileMetrics(path=rel_path)
        
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return metrics
        
        lines = content.split("\n")
        metrics.lines_total = len(lines)
        
        in_multiline_comment = False
        
        for line in lines:
            stripped = line.strip()
            
            if not stripped:
                metrics.lines_blank += 1
            elif stripped.startswith("#") or stripped.startswith("//"):
                metrics.lines_comment += 1
            elif '"""' in stripped or "'''" in stripped:
                metrics.lines_comment += 1
                if stripped.count('"""') == 1 or stripped.count("'''") == 1:
                    in_multiline_comment = not in_multiline_comment
            elif in_multiline_comment:
                metrics.lines_comment += 1
            else:
                metrics.lines_code += 1
        
        # Python-specific анализ
        if file_path.suffix == ".py":
            try:
                tree = ast.parse(content)
                metrics.functions = sum(1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))
                metrics.classes = sum(1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
                metrics.imports = self._extract_imports(tree)
                metrics.complexity = self._estimate_complexity(tree)
            except SyntaxError:
                metrics.issues.append("Syntax error in file")
        
        return metrics
    
    def _extract_imports(self, tree: ast.AST) -> list[str]:
        """Извлекает импорты из AST."""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        return imports
    
    def _estimate_complexity(self, tree: ast.AST) -> int:
        """Оценивает цикломатическую сложность."""
        complexity = 1  # Base complexity
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1
            elif isinstance(node, (ast.And, ast.Or)):
                complexity += 1
        
        return complexity
    
    def _check_security(self, file_path: Path, base_path: Path) -> list[SecurityIssue]:
        """Проверяет файл на проблемы безопасности."""
        issues = []
        rel_path = str(file_path.relative_to(base_path))
        
        # Пропускаем документацию и тесты для security анализа
        if file_path.suffix in [".md", ".mdx", ".rst", ".txt"]:
            return issues
        # More robust test file exclusion
        path_lower = rel_path.lower()
        if any(part in path_lower for part in ["test", "tests", "spec", "__tests__"]) and file_path.suffix == ".py":
            return issues  # Tests often have intentional "bad" patterns
        
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.debug(f"Failed to read {rel_path}: {e}")
            return issues
        
        lines = content.split("\n")
        
        for i, line in enumerate(lines, 1):
            # Пропускаем комментарии
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue
            if stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            
            # Use pre-compiled patterns for performance
            for compiled_pattern, severity, issue, recommendation in self._compiled_security_patterns:
                if compiled_pattern.search(line):
                    issues.append(SecurityIssue(
                        severity=severity,
                        file=rel_path,
                        line=i,
                        issue=issue,
                        recommendation=recommendation,
                    ))
        
        return issues
    
    def _find_code_smells(self, files: list[Path], base_path: Path) -> list[str]:
        """Находит code smells using pre-compiled patterns."""
        smells = []
        
        for file_path in files:
            if file_path.suffix != ".py":
                continue
            
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            
            rel_path = str(file_path.relative_to(base_path))
            
            # Use pre-compiled patterns
            for compiled_pattern, description in self._compiled_smell_patterns:
                matches = compiled_pattern.findall(content)
                if matches:
                    smells.append(f"{rel_path}: {description} ({len(matches)} occurrences)")
        
        return smells[:20]  # Limit to 20
    
    def _analyze_architecture(self, path: Path, files: list[Path]) -> ArchitectureInfo:
        """Анализирует архитектуру проекта."""
        arch = ArchitectureInfo()
        
        # Определяем слои по директориям
        for file_path in files:
            rel = file_path.relative_to(path)
            parts = rel.parts
            
            if len(parts) > 1:
                layer = parts[0]
                if layer not in arch.layers:
                    arch.layers[layer] = []
                arch.layers[layer].append(str(rel))
        
        # Находим точки входа
        entry_patterns = ["main.py", "app.py", "run.py", "index.py", "__main__.py", "cli.py"]
        for file_path in files:
            if file_path.name in entry_patterns:
                arch.entry_points.append(str(file_path.relative_to(path)))
        
        # Находим конфигурационные файлы
        config_patterns = ["*.toml", "*.yaml", "*.yml", "*.json", "*.ini", "*.env*"]
        for file_path in files:
            for pattern in config_patterns:
                if file_path.match(pattern):
                    arch.config_files.append(str(file_path.relative_to(path)))
                    break
        
        # Анализ зависимостей между модулями
        for file_path in files:
            if file_path.suffix != ".py":
                continue
            
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(content)
                imports = self._extract_imports(tree)
                
                rel_path = str(file_path.relative_to(path))
                local_imports = [i for i in imports if not i.startswith(("os", "sys", "re", "json", "typing", "dataclass"))]
                if local_imports:
                    arch.dependencies[rel_path] = local_imports[:10]
            except (SyntaxError, OSError):
                continue
        
        return arch
    
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
