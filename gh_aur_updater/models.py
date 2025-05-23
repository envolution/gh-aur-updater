"""
models.py - Core data structures for the Arch Package Updater.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

# --- Configuration Models ---

@dataclass(frozen=True) # Configuration should generally be immutable after loading
class BuildConfiguration:
    """Overall configuration for the build process, loaded from environment."""
    github_repository: str          # e.g., "owner/repo"
    github_token: str

    github_workspace: Path

    github_run_id: str
    github_actor: str               # User who triggered the workflow

    aur_maintainer_name: str
    aur_git_user_name: str          # User for AUR git commits
    aur_git_user_email: str         # Email for AUR git commits

    source_repo_git_user_name: str  # User for source repo git commits (PKGBUILD updates)
    source_repo_git_user_email: str # Email for source repo git commits

    base_build_dir: Path            # Base for package-specific temporary build dirs
    nvchecker_run_dir: Path         # Dir for global nvchecker files (aur.json, keyfile.toml)
    artifacts_dir_base: Path        # Base for storing build artifacts (logs, packages)

    commit_message_prefix: str
    debug_mode: bool
    dry_run_mode: bool              # If True, no actual changes (git push, releases) are made

    pkgbuild_search_root: Path      # NEW: The root directory for PKGBUILD searches
    secret_ghuk_value: Optional[str] = None # For nvchecker keyfile.toml
    pkgbuild_search_patterns: List[str] = field(default_factory=lambda: ["**/PKGBUILD"])

# --- Package Information Models ---

@dataclass
class PkgVersion:
    """Represents a package version, including pkgver, pkgrel, and epoch."""
    pkgver: str
    pkgrel: str
    pkgbase: str = ""
    epoch: Optional[str] = None

    def __str__(self) -> str:
        version_str = ""
        if self.epoch:
            version_str += f"{self.epoch}:"
        version_str += self.pkgver
        if self.pkgrel: # Should always be present for a full version
            version_str += f"-{self.pkgrel}"
        return version_str

    @classmethod
    def from_string(cls, version_string: str) -> 'PkgVersion':
        """
        Parses a full version string like "epoch:pkgver-pkgrel" or "pkgver-pkgrel".
        """
        epoch: Optional[str] = None
        if ':' in version_string:
            epoch, version_string = version_string.split(':', 1)

        match = re.match(r'(.+?)-([^-]+)$', version_string) # pkgrel is usually numeric but can be complex
        if match:
            pkgver, pkgrel = match.group(1), match.group(2)
            return cls(pkgver=pkgver, pkgrel=pkgrel, epoch=epoch)
        else:
            # Fallback: assume the whole string (after epoch) is pkgver, pkgrel is "1"
            # This might happen for upstream versions without a pkgrel
            return cls(pkgver=version_string, pkgrel="1", epoch=epoch)


@dataclass
class PKGBUILDData:
    """
    Represents metadata extracted from a PKGBUILD (likely via .SRCINFO).
    All list fields default to empty lists.
    """
    pkgbuild_path: Path                 # Absolute path to the PKGBUILD file
    pkgbase: str = ""                       # Usually the primary name
    pkgname: List[str] = field(default_factory=list) # Can be a list for split packages
    pkgver: str = ""
    pkgrel: str = ""
    epoch: Optional[str] = None
    pkgdesc: str = ""
    url: str = ""
    arch: List[str] = field(default_factory=list)
    license: List[str] = field(default_factory=list)
    depends: List[str] = field(default_factory=list)
    makedepends: List[str] = field(default_factory=list)
    checkdepends: List[str] = field(default_factory=list)
    optdepends: List[str] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    replaces: List[str] = field(default_factory=list)
    source: List[str] = field(default_factory=list) # Raw source entries
    sha256sums: List[str] = field(default_factory=list)
    # Add other checksum types if needed (md5, sha512, etc.)

    # Path to the associated .nvchecker.toml, relative to workspace or absolute
    nvchecker_config_path_relative: Optional[str] = None

    @property
    def current_version_obj(self) -> PkgVersion:
        return PkgVersion(pkgver=self.pkgver, pkgrel=self.pkgrel, epoch=self.epoch)

    @property
    def display_name(self) -> str:
        return self.pkgbase or (self.pkgname[0] if self.pkgname else "UnknownPackage")


@dataclass
class AURPackageInfo:
    """Information about a package as listed on the AUR."""
    pkgbase: str # From AUR 'PackageBase'
    name: str    # From AUR 'Name'
    version_str: str # Full version string from AUR, e.g., "1:2.0.1-3"
    maintainer: Optional[str] = None
    # Other useful fields: 'ID', 'NumVotes', 'Popularity', 'LastModified'
    aur_id: Optional[int] = None
    num_votes: Optional[int] = None
    popularity: Optional[float] = None
    last_modified_timestamp: Optional[int] = None

    @property
    def version_obj(self) -> PkgVersion:
        return PkgVersion.from_string(self.version_str)

# --- Task and Result Models ---

@dataclass
class PackageUpdateTask:
    """Represents a package to be processed for updates."""
    pkgbuild_data: PKGBUILDData              # Data from the local PKGBUILD/.SRCINFO
    aur_info: Optional[AURPackageInfo] = None  # Info if it exists on AUR
    # Target upstream version string (e.g., "2.1.0") as determined by global nvchecker
    # This is the version we aim to update the PKGBUILD to.
    target_upstream_ver_str: Optional[str] = None

@dataclass
class BuildResult:
    """Result of processing a single package update task."""
    package_name: str
    success: bool = False
    message: str = ""
    old_version: Optional[str] = None
    new_version: Optional[str] = None # Version after update, if any
    actions_taken: List[str] = field(default_factory=list) # e.g., "PKGBUILD updated", "AUR pushed", "Release created"
    built_package_paths: List[Path] = field(default_factory=list)
    log_artifact_paths: List[Path] = field(default_factory=list)
    error_details: Optional[str] = None


# --- Utility Models (can also be in utils.py) ---
@dataclass
class SubprocessResult:
    """Result of a subprocess execution."""
    returncode: int
    stdout: str
    stderr: str
    command_str: str # For logging
