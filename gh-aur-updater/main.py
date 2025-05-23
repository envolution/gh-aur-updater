"""
main.py - Main orchestrator for the Arch Package Updater.
"""
import logging
import sys
from pathlib import Path
from typing import List, Dict, Optional

# --- Configuration and Core Models ---
from .config import load_configuration, BuildConfiguration
from .models import (
    PKGBUILDData, AURPackageInfo, PackageUpdateTask, BuildResult,
    PkgVersion # For version comparisons
)

# --- Utilities and Clients ---
from .logging_utils import setup_logging
from .utils import run_subprocess # Assuming run_subprocess is in utils.py
from .exceptions import ArchPackageUpdaterError # Assuming exceptions.py exists

# --- Workflow Components ---
from .workspace_scanner import scan_workspace_pkgbuilds
from .aur_client import fetch_maintained_packages
from .nvchecker_client import NvCheckerClient
from .github_client import GitHubClient
from .package_updater import PackageUpdater


# Initialize a module-level logger
# Logging will be fully configured after config load
logger = logging.getLogger("main_orchestrator")


def create_update_tasks(
    globally_updated_versions: Dict[str, str], # {pkg_name: new_upstream_version_str}
    workspace_pkgs_map: Dict[str, PKGBUILDData], # {pkg_base: PKGBUILDData}
    aur_pkgs_map: Dict[str, AURPackageInfo]      # {pkg_base: AURPackageInfo}
) -> List[PackageUpdateTask]:
    """
    Creates PackageUpdateTask objects for packages that have upstream updates
    and are present in the local workspace.
    """
    tasks: List[PackageUpdateTask] = []
    logger.info("Creating update tasks based on global nvchecker results...")

    for pkg_name, new_upstream_ver_str in globally_updated_versions.items():
        if pkg_name not in workspace_pkgs_map:
            logger.warning(f"Package '{pkg_name}' has upstream update to '{new_upstream_ver_str}', "
                           "but no corresponding PKGBUILD found in workspace. Skipping.")
            continue

        pkgbuild_data = workspace_pkgs_map[pkg_name]
        aur_info = aur_pkgs_map.get(pkg_name) # Might be None if new to AUR

        current_aur_ver_str: Optional[str] = None
        if aur_info:
            current_aur_ver_str = str(aur_info.version_obj)
            logger.debug(f"Package '{pkg_name}': Upstream '{new_upstream_ver_str}', AUR '{current_aur_ver_str}', Local PKGBUILD '{str(pkgbuild_data.current_version_obj)}'")
        else:
            logger.debug(f"Package '{pkg_name}': Upstream '{new_upstream_ver_str}', Not on AUR, Local PKGBUILD '{str(pkgbuild_data.current_version_obj)}'")


        # Heuristic: if AUR version is already at or newer than upstream (unlikely but possible with manual updates), skip.
        # More sophisticated version comparison might be needed if PkgVersion objects were created for upstream.
        # For now, string comparison, or assume nvchecker gives truly newer versions.
        if aur_info and aur_info.version_obj.pkgver == new_upstream_ver_str:
            # Could also compare PkgVersion objects if upstream_ver_str was parsed into one
            logger.info(f"Package '{pkg_name}' on AUR (v{aur_info.version_obj}) already matches upstream target '{new_upstream_ver_str}'. Skipping task creation based on global check.")
            continue
        
        # Also check if local PKGBUILD is already at the target version (could happen if run previously and only AUR push failed)
        if pkgbuild_data.pkgver == new_upstream_ver_str and pkgbuild_data.pkgrel == "1":
             logger.info(f"Local PKGBUILD for '{pkg_name}' (v{pkgbuild_data.current_version_obj}) already at target upstream version '{new_upstream_ver_str}-1'. "
                         "Will still process for potential build/push/release if other changes detected by PackageUpdater.")
             # Task is still created; PackageUpdater will see if PKGBUILD content actually changes.

        task = PackageUpdateTask(
            pkgbuild_data=pkgbuild_data,
            aur_info=aur_info,
            target_upstream_ver_str=new_upstream_ver_str
        )
        tasks.append(task)
        logger.info(f"Created task for '{pkg_name}' to update to version '{new_upstream_ver_str}'.")

    if not tasks:
        logger.info("No update tasks created. All relevant packages appear up-to-date with upstream based on global check.")
    return tasks


def run_main_workflow(config: BuildConfiguration):
    """
    Main workflow execution.
    """
    logger.info(f"Starting Arch Package Update workflow for repository: '{config.github_repository}'.")
    logger.info(f"AUR Maintainer: {config.aur_maintainer_name}, Dry Run: {config.dry_run_mode}, Debug: {config.debug_mode}")
    logger.debug(f"Full configuration loaded: {config}")

    if not config.github_workspace.exists() or not config.github_workspace.is_dir():
        logger.critical(f"GITHUB_WORKSPACE path does not exist or is not a directory: {config.github_workspace}")
        raise ArchPackageUpdaterError(f"Invalid GITHUB_WORKSPACE: {config.github_workspace}")
    
    try:
        logger.info("Ensuring essential directories exist...")
        config.base_build_dir.mkdir(parents=True, exist_ok=True)
        config.nvchecker_run_dir.mkdir(parents=True, exist_ok=True)
        config.artifacts_dir_base.mkdir(parents=True, exist_ok=True)
        logger.debug(f"  Base build dir: {config.base_build_dir}")
        logger.debug(f"  Nvchecker run dir: {config.nvchecker_run_dir}")
        logger.debug(f"  Artifacts base dir: {config.artifacts_dir_base}")
    except OSError as e:
        logger.critical(f"Failed to create essential directories: {e}", exc_info=True)
        raise ArchPackageUpdaterError(f"Directory creation failed: {e}") from e

    # --- Initialize Clients ---
    # run_subprocess is passed directly from utils
    nv_client = NvCheckerClient(config, run_subprocess)
    gh_client = GitHubClient(config, run_subprocess) # gh_client checks auth in its init
    updater = PackageUpdater(config, nv_client, gh_client, run_subprocess)

    # --- Phase 1: Information Gathering ---
    logger.info("--- Phase 1: Gathering Package Information ---")
    
    workspace_pkgs: List[PKGBUILDData] = scan_workspace_pkgbuilds(config)
    if not workspace_pkgs:
        logger.warning("No PKGBUILDs successfully parsed from the workspace. Cannot proceed with update checks.")
        logger.info("Workflow finished: No PKGBUILDs to process.")
        return
    
    workspace_pkgs_map: Dict[str, PKGBUILDData] = {pkg.pkgbase: pkg for pkg in workspace_pkgs}
    logger.info(f"Found and parsed {len(workspace_pkgs)} PKGBUILDs from workspace.")

    aur_maintained_pkgs: List[AURPackageInfo] = fetch_maintained_packages(config.aur_maintainer_name)
    aur_pkgs_map: Dict[str, AURPackageInfo] = {pkg.pkgbase: pkg for pkg in aur_maintained_pkgs}
    logger.info(f"Found {len(aur_maintained_pkgs)} packages maintained by '{config.aur_maintainer_name}' on AUR.")

    # --- Phase 2: Global Update Detection (nvchecker) ---
    logger.info("--- Phase 2: Detecting Global Upstream Updates ---")
    
    aur_snapshot_path = nv_client.generate_aur_snapshot_json(aur_maintained_pkgs)
    
    # Define where nvchecker's global run will write its "newver" file
    # This file isn't strictly needed if we parse nvchecker's JSON stream directly,
    # but nvchecker config schema expects a `newver` path.
    global_upstream_versions_path = config.nvchecker_run_dir / "upstream_versions.json"
    
    global_nv_config_path = nv_client.prepare_global_nvchecker_config(
        workspace_pkgs, aur_snapshot_path, global_upstream_versions_path
    )
    keyfile_path = nv_client.generate_keyfile() # Uses config.secret_ghuk_value

    globally_updated_versions: Dict[str, str] = nv_client.run_global_check_and_get_updates(
        global_nv_config_path, keyfile_path
    )

    if not globally_updated_versions:
        logger.info("No packages found with upstream updates compared to AUR during global check.")
        logger.info("Workflow finished: No updates to process.")
        return
    logger.info(f"Global check identified {len(globally_updated_versions)} package(s) with potential updates: {list(globally_updated_versions.keys())}")

    # --- Phase 3: Task Creation ---
    logger.info("--- Phase 3: Creating Update Tasks ---")
    tasks_to_process: List[PackageUpdateTask] = create_update_tasks(
        globally_updated_versions, workspace_pkgs_map, aur_pkgs_map
    )

    if not tasks_to_process:
        logger.info("No actionable update tasks created after filtering. Workflow finished.")
        return
    logger.info(f"Created {len(tasks_to_process)} tasks for package processing.")

    # --- Phase 4: Individual Package Processing ---
    logger.info("--- Phase 4: Processing Individual Package Updates ---")
    all_build_results: List[BuildResult] = []
    overall_success = True

    for i, task in enumerate(tasks_to_process):
        logger.info(f"Processing task {i+1}/{len(tasks_to_process)}: Package '{task.pkgbuild_data.display_name}' "
                    f"Targeting version: {task.target_upstream_ver_str or 'latest'}")
        try:
            build_result = updater.process_package(task)
            all_build_results.append(build_result)
            if build_result.success:
                logger.info(f"Successfully processed '{task.pkgbuild_data.display_name}'. Version: {build_result.new_version}. Actions: {', '.join(build_result.actions_taken)}")
            else:
                overall_success = False
                logger.error(f"Failed to process '{task.pkgbuild_data.display_name}': {build_result.message} "
                             f"{build_result.error_details or ''}")
        except Exception as e: # Catch unexpected errors from process_package itself
            overall_success = False
            logger.critical(f"Critical error during processing of '{task.pkgbuild_data.display_name}': {e}", exc_info=True)
            # Create a BuildResult for this catastrophic failure
            error_result = BuildResult(
                package_name=task.pkgbuild_data.display_name,
                success=False,
                message="Critical error during package processing.",
                error_details=str(e)
            )
            all_build_results.append(error_result)
        logger.info("-" * 60) # Separator between package processing logs

    # --- Phase 5: Reporting & Summary ---
    logger.info("--- Phase 5: Workflow Summary ---")
    successful_updates = sum(1 for r in all_build_results if r.success)
    failed_updates = len(all_build_results) - successful_updates

    logger.info(f"Total tasks processed: {len(all_build_results)}")
    logger.info(f"Successful updates: {successful_updates}")
    logger.info(f"Failed updates: {failed_updates}")

    # Detailed summary using GitHub Actions log grouping
    if all_build_results:
        print("::group::Detailed Package Results Summary") # Start GHA group
        for res in all_build_results:
            status_icon = "✅" if res.success else "❌"
            log_func = logger.info if res.success else logger.error
            log_func(f"{status_icon} Package: {res.package_name}")
            if res.old_version: log_func(f"  Old Version: {res.old_version}")
            if res.new_version: log_func(f"  New Version: {res.new_version}")
            if res.actions_taken: log_func(f"  Actions: {', '.join(res.actions_taken)}")
            if not res.success: log_func(f"  Message: {res.message}")
            if res.error_details: log_func(f"  Error Details: {res.error_details}")
        print("::endgroup::") # End GHA group

    if not overall_success:
        logger.error("One or more packages failed to process. See logs for details.")
        # The script will exit with 1 due to the main try/except block if an unhandled error occurs,
        # or we can explicitly sys.exit(1) here.
        # sys.exit(1) # No, let the main exception handler do this for cleaner exit.

    logger.info("Arch Package Update workflow finished.")
    if not overall_success:
        # Make sure to signal failure to the GHA runner
        raise ArchPackageUpdaterError("Workflow completed with one or more package processing failures.")


#if __name__ == "__main__":
def main_cli_entry_function():
    loaded_config: Optional[BuildConfiguration] = None
    exit_code = 0
    try:
        # Load configuration first, as logging setup depends on it (debug_mode)
        loaded_config = load_configuration()
        setup_logging(debug_enabled=loaded_config.debug_mode)
        
        # Now that logging is configured, use the main logger
        logger.info("Application starting...")
        run_main_workflow(loaded_config)
        logger.info("Application finished successfully.")

    except ArchPackageUpdaterError as e: # Catch our application-specific errors
        # These are "expected" failures in the workflow, log them as errors.
        # Logging should already be set up if config load succeeded.
        logger.error(f"Workflow failed: {e}", exc_info=loaded_config.debug_mode if loaded_config else False)
        exit_code = 1
    except ValueError as e: # Catch config loading value errors
        # Logging might not be fully set up here.
        print(f"CRITICAL CONFIGURATION ERROR: {e}", file=sys.stderr)
        # For GHA, try to emit a GHA error command
        if os.getenv("GITHUB_ACTIONS") == "true":
            print(f"::error title=ConfigurationError::{str(e).replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')}", file=sys.stderr)
        exit_code = 1
    except Exception as e:
        # Catch any other truly unexpected errors.
        # Logging might or might not be set up.
        if logger.handlers:
            logger.critical("Unhandled critical exception in main application.", exc_info=True)
        else:
            print(f"CRITICAL UNHANDLED EXCEPTION: {e}", file=sys.stderr)
            # Try to print traceback manually
            import traceback
            traceback.print_exc(file=sys.stderr)
        exit_code = 1
    finally:
        if exit_code == 0 and logger.handlers:
            logger.info(f"Exiting with status code {exit_code}")
        elif logger.handlers:
            logger.error(f"Exiting with status code {exit_code}")
        else: # If logging failed to setup
            print(f"Exiting with status code {exit_code}", file=sys.stderr)
        sys.exit(exit_code)
