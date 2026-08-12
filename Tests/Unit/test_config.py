"""Tests for core configuration."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.config import CynexisSettings, PROJECT_ROOT


def test_default_settings():
    """Settings load with sensible defaults."""
    s = CynexisSettings()
    assert s.cynexis_name == "CYNEXIS"
    assert s.robot_id == "cynexis-001"
    assert s.api_port == 8000
    assert s.mock_mode is True


def test_project_root():
    """Project root resolves correctly."""
    assert PROJECT_ROOT.exists()
    assert (PROJECT_ROOT / "core").is_dir()


def test_resolve_path():
    """Relative paths resolve against project root."""
    s = CynexisSettings()
    resolved = s.resolve_path("./Database/cynexis.db")
    assert "Database" in str(resolved)
    assert "cynexis.db" in str(resolved)
