"""Prompt Templates - reusable prompt library."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class PromptTemplate:
    """A saved prompt template."""

    id: str
    name: str
    content: str
    category: str = "general"
    description: str = ""


# Built-in templates
BUILTIN_TEMPLATES: list[PromptTemplate] = [
    # Code templates
    PromptTemplate(
        id="explain-code",
        name="Explain Code",
        category="code",
        description="Get explanation of code",
        content="Explain this code step by step:\n\n```\n{code}\n```",
    ),
    PromptTemplate(
        id="review-code",
        name="Code Review",
        category="code",
        description="Get code review feedback",
        content="Review this code for bugs, security issues, and improvements:\n\n```{language}\n{code}\n```",
    ),
    PromptTemplate(
        id="refactor",
        name="Refactor Code",
        category="code",
        description="Suggest refactoring improvements",
        content="Refactor this code to be cleaner and more efficient. Explain your changes:\n\n```{language}\n{code}\n```",
    ),
    PromptTemplate(
        id="add-tests",
        name="Generate Tests",
        category="code",
        description="Generate unit tests",
        content="Write unit tests for this code using pytest:\n\n```python\n{code}\n```",
    ),
    PromptTemplate(
        id="add-types",
        name="Add Type Hints",
        category="code",
        description="Add Python type hints",
        content="Add comprehensive type hints to this Python code:\n\n```python\n{code}\n```",
    ),
    PromptTemplate(
        id="document",
        name="Add Documentation",
        category="code",
        description="Add docstrings and comments",
        content="Add comprehensive docstrings and inline comments to this code:\n\n```{language}\n{code}\n```",
    ),
    # Writing templates
    PromptTemplate(
        id="summarize",
        name="Summarize",
        category="writing",
        description="Summarize text",
        content="Summarize the following text in {length} sentences:\n\n{text}",
    ),
    PromptTemplate(
        id="improve-writing",
        name="Improve Writing",
        category="writing",
        description="Improve clarity and style",
        content="Improve this text for clarity and readability while preserving the meaning:\n\n{text}",
    ),
    PromptTemplate(
        id="translate",
        name="Translate",
        category="writing",
        description="Translate text",
        content="Translate the following text to {language}:\n\n{text}",
    ),
    # Analysis templates
    PromptTemplate(
        id="compare",
        name="Compare Options",
        category="analysis",
        description="Compare alternatives",
        content="Compare these options with pros and cons:\n\n{options}\n\nConsider: {criteria}",
    ),
    PromptTemplate(
        id="debug",
        name="Debug Error",
        category="code",
        description="Help debug an error",
        content="I'm getting this error:\n\n```\n{error}\n```\n\nFrom this code:\n\n```{language}\n{code}\n```\n\nHelp me understand and fix it.",
    ),
    PromptTemplate(
        id="architecture",
        name="Design Architecture",
        category="code",
        description="Design system architecture",
        content="Design the architecture for: {description}\n\nRequirements:\n{requirements}\n\nProvide: components, data flow, and technology choices.",
    ),
    # Quick templates
    PromptTemplate(
        id="eli5",
        name="ELI5",
        category="general",
        description="Explain like I'm 5",
        content="Explain {topic} in simple terms that anyone can understand.",
    ),
    PromptTemplate(
        id="pros-cons",
        name="Pros & Cons",
        category="analysis",
        description="List pros and cons",
        content="List the pros and cons of {topic}",
    ),
]


class PromptLibrary:
    """Manages prompt templates."""

    def __init__(self, storage_path: str = "output/prompts.json"):
        self._storage_path = Path(storage_path)
        self._custom_templates: dict[str, PromptTemplate] = {}
        self._load()

    def _load(self):
        """Load custom templates from storage."""
        if self._storage_path.exists():
            try:
                data = json.loads(self._storage_path.read_text())
                for item in data:
                    template = PromptTemplate(**item)
                    self._custom_templates[template.id] = template
            except Exception:
                pass

    def _save(self):
        """Save custom templates to storage."""
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = [asdict(t) for t in self._custom_templates.values()]
        self._storage_path.write_text(json.dumps(data, indent=2))

    def list_all(self) -> list[PromptTemplate]:
        """Get all templates (builtin + custom)."""
        return BUILTIN_TEMPLATES + list(self._custom_templates.values())

    def list_by_category(self, category: str) -> list[PromptTemplate]:
        """Get templates in a category."""
        return [t for t in self.list_all() if t.category == category]

    def get(self, template_id: str) -> PromptTemplate | None:
        """Get template by ID."""
        # Check custom first
        if template_id in self._custom_templates:
            return self._custom_templates[template_id]
        # Check builtin
        for t in BUILTIN_TEMPLATES:
            if t.id == template_id:
                return t
        return None

    def add(self, template: PromptTemplate) -> bool:
        """Add a custom template."""
        # Don't override builtin
        if any(t.id == template.id for t in BUILTIN_TEMPLATES):
            return False
        self._custom_templates[template.id] = template
        self._save()
        return True

    def remove(self, template_id: str) -> bool:
        """Remove a custom template."""
        if template_id in self._custom_templates:
            del self._custom_templates[template_id]
            self._save()
            return True
        return False

    def get_categories(self) -> list[str]:
        """Get list of categories."""
        categories = set()
        for t in self.list_all():
            categories.add(t.category)
        return sorted(categories)

    def fill_template(self, template_id: str, **kwargs) -> str | None:
        """Fill template with variables."""
        template = self.get(template_id)
        if not template:
            return None

        content = template.content
        for key, value in kwargs.items():
            content = content.replace(f"{{{key}}}", str(value))

        return content
