"""
nvchecker_client.py - Wraps nvchecker and nvcmp command-line tools.
"""
import logging
import json
import os
from pathlib import Path
from typing import List, Dict, Optional, Callable

from .models import BuildConfiguration, AURPackageInfo, PKGBUILDData, SubprocessResult
from .exceptions import ArchPackageUpdaterError
# Assuming utils.py contains run_subprocess and is in the same package level
# from .utils import run_subprocess 

logger = logging.getLogger(__name__)

# Type alias for the subprocess runner function for clarity
SubprocessRunnerFunc = Callable[[List[str], Optional[Path | str], Optional[Dict[str, str]], bool, bool, Optional[str]], SubprocessResult]


class NvCheckerClient:
    """
    Client for interacting with nvchecker and nvcmp.
    """
    def __init__(self, config: BuildConfiguration, run_subprocess_func: SubprocessRunnerFunc):
        self.config = config
        self.run_subprocess = run_subprocess_func

    def generate_aur_snapshot_json(self, aur_packages: List[AURPackageInfo]) -> Path:
        """
        Creates aur.json (oldVer for nvchecker) from the list of AUR packages.
        File is created in config.nvchecker_run_dir.
        """
        output_path = self.config.nvchecker_run_dir / "aur.json"
        aur_data: Dict[str, str] = {}
        for pkg_info in aur_packages:
            # nvchecker typically uses pkgbase as the key.
            # The version string should be just "pkgver" for comparison if epoch/release handled by nvchecker itself.
            # However, for comparing against AUR, using the full version string from AUR is common.
            # Let's use the full version string from AURPackageInfo.
            aur_data[pkg_info.pkgbase] = str(pkg_info.version_obj) # Uses PkgVersion.__str__

        logger.info(f"Generating AUR snapshot (oldVer) at: {output_path}")
        try:
            with open(output_path, 'w') as f:
                json.dump(aur_data, f, indent=2, sort_keys=True)
            logger.debug(f"aur.json content: {json.dumps(aur_data, indent=2, sort_keys=True)}")
        except IOError as e:
            logger.error(f"Failed to write aur.json to {output_path}: {e}", exc_info=True)
            raise ArchPackageUpdaterError(f"IOError writing aur.json: {e}") from e
        return output_path

    def prepare_global_nvchecker_config(
        self,
        workspace_packages: List[PKGBUILDData],
        aur_json_path: Path, # Path to the generated aur.json
        upstream_versions_json_path: Path # Path where nvchecker will write its results
    ) -> Path:
        """
        Aggregates all individual .nvchecker.toml files from workspace_packages
        into a single global configuration file (new.toml) for nvchecker.
        File is created in config.nvchecker_run_dir.
        """
        global_config_path = self.config.nvchecker_run_dir / "new.toml"
        logger.info(f"Preparing global nvchecker configuration at: {global_config_path}")

        config_content = f"[__config__]\n"
        config_content += f"oldver = \"{aur_json_path.resolve()}\"\n"
        # nvchecker will write its findings here if using this newver mechanism
        config_content += f"newver = \"{upstream_versions_json_path.resolve()}\"\n\n"


        aggregated_count = 0
        for pkg_data in workspace_packages:
            if pkg_data.nvchecker_config_path_relative:
                # Resolve relative path from workspace root
                abs_nvchecker_path = (self.config.github_workspace / pkg_data.nvchecker_config_path_relative).resolve()
                if abs_nvchecker_path.is_file():
                    try:
                        logger.debug(f"Appending content from: {abs_nvchecker_path} for {pkg_data.display_name}")
                        config_content += f"# --- Config for {pkg_data.display_name} from {pkg_data.nvchecker_config_path_relative} ---\n"
                        config_content += abs_nvchecker_path.read_text()
                        config_content += "\n\n"
                        aggregated_count += 1
                    except IOError as e:
                        logger.warning(f"Could not read .nvchecker.toml for {pkg_data.display_name} at {abs_nvchecker_path}: {e}")
                else:
                    logger.warning(f".nvchecker.toml for {pkg_data.display_name} not found at resolved path: {abs_nvchecker_path}")
            else:
                logger.debug(f"No .nvchecker.toml specified for {pkg_data.display_name}, skipping aggregation.")

        if aggregated_count == 0:
            logger.warning("No .nvchecker.toml files were found or aggregated for the global check.")
            # Depending on desired behavior, could raise error or return None
            # For now, create an empty (but valid with __config__) new.toml

        try:
            with open(global_config_path, 'w') as f:
                f.write(config_content)
        except IOError as e:
            logger.error(f"Failed to write global nvchecker config to {global_config_path}: {e}", exc_info=True)
            raise ArchPackageUpdaterError(f"IOError writing new.toml: {e}") from e
        
        logger.info(f"Global nvchecker configuration generated with {aggregated_count} individual configs.")
        return global_config_path

    def generate_keyfile(self) -> Optional[Path]:
        """
        Generates keyfile.toml in config.nvchecker_run_dir if secret_ghuk_value is set.
        """
        if not self.config.secret_ghuk_value:
            logger.info("No SECRET_GHUK_VALUE provided, skipping keyfile.toml generation.")
            return None

        keyfile_path = self.config.nvchecker_run_dir / "keyfile.toml"
        keyfile_content = f"[keys]\ngithub = \"{self.config.secret_ghuk_value}\"\n"
        
        logger.info(f"Generating nvchecker keyfile at: {keyfile_path}")
        try:
            with open(keyfile_path, 'w') as f:
                f.write(keyfile_content)
            # Set restrictive permissions for keyfile if possible (best effort)
            try:
                os.chmod(keyfile_path, 0o600)
            except OSError as e:
                logger.warning(f"Could not set permissions on keyfile {keyfile_path}: {e}")
        except IOError as e:
            logger.error(f"Failed to write keyfile.toml to {keyfile_path}: {e}", exc_info=True)
            raise ArchPackageUpdaterError(f"IOError writing keyfile.toml: {e}") from e
        return keyfile_path

    def run_global_check_and_get_updates(
        self,
        global_nvchecker_config_path: Path,
        keyfile_path: Optional[Path]
    ) -> Dict[str, str]:
        """
        Runs nvchecker with the global configuration and --logger json.
        Parses the JSON stream to find packages with "event": "updated".

        Returns:
            A dictionary of {"package_name": "new_version_string"} for updated packages.
        """
        command = ["nvchecker", "-c", str(global_nvchecker_config_path), "--logger", "json"]
        if keyfile_path and keyfile_path.is_file():
            command.extend(["-k", str(keyfile_path)])

        logger.info(f"Running global nvchecker check with config: {global_nvchecker_config_path}")
        
        try:
            # nvchecker with --logger json streams JSON objects, one per line.
            # check=False because nvchecker might exit non-zero if some sources fail but others succeed.
            result = self.run_subprocess(command, cwd=self.config.nvchecker_run_dir, check=False)
            
            updated_packages: Dict[str, str] = {}
            if result.stdout:
                for line in result.stdout.splitlines():
                    try:
                        event_data = json.loads(line)
                        pkg_name = event_data.get("name")
                        event_type = event_data.get("event")
                        version = event_data.get("version")

                        if pkg_name and event_type == "updated" and version:
                            updated_packages[pkg_name] = version
                            logger.info(f"Global nvchecker: '{pkg_name}' updated to '{version}'.")
                        elif event_type == "error":
                            logger.warning(f"Global nvchecker: Error processing '{pkg_name}': {event_data.get('message', 'Unknown error')}")

                    except json.JSONDecodeError:
                        logger.warning(f"Global nvchecker: Could not decode JSON line: {line}")
            
            if result.returncode != 0:
                 logger.warning(f"Global nvchecker command finished with exit code {result.returncode}. Some checks might have failed. Stderr: {result.stderr}")
            
            logger.info(f"Global nvchecker check found {len(updated_packages)} packages with upstream updates.")
            return updated_packages
            
        except subprocess.CalledProcessError as e: # Should not be hit if check=False
            logger.error(f"Global nvchecker run failed unexpectedly (CalledProcessError): {e}", exc_info=True)
            raise ArchPackageUpdaterError(f"Global nvchecker failed: {e}") from e
        except Exception as e:
            logger.error(f"An unexpected error occurred during global nvchecker run: {e}", exc_info=True)
            raise ArchPackageUpdaterError(f"Unexpected error in global nvchecker: {e}") from e

    def run_package_specific_check(
        self,
        package_nvchecker_config_path: Path, # Absolute path to the package's .nvchecker.toml
        keyfile_path: Optional[Path],
        build_dir_for_nvchecker_run: Path # Directory where nvchecker should be run for this package
    ) -> Optional[str]:
        """
        Runs nvchecker for a single package's .nvchecker.toml to get its latest version.
        Parses stderr for "updated to <version>" or "current <version>".

        Returns:
            The latest version string found, or None if no update or error.
        """
        if not package_nvchecker_config_path.is_file():
            logger.warning(f"Package-specific .nvchecker.toml not found at: {package_nvchecker_config_path}")
            return None

        command = ["nvchecker", "-c", str(package_nvchecker_config_path)]
        if keyfile_path and keyfile_path.is_file():
            command.extend(["-k", str(keyfile_path)])

        logger.info(f"Running package-specific nvchecker for config: {package_nvchecker_config_path}")
        
        try:
            # nvchecker without --logger json usually prints "updated to" on stderr.
            # It might exit 0 even if no update, or non-zero on error/no update depending on exact case.
            result = self.run_subprocess(command, cwd=build_dir_for_nvchecker_run, check=False)
            
            # Regex patterns to find version information in nvchecker's default stderr logging
            # Example: "[I M D H:M:S module:LINE] pkgname: updated to 1.2.3"
            # Example: "[I M D H:M:S module:LINE] pkgname: current 1.2.3"
            update_pattern = re.compile(r":\s*updated to\s+([^\s,]+)", re.IGNORECASE)
            current_pattern = re.compile(r":\s*current\s+([^\s,]+)", re.IGNORECASE)

            latest_version_found: Optional[str] = None

            if result.stderr: # Primary place for version info without --logger json
                for line in result.stderr.splitlines():
                    update_match = update_pattern.search(line)
                    if update_match:
                        latest_version_found = update_match.group(1)
                        logger.info(f"Package-specific nvchecker: Found update to '{latest_version_found}' from stderr.")
                        break # Take the first "updated to" found
                    
                    current_match = current_pattern.search(line)
                    if current_match and not latest_version_found: # Prioritize "updated to"
                        latest_version_found = current_match.group(1)
                        logger.info(f"Package-specific nvchecker: Version is current at '{latest_version_found}' from stderr.")
                        # Do not break, "updated to" might appear later if multiple sources defined.
                        # This logic might need refinement if a .toml has multiple version sources.
                        # Usually, for a single package's .toml, the first conclusive result is taken.
            
            if result.returncode != 0 and not latest_version_found:
                 logger.warning(f"Package-specific nvchecker command finished with exit code {result.returncode} and no version info parsed. Stderr: {result.stderr}")
            
            return latest_version_found

        except subprocess.CalledProcessError as e:
            logger.error(f"Package-specific nvchecker run failed (CalledProcessError): {e}", exc_info=True)
            # No ArchPackageUpdaterError here, as it's handled by run_subprocess if check=True
            return None # Or re-raise specific error
        except Exception as e:
            logger.error(f"An unexpected error occurred during package-specific nvchecker run: {e}", exc_info=True)
            # raise ArchPackageUpdaterError(f"Unexpected error in package-specific nvchecker: {e}") from e
            return None