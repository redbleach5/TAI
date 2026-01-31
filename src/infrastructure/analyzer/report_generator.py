"""Report Generator - генерация отчётов анализа.

Создаёт Markdown отчёты с визуализацией результатов.

Production-ready with:
- Markdown special character escaping
- Null/empty safety checks
"""

import re
from datetime import datetime
from pathlib import Path

from src.infrastructure.analyzer.project_analyzer import ProjectAnalysis


def escape_markdown(text: str | None) -> str:
    """Escape markdown special characters in text.
    
    Escapes: | ` * _ [ ] ( ) # + - . !
    """
    if not text:
        return ""
    # Escape pipe (most important for tables)
    text = text.replace("|", "\\|")
    # Escape backticks
    text = text.replace("`", "\\`")
    # Escape asterisks and underscores (but not when used for emphasis)
    # Only escape at word boundaries to avoid breaking formatting
    text = re.sub(r'(\*+)(?=\S)', r'\\\1', text)
    text = re.sub(r'(?<=\S)(\*+)', r'\\\1', text)
    return text


def safe_str(value: str | None, default: str = "") -> str:
    """Return value if not None/empty, else default."""
    return value if value else default


class ReportGenerator:
    """Генератор отчётов анализа проекта."""
    
    def generate_markdown(self, analysis: ProjectAnalysis | None) -> str:
        """Генерирует Markdown отчёт.
        
        Args:
            analysis: Результат анализа проекта
            
        Returns:
            Markdown строка с отчётом
        """
        if analysis is None:
            return "# Project Analysis Report\n\n**Error:** No analysis data available."
        
        sections = [
            self._header(analysis),
            self._executive_summary(analysis),
            self._scores_section(analysis),
            self._statistics_section(analysis),
            self._languages_section(analysis),
            self._security_section(analysis),
            self._quality_section(analysis),
            self._architecture_section(analysis),
            self._recommendations_section(analysis),
            self._top_files_section(analysis),
            self._footer(analysis),
        ]
        
        # Filter out empty sections
        sections = [s for s in sections if s and s.strip()]
        
        return "\n\n".join(sections)
    
    def _header(self, analysis: ProjectAnalysis) -> str:
        """Заголовок отчёта."""
        project_name = safe_str(analysis.project_name, "Unknown")
        project_path = safe_str(analysis.project_path, "Unknown")
        analyzed_at = safe_str(analysis.analyzed_at, datetime.now().isoformat())
        
        return f"""# 📊 Project Analysis Report

**Project:** `{escape_markdown(project_name)}`  
**Path:** `{escape_markdown(project_path)}`  
**Analyzed:** {analyzed_at}

---"""
    
    def _executive_summary(self, analysis: ProjectAnalysis) -> str:
        """Executive Summary."""
        # Определяем общую оценку
        security_score = analysis.security_score if analysis.security_score is not None else 0
        quality_score = analysis.quality_score if analysis.quality_score is not None else 0
        overall = (security_score + quality_score) // 2
        
        if overall >= 80:
            status = "🟢 **HEALTHY**"
            emoji = "✅"
        elif overall >= 60:
            status = "🟡 **NEEDS ATTENTION**"
            emoji = "⚠️"
        else:
            status = "🔴 **CRITICAL**"
            emoji = "❌"
        
        strengths = analysis.strengths if analysis.strengths else []
        weaknesses = analysis.weaknesses if analysis.weaknesses else []
        
        strengths_str = "\n".join(
            f"- {escape_markdown(s)}" for s in strengths[:5] if s
        ) or "- None identified"
        weaknesses_str = "\n".join(
            f"- {escape_markdown(w)}" for w in weaknesses[:5] if w
        ) or "- None identified"
        
        return f"""## 📋 Executive Summary

### Overall Status: {status}

| Metric | Score | Status |
|--------|-------|--------|
| Security | {security_score}/100 | {self._score_emoji(security_score)} |
| Quality | {quality_score}/100 | {self._score_emoji(quality_score)} |
| **Overall** | **{overall}/100** | {emoji} |

### Strengths
{strengths_str}

### Weaknesses
{weaknesses_str}"""
    
    def _score_emoji(self, score: int) -> str:
        """Эмодзи для score."""
        if score >= 80:
            return "🟢 Good"
        elif score >= 60:
            return "🟡 Fair"
        elif score >= 40:
            return "🟠 Poor"
        else:
            return "🔴 Critical"
    
    def _scores_section(self, analysis: ProjectAnalysis) -> str:
        """Секция со scores (ASCII диаграммы)."""
        security_bar = self._progress_bar(analysis.security_score)
        quality_bar = self._progress_bar(analysis.quality_score)
        
        return f"""## 📈 Scores

### Security Score
```
{security_bar} {analysis.security_score}%
```

### Quality Score
```
{quality_bar} {analysis.quality_score}%
```"""
    
    def _progress_bar(self, score: int, width: int = 30) -> str:
        """Создаёт ASCII progress bar."""
        filled = int(width * score / 100)
        empty = width - filled
        return f"[{'█' * filled}{'░' * empty}]"
    
    def _statistics_section(self, analysis: ProjectAnalysis) -> str:
        """Общая статистика."""
        avg_file_size = analysis.total_lines // max(1, analysis.total_files)
        comment_ratio = 0
        if analysis.total_code_lines > 0:
            total_comments = sum(f.lines_comment for f in analysis.file_metrics)
            comment_ratio = round(total_comments / analysis.total_code_lines * 100, 1)
        
        return f"""## 📊 Statistics

| Metric | Value |
|--------|-------|
| Total Files | {analysis.total_files} |
| Total Lines | {analysis.total_lines:,} |
| Code Lines | {analysis.total_code_lines:,} |
| Avg Lines/File | {avg_file_size} |
| Comment Ratio | {comment_ratio}% |
| Languages | {len(analysis.languages)} |
| Security Issues | {len(analysis.security_issues)} |
| Code Smells | {len(analysis.code_smells)} |"""
    
    def _languages_section(self, analysis: ProjectAnalysis) -> str:
        """Секция языков."""
        if not analysis.languages:
            return ""
        
        total = sum(analysis.languages.values())
        if total == 0:
            return ""
        
        rows = []
        
        for lang, count in sorted(analysis.languages.items(), key=lambda x: -x[1]):
            if not lang:
                continue
            pct = round(count / total * 100, 1)
            bar = "█" * int(pct / 5)
            rows.append(f"| {escape_markdown(lang)} | {count} | {pct}% | {bar} |")
        
        if not rows:
            return ""
        
        return f"""## 🌐 Languages

| Language | Files | % | Distribution |
|----------|-------|---|--------------|
{chr(10).join(rows)}"""
    
    def _security_section(self, analysis: ProjectAnalysis) -> str:
        """Секция безопасности."""
        if not analysis.security_issues:
            return """## 🔒 Security

✅ **No security issues detected!**"""
        
        # Группировка по severity
        by_severity = {"critical": [], "high": [], "medium": [], "low": []}
        for issue in analysis.security_issues:
            by_severity[issue.severity].append(issue)
        
        sections = ["## 🔒 Security\n"]
        
        severity_emoji = {
            "critical": "🔴 CRITICAL",
            "high": "🟠 HIGH",
            "medium": "🟡 MEDIUM",
            "low": "⚪ LOW",
        }
        
        for severity in ["critical", "high", "medium", "low"]:
            issues = by_severity[severity]
            if issues:
                sections.append(f"\n### {severity_emoji[severity]} ({len(issues)})\n")
                sections.append("| File | Line | Issue | Recommendation |")
                sections.append("|------|------|-------|----------------|")
                for issue in issues[:10]:  # Limit to 10 per severity
                    file_path = escape_markdown(safe_str(issue.file, "unknown"))
                    issue_text = escape_markdown(safe_str(issue.issue, ""))
                    rec_text = escape_markdown(safe_str(issue.recommendation, ""))
                    sections.append(
                        f"| `{file_path}` | {issue.line} | {issue_text} | {rec_text} |"
                    )
        
        return "\n".join(sections)
    
    def _quality_section(self, analysis: ProjectAnalysis) -> str:
        """Секция качества кода."""
        if not analysis.code_smells:
            return """## 🎯 Code Quality

✅ **No major code smells detected!**"""
        
        smells_list = "\n".join(
            f"- `{escape_markdown(smell)}`" 
            for smell in analysis.code_smells[:15] 
            if smell
        )
        
        if not smells_list:
            return """## 🎯 Code Quality

✅ **No major code smells detected!**"""
        
        return f"""## 🎯 Code Quality

### Code Smells ({len(analysis.code_smells)})

{smells_list}"""
    
    def _architecture_section(self, analysis: ProjectAnalysis) -> str:
        """Секция архитектуры."""
        arch = analysis.architecture
        if not arch:
            return "## 🏗️ Architecture\n\nNo architecture information available."
        
        # Структура директорий
        layers = ""
        if arch.layers:
            layers = "### Directory Structure\n\n```\n"
            for layer, files in sorted(arch.layers.items()):
                # No escaping needed inside code blocks
                safe_layer = safe_str(layer, "unknown")
                file_count = len(files) if files else 0
                layers += f"📁 {safe_layer}/ ({file_count} files)\n"
            layers += "```\n"
        
        # Entry points
        entries = ""
        if arch.entry_points:
            entries = "### Entry Points\n\n"
            entries += "\n".join(
                f"- `{escape_markdown(safe_str(e, ''))}`" 
                for e in arch.entry_points 
                if e
            )
            entries += "\n"
        
        # Config files
        configs = ""
        if arch.config_files:
            configs = "### Configuration Files\n\n"
            configs += "\n".join(
                f"- `{escape_markdown(safe_str(c, ''))}`" 
                for c in arch.config_files[:10] 
                if c
            )
            configs += "\n"
        
        return f"""## 🏗️ Architecture

{layers}
{entries}
{configs}"""
    
    def _recommendations_section(self, analysis: ProjectAnalysis) -> str:
        """Секция рекомендаций."""
        if not analysis.recommendations:
            return """## 💡 Recommendations

✅ **No critical recommendations. Good job!**"""
        
        recs = "\n".join(
            f"{i+1}. {escape_markdown(rec)}" 
            for i, rec in enumerate(analysis.recommendations) 
            if rec
        )
        
        if not recs:
            return """## 💡 Recommendations

✅ **No critical recommendations. Good job!**"""
        
        return f"""## 💡 Recommendations

{recs}"""
    
    def _top_files_section(self, analysis: ProjectAnalysis) -> str:
        """Топ файлов по размеру и сложности."""
        if not analysis.file_metrics:
            return ""
        
        # Top by lines
        by_lines = sorted(analysis.file_metrics, key=lambda f: -f.lines_code)[:5]
        lines_rows = [
            f"| `{escape_markdown(safe_str(f.path, 'unknown'))}` | {f.lines_code} | {f.functions} | {f.classes} |"
            for f in by_lines
            if f and f.path
        ]
        
        # Top by complexity (only Python)
        by_complexity = sorted(
            [f for f in analysis.file_metrics if f and f.complexity > 0],
            key=lambda f: -f.complexity
        )[:5]
        complexity_rows = [
            f"| `{escape_markdown(safe_str(f.path, 'unknown'))}` | {f.complexity} |"
            for f in by_complexity
            if f and f.path
        ]
        
        lines_content = chr(10).join(lines_rows) if lines_rows else "| No files | - | - | - |"
        complexity_content = chr(10).join(complexity_rows) if complexity_rows else "| No files | - |"
        
        return f"""## 📁 Top Files

### By Lines of Code

| File | Lines | Functions | Classes |
|------|-------|-----------|---------|
{lines_content}

### By Complexity (Python)

| File | Complexity |
|------|------------|
{complexity_content}"""
    
    def _footer(self, analysis: ProjectAnalysis) -> str:
        """Футер отчёта."""
        return f"""---

*Report generated by TAi v3 Project Analyzer*  
*{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"""
    
    def save_report(self, analysis: ProjectAnalysis, output_path: str | Path) -> Path:
        """Сохраняет отчёт в файл.
        
        Args:
            analysis: Результат анализа
            output_path: Путь для сохранения
            
        Returns:
            Path к созданному файлу
        """
        output = Path(output_path)
        content = self.generate_markdown(analysis)
        output.write_text(content, encoding="utf-8")
        return output
