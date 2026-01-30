"""Code Security - проверка безопасности сгенерированного кода.

Проверяет код на опасные операции перед выполнением или сохранением.
"""

from dataclasses import dataclass


@dataclass
class SecurityCheckResult:
    """Результат проверки безопасности."""
    is_safe: bool
    warnings: list[str]
    blocked: list[str]


class CodeSecurityChecker:
    """Проверяет код на опасные операции.
    
    Использует паттерны для обнаружения:
    - Опасных импортов (os, subprocess, etc.)
    - Опасных функций (eval, exec, etc.)
    - Опасных системных вызовов
    """
    
    # Опасные импорты
    DANGEROUS_IMPORTS = [
        "import os",
        "import subprocess",
        "import sys",
        "import socket",
        "import ctypes",
        "from os",
        "from subprocess",
        "from sys",
        "from socket",
        "from ctypes",
        "__import__",
    ]
    
    # Опасные функции
    DANGEROUS_FUNCTIONS = [
        "eval(",
        "exec(",
        "compile(",
        "globals(",
        "locals(",
        "__builtins__",
        "__code__",
        "__globals__",
    ]
    
    # Опасные системные вызовы
    DANGEROUS_CALLS = [
        "os.system",
        "os.popen",
        "os.execv",
        "os.spawn",
        "subprocess.run",
        "subprocess.call",
        "subprocess.Popen",
        "subprocess.check_output",
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
    
    def check(self, code: str) -> SecurityCheckResult:
        """Проверяет код на опасные операции.
        
        Args:
            code: Код для проверки
        
        Returns:
            SecurityCheckResult с результатом проверки
        """
        if not code:
            return SecurityCheckResult(is_safe=True, warnings=[], blocked=[])
        
        warnings: list[str] = []
        blocked: list[str] = []
        code_lower = code.lower()
        
        # Проверяем опасные импорты
        for pattern in self.DANGEROUS_IMPORTS:
            if pattern.lower() in code_lower:
                msg = f"Dangerous import: {pattern}"
                if self.strict_mode:
                    blocked.append(msg)
                else:
                    warnings.append(msg)
        
        # Проверяем опасные функции
        for pattern in self.DANGEROUS_FUNCTIONS:
            if pattern.lower() in code_lower:
                msg = f"Dangerous function: {pattern}"
                if self.strict_mode:
                    blocked.append(msg)
                else:
                    warnings.append(msg)
        
        # Проверяем опасные системные вызовы
        for pattern in self.DANGEROUS_CALLS:
            if pattern.lower() in code_lower:
                msg = f"Dangerous system call: {pattern}"
                blocked.append(msg)  # Всегда блокируем
        
        # Проверяем файловые операции (если запрещены)
        if not self.allow_file_ops:
            if "open(" in code_lower or "file(" in code_lower:
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
        
        WARNING: Это простая реализация, не гарантирует безопасность.
        """
        lines = code.split("\n")
        safe_lines = []
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # Пропускаем строки с опасными импортами
            skip = False
            for pattern in self.DANGEROUS_IMPORTS:
                if line_lower.startswith(pattern.lower()):
                    skip = True
                    safe_lines.append(f"# REMOVED: {line}")
                    break
            
            # Пропускаем строки с опасными вызовами
            if not skip:
                for pattern in self.DANGEROUS_CALLS:
                    if pattern.lower() in line_lower:
                        skip = True
                        safe_lines.append(f"# REMOVED: {line}")
                        break
            
            if not skip:
                safe_lines.append(line)
        
        return "\n".join(safe_lines)


# Singleton
_checker: CodeSecurityChecker | None = None


def get_security_checker(strict: bool = False) -> CodeSecurityChecker:
    """Получить или создать security checker."""
    global _checker
    if _checker is None:
        _checker = CodeSecurityChecker(strict_mode=strict)
    return _checker
