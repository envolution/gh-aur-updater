"""
github_client.py - Encapsulates interactions with GitHub API, primarily via the 'gh' CLI.
"""
import logging
import base64
import json # For parsing gh api json output if needed
from pathlib import Path
from typing import List, Dict, Optional, Callable # Callable is for the subprocess_runner_func

from .models import BuildConfiguration, SubprocessResult
from .exceptions import ArchPackageUpdaterError

# from .utils import run_subprocess # Assuming run_subprocess is defined in utils.py

logger = logging.getLogger(__name__)
SubprocessRunnerFunc = Callable[[List[str], Optional[Path | str], Optional[Dict[str, str]], bool, bool, Optional[str]], SubprocessResult]


class GitHubClient:
    """
    Client for interacting with GitHub services (releases, repository files).
    """
    def __init__(self, config: BuildConfiguration, run_subprocess_func: SubprocessRunnerFunc):
        self.config = config
        self.run_subprocess = run_subprocess_func
        self._check_gh_auth()

    def _check_gh_auth(self):
        """Verifies gh CLI authentication."""
        logger.debug("Checking gh CLI authentication status...")
        try:
            # Use check=False as gh auth status might exit non-zero if not logged in,
            # but we don't want to halt everything just for a check.
            # Actual commands will fail later if not authenticated.
            result = self.run_subprocess(["gh", "auth", "status"], check=False)
            if result.returncode == 0:
                logger.info("gh CLI is authenticated.")
            else:
                logger.warning(f"gh CLI auth status check failed or not logged in. Stderr: {result.stderr}")
                logger.warning("Ensure GH_TOKEN is correctly configured and gh CLI is logged in for full functionality.")
        except FileNotFoundError:
            logger.critical("'gh' command not found. GitHub interactions will fail.")
            raise ArchPackageUpdaterError("'gh' command-line tool not found. Please install it.")
        except Exception as e: # Catch other potential errors like permission issues
            logger.error(f"Error during gh auth check: {e}", exc_info=self.config.debug_mode)


    def get_file_sha(self, repo_file_path: str) -> Optional[str]:
        """
        Gets the SHA of a file in the source repository.
        repo_file_path: Path to the file relative to the repository root.
        """
        logger.debug(f"Fetching SHA for '{repo_file_path}' in '{self.config.github_repository}'")
        command = [
            "gh", "api",
            f"repos/{self.config.github_repository}/contents/{repo_file_path}",
            "--jq", ".sha"
        ]
        try:
            result = self.run_subprocess(command, check=False) # check=False because file might not exist (404)
            if result.returncode == 0 and result.stdout.strip() and result.stdout.strip() != "null":
                sha = result.stdout.strip().strip('"') # Remove quotes if any
                logger.debug(f"Found SHA '{sha}' for '{repo_file_path}'.")
                return sha
            elif result.returncode == 0 and (not result.stdout.strip() or result.stdout.strip() == "null"):
                 logger.info(f"File '{repo_file_path}' not found or has no SHA in repo (may be new).")
                 return None
            else: # Non-zero exit code from gh api usually means an error (e.g. 404 not found)
                logger.warning(f"Failed to get SHA for '{repo_file_path}'. Exit: {result.returncode}, Stderr: {result.stderr}")
                return None
        except Exception as e:
            logger.error(f"Error getting SHA for '{repo_file_path}': {e}", exc_info=self.config.debug_mode)
            return None

    def update_file_in_source_repo(
        self,
        repo_file_path: str,  # Relative path in the source GitHub repo
        local_file_to_upload: Path,
        commit_message: str,
        current_sha: Optional[str]
    ):
        """
        Updates a file in the source GitHub repository using the GitHub API.
        """
        logger.info(f"Updating '{repo_file_path}' in source repo '{self.config.github_repository}' from '{local_file_to_upload}'.")
        if self.config.dry_run_mode:
            logger.info(f"[DRY RUN] Would update '{repo_file_path}' with commit: '{commit_message}'.")
            return

        if not local_file_to_upload.is_file():
            logger.error(f"Local file for upload does not exist: {local_file_to_upload}")
            raise ArchPackageUpdaterError(f"Local file not found: {local_file_to_upload}")

        try:
            content_bytes = local_file_to_upload.read_bytes()
            content_b64 = base64.b64encode(content_bytes).decode("utf-8")

            api_endpoint = f"repos/{self.config.github_repository}/contents/{repo_file_path}"
            
            command_fields = [
                "-f", f"message={commit_message}",
                "-f", f"content={content_b64}",
                "-f", f"author.name={self.config.source_repo_git_user_name}",
                "-f", f"author.email={self.config.source_repo_git_user_email}",
                "-f", f"committer.name={self.config.source_repo_git_user_name}", # Often same as author for CI
                "-f", f"committer.email={self.config.source_repo_git_user_email}",
            ]
            if current_sha:
                command_fields.extend(["-f", f"sha={current_sha}"])

            command = ["gh", "api", "--method", "PUT", api_endpoint] + command_fields
            
            self.run_subprocess(command, check=True) # check=True will raise on failure
            logger.info(f"Successfully updated '{repo_file_path}' in source repository.")

        except Exception as e: # Catches CalledProcessError from run_subprocess or other errors
            logger.error(f"Failed to update '{repo_file_path}' in source repository: {e}", exc_info=self.config.debug_mode)
            raise ArchPackageUpdaterError(f"Failed to update GitHub file '{repo_file_path}': {e}") from e

    def tag_exists(self, tag_name: str) -> bool:
        """Checks if a Git tag (and usually its corresponding release) exists."""
        logger.debug(f"Checking if tag/release '{tag_name}' exists for repo '{self.config.github_repository}'.")
        command = ["gh", "release", "view", tag_name, "-R", self.config.github_repository]
        try:
            # check=False because a non-existent release will cause non-zero exit
            result = self.run_subprocess(command, check=False, capture_output=True) 
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Error checking for tag '{tag_name}': {e}", exc_info=self.config.debug_mode)
            return False # Assume not exists on error

    def delete_release_and_tag(self, tag_name: str):
        """Deletes a GitHub release and its associated Git tag."""
        logger.info(f"Deleting release and tag '{tag_name}' for repo '{self.config.github_repository}'.")
        if self.config.dry_run_mode:
            logger.info(f"[DRY RUN] Would delete release and tag '{tag_name}'.")
            return

        # Delete the release first. If --cleanup-tag is supported and works, it's cleaner.
        # If gh release delete doesn't reliably delete the git tag, we might need a separate gh api call.
        delete_release_command = [
            "gh", "release", "delete", tag_name,
            "--cleanup-tag", # This flag tells gh to delete the underlying git tag as well
            "--yes",         # Skip confirmation prompt
            "-R", self.config.github_repository
        ]
        try:
            self.run_subprocess(delete_release_command, check=True)
            logger.info(f"Successfully deleted release and tag '{tag_name}'.")
        except Exception as e: # Catches CalledProcessError or other errors
            logger.error(f"Failed to delete release/tag '{tag_name}': {e}", exc_info=self.config.debug_mode)
            # Don't re-raise immediately, allow attempting to create new release.
            # If tag deletion failed but release deletion succeeded, create might still work.
            # If release deletion failed, create will likely also fail if it uses same tag.
            # This might need more nuanced error handling if partial success is an issue.
            raise ArchPackageUpdaterError(f"Failed to delete release/tag '{tag_name}': {e}") from e


    def create_release(
        self,
        tag_name: str,
        release_title: str,
        notes: str,
        asset_paths: Optional[List[Path]] = None
    ):
        """Creates a new GitHub release and optionally uploads assets."""
        logger.info(f"Creating release '{release_title}' with tag '{tag_name}' for repo '{self.config.github_repository}'.")
        if self.config.dry_run_mode:
            logger.info(f"[DRY RUN] Would create release '{release_title}' (tag: {tag_name}). Assets: {asset_paths or 'None'}.")
            return

        command = [
            "gh", "release", "create", tag_name,
            "--title", release_title,
            "--notes", notes,
            "-R", self.config.github_repository
        ]
        if asset_paths:
            for asset_path in asset_paths:
                if asset_path.is_file():
                    command.append(str(asset_path))
                else:
                    logger.warning(f"Asset path for release does not exist, skipping: {asset_path}")
        
        try:
            self.run_subprocess(command, check=True)
            logger.info(f"Successfully created release '{release_title}' (tag: {tag_name}) "
                        f"{'with assets.' if asset_paths else 'without assets.'}")
        except Exception as e: # Catches CalledProcessError or other errors
            logger.error(f"Failed to create release '{tag_name}': {e}", exc_info=self.config.debug_mode)
            raise ArchPackageUpdaterError(f"Failed to create GitHub release '{tag_name}': {e}") from e
