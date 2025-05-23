"""
workspace_scanner.py - Scans the workspace for PKGBUILD files and parses them.
"""
import logging
from pathlib import Path
from typing import List, Optional

from .models import PKGBUILDData, BuildConfiguration
from .pkgbuild_parser import parse_pkgbuild_srcinfo

logger = logging.getLogger(__name__)

def find_pkgbuild_files(workspace_root: Path, search_patterns: Optional[List[str]] = None) -> List[Path]:
    """
    Finds all PKGBUILD files within the workspace_root, optionally using glob patterns.
    """
    if not search_patterns:
        # Default search: look for PKGBUILDs in 'maintain/build/*' and 'maintain/test/*' etc.
        # For simplicity, just find all PKGBUILDs under the workspace root.
        # Users can organize their package source directories as they see fit.
        search_patterns = ["**/PKGBUILD"] 
        # More specific example: search_patterns = ["maintain/build/*/PKGBUILD", "experimental/*/PKGBUILD"]

    found_files: List[Path] = []
    for pattern in search_patterns:
        try:
            found_files.extend(list(workspace_root.glob(pattern)))
        except Exception as e:
            logger.error(f"Error during glob pattern '{pattern}' in '{workspace_root}': {e}")
            
    # Filter out duplicates and ensure they are files
    unique_files = sorted(list(set(f for f in found_files if f.is_file())))
    logger.debug(f"Found {len(unique_files)} unique PKGBUILD files using patterns: {search_patterns}")
    return unique_files

def scan_workspace_pkgbuilds(config: BuildConfiguration) -> List[PKGBUILDData]:
    """
    Scans the configured GitHub workspace for PKGBUILDs, parses them,
    and attempts to find associated .nvchecker.toml files.
    """
    logger.info(f"Scanning workspace '{config.github_workspace}' for PKGBUILDs...")
    
    # Define search patterns or get them from config if more flexibility is needed
    # For now, a simple recursive search for any file named "PKGBUILD"
    pkgbuild_file_paths = find_pkgbuild_files(config.github_workspace)

    if not pkgbuild_file_paths:
        logger.warning("No PKGBUILD files found in the workspace.")
        return []

    parsed_pkgbuilds: List[PKGBUILDData] = []
    for pkgbuild_path in pkgbuild_file_paths:
        logger.debug(f"Processing PKGBUILD: {pkgbuild_path}")
        
        # Determine builder_home_dir for makepkg context (if needed, e.g. sudo -u)
        # Assuming makepkg runs as current user, so HOME is not explicitly changed here by default.
        # If `config` had a specific `makepkg_user_home`, it could be passed.
        pkg_data = parse_pkgbuild_srcinfo(pkgbuild_path) # builder_home_dir can be passed if needed

        if pkg_data:
            # Attempt to find an associated .nvchecker.toml file
            # Common locations: same directory as PKGBUILD, or a '.config' subdir
            nvchecker_toml_path = pkgbuild_path.parent / ".nvchecker.toml"
            if nvchecker_toml_path.is_file():
                # Store path relative to workspace root for portability/logging
                try:
                    relative_nv_path = nvchecker_toml_path.relative_to(config.github_workspace)
                    pkg_data.nvchecker_config_path_relative = str(relative_nv_path)
                    logger.debug(f"Found associated .nvchecker.toml for {pkg_data.display_name} at {relative_nv_path}")
                except ValueError: # If not relative (e.g. symlink outside workspace)
                    pkg_data.nvchecker_config_path_relative = str(nvchecker_toml_path.resolve())
                    logger.debug(f"Found associated .nvchecker.toml (absolute path) for {pkg_data.display_name} at {pkg_data.nvchecker_config_path_relative}")
            else:
                logger.debug(f"No .nvchecker.toml found in the same directory as {pkgbuild_path.name} for {pkg_data.display_name}")
            
            parsed_pkgbuilds.append(pkg_data)
        else:
            logger.warning(f"Skipping {pkgbuild_path} due to parsing errors.")
            # Optionally, collect these failures for a summary report

    logger.info(f"Successfully parsed {len(parsed_pkgbuilds)} PKGBUILDs out of {len(pkgbuild_file_paths)} found.")
    return parsed_pkgbuilds