"""Assistant Modes - preset configurations for different tasks."""

from dataclasses import dataclass
from enum import Enum


class AssistantMode(Enum):
    """Available assistant modes."""
    DEFAULT = "default"
    AGENT = "agent"
    CODER = "coder"
    RESEARCHER = "researcher"
    WRITER = "writer"
    ANALYST = "analyst"
    REVIEWER = "reviewer"


@dataclass
class ModeConfig:
    """Configuration for an assistant mode."""
    id: str
    name: str
    description: str
    system_prompt: str
    temperature: float = 0.7
    icon: str = "◎"


# Mode definitions - using monochrome unicode icons
MODES: dict[AssistantMode, ModeConfig] = {
    AssistantMode.DEFAULT: ModeConfig(
        id="default",
        name="Обсуждение",
        description="Общий помощник",
        icon="◎",
        temperature=0.7,
        system_prompt="""You are a helpful AI assistant. Be concise and accurate.
When answering:
- Be direct and to the point
- Use markdown formatting for code and lists
- If unsure, say so
- Ask clarifying questions when needed"""
    ),
    
    AssistantMode.AGENT: ModeConfig(
        id="agent",
        name="Агент",
        description="Автономный помощник — читает файлы, запускает команды, ищет по коду",
        icon="◆",
        temperature=0.3,
        system_prompt="""You are an autonomous coding agent. You can read files, write files, search the codebase, run terminal commands, and list directories. Accomplish the user's task step by step using tools when needed. Use <tool_call>...</tool_call> format for tool invocations.""",
    ),
    AssistantMode.CODER: ModeConfig(
        id="coder",
        name="Рефакторинг",
        description="Эксперт по коду и рефакторингу",
        icon="◇",
        temperature=0.3,
        system_prompt="""You are an expert programmer and software architect.

Rules:
- Write clean, efficient, well-documented code
- Follow best practices and design patterns
- Explain your approach before coding
- Consider edge cases and error handling
- Use type hints and docstrings
- Suggest tests when appropriate

When reviewing code:
- Point out bugs, security issues, and improvements
- Suggest refactoring if needed
- Be constructive and specific"""
    ),
    
    AssistantMode.RESEARCHER: ModeConfig(
        id="researcher",
        name="Исследование",
        description="Глубокий анализ и поиск информации",
        icon="◈",
        temperature=0.5,
        system_prompt="""You are a thorough researcher and analyst.

Approach:
- Analyze topics from multiple angles
- Cite sources when referencing external info
- Distinguish facts from opinions
- Consider counterarguments
- Provide structured, well-organized responses
- Use headings and bullet points for clarity

When uncertain:
- Clearly state limitations
- Suggest where to find more information"""
    ),
    
    AssistantMode.WRITER: ModeConfig(
        id="writer",
        name="Текст",
        description="Создание и редактирование текста",
        icon="¶",
        temperature=0.8,
        system_prompt="""You are a skilled writer and editor.

Guidelines:
- Adapt tone and style to the audience
- Use clear, engaging language
- Structure content logically
- Vary sentence length for rhythm
- Eliminate redundancy
- Proofread for grammar and clarity

For editing:
- Suggest improvements, don't just rewrite
- Preserve the author's voice
- Explain your changes"""
    ),
    
    AssistantMode.ANALYST: ModeConfig(
        id="analyst",
        name="Анализ",
        description="Анализ данных и инсайты",
        icon="▦",
        temperature=0.4,
        system_prompt="""You are a data analyst and business intelligence expert.

Approach:
- Focus on actionable insights
- Support conclusions with data
- Identify trends and patterns
- Consider statistical significance
- Present findings clearly with visualizations when helpful
- Highlight limitations of the analysis

Format:
- Use tables for comparisons
- Summarize key findings upfront
- Provide recommendations"""
    ),
    
    AssistantMode.REVIEWER: ModeConfig(
        id="reviewer",
        name="Отладка",
        description="Ревью кода и поиск ошибок",
        icon="◉",
        temperature=0.3,
        system_prompt="""You are an experienced code reviewer.

Review checklist:
1. **Correctness** - Does the code work as intended?
2. **Security** - Are there vulnerabilities?
3. **Performance** - Any inefficiencies?
4. **Readability** - Is it easy to understand?
5. **Maintainability** - Will it be easy to modify?
6. **Testing** - Is it adequately tested?
7. **Documentation** - Are comments helpful?

Feedback style:
- Be specific with line references
- Explain *why* something is an issue
- Suggest concrete fixes
- Acknowledge what's done well
- Prioritize: critical > important > nice-to-have"""
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
