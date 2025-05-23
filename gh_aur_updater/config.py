"""
config.py - Loads and provides the BuildConfiguration.
"""
import os
import re # For PkgVersion model parsing
from pathlib import Path
from typing import Optional

from .models import BuildConfiguration # Assuming models.py is in the same directory

# For local development with .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv is optional, mainly for local dev. Fail silently if not present.
    pass

def _get_env_var(name: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
    value = os.getenv(name)
    if value is None or value == "": # Treat empty string as None for optional vars
        if required:
            raise ValueError(f"Missing required environment variable: {name}")
        return default
    return value

def _to_path(value: Optional[str], base_if_relative: Optional[Path] = None) -> Optional[Path]:
    if not value:
        return None
    path = Path(value)
    if base_if_relative and not path.is_absolute():
        return (base_if_relative / path).resolve()
    return path.resolve()

def _to_bool(value: Optional[str]) -> bool:
    return value.lower() in ['true', '1', 'yes'] if value else False

def _get_env_list(name: str, default: Optional[List[str]] = None) -> Optional[List[str]]:
    # Helper to parse comma-separated string to list
    value = os.getenv(name)
    if value:
        return [item.strip() for item in value.split(',') if item.strip()]
    return default
def load_configuration() -> BuildConfiguration:
    """Loads configuration from environment variables into a BuildConfiguration object."""
    
    github_workspace_path = _to_path(_get_env_var("GITHUB_WORKSPACE", required=True))
    if not github_workspace_path or not github_workspace_path.is_dir():
        raise ValueError(f"GITHUB_WORKSPACE ('{_get_env_var('GITHUB_WORKSPACE')}') is not a valid directory.")

    home_dir_str = _get_env_var("HOME", "/tmp")

    # --- Determine PKGBUILD Search Root ---
    # User can provide a suffix path relative to GITHUB_WORKSPACE
    pkgbuild_search_root_suffix = _get_env_var("PKGBUILD_SEARCH_ROOT_SUFFIX") # e.g., "my-packages/aur" or just "aur"
    if pkgbuild_search_root_suffix:
        pkgbuild_search_root_actual = (github_workspace_path / pkgbuild_search_root_suffix).resolve()
        if not pkgbuild_search_root_actual.is_dir():
            raise ValueError(f"PKGBUILD_SEARCH_ROOT_SUFFIX ('{pkgbuild_search_root_suffix}') "
                             f"resolved to non-existent directory: {pkgbuild_search_root_actual}")
    else:
        pkgbuild_search_root_actual = github_workspace_path # Default to the entire workspace

    # --- PKGBUILD Search Patterns ---
    default_patterns = ["**/PKGBUILD"] # Default pattern relative to pkgbuild_search_root_actual
    pkgbuild_patterns = _get_env_list("PKGBUILD_SEARCH_PATTERNS", default=default_patterns)

    # --- Maintainer and Committer Information ---
    aur_maintainer = _get_env_var("AUR_MAINTAINER_NAME", required=True)
    github_actor = _get_env_var("GITHUB_ACTOR", "github-actions[bot]") # Default if GITHUB_ACTOR not set

    default_aur_user_name = _get_env_var("AUR_GIT_USER_NAME", aur_maintainer)
    default_aur_email = f"{default_aur_user_name.replace(' ', '-').lower()}@users.noreply.github.com"

    default_source_committer_name = _get_env_var("SOURCE_REPO_GIT_USER_NAME", f"{github_actor} (via CI)")
    default_source_committer_email = _get_env_var("SOURCE_REPO_GIT_USER_EMAIL", 
                                                 f"{github_actor.split('[bot]')[0]}@users.noreply.github.com")


    return BuildConfiguration(
        github_repository=_get_env_var("GITHUB_REPOSITORY", required=True),
        github_token=_get_env_var("GH_TOKEN", required=True),
        github_workspace=github_workspace,
        github_run_id=_get_env_var("GITHUB_RUNID", "local-run-unknown-id"),
        github_actor=github_actor,

        aur_maintainer_name=aur_maintainer,
        aur_git_user_name=_get_env_var("AUR_GIT_USER_NAME", default_aur_user_name),
        aur_git_user_email=_get_env_var("AUR_GIT_USER_EMAIL", default_aur_email),

        source_repo_git_user_name=_get_env_var("SOURCE_REPO_GIT_USER_NAME", default_source_committer_name),
        source_repo_git_user_email=_get_env_var("SOURCE_REPO_GIT_USER_EMAIL", default_source_committer_email),
        
        # Default paths are relative to HOME if not overridden by specific env vars
        base_build_dir=_to_path(_get_env_var("PACKAGE_BUILD_BASE_DIR", str(Path(home_dir_str) / "arch_package_builds"))),
        nvchecker_run_dir=_to_path(_get_env_var("NVCHECKER_RUN_DIR", str(Path(home_dir_str) / "nvchecker_run"))),
        artifacts_dir_base=_to_path(_get_env_var("ARTIFACTS_DIR", str(github_workspace / "artifacts"))),

        commit_message_prefix=_get_env_var("COMMIT_MESSAGE_PREFIX", "CI: Auto update"),
        debug_mode=_to_bool(_get_env_var("DEBUG_MODE", "false")),
        dry_run_mode=_to_bool(_get_env_var("DRY_RUN_MODE", "false")),
        secret_ghuk_value=_get_env_var("SECRET_GHUK_VALUE") # Optional
        pkgbuild_search_root=pkgbuild_search_root_actual,
        pkgbuild_search_patterns=pkgbuild_patterns if pkgbuild_patterns else default_patterns # Ensure it's never None
    )
