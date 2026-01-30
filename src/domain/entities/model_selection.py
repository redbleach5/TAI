"""Model selection entities."""

from enum import Enum


class TaskComplexity(str, Enum):
    """Task complexity for model selection."""

    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
