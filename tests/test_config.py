"""
tests/test_config.py - Unit tests for configuration loading.
"""
import os
import pytest
from pathlib import Path
from gh-aur-updater.config import load_configuration, BuildConfiguration

@pytest.fixture
def mock_env_vars(monkeypatch):
    """Fixture to mock environment variables."""
    env_vars = {
        "GITHUB_REPOSITORY": "testowner/testrepo",
        "GH_TOKEN": "test_token_123",
        "GITHUB_WORKSPACE": "/tmp/gh_workspace",
        "GITHUB_RUNID": "12345",
        "GITHUB_ACTOR": "test_actor",
        "AUR_MAINTAINER_NAME": "test_maintainer",
        "AUR_GIT_USER_NAME": "aur_user",
        "AUR_GIT_USER_EMAIL": "aur_user@example.com",
        "SOURCE_REPO_GIT_USER_NAME": "source_user",
        "SOURCE_REPO_GIT_USER_EMAIL": "source_user@example.com",
        "PACKAGE_BUILD_BASE_DIR": "/tmp/pkg_builds_custom",
        "NVCHECKER_RUN_DIR": "/tmp/nvchecker_run_custom",
        "ARTIFACTS_DIR": "/tmp/artifacts_custom",
        "COMMIT_MESSAGE_PREFIX": "TEST: Auto update",
        "DEBUG_MODE": "true",
        "DRY_RUN_MODE": "true",
        "SECRET_GHUK_VALUE": "secret_key_for_nvchecker"
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    
    # Ensure directories for Path conversion exist if they are checked
    Path(env_vars["GITHUB_WORKSPACE"]).mkdir(parents=True, exist_ok=True)
    Path(env_vars["PACKAGE_BUILD_BASE_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(env_vars["NVCHECKER_RUN_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(env_vars["ARTIFACTS_DIR"]).mkdir(parents=True, exist_ok=True)
    
    return env_vars

def test_load_configuration_all_vars_set(mock_env_vars):
    config = load_configuration()
    assert isinstance(config, BuildConfiguration)
    assert config.github_repository == "testowner/testrepo"
    assert config.github_token == "test_token_123"
    assert config.github_workspace == Path("/tmp/gh_workspace")
    assert config.aur_maintainer_name == "test_maintainer"
    assert config.aur_git_user_name == "aur_user"
    assert config.base_build_dir == Path("/tmp/pkg_builds_custom")
    assert config.debug_mode is True
    assert config.dry_run_mode is True
    assert config.secret_ghuk_value == "secret_key_for_nvchecker"


def test_load_configuration_required_vars_missing(monkeypatch, mock_env_vars): # Use mock_env_vars to set up others
    # mock_env_vars already set GITHUB_WORKSPACE. Now, delete it.
    monkeypatch.delenv("GITHUB_WORKSPACE") # Delete the specific var you want to test for missing

    with pytest.raises(ValueError, match="Missing required environment variable: GITHUB_WORKSPACE"):
        load_configuration()

def test_load_configuration_required_vars_missing(monkeypatch, mock_env_vars): # Use mock_env_vars to set up others
    # mock_env_vars already set GITHUB_WORKSPACE. Now, delete it.
    monkeypatch.delenv("GITHUB_WORKSPACE") # Delete the specific var you want to test for missing

    with pytest.raises(ValueError, match="Missing required environment variable: GITHUB_WORKSPACE"):
        load_configuration()

def test_load_configuration_defaults(monkeypatch):
    # Set only required vars, let others use defaults
    minimal_env = {
        "GITHUB_REPOSITORY": "owner/repo",
        "GH_TOKEN": "token",
        "GITHUB_WORKSPACE": "/tmp/ws_default",
        "AUR_MAINTAINER_NAME": "default_maint",
        "GITHUB_ACTOR": "default_actor" # For default email construction
    }
    for key, value in minimal_env.items():
        monkeypatch.setenv(key, value)
    
    Path(minimal_env["GITHUB_WORKSPACE"]).mkdir(parents=True, exist_ok=True)
    # Simulate HOME for default path constructions
    monkeypatch.setenv("HOME", "/tmp/home_default")
    Path("/tmp/home_default").mkdir(parents=True, exist_ok=True)


    config = load_configuration()
    assert config.aur_git_user_name == "default_maint" # Defaults to maintainer name
    assert config.aur_git_user_email == "default_maint@users.noreply.github.com"
    assert config.debug_mode is False # Default
    assert config.dry_run_mode is False # Default
    assert config.secret_ghuk_value is None # Default
    assert config.base_build_dir == Path("/tmp/home_default/arch_package_builds")
    assert config.commit_message_prefix == "CI: Auto update"
