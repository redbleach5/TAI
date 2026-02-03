"""Assistant Modes — два режима: Чат (быстрый ответ) и Агент (полный доступ к проекту)."""

from dataclasses import dataclass
from enum import Enum


class AssistantMode(Enum):
    """Доступные режимы: только Чат и Агент."""

    DEFAULT = "default"
    AGENT = "agent"


@dataclass
class ModeConfig:
    """Конфигурация режима."""

    id: str
    name: str
    description: str
    system_prompt: str
    temperature: float = 0.7
    icon: str = "◎"


MODES: dict[AssistantMode, ModeConfig] = {
    AssistantMode.DEFAULT: ModeConfig(
        id="default",
        name="Чат",
        description="Быстрый ответ без доступа к проекту. Вопросы, объяснения, советы.",
        icon="◎",
        temperature=0.7,
        system_prompt="""You are a helpful AI assistant. Be concise and accurate.
- Be direct; use markdown for code and lists
- If unsure, say so; ask clarifying questions when needed
- You do not have access to the user's files or terminal — answer from context they provide

When the user message includes "Результаты веб-поиска" (web search results): you MUST use those results to answer. Do not say you have no internet or no access to current information — the results are already provided above. Summarize and answer based on them.

When the message says "web search temporarily unavailable" or "Web search was requested but could not be performed": tell the user that web search is temporarily unavailable and suggest trying again later or checking their connection/API keys. Do not claim you personally have no internet access.""",
    ),
    AssistantMode.AGENT: ModeConfig(
        id="agent",
        name="Агент",
        description="Полный доступ к проекту: читает и правит файлы, ищет по коду, запускает команды, анализирует проект. Рекомендуется для работы с кодом.",
        icon="◆",
        temperature=0.3,
        system_prompt="""You are the primary coding assistant. You have full access to the project via tools: read/write files, search codebase, run terminal commands, list files, index workspace, run project analysis. Accomplish the user's task step by step; use tools whenever they help. Use <tool_call>...</tool_call> format for tool invocations. Prefer acting over long explanations when the task involves the codebase.""",
    ),
}


def get_mode(mode_id: str) -> ModeConfig:
    """Get mode configuration by ID."""
    try:
        mode = AssistantMode(mode_id)
        return MODES[mode]
    except (ValueError, KeyError):
        return MODES[AssistantMode.DEFAULT]


def list_modes() -> list[dict]:
    """List all available modes."""
    return [
        {
            "id": config.id,
            "name": config.name,
            "description": config.description,
            "icon": config.icon,
        }
        for config in MODES.values()
    ]
