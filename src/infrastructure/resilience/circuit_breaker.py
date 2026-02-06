"""Circuit Breaker - защита от каскадных сбоев LLM.

Паттерн Circuit Breaker предотвращает повторные вызовы к недоступному сервису,
давая ему время на восстановление.

Состояния:
- CLOSED: Нормальная работа, запросы проходят
- OPEN: Сервис недоступен, запросы блокируются
- HALF_OPEN: Пробный запрос для проверки восстановления
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)
T = TypeVar("T")

# Lock for global registry
_registry_lock = threading.Lock()


class CircuitState(Enum):
    """Состояния Circuit Breaker."""

    CLOSED = "closed"  # Нормальная работа
    OPEN = "open"  # Сервис недоступен
    HALF_OPEN = "half_open"  # Пробный запрос


@dataclass
class CircuitBreakerConfig:
    """Конфигурация Circuit Breaker."""

    failure_threshold: int = 5  # Ошибок до открытия
    recovery_timeout: float = 30.0  # Секунд до попытки восстановления
    success_threshold: int = 2  # Успехов для закрытия

    # Исключения, которые считаются ошибками (исключая системные)
    tracked_exceptions: tuple = (Exception,)

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if self.recovery_timeout <= 0:
            raise ValueError("recovery_timeout must be > 0")
        if self.success_threshold < 1:
            raise ValueError("success_threshold must be >= 1")
        # Exclude system exceptions that shouldn't be tracked
        if self.tracked_exceptions == (Exception,):
            self.tracked_exceptions = (Exception,)  # Keep as-is but document

    def is_tracked(self, exc: BaseException) -> bool:
        """Check if exception should be tracked (excludes system exceptions)."""
        if isinstance(exc, (SystemExit, KeyboardInterrupt, GeneratorExit)):
            return False
        return isinstance(exc, self.tracked_exceptions)


@dataclass
class CircuitBreaker:
    """Circuit Breaker для защиты от каскадных сбоев.

    Использование:
        breaker = CircuitBreaker("ollama")

        try:
            result = await breaker.call(async_function, arg1, arg2)
        except CircuitOpenError:
            # Сервис недоступен, использовать fallback
            pass
    """

    name: str
    config: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    @property
    def state(self) -> CircuitState:
        """Текущее состояние."""
        return self._state

    @property
    def is_closed(self) -> bool:
        """Можно ли делать запросы."""
        return self._state == CircuitState.CLOSED

    def _should_try_reset(self) -> bool:
        """Проверить, пора ли попробовать восстановление."""
        if self._state != CircuitState.OPEN:
            return False
        return time.time() - self._last_failure_time >= self.config.recovery_timeout

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Выполнить функцию через Circuit Breaker.

        Raises:
            CircuitOpenError: Если circuit открыт
            ValueError: Если func не callable

        """
        if not callable(func):
            raise ValueError("func must be callable")

        async with self._lock:
            # Проверка состояния
            if self._state == CircuitState.OPEN:
                if self._should_try_reset():
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    logger.debug("Circuit '%s' transitioned to HALF_OPEN", self.name)
                else:
                    retry_in = max(0, self.config.recovery_timeout - (time.time() - self._last_failure_time))
                    raise CircuitOpenError(f"Circuit '{self.name}' is OPEN. Retry in {retry_in:.1f}s")

        # Выполнение запроса
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            await self._on_success()
            return result

        except BaseException as e:
            # Only track configured exceptions, not system exceptions
            if self.config.is_tracked(e):
                await self._on_failure()
            raise

    async def _on_success(self) -> None:
        """Обработка успешного вызова."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0  # Reset on transition to CLOSED
                    self._success_count = 0
                    logger.info("Circuit '%s' transitioned to CLOSED", self.name)
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on any success in CLOSED state
                self._failure_count = 0

    async def _on_failure(self) -> None:
        """Обработка неудачного вызова."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # Одна ошибка в HALF_OPEN - снова OPEN
                self._state = CircuitState.OPEN
            elif self._failure_count >= self.config.failure_threshold:
                self._state = CircuitState.OPEN

    def reset(self) -> None:
        """Сбросить состояние (для тестов)."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0

    def get_stats(self) -> dict:
        """Получить статистику."""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure": self._last_failure_time,
        }


class CircuitOpenError(Exception):
    """Ошибка: Circuit Breaker открыт."""

    pass


# Глобальный реестр Circuit Breakers
_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    config: CircuitBreakerConfig | None = None,
) -> CircuitBreaker:
    """Получить или создать Circuit Breaker по имени.

    Thread-safe: uses double-checked locking pattern.
    """
    # Fast path without lock
    if name in _breakers:
        return _breakers[name]

    # Slow path with lock
    with _registry_lock:
        # Double-check after acquiring lock
        if name not in _breakers:
            _breakers[name] = CircuitBreaker(
                name=name,
                config=config or CircuitBreakerConfig(),
            )
        return _breakers[name]


def get_all_breakers() -> dict[str, dict]:
    """Получить статистику всех breakers (thread-safe)."""
    with _registry_lock:
        return {name: b.get_stats() for name, b in _breakers.items()}


def reset_all_breakers() -> None:
    """Сбросить все breakers (для тестов, thread-safe)."""
    with _registry_lock:
        for breaker in _breakers.values():
            breaker.reset()
