# arch_package_updater/workspace_scanner.py
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field


from .models import BuildConfiguration # Only need BuildConfiguration here

logger = logging.getLogger(__name__)

@dataclass # Simple dataclass for this stage
class PotentialPackage:
    pkgbuild_path: Path
    nvchecker_config_path_relative: Optional[str] = None
    # We might need pkgbase here if .nvchecker.toml doesn't name the package explicitly.
    # For now, assume nvchecker files are named or sectioned by pkgbase.
    # Alternatively, a quick grep for pkgbase in PKGBUILD could be done here.
    # For simplicity, let's assume nvchecker_client can later map nvchecker output names to pkgbuild_paths.

def find_potential_packages(config: BuildConfiguration) -> List[PotentialPackage]:
    """
    Scans the workspace to find PKGBUILD files and their associated .nvchecker.toml files.
    Does not perform a full PKGBUILD parse at this stage.
    """
    search_root = config.pkgbuild_search_root
    patterns = config.pkgbuild_search_patterns
    logger.info(f"Scanning for PKGBUILDs in '{search_root}' using patterns: {patterns}")
    
    found_pkgbuild_files: List[Path] = []
    for pattern in patterns:
        try:
            # Glob relative to the specified search_root
            found_pkgbuild_files.extend(list(search_root.glob(pattern)))
        except Exception as e:
            logger.error(f"Error during glob pattern '{pattern}' in '{search_root}': {e}")
            
    # Filter out duplicates and ensure they are files
    unique_pkgbuild_paths = sorted(list(set(f for f in found_pkgbuild_files if f.is_file())))
    
    if not unique_pkgbuild_paths:
        logger.warning(f"No PKGBUILD files found in '{search_root}' with patterns: {patterns}")
        return []

    potential_pkgs: List[PotentialPackage] = []
    for pkgbuild_path_abs in unique_pkgbuild_paths:
        nvchecker_toml_abs_path: Optional[Path] = None
        # .nvchecker.toml is usually in the same directory as PKGBUILD
        potential_nv_toml = pkgbuild_path_abs.parent / ".nvchecker.toml"
        if potential_nv_toml.is_file():
            nvchecker_toml_abs_path = potential_nv_toml.resolve()
        
        potential_pkgs.append(
            PotentialPackage(
                pkgbuild_path=pkgbuild_path_abs.resolve(),
                nvchecker_config_path_absolute=nvchecker_toml_abs_path
            )
        )
        logger.debug(f"Found potential package: PKGBUILD at '{pkgbuild_path_abs}', "
                     f"nvchecker: '{nvchecker_toml_abs_path if nvchecker_toml_abs_path else 'None'}'")
            
    logger.info(f"Identified {len(potential_pkgs)} potential packages with PKGBUILDs from '{search_root}'.")
    return potential_pkgs

