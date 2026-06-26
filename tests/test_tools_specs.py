"""
tests/test_tools_specs.py — unit tests for the specs/ sandbox added to
hub/tools/tools.py to support the planning agents (Part D: Orchestrator,
Feature Lead). Kept separate from tests/test_tools.py (Part B's file) to
avoid touching it.
"""

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hub.tools import tools as T  # noqa: E402


@pytest.fixture
def clean_specs_sandbox(tmp_path, monkeypatch):
    """Point tools.SPECS_ROOT at a throwaway directory so these tests
    never touch the real specs/ folder."""
    fake_specs_root = tmp_path / "specs"
    fake_specs_root.mkdir(parents=True)
    monkeypatch.setattr(T, "ROOT", tmp_path)
    monkeypatch.setattr(T, "SPECS_ROOT", fake_specs_root.resolve())
    yield fake_specs_root


class TestWriteSpecFile:
    def test_writes_and_creates_parent_dirs(self, clean_specs_sandbox):
        result = T.write_spec_file("specs/features/F01-auth.md", "# F01: Auth\n")
        assert result["ok"] is True
        assert result["created"] is True
        assert (clean_specs_sandbox / "features" / "F01-auth.md").read_text() == "# F01: Auth\n"

    def test_writes_nested_task_path(self, clean_specs_sandbox):
        result = T.write_spec_file("specs/tasks/F01/T01-models.md", "# T01: Models\n")
        assert result["ok"] is True
        assert (clean_specs_sandbox / "tasks" / "F01" / "T01-models.md").exists()

    def test_overwrite_reports_created_false(self, clean_specs_sandbox):
        T.write_spec_file("specs/x.md", "v1")
        result = T.write_spec_file("specs/x.md", "v2")
        assert result["ok"] is True
        assert result["created"] is False
        assert (clean_specs_sandbox / "x.md").read_text() == "v2"

    def test_blocks_path_outside_specs(self, clean_specs_sandbox):
        result = T.write_spec_file("config/agents.yaml", "evil: true")
        assert result["ok"] is False
        assert "specs/" in result["error"]

    def test_blocks_traversal_escape(self, clean_specs_sandbox):
        result = T.write_spec_file("specs/../../etc/evil.md", "x")
        assert result["ok"] is False

    def test_blocks_absolute_path(self, clean_specs_sandbox):
        result = T.write_spec_file("/etc/passwd", "x")
        assert result["ok"] is False

    def test_rejects_writing_over_a_directory(self, clean_specs_sandbox):
        (clean_specs_sandbox / "features").mkdir()
        result = T.write_spec_file("specs/features", "x")
        assert result["ok"] is False


class TestReadSpecFile:
    def test_reads_existing_file(self, clean_specs_sandbox):
        T.write_spec_file("specs/features/F01-auth.md", "# F01: Auth\n")
        result = T.read_spec_file("specs/features/F01-auth.md")
        assert result["ok"] is True
        assert result["content"] == "# F01: Auth\n"

    def test_missing_file_returns_error(self, clean_specs_sandbox):
        result = T.read_spec_file("specs/does-not-exist.md")
        assert result["ok"] is False
        assert "not found" in result["error"].lower()

    def test_blocks_path_outside_specs(self, clean_specs_sandbox):
        result = T.read_spec_file("project.meta.json")
        assert result["ok"] is False
