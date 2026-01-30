"""Tests for FileWriter agent."""

import tempfile
from pathlib import Path

import pytest

from src.infrastructure.agents.file_writer import FileWriter


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def file_writer(temp_dir):
    """FileWriter with temp backup dir."""
    return FileWriter(backup_dir=str(temp_dir / "backups"))


class TestFileWriter:
    """Tests for FileWriter."""

    def test_write_new_file(self, file_writer, temp_dir):
        """Write creates new file."""
        file_path = temp_dir / "new_file.py"
        result = file_writer.write_file(str(file_path), "content")

        assert result["success"] is True
        assert result["created"] is True
        assert result["backup_path"] is None
        assert file_path.read_text() == "content"

    def test_write_existing_file_creates_backup(self, file_writer, temp_dir):
        """Write existing file creates backup."""
        file_path = temp_dir / "existing.py"
        file_path.write_text("original")

        result = file_writer.write_file(str(file_path), "updated")

        assert result["success"] is True
        assert result["created"] is False
        assert result["backup_path"] is not None
        assert file_path.read_text() == "updated"
        assert Path(result["backup_path"]).read_text() == "original"

    def test_write_without_backup(self, file_writer, temp_dir):
        """Write without backup doesn't create backup."""
        file_path = temp_dir / "nobackup.py"
        file_path.write_text("original")

        result = file_writer.write_file(str(file_path), "updated", create_backup=False)

        assert result["success"] is True
        assert result["backup_path"] is None

    def test_write_creates_directories(self, file_writer, temp_dir):
        """Write creates parent directories."""
        file_path = temp_dir / "nested" / "dir" / "file.py"

        result = file_writer.write_file(str(file_path), "content")

        assert result["success"] is True
        assert file_path.read_text() == "content"

    def test_read_file(self, file_writer, temp_dir):
        """Read returns file content."""
        file_path = temp_dir / "read.py"
        file_path.write_text("content to read")

        result = file_writer.read_file(str(file_path))

        assert result["success"] is True
        assert result["content"] == "content to read"

    def test_read_nonexistent_file(self, file_writer, temp_dir):
        """Read nonexistent file returns error."""
        result = file_writer.read_file(str(temp_dir / "nonexistent.py"))

        assert result["success"] is False
        assert result["error"] is not None

    def test_restore_backup(self, file_writer, temp_dir):
        """Restore from backup."""
        # Create original and backup
        file_path = temp_dir / "restore.py"
        file_path.write_text("original")
        write_result = file_writer.write_file(str(file_path), "modified")
        backup_path = write_result["backup_path"]

        # Restore
        result = file_writer.restore_backup(backup_path, str(file_path))

        assert result["success"] is True
        assert file_path.read_text() == "original"

    def test_list_backups(self, file_writer, temp_dir):
        """List backups returns backup info."""
        file_path = temp_dir / "backed.py"
        file_path.write_text("v1")
        file_writer.write_file(str(file_path), "v2")

        backups = file_writer.list_backups()

        # At least one backup should exist
        assert len(backups) >= 1
        assert backups[0]["original_name"] == "backed.py"

    def test_list_backups_filtered(self, file_writer, temp_dir):
        """List backups can filter by filename."""
        file1 = temp_dir / "file1.py"
        file2 = temp_dir / "file2.py"
        file1.write_text("a")
        file2.write_text("b")
        file_writer.write_file(str(file1), "a2")
        file_writer.write_file(str(file2), "b2")

        backups = file_writer.list_backups("file1.py")

        assert all("file1.py" in b["original_name"] for b in backups)
