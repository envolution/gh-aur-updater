"""
aur_client.py - Interacts with the Arch User Repository (AUR) RPC interface.
"""
import logging
import requests # Add 'requests' to requirements.txt
import json
from typing import List, Dict, Any, Optional

from .models import AURPackageInfo, PkgVersion # Assuming models.py is in the same directory or installable package
from .exceptions import ArchPackageUpdaterError

logger = logging.getLogger(__name__)

AUR_RPC_BASE_URL = "https://aur.archlinux.org/rpc"

def fetch_maintained_packages(maintainer_name: str) -> List[AURPackageInfo]:
    """
    Fetches all packages maintained by a specific user from the AUR.

    Args:
        maintainer_name: The AUR username of the maintainer.

    Returns:
        A list of AURPackageInfo objects.

    Raises:
        ArchPackageUpdaterError: If the request fails or the response is unexpected.
    """
    if not maintainer_name:
        logger.error("Maintainer name cannot be empty for fetching AUR packages.")
        return []

    rpc_url = f"{AUR_RPC_BASE_URL}/v5/search/{maintainer_name}?by=maintainer"
    logger.info(f"Fetching AUR packages for maintainer '{maintainer_name}' from {rpc_url}")

    try:
        response = requests.get(rpc_url, timeout=15) # 15-second timeout
        response.raise_for_status()  # Raises HTTPError for bad responses (4XX or 5XX)
        
        json_response = response.json()

        if json_response.get("type") == "error":
            error_msg = json_response.get("error", "Unknown error from AUR RPC.")
            logger.error(f"AUR RPC error for maintainer '{maintainer_name}': {error_msg}")
            raise ArchPackageUpdaterError(f"AUR RPC error: {error_msg}")

        results: List[Dict[str, Any]] = json_response.get("results", [])
        if not results:
            logger.info(f"No packages found for maintainer '{maintainer_name}' on AUR.")
            return []

        aur_packages: List[AURPackageInfo] = []
        for pkg_data in results:
            try:
                # 'PackageBase' is preferred for unique identification, 'Name' can vary for sub-packages
                pkgbase = pkg_data.get("PackageBase")
                name = pkg_data.get("Name")
                version_str = pkg_data.get("Version")

                if not pkgbase or not name or not version_str:
                    logger.warning(f"Skipping AUR package due to missing PackageBase, Name, or Version: {pkg_data}")
                    continue
                
                aur_info = AURPackageInfo(
                    pkgbase=pkgbase,
                    name=name,
                    version_str=version_str,
                    maintainer=pkg_data.get("Maintainer"), # Could be different if co-maintained
                    aur_id=pkg_data.get("ID"),
                    num_votes=pkg_data.get("NumVotes"),
                    popularity=pkg_data.get("Popularity"),
                    last_modified_timestamp=pkg_data.get("LastModified")
                )
                aur_packages.append(aur_info)
                logger.debug(f"Fetched AUR info for: {aur_info.pkgbase} v{aur_info.version_str}")
            except Exception as e: # Catch errors during individual package parsing
                logger.warning(f"Could not parse AUR package data for an entry: {pkg_data}. Error: {e}", exc_info=True)
        
        logger.info(f"Successfully fetched {len(aur_packages)} packages for maintainer '{maintainer_name}'.")
        return aur_packages

    except requests.exceptions.RequestException as e:
        logger.error(f"Network error while fetching AUR packages for '{maintainer_name}': {e}", exc_info=True)
        raise ArchPackageUpdaterError(f"Network error fetching AUR data: {e}") from e
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON response from AUR RPC for '{maintainer_name}': {e}", exc_info=True)
        raise ArchPackageUpdaterError(f"Invalid JSON from AUR RPC: {e}") from e
    except Exception as e: # Catch-all for other unexpected errors
        logger.error(f"Unexpected error fetching AUR packages for '{maintainer_name}': {e}", exc_info=True)
        raise ArchPackageUpdaterError(f"Unexpected error: {e}") from e
