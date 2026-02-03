"""Projects store - file-based project context (DI-friendly, no global singleton)."""

import json
from pathlib import Path

from pydantic import BaseModel

PROJECTS_FILE = Path("output/projects.json")


class Project(BaseModel):
    """Project configuration."""

    id: str
    name: str
    path: str
    indexed: bool = False
    files_count: int = 0
    last_indexed: str | None = None


class ProjectsStore:
    """Simple file-based project store."""

    def __init__(self, projects_file: Path | None = None):
        self._file = projects_file or PROJECTS_FILE
        self._projects: dict[str, Project] = {}
        self._current_project: str | None = None
        self._load()

    def _load(self) -> None:
        if self._file.exists():
            try:
                data = json.loads(self._file.read_text())
                for p_data in data.get("projects", []):
                    proj = Project(**p_data)
                    self._projects[proj.id] = proj
                self._current_project = data.get("current")
            except Exception:
                pass

    def _save(self) -> None:
        self._file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "projects": [p.model_dump() for p in self._projects.values()],
            "current": self._current_project,
        }
        self._file.write_text(json.dumps(data, indent=2))

    def list_projects(self) -> list[Project]:
        return list(self._projects.values())

    def get_project(self, project_id: str) -> Project | None:
        return self._projects.get(project_id)

    def add_project(self, name: str, path: str) -> Project:
        p = Path(path)
        if not p.is_absolute():
            p = Path.cwd() / p
        p = p.resolve()
        if not p.exists():
            raise ValueError(f"Path does not exist: {p}")
        if not p.is_dir():
            raise ValueError(f"Path is not a directory: {p}")
        project_id = name.lower().replace(" ", "-")
        counter = 1
        while project_id in self._projects:
            project_id = f"{name.lower().replace(' ', '-')}-{counter}"
            counter += 1
        project = Project(id=project_id, name=name, path=str(p))
        self._projects[project_id] = project
        self._save()
        return project

    def remove_project(self, project_id: str) -> bool:
        if project_id in self._projects:
            del self._projects[project_id]
            if self._current_project == project_id:
                self._current_project = None
            self._save()
            return True
        return False

    def set_current(self, project_id: str) -> bool:
        if project_id in self._projects:
            self._current_project = project_id
            self._save()
            return True
        return False

    def get_current(self) -> Project | None:
        if self._current_project:
            return self._projects.get(self._current_project)
        return None

    def update_project(self, project_id: str, **kwargs: object) -> Project | None:
        if project_id in self._projects:
            proj = self._projects[project_id]
            for k, v in kwargs.items():
                if hasattr(proj, k):
                    setattr(proj, k, v)
            self._save()
            return proj
        return None
