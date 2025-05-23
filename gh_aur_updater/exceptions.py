"""
exceptions.py - Custom exceptions for the Arch Package Updater.
"""
from typing import Optional # <<< ADD THIS IMPORT

class ArchPackageUpdaterError(Exception):
    """Base exception for this application."""
    pass

class PKGBUILDParseError(ArchPackageUpdaterError):
    """Error during PKGBUILD or .SRCINFO parsing."""
    def __init__(self, pkgbuild_path: str, message: str, stderr: Optional[str] = None):
        self.pkgbuild_path = pkgbuild_path
        self.message = message
        self.stderr = stderr
        super().__init__(f"Failed to parse {pkgbuild_path}: {message}" + (f"\nStderr: {stderr}" if stderr else ""))

class SubprocessExecutionError(ArchPackageUpdaterError):
    """Error during subprocess execution not caught by CalledProcessError."""
    pass