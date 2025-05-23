"""
package_updater.py - Core logic for updating, building, and publishing a single package.
Replaces buildscript2.py.
"""
import logging
import shutil
import tempfile
import re
import os
from pathlib import Path
from typing import List, Dict, Optional, Callable # Callable for subprocess_runner

from .models import (
    BuildConfiguration, PackageUpdateTask, BuildResult,
    AURPackageInfo, PKGBUILDData, PkgVersion, SubprocessResult
)
from .exceptions import ArchPackageUpdaterError, PKGBUILDParseError
from .github_client import GitHubClient # Assuming GitHubClient is defined
from .nvchecker_client import NvCheckerClient # Assuming NvCheckerClient is defined
# from .utils import run_subprocess

logger = logging.getLogger(__name__)
SubprocessRunnerFunc = Callable[[List[str], Optional[Path | str], Optional[Dict[str, str]], bool, bool, Optional[str]], SubprocessResult]


class PackageUpdater:
    """
    Handles the end-to-end update process for a single Arch package.
    """
    def __init__(
        self,
        config: BuildConfiguration,
        nv_client: NvCheckerClient,
        gh_client: GitHubClient,
        run_subprocess_func: SubprocessRunnerFunc
    ):
        self.config = config
        self.nv_client = nv_client
        self.gh_client = gh_client
        self.run_subprocess = run_subprocess_func
        self.current_build_dir: Optional[Path] = None # Tracks the temp dir for the current package

    def _cleanup_build_dir(self):
        if self.current_build_dir and self.current_build_dir.exists():
            logger.info(f"Cleaning up temporary build directory: {self.current_build_dir}")
            try:
                # Ensure builder user owns this dir for rmtree if created by builder
                # If Python script (as runner user) created it, it should be able to remove it.
                shutil.rmtree(self.current_build_dir)
            except Exception as e:
                logger.error(f"Failed to remove temporary build directory {self.current_build_dir}: {e}", exc_info=self.config.debug_mode)
        self.current_build_dir = None


    def _update_pkgbuild_version_in_file(
        self,
        pkgbuild_file: Path,
        new_pkgver: str,
        new_pkgrel: str = "1"
    ) -> bool:
        """Updates pkgver and pkgrel in the specified PKGBUILD file."""
        logger.info(f"Attempting to update PKGBUILD '{pkgbuild_file}' to version {new_pkgver}-{new_pkgrel}.")
        try:
            content = pkgbuild_file.read_text()
            original_content = content

            # Update pkgver
            content, subs_made = re.subn(
                r"^(pkgver=)([^\s#]+)",
                rf"\g<1>{new_pkgver}",
                content,
                count=1,
                flags=re.MULTILINE
            )
            if subs_made == 0:
                logger.warning(f"'pkgver=' line not found or not updated in {pkgbuild_file}.")
                # Could be an error if an update was expected.

            # Update pkgrel
            content, subs_made_rel = re.subn(
                r"^(pkgrel=)([^\s#]+)",
                rf"\g<1>{new_pkgrel}",
                content,
                count=1,
                flags=re.MULTILINE
            )
            if subs_made_rel == 0:
                logger.warning(f"'pkgrel=' line not found or not updated in {pkgbuild_file}. Adding it if pkgver updated.")
                if subs_made > 0: # If pkgver was updated, ensure pkgrel exists or is added
                    if "pkgrel=" not in content: # Add it if not present at all
                        content = re.sub(
                            r"^(pkgver=[^\s#]+)",
                            rf"\g<0>\npkgrel={new_pkgrel}",
                            content,
                            count=1,
                            flags=re.MULTILINE
                        )
                    else: # Should have been caught by the subn above if it existed.
                        pass 
            
            if content != original_content:
                pkgbuild_file.write_text(content)
                logger.info(f"PKGBUILD '{pkgbuild_file.name}' updated to {new_pkgver}-{new_pkgrel}.")
                return True
            else:
                logger.info(f"No changes made to PKGBUILD '{pkgbuild_file.name}' content during version update attempt.")
                return False
        except IOError as e:
            logger.error(f"IOError updating PKGBUILD {pkgbuild_file}: {e}", exc_info=self.config.debug_mode)
            raise ArchPackageUpdaterError(f"Failed to read/write PKGBUILD {pkgbuild_file}") from e
        except Exception as e:
            logger.error(f"Unexpected error updating PKGBUILD {pkgbuild_file}: {e}", exc_info=self.config.debug_mode)
            raise ArchPackageUpdaterError(f"Unexpected error updating PKGBUILD {pkgbuild_file}") from e


    def process_package(self, task: PackageUpdateTask) -> BuildResult:
        """
        Processes a single package: updates, builds, publishes.
        """
        pkg_data = task.pkgbuild_data
        pkg_name = pkg_data.display_name # Use pkgbase or first pkgname
        result = BuildResult(package_name=pkg_name, old_version=str(pkg_data.current_version_obj))
        
        original_cwd = Path.cwd()
        self.current_build_dir = Path(tempfile.mkdtemp(prefix=f"{pkg_name}-build-", dir=self.config.base_build_dir))
        
        logger.info(f"Processing package '{pkg_name}' in temporary directory: {self.current_build_dir}")

        try:
            os.chdir(self.current_build_dir)

            # 1. AUR Clone
            aur_repo_url = f"ssh://aur@aur.archlinux.org/{pkg_data.pkgbase}.git"
            logger.info(f"Cloning AUR repository: {aur_repo_url}")
            self.run_subprocess(["git", "clone", aur_repo_url, "."], check=True) # Clone into current dir (self.current_build_dir)
            
            # 2. File Sync from workspace to AUR clone
            logger.info(f"Syncing files from workspace '{pkg_data.pkgbuild_path.parent}' to AUR clone.")
            source_pkg_dir = pkg_data.pkgbuild_path.parent
            try:
                # shutil.copytree needs target dir to not exist or dirs_exist_ok=True (Python 3.8+)
                # A simple loop for robust copy/overwrite:
                for item in source_pkg_dir.iterdir():
                    dest_item = self.current_build_dir / item.name
                    if item.is_dir():
                        shutil.copytree(item, dest_item, dirs_exist_ok=True, symlinks=True)
                    else:
                        shutil.copy2(item, dest_item) # Preserves metadata, overwrites
                logger.debug("Workspace files synced to AUR clone.")
            except Exception as e:
                raise ArchPackageUpdaterError(f"Failed to sync files from workspace: {e}")

            # 3. Git Config for AUR repo
            logger.info(f"Configuring git user for AUR commits as '{self.config.aur_git_user_name}'.")
            self.run_subprocess(["git", "config", "user.name", self.config.aur_git_user_name], check=True)
            self.run_subprocess(["git", "config", "user.email", self.config.aur_git_user_email], check=True)

            # 4. Version Check & PKGBUILD Update
            new_pkgver_str = task.target_upstream_ver_str # Version from global nvchecker
            final_target_version: Optional[str] = new_pkgver_str
            
            # Optional: Run package-specific nvchecker for maximum freshness
            if pkg_data.nvchecker_config_path_relative:
                abs_nvchecker_path = (self.config.github_workspace / pkg_data.nvchecker_config_path_relative).resolve()
                keyfile_path = self.config.nvchecker_run_dir / "keyfile.toml" # Global keyfile
                
                logger.info(f"Performing package-specific nvchecker using: {abs_nvchecker_path}")
                pkg_specific_latest_ver = self.nv_client.run_package_specific_check(
                    abs_nvchecker_path,
                    keyfile_path if keyfile_path.exists() else None,
                    build_dir_for_nvchecker_run=self.current_build_dir # nvchecker can run here
                )
                if pkg_specific_latest_ver:
                    # TODO: Robust version comparison (e.g., using packaging.version)
                    # For simplicity, assume string comparison or that nvchecker gives a 'better' version
                    if not new_pkgver_str or pkg_specific_latest_ver != new_pkgver_str: # Simple check
                        logger.info(f"Package-specific nvchecker found version '{pkg_specific_latest_ver}', "
                                    f"overriding global target '{new_pkgver_str}'.")
                        final_target_version = pkg_specific_latest_ver
            
            pkgs_updated = False
            if final_target_version and final_target_version != pkg_data.pkgver:
                logger.info(f"Newer version found: {final_target_version} (current: {pkg_data.pkgver}). Updating PKGBUILD.")
                if self._update_pkgbuild_version_in_file(Path("PKGBUILD"), final_target_version, "1"):
                    result.actions_taken.append(f"PKGBUILD updated to {final_target_version}-1")
                    result.new_version = f"{final_target_version}-1"
                    pkgs_updated = True
            else:
                logger.info(f"Package '{pkg_name}' is already up-to-date (version: {pkg_data.pkgver}).")
                result.new_version = str(pkg_data.current_version_obj)

            # 5. Build Process
            if pkgs_updated or self.config.debug_mode: # Or some build_mode flag from config
                logger.info("Running updpkgsums...")
                self.run_subprocess(["updpkgsums"], check=True)
                result.actions_taken.append("Checksums updated")

                logger.info("Generating .SRCINFO...")
                srcinfo_proc = self.run_subprocess(["makepkg", "--printsrcinfo", "--nocolor"], check=True)
                Path(".SRCINFO").write_text(srcinfo_proc.stdout)
                result.actions_taken.append(".SRCINFO generated")

                logger.info(f"Building package '{pkg_name}'...")
                # Consider HOME env var for makepkg if running as different user
                # makepkg_env = os.environ.copy()
                # if self.config.makepkg_user_home: makepkg_env["HOME"] = str(self.config.makepkg_user_home)
                self.run_subprocess(
                    ["makepkg", "-Lcs", "--noconfirm", "--needed", "--noprogressbar"],
                    check=True # , env=makepkg_env if makepkg_env differs
                )
                result.actions_taken.append("Package built")

                built_packages = sorted(Path(".").glob(f"{pkg_data.pkgbase}*.pkg.tar.zst")) # Glob in current_build_dir
                if not built_packages: # Fallback for split packages if pkgbase not used in filename
                     built_packages = sorted(Path(".").glob(f"{pkg_name}*.pkg.tar.zst"))
                if not built_packages: # Generic fallback
                     built_packages = sorted(Path(".").glob(f"*.pkg.tar.zst"))

                if not built_packages:
                    raise ArchPackageUpdaterError("No package files (*.pkg.tar.zst) found after successful makepkg.")
                
                result.built_package_paths = [p.resolve() for p in built_packages]
                logger.info(f"Built packages: {[p.name for p in result.built_package_paths]}")

                # 6. Artifact Collection (before potential cleanup)
                package_artifact_dir = self.config.artifacts_dir_base / pkg_name
                package_artifact_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Collecting artifacts to {package_artifact_dir}")
                
                files_to_artifact = [Path("PKGBUILD"), Path(".SRCINFO")] + result.built_package_paths
                for log_file_pattern in ["*.log"]: # Only *.log as per user request
                    files_to_artifact.extend(Path(".").glob(log_file_pattern))
                
                for src_file_rel_path in set(files_to_artifact):
                    src_file_abs = (self.current_build_dir / src_file_rel_path).resolve()
                    if src_file_abs.exists():
                        dest_file = package_artifact_dir / src_file_abs.name
                        shutil.copy2(src_file_abs, dest_file)
                        result.log_artifact_paths.append(dest_file)
                        logger.debug(f"Copied artifact: {dest_file}")

            # 7. AUR Commit & Push
            git_status_check = self.run_subprocess(["git", "status", "--porcelain"], check=True)
            if git_status_check.stdout.strip(): # If there are changes staged or unstaged
                logger.info("Changes detected in AUR git repository. Committing and pushing.")
                # Add all relevant files: PKGBUILD, .SRCINFO, and local source files
                # that were copied from workspace and are part of the PKGBUILD's source array
                files_to_add_to_git = ["PKGBUILD", ".SRCINFO"]
                # Add local files mentioned in PKGBUILDData.source
                for src_entry in pkg_data.source:
                    src_parts = src_entry.split('::')
                    src_filename = src_parts[0]
                    if not ("://" in src_entry or src_entry.startswith("git+")): # If it's a local file
                        if (self.current_build_dir / src_filename).exists():
                           files_to_add_to_git.append(src_filename)
                        else:
                           logger.warning(f"Local source file '{src_filename}' listed in PKGBUILD sources not found in build dir for git add.")
                
                self.run_subprocess(["git", "add"] + list(set(files_to_add_to_git)), check=True)
                
                commit_ver = result.new_version or str(pkg_data.current_version_obj)
                aur_commit_msg = f"{self.config.commit_message_prefix}: {pkg_name} to v{commit_ver}"
                self.run_subprocess(["git", "commit", "-m", aur_commit_msg], check=True)
                
                if not self.config.dry_run_mode:
                    self.run_subprocess(["git", "push"], check=True)
                    logger.info("Pushed changes to AUR.")
                    result.actions_taken.append("AUR changes pushed")
                else:
                    logger.info("[DRY RUN] Would push changes to AUR.")
            else:
                logger.info("No git changes to commit to AUR repository.")

            # 8. GitHub Release
            # Assuming build_mode implies creating a release if packages were built and version changed
            if result.built_package_paths and (pkgs_updated or "Package built" in result.actions_taken) :
                release_tag = f"{pkg_name}-{result.new_version or pkg_data.pkgver}" # Use updated pkgver
                release_title = f"{pkg_name} {result.new_version or pkg_data.pkgver}"
                release_notes = f"Automated release for {pkg_name} version {result.new_version or pkg_data.pkgver}."
                
                if self.gh_client.tag_exists(release_tag):
                    logger.info(f"Release tag '{release_tag}' already exists. Deleting and recreating.")
                    if not self.config.dry_run_mode: self.gh_client.delete_release_and_tag(release_tag)
                    result.actions_taken.append(f"Deleted existing release/tag: {release_tag}")

                logger.info(f"Creating GitHub release: {release_title}")
                if not self.config.dry_run_mode:
                    self.gh_client.create_release(release_tag, release_title, release_notes, result.built_package_paths)
                    result.actions_taken.append(f"GitHub release created/updated: {release_tag}")
                else:
                     logger.info(f"[DRY RUN] Would create GitHub release '{release_title}' with assets.")


            # 9. Sync to Source Repo (PKGBUILD, .SRCINFO)
            if "PKGBUILD updated" in result.actions_taken or ".SRCINFO generated" in result.actions_taken:
                logger.info("Syncing updated PKGBUILD and .SRCINFO back to source repository.")
                files_to_sync_to_source = {
                    "PKGBUILD": pkg_data.pkgbuild_path, # Original path in source workspace
                    ".SRCINFO": pkg_data.pkgbuild_path.parent / ".SRCINFO" # Assumed path in source
                }
                sync_commit_msg_base = f"Sync {pkg_name} files after AUR update to v{result.new_version or pkg_data.pkgver}"

                for filename_in_aur_clone, original_workspace_path in files_to_sync_to_source.items():
                    local_aur_file = self.current_build_dir / filename_in_aur_clone
                    if local_aur_file.exists():
                        # Path relative to GITHUB_WORKSPACE for gh api
                        repo_relative_path = str(original_workspace_path.relative_to(self.config.github_workspace))
                        sha = self.gh_client.get_file_sha(repo_relative_path)
                        commit_msg = f"{sync_commit_msg_base} ({filename_in_aur_clone})"
                        if not self.config.dry_run_mode:
                            self.gh_client.update_file_in_source_repo(repo_relative_path, local_aur_file, commit_msg, sha)
                            result.actions_taken.append(f"Synced {filename_in_aur_clone} to source repo")
                        else:
                            logger.info(f"[DRY RUN] Would sync {filename_in_aur_clone} to source repo path {repo_relative_path}.")
                    else:
                        logger.warning(f"Cannot sync '{filename_in_aur_clone}' to source repo: file not found in AUR clone.")

            result.success = True
            result.message = f"Package '{pkg_name}' processed successfully."

        except ArchPackageUpdaterError as e: # Catch our custom errors
            logger.error(f"Processing failed for '{pkg_name}': {e}", exc_info=self.config.debug_mode)
            result.success = False
            result.message = f"Error processing '{pkg_name}': {e}"
            result.error_details = str(e)
        except subprocess.CalledProcessError as e: # From run_subprocess(check=True)
            logger.error(f"Subprocess command failed for '{pkg_name}': {e.cmd}. Stderr: {e.stderr}", exc_info=self.config.debug_mode)
            result.success = False
            result.message = f"Command failed: {shlex.join(e.cmd)}. Error: {e.stderr[:200]}" # First 200 chars of stderr
            result.error_details = e.stderr
        except Exception as e: # Catch any other unexpected errors
            logger.critical(f"Unexpected critical error processing '{pkg_name}': {e}", exc_info=True)
            result.success = False
            result.message = f"Unexpected critical error processing '{pkg_name}'."
            result.error_details = str(e)
        finally:
            os.chdir(original_cwd) # Crucial to change back
            self._cleanup_build_dir()
            logger.info(f"Finished processing for '{pkg_name}'. Success: {result.success}")

        return result
