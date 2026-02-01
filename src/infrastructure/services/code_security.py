"""Code Security - проверка безопасности сгенерированного кода.

Проверяет код на опасные операции перед выполнением или сохранением.

Production-ready with:
- Regex-based pattern matching with word boundaries
- Comment and string detection to reduce false positives
- Extended dangerous pattern list
"""

import re
from dataclasses import dataclass


@dataclass
class SecurityCheckResult:
    """Результат проверки безопасности."""
    is_safe: bool
    warnings: list[str]
    blocked: list[str]


class CodeSecurityChecker:
    """Проверяет код на опасные операции.
    
    Использует regex паттерны для обнаружения:
    - Опасных импортов (os, subprocess, pickle, etc.)
    - Опасных функций (eval, exec, etc.)
    - Опасных системных вызовов
    
    Reduces false positives by skipping comments and strings.
    """
    
    # Опасные импорты (regex patterns)
    DANGEROUS_IMPORT_PATTERNS = [
        r"^\s*import\s+os\b",
        r"^\s*import\s+subprocess\b",
        r"^\s*import\s+sys\b",
        r"^\s*import\s+socket\b",
        r"^\s*import\s+ctypes\b",
        r"^\s*import\s+pickle\b",
        r"^\s*import\s+marshal\b",
        r"^\s*from\s+os\b",
        r"^\s*from\s+subprocess\b",
        r"^\s*from\s+sys\b",
        r"^\s*from\s+socket\b",
        r"^\s*from\s+ctypes\b",
        r"^\s*from\s+pickle\b",
        r"^\s*from\s+marshal\b",
        r"\b__import__\s*\(",
    ]
    
    # Опасные функции (regex patterns)
    DANGEROUS_FUNCTION_PATTERNS = [
        r"\beval\s*\(",
        r"\bexec\s*\(",
        r"\bcompile\s*\(",
        r"\bglobals\s*\(",
        r"\blocals\s*\(",
        r"\b__builtins__\b",
        r"\b__code__\b",
        r"\b__globals__\b",
    ]
    
    # Опасные системные вызовы (regex patterns) - always blocked
    DANGEROUS_CALL_PATTERNS = [
        r"\bos\.system\s*\(",
        r"\bos\.popen\s*\(",
        r"\bos\.execv\s*\(",
        r"\bos\.spawn\w*\s*\(",
        r"\bsubprocess\.run\s*\(",
        r"\bsubprocess\.call\s*\(",
        r"\bsubprocess\.Popen\s*\(",
        r"\bsubprocess\.check_output\s*\(",
        r"\bshutil\.rmtree\s*\(",
        r"\bos\.remove\s*\(",
        r"\bos\.unlink\s*\(",
    ]
    
    def __init__(
        self,
        strict_mode: bool = False,
        allow_file_ops: bool = True,
    ):
        """Инициализация проверщика.
        
        Args:
            strict_mode: Блокировать при любом предупреждении
            allow_file_ops: Разрешить операции с файлами (open)
        """
        self.strict_mode = strict_mode
        self.allow_file_ops = allow_file_ops
        
        # Pre-compile regex patterns
        self._import_patterns = [
            (re.compile(p, re.MULTILINE), p) for p in self.DANGEROUS_IMPORT_PATTERNS
        ]
        self._function_patterns = [
            (re.compile(p), p) for p in self.DANGEROUS_FUNCTION_PATTERNS
        ]
        self._call_patterns = [
            (re.compile(p), p) for p in self.DANGEROUS_CALL_PATTERNS
        ]
    
    def _remove_comments_and_strings(self, code: str) -> str:
        """Remove comments and string literals to reduce false positives."""
        # Remove single-line comments
        code = re.sub(r'#.*$', '', code, flags=re.MULTILINE)
        # Remove triple-quoted strings (docstrings)
        code = re.sub(r'""".*?"""', '""', code, flags=re.DOTALL)
        code = re.sub(r"'''.*?'''", "''", code, flags=re.DOTALL)
        # Remove regular strings (simplified - may have edge cases)
        code = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', '""', code)
        code = re.sub(r"'[^'\\]*(?:\\.[^'\\]*)*'", "''", code)
        return code
    
    def check(self, code: str) -> SecurityCheckResult:
        """Проверяет код на опасные операции.
        
        Uses regex with word boundaries to reduce false positives.
        Skips patterns found in comments and strings.
        
        Args:
            code: Код для проверки
        
        Returns:
            SecurityCheckResult с результатом проверки
        """
        if not code or not code.strip():
            return SecurityCheckResult(is_safe=True, warnings=[], blocked=[])
        
        warnings: list[str] = []
        blocked: list[str] = []
        
        # Clean code for analysis (remove comments/strings)
        clean_code = self._remove_comments_and_strings(code)
        
        # Проверяем опасные импорты
        for compiled_pattern, pattern in self._import_patterns:
            match = compiled_pattern.search(clean_code)
            if match:
                # Extract the matched import for better error message
                matched_text = match.group(0).strip()
                msg = f"Dangerous import: {matched_text}"
                if self.strict_mode:
                    blocked.append(msg)
                else:
                    warnings.append(msg)
        
        # Проверяем опасные функции
        for compiled_pattern, pattern in self._function_patterns:
            match = compiled_pattern.search(clean_code)
            if match:
                matched_text = match.group(0).strip()
                msg = f"Dangerous function: {matched_text}"
                if self.strict_mode:
                    blocked.append(msg)
                else:
                    warnings.append(msg)
        
        # Проверяем опасные системные вызовы
        for compiled_pattern, pattern in self._call_patterns:
            match = compiled_pattern.search(clean_code)
            if match:
                matched_text = match.group(0).strip()
                msg = f"Dangerous system call: {matched_text}"
                blocked.append(msg)  # Всегда блокируем
        
        # Проверяем файловые операции (если запрещены)
        if not self.allow_file_ops:
            if re.search(r'\bopen\s*\(', clean_code):
                warnings.append("File operation detected: open()")
        
        is_safe = len(blocked) == 0
        if self.strict_mode and warnings:
            is_safe = False
        
        return SecurityCheckResult(
            is_safe=is_safe,
            warnings=warnings,
            blocked=blocked,
        )
    
    def is_safe_for_execution(self, code: str) -> bool:
        """Проверяет, безопасен ли код для выполнения.
        
        Более строгая проверка чем check().
        """
        result = self.check(code)
        return result.is_safe and len(result.warnings) == 0
    
    def sanitize(self, code: str) -> str:
        """Удаляет опасные конструкции из кода.
        
        WARNING: Это простая реализация, не гарантирует полную безопасность.
        Используйте только как дополнительный слой защиты.
        """
        lines = code.split("\n")
        safe_lines = []
        
        for line in lines:
            # Пропускаем строки с опасными импортами
            skip = False
            for compiled_pattern, _ in self._import_patterns:
                if compiled_pattern.search(line):
                    skip = True
                    safe_lines.append(f"# REMOVED: {line}")
                    break
            
            # Пропускаем строки с опасными вызовами
            if not skip:
                for compiled_pattern, _ in self._call_patterns:
                    if compiled_pattern.search(line):
                        skip = True
                        safe_lines.append(f"# REMOVED: {line}")
                        break
            
            if not skip:
                safe_lines.append(line)
        
        return "\n".join(safe_lines)
