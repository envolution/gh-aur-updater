"""
pkgbuild_parser.py - Parses PKGBUILD metadata using the .SRCINFO method.
"""
import logging
import re
import os
import subprocess # Using subprocess directly here for focused error handling
from pathlib import Path
from typing import Dict, List, Optional, Any

from .models import PKGBUILDData
from .exceptions import PKGBUILDParseError
from .utils import run_subprocess, SubprocessResult # Assuming utils.py and SubprocessResult are available

logger = logging.getLogger(__name__)

def _parse_srcinfo_content(content: str, pkgbuild_path: Path) -> Dict[str, Any]:
    """
    Parses the raw string content of a .SRCINFO file into a dictionary.
    Handles multi-line values and common array fields.
    """
    data: Dict[str, Any] = {}
    # Keys that are known to be arrays in .SRCINFO even if they appear once
    # (makepkg --printsrcinfo outputs them one per line for arrays)
    array_keys = {
        "pkgname", "arch", "license", "groups",
        "depends", "makedepends", "checkdepends", "optdepends",
        "provides", "conflicts", "replaces", "backup",
        "source", "sha1sums", "sha256sums", "sha384sums", "sha512sums", "md5sums"
    }

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        # Split on the first '='
        key_value = line.split('=', 1)
        if len(key_value) != 2:
            logger.warning(f"Skipping malformed .SRCINFO line in {pkgbuild_path}: '{line}'")
            continue
        
        key, value = key_value[0].strip(), key_value[1].strip()

        if key in array_keys:
            if key not in data:
                data[key] = []
            data[key].append(value)
        elif key in data: # A non-array key appearing again (should not happen in valid .SRCINFO for scalar values)
            # If it happens, convert to list and append. This is defensive.
            if not isinstance(data[key], list):
                data[key] = [data[key]]
            data[key].append(value)
            logger.warning(f"Scalar key '{key}' appeared multiple times in .SRCINFO for {pkgbuild_path}. Treating as array.")
        else:
            data[key] = value
            
    return data

def parse_pkgbuild_srcinfo(
    pkgbuild_file_path: Path,
    builder_home_dir: Optional[Path] = None # For setting HOME if makepkg runs as different user
) -> Optional[PKGBUILDData]:
    """
    Generates .SRCINFO for a given PKGBUILD and parses it into PKGBUILDData.

    Args:
        pkgbuild_file_path: Absolute path to the PKGBUILD file.
        builder_home_dir: Optional home directory to set for the makepkg environment.
                          Useful if makepkg is run via sudo -u builder.

    Returns:
        A PKGBUILDData object if successful, None otherwise.
    """
    if not pkgbuild_file_path.is_file():
        logger.error(f"PKGBUILD file not found at: {pkgbuild_file_path}")
        return None

    pkgbuild_dir = pkgbuild_file_path.parent
    logger.debug(f"Generating .SRCINFO for: {pkgbuild_file_path}")

    command = ["sudo", "-u", "builder", "makepkg", "--printsrcinfo", "--nocolor", 
               "BUILDDIR=/tmp", "PKGDEST=/tmp", "SRCDEST=/tmp"]
    env_vars = os.environ.copy() # Inherit current environment
    if builder_home_dir:
        env_vars["HOME"] = str(builder_home_dir)
        # If running makepkg as a different user via sudo, that sudo command
        # in run_subprocess would need to handle -E and -u.
        # For now, assume run_subprocess executes as current user, or env is for current user.
        
    try:
        # Using subprocess directly for more control over env and potential sudo
        # If `run_subprocess` from `utils.py` can handle `env` properly, it can be used.
        # For now, this is more explicit for `makepkg`.
        process = subprocess.run(
            command,
            cwd=str(pkgbuild_dir), # makepkg needs to run in the PKGBUILD's directory
            capture_output=True,
            text=True,
            check=False, # We will check returncode manually
            env=env_vars
        )

        if process.returncode != 0:
            raise PKGBUILDParseError(
                pkgbuild_path=str(pkgbuild_file_path),
                message=f"makepkg --printsrcinfo failed with exit code {process.returncode}.",
                stderr=process.stderr.strip()
            )
        
        srcinfo_content = process.stdout
        if not srcinfo_content:
            raise PKGBUILDParseError(
                pkgbuild_path=str(pkgbuild_file_path),
                message="makepkg --printsrcinfo produced no output."
            )

        parsed_dict = _parse_srcinfo_content(srcinfo_content, pkgbuild_file_path)
        
        # .SRCINFO might not have all fields if PKGBUILD is minimal/broken
        # Default to empty strings or lists where appropriate in PKGBUILDData
        
        # pkgname in .SRCINFO is always a list, even for single packages
        pkgname_list = parsed_dict.get("pkgname", [])
        if not pkgname_list:
             raise PKGBUILDParseError(
                pkgbuild_path=str(pkgbuild_file_path),
                message="Mandatory 'pkgname' not found in .SRCINFO."
            )

        data = PKGBUILDData(
            pkgbuild_path=pkgbuild_file_path.resolve(),
            pkgbase=parsed_dict.get("pkgbase", pkgname_list[0]), # Fallback pkgbase to first pkgname
            pkgname=pkgname_list,
            pkgver=parsed_dict.get("pkgver", ""),
            pkgrel=parsed_dict.get("pkgrel", ""),
            epoch=parsed_dict.get("epoch"), # Optional
            pkgdesc=parsed_dict.get("pkgdesc", ""),
            url=parsed_dict.get("url", ""),
            arch=parsed_dict.get("arch", []),
            license=parsed_dict.get("license", []),
            depends=parsed_dict.get("depends", []),
            makedepends=parsed_dict.get("makedepends", []),
            checkdepends=parsed_dict.get("checkdepends", []),
            optdepends=parsed_dict.get("optdepends", []),
            provides=parsed_dict.get("provides", []),
            conflicts=parsed_dict.get("conflicts", []),
            replaces=parsed_dict.get("replaces", []),
            source=parsed_dict.get("source", []),
            sha256sums=parsed_dict.get("sha256sums", [])
            # Add other checksums and fields as needed
        )
        
        # Basic validation: pkgver and pkgrel should exist if pkgname does
        if not data.pkgver or not data.pkgrel:
            logger.warning(f"Potentially incomplete .SRCINFO for {data.display_name}: pkgver or pkgrel missing.")
            # Depending on strictness, could raise PKGBUILDParseError here too.

        logger.info(f"Successfully parsed .SRCINFO for {data.display_name} (v{data.current_version_obj})")
        return data

    except PKGBUILDParseError as e: # Catch our own specific error
        logger.error(str(e))
        return None
    except FileNotFoundError: # makepkg not found
        logger.critical(f"The 'makepkg' command was not found. It is required to parse PKGBUILDs.")
        # This is a fatal error for the application's current strategy.
        # Re-raise or handle by exiting. For now, log and return None.
        # raise # Or sys.exit(1) after logging
        return None
    except Exception as e: # Catch any other unexpected errors
        logger.error(f"An unexpected error occurred parsing {pkgbuild_file_path}: {e}", exc_info=True)
        return None
