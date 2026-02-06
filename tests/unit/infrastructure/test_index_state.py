"""Tests for index_state — diff_files (pure) + state persistence (tmp_path)."""

from pathlib import Path

from src.infrastructure.rag.index_state import IndexState


class TestDiffFiles:
    """IndexState.diff_files: pure static method, zero I/O."""

    def test_empty_both(self):
        new, changed, deleted = IndexState.diff_files({}, {})
        assert new == []
        assert changed == []
        assert deleted == []

    def test_all_new(self):
        current = {
            "a.py": {"mtime": 1.0, "size": 100},
            "b.py": {"mtime": 2.0, "size": 200},
        }
        new, changed, deleted = IndexState.diff_files(current, {})
        assert sorted(new) == ["a.py", "b.py"]
        assert changed == []
        assert deleted == []

    def test_all_deleted(self):
        indexed = {
            "a.py": {"mtime": 1.0, "size": 100},
            "b.py": {"mtime": 2.0, "size": 200},
        }
        new, changed, deleted = IndexState.diff_files({}, indexed)
        assert new == []
        assert changed == []
        assert sorted(deleted) == ["a.py", "b.py"]

    def test_unchanged(self):
        state = {
            "a.py": {"mtime": 1.0, "size": 100},
            "b.py": {"mtime": 2.0, "size": 200},
        }
        new, changed, deleted = IndexState.diff_files(state, state)
        assert new == []
        assert changed == []
        assert deleted == []

    def test_changed_mtime(self):
        current = {"a.py": {"mtime": 2.0, "size": 100}}
        indexed = {"a.py": {"mtime": 1.0, "size": 100}}
        new, changed, deleted = IndexState.diff_files(current, indexed)
        assert new == []
        assert changed == ["a.py"]
        assert deleted == []

    def test_changed_size(self):
        current = {"a.py": {"mtime": 1.0, "size": 200}}
        indexed = {"a.py": {"mtime": 1.0, "size": 100}}
        new, changed, deleted = IndexState.diff_files(current, indexed)
        assert changed == ["a.py"]

    def test_mixed_operations(self):
        current = {
            "existing.py": {"mtime": 1.0, "size": 100},
            "modified.py": {"mtime": 3.0, "size": 300},
            "new.py": {"mtime": 4.0, "size": 400},
        }
        indexed = {
            "existing.py": {"mtime": 1.0, "size": 100},
            "modified.py": {"mtime": 2.0, "size": 200},
            "removed.py": {"mtime": 5.0, "size": 500},
        }
        new, changed, deleted = IndexState.diff_files(current, indexed)
        assert new == ["new.py"]
        assert changed == ["modified.py"]
        assert deleted == ["removed.py"]


class TestIndexStatePersistence:
    """IndexState with tmp_path — no external dependencies."""

    def test_empty_state(self, tmp_path: Path):
        state = IndexState(str(tmp_path))
        assert state.get_indexed_files("/some/path") == {}

    def test_update_and_get(self, tmp_path: Path):
        state = IndexState(str(tmp_path))
        files = {"a.py": {"mtime": 1.0, "size": 100}}
        state.update_state(str(tmp_path / "project"), files)
        result = state.get_indexed_files(str(tmp_path / "project"))
        assert result == files

    def test_persistence_across_instances(self, tmp_path: Path):
        files = {"a.py": {"mtime": 1.0, "size": 100}}
        state1 = IndexState(str(tmp_path))
        state1.update_state(str(tmp_path / "project"), files)

        state2 = IndexState(str(tmp_path))
        result = state2.get_indexed_files(str(tmp_path / "project"))
        assert result == files

    def test_clear_specific_path(self, tmp_path: Path):
        state = IndexState(str(tmp_path))
        state.update_state(str(tmp_path / "p1"), {"a.py": {"mtime": 1.0, "size": 100}})
        state.update_state(str(tmp_path / "p2"), {"b.py": {"mtime": 2.0, "size": 200}})
        state.clear_state(str(tmp_path / "p1"))
        assert state.get_indexed_files(str(tmp_path / "p1")) == {}
        assert state.get_indexed_files(str(tmp_path / "p2")) != {}

    def test_clear_all(self, tmp_path: Path):
        state = IndexState(str(tmp_path))
        state.update_state(str(tmp_path / "p1"), {"a.py": {"mtime": 1.0, "size": 100}})
        state.clear_state()
        assert state.get_indexed_files(str(tmp_path / "p1")) == {}

    def test_corrupted_state_file(self, tmp_path: Path):
        state_file = tmp_path / "index_state.json"
        state_file.write_text("not valid json")
        state = IndexState(str(tmp_path))
        # Should recover gracefully
        assert state.get_indexed_files("/any") == {}
