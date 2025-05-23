"""
logging_utils.py - Configures logging for GitHub Actions and local development.
"""
import logging
import sys
import os

# Determine if running in GitHub Actions
IS_GHA = os.getenv("GITHUB_ACTIONS") == "true"

class GitHubActionsFormatter(logging.Formatter):
    """
    Formats log messages for GitHub Actions commands.
    See: https://docs.github.com/en/actions/reference/workflow-commands-for-github-actions
    """
    def format(self, record: logging.LogRecord) -> str:
        # Get the formatted message using the original formatter (or just record.getMessage())
        # This ensures that if a format string was set for the handler, it's used.
        # However, for GHA, we typically just want the raw message.
        message = record.getMessage()
        
        # Sanitize message for GHA: % -> %25, \r -> %0D, \n -> %0A
        message = message.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')

        filename = record.pathname
        lineno = record.lineno
        title = record.name # Using logger name as title for ::notice

        if record.levelno == logging.DEBUG:
            return f"::debug file={filename},line={lineno}::{message}"
        elif record.levelno == logging.INFO:
            return f"::notice file={filename},line={lineno},title={title}::{message}"
        elif record.levelno == logging.WARNING:
            return f"::warning file={filename},line={lineno}::{message}"
        elif record.levelno >= logging.ERROR: # Catches ERROR and CRITICAL
            return f"::error file={filename},line={lineno}::{message}"
        
        # Fallback for any other levels, though not expected with standard setup
        return f"{logging.getLevelName(record.levelno)}: {message}"


def setup_logging(debug_enabled: bool = False, force_gha_logging: bool = False):
    """
    Configures root logger.
    - debug_enabled: If True, sets logging level to DEBUG.
    - force_gha_logging: If True, uses GHA formatter even if not in GHA env.
    """
    root_logger = logging.getLogger()
    
    # Clear any existing handlers to prevent duplicate logs if setup_logging is called multiple times
    if root_logger.hasHandlers():
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

    log_level = logging.DEBUG if debug_enabled else logging.INFO
    root_logger.setLevel(log_level)

    # In GHA, all logs (debug, info, warning, error) should generally go to stderr.
    # stdout is often reserved for primary output data if the script is part of a pipe.
    handler = logging.StreamHandler(sys.stderr) 

    use_gha_formatter = IS_GHA or force_gha_logging

    if use_gha_formatter:
        # For GHA, the message itself is the core, file/line are part of the command.
        # No need for timestamp or level name in the message part of the GHA command.
        formatter = GitHubActionsFormatter() 
    else:
        # For local development, a more verbose and human-readable format.
        # Consider using 'rich.logging.RichHandler' for colored output locally.
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)-8s] %(name)s (%(filename)s:%(lineno)d): %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Suppress overly verbose logs from common libraries if desired
    # logging.getLogger("requests").setLevel(logging.WARNING)
    # logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Log that logging is setup (this will use the new handlers/formatters)
    logging.debug(f"Logging initialized. Level: {logging.getLevelName(log_level)}. GHA Mode: {use_gha_formatter}.")