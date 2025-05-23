"""
conftest.py - Shared fixtures for pytest.
"""
import pytest
from pathlib import Path

# Example fixture if needed later
@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    """Creates a temporary workspace directory."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace