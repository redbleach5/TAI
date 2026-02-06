"""Tests for ProjectsStore — file-based persistence, tmp_path only."""

from pathlib import Path

import pytest

from src.api.store import Project, ProjectsStore


class TestProjectsStore:
    """ProjectsStore: CRUD operations with tmp_path."""

    @pytest.fixture()
    def store(self, tmp_path: Path) -> ProjectsStore:
        return ProjectsStore(projects_file=tmp_path / "projects.json")

    def test_empty_store(self, store: ProjectsStore):
        assert store.list_projects() == []
        assert store.get_current() is None

    def test_add_project(self, store: ProjectsStore, tmp_path: Path):
        project_dir = tmp_path / "my_project"
        project_dir.mkdir()
        project = store.add_project("My Project", str(project_dir))
        assert project.name == "My Project"
        assert project.id == "my-project"
        assert project.path == str(project_dir.resolve())
        assert project.indexed is False

    def test_add_project_nonexistent_path_raises(self, store: ProjectsStore):
        with pytest.raises(ValueError, match="does not exist"):
            store.add_project("Bad", "/nonexistent/path")

    def test_add_project_file_path_raises(self, store: ProjectsStore, tmp_path: Path):
        f = tmp_path / "file.txt"
        f.write_text("content")
        with pytest.raises(ValueError, match="not a directory"):
            store.add_project("File", str(f))

    def test_list_projects(self, store: ProjectsStore, tmp_path: Path):
        d1 = tmp_path / "p1"
        d1.mkdir()
        d2 = tmp_path / "p2"
        d2.mkdir()
        store.add_project("P1", str(d1))
        store.add_project("P2", str(d2))
        projects = store.list_projects()
        assert len(projects) == 2
        names = {p.name for p in projects}
        assert names == {"P1", "P2"}

    def test_get_project(self, store: ProjectsStore, tmp_path: Path):
        d = tmp_path / "proj"
        d.mkdir()
        store.add_project("Proj", str(d))
        project = store.get_project("proj")
        assert project is not None
        assert project.name == "Proj"

    def test_get_nonexistent_project(self, store: ProjectsStore):
        assert store.get_project("nonexistent") is None

    def test_remove_project(self, store: ProjectsStore, tmp_path: Path):
        d = tmp_path / "proj"
        d.mkdir()
        store.add_project("Proj", str(d))
        assert store.remove_project("proj") is True
        assert store.get_project("proj") is None
        assert store.list_projects() == []

    def test_remove_nonexistent(self, store: ProjectsStore):
        assert store.remove_project("nonexistent") is False

    def test_set_and_get_current(self, store: ProjectsStore, tmp_path: Path):
        d = tmp_path / "proj"
        d.mkdir()
        store.add_project("Proj", str(d))
        assert store.set_current("proj") is True
        current = store.get_current()
        assert current is not None
        assert current.name == "Proj"

    def test_set_current_nonexistent(self, store: ProjectsStore):
        assert store.set_current("nonexistent") is False

    def test_remove_current_clears_selection(self, store: ProjectsStore, tmp_path: Path):
        d = tmp_path / "proj"
        d.mkdir()
        store.add_project("Proj", str(d))
        store.set_current("proj")
        store.remove_project("proj")
        assert store.get_current() is None

    def test_update_project(self, store: ProjectsStore, tmp_path: Path):
        d = tmp_path / "proj"
        d.mkdir()
        store.add_project("Proj", str(d))
        updated = store.update_project("proj", indexed=True, files_count=42)
        assert updated is not None
        assert updated.indexed is True
        assert updated.files_count == 42

    def test_update_nonexistent(self, store: ProjectsStore):
        assert store.update_project("nonexistent", indexed=True) is None

    def test_persistence(self, tmp_path: Path):
        projects_file = tmp_path / "projects.json"
        d = tmp_path / "proj"
        d.mkdir()

        store1 = ProjectsStore(projects_file=projects_file)
        store1.add_project("Proj", str(d))
        store1.set_current("proj")

        store2 = ProjectsStore(projects_file=projects_file)
        assert len(store2.list_projects()) == 1
        current = store2.get_current()
        assert current is not None
        assert current.name == "Proj"

    def test_duplicate_id_gets_suffix(self, store: ProjectsStore, tmp_path: Path):
        d1 = tmp_path / "d1"
        d1.mkdir()
        d2 = tmp_path / "d2"
        d2.mkdir()
        p1 = store.add_project("test", str(d1))
        p2 = store.add_project("test", str(d2))
        assert p1.id != p2.id
        assert p2.id == "test-1"

    def test_corrupted_file_recovers(self, tmp_path: Path):
        projects_file = tmp_path / "projects.json"
        projects_file.write_text("not valid json")
        store = ProjectsStore(projects_file=projects_file)
        assert store.list_projects() == []


class TestProjectModel:
    """Project Pydantic model."""

    def test_defaults(self):
        p = Project(id="test", name="Test", path="/tmp/test")
        assert p.indexed is False
        assert p.files_count == 0
        assert p.last_indexed is None

    def test_serialization(self):
        p = Project(id="test", name="Test", path="/tmp/test", indexed=True, files_count=10)
        data = p.model_dump()
        assert data["id"] == "test"
        assert data["indexed"] is True
        restored = Project(**data)
        assert restored == p
