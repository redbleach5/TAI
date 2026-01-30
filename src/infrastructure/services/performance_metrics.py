"""Performance Metrics - отслеживание производительности системы.

Собирает метрики по этапам обработки для оптимизации и мониторинга.
Thread-safe implementation with atomic file writes.
"""

import json
import logging
import os
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from statistics import mean, median
from typing import Callable

logger = logging.getLogger(__name__)

# Lock for singleton initialization
_singleton_lock = threading.Lock()


@dataclass
class StageMetrics:
    """Метрики для одного этапа."""
    name: str
    samples: list[float] = field(default_factory=list)
    max_samples: int = 100
    
    def add(self, duration: float) -> None:
        """Добавить замер."""
        self.samples.append(duration)
        if len(self.samples) > self.max_samples:
            self.samples = self.samples[-self.max_samples:]
    
    @property
    def count(self) -> int:
        return len(self.samples)
    
    @property
    def avg(self) -> float:
        return mean(self.samples) if self.samples else 0.0
    
    @property
    def med(self) -> float:
        return median(self.samples) if self.samples else 0.0
    
    @property
    def min_time(self) -> float:
        return min(self.samples) if self.samples else 0.0
    
    @property
    def max_time(self) -> float:
        return max(self.samples) if self.samples else 0.0
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "count": self.count,
            "avg": round(self.avg, 3),
            "median": round(self.med, 3),
            "min": round(self.min_time, 3),
            "max": round(self.max_time, 3),
        }


class PerformanceMetrics:
    """Менеджер метрик производительности.
    
    Функции:
    - Сбор метрик по этапам
    - Персистентность данных
    - API для мониторинга
    
    Thread-safe: uses lock for all state modifications.
    """
    
    def __init__(self, persist_path: str | None = None):
        """Инициализация.
        
        Args:
            persist_path: Путь для сохранения метрик
        """
        self._stages: dict[str, StageMetrics] = {}
        self._persist_path = Path(persist_path) if persist_path else Path("output/metrics")
        self._persist_path.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._load()
    
    def record(self, stage: str, duration: float) -> None:
        """Записать время выполнения этапа (thread-safe).
        
        Args:
            stage: Название этапа
            duration: Время выполнения (должно быть >= 0)
        """
        if duration < 0:
            logger.warning(f"Negative duration {duration} for stage '{stage}', using 0")
            duration = 0.0
        
        with self._lock:
            if stage not in self._stages:
                self._stages[stage] = StageMetrics(name=stage)
            self._stages[stage].add(duration)
            
            # Сохраняем каждые 10 замеров
            if self._stages[stage].count % 10 == 0:
                self._save_unsafe()  # Already under lock
    
    def measure(self, stage: str) -> Callable:
        """Декоратор для измерения времени функции.
        
        Usage:
            @metrics.measure("chat")
            async def process_chat(...):
                ...
        """
        def decorator(func: Callable) -> Callable:
            import asyncio
            import functools
            
            if asyncio.iscoroutinefunction(func):
                @functools.wraps(func)
                async def async_wrapper(*args, **kwargs):
                    start = time.perf_counter()
                    try:
                        return await func(*args, **kwargs)
                    finally:
                        self.record(stage, time.perf_counter() - start)
                return async_wrapper
            else:
                @functools.wraps(func)
                def sync_wrapper(*args, **kwargs):
                    start = time.perf_counter()
                    try:
                        return func(*args, **kwargs)
                    finally:
                        self.record(stage, time.perf_counter() - start)
                return sync_wrapper
        return decorator
    
    def get_stats(self, stage: str) -> dict | None:
        """Получить статистику по этапу (thread-safe)."""
        with self._lock:
            if stage in self._stages:
                return self._stages[stage].to_dict()
            return None
    
    def get_all_stats(self) -> dict:
        """Получить статистику по всем этапам (thread-safe)."""
        with self._lock:
            return {
                "stages": {name: s.to_dict() for name, s in self._stages.items()},
                "total_samples": sum(s.count for s in self._stages.values()),
                "updated_at": datetime.now().isoformat(),
            }
    
    def estimate_duration(self, stage: str, default: float = 5.0) -> float:
        """Оценить время выполнения этапа (thread-safe).
        
        Использует медиану если есть данные, иначе default.
        """
        with self._lock:
            if stage in self._stages and self._stages[stage].count >= 3:
                return self._stages[stage].med
            return default
    
    def _load(self) -> None:
        """Загрузить метрики с диска (called during init, no lock needed)."""
        metrics_file = self._persist_path / "stage_metrics.json"
        if metrics_file.exists():
            try:
                with open(metrics_file, encoding="utf-8") as f:
                    data = json.load(f)
                for stage_data in data.get("stages", []):
                    name = stage_data.get("name")
                    if not name:
                        continue
                    stage = StageMetrics(name=name)
                    samples = stage_data.get("samples", [])
                    # Validate samples are numbers
                    stage.samples = [s for s in samples if isinstance(s, (int, float)) and s >= 0]
                    self._stages[stage.name] = stage
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load metrics: {e}")
    
    def _save_unsafe(self) -> None:
        """Сохранить метрики на диск (caller must hold lock, atomic write)."""
        metrics_file = self._persist_path / "stage_metrics.json"
        try:
            data = {
                "stages": [
                    {
                        "name": s.name,
                        "samples": s.samples[-100:],  # Save all samples (up to max_samples)
                    }
                    for s in self._stages.values()
                ],
                "updated_at": datetime.now().isoformat(),
            }
            # Atomic write: write to temp file, then rename
            fd, tmp_path = tempfile.mkstemp(
                suffix=".json",
                prefix="metrics_",
                dir=self._persist_path,
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                os.replace(tmp_path, metrics_file)  # Atomic on most filesystems
            except Exception:
                # Clean up temp file on error
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise
        except OSError as e:
            logger.warning(f"Failed to save metrics: {e}")
    
    def _save(self) -> None:
        """Сохранить метрики на диск (thread-safe)."""
        with self._lock:
            self._save_unsafe()
    
    def reset(self) -> None:
        """Сбросить все метрики (thread-safe)."""
        with self._lock:
            self._stages.clear()
            metrics_file = self._persist_path / "stage_metrics.json"
            try:
                if metrics_file.exists():
                    metrics_file.unlink()
            except OSError as e:
                logger.warning(f"Failed to delete metrics file: {e}")


# Singleton
_metrics: PerformanceMetrics | None = None


def get_metrics() -> PerformanceMetrics:
    """Получить глобальный экземпляр метрик (thread-safe singleton)."""
    global _metrics
    # Fast path without lock
    if _metrics is not None:
        return _metrics
    
    # Slow path with lock (double-checked locking)
    with _singleton_lock:
        if _metrics is None:
            _metrics = PerformanceMetrics()
        return _metrics
