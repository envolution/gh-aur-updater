"""
utils.py - Common utility functions and classes.
"""
import subprocess
import shlex
import logging
from pathlib import Path # <<< ADD THIS IMPORT
from typing import Optional, Dict, List # Keep existing typing imports

from .models import SubprocessResult

logger = logging.getLogger(__name__)

def run_subprocess(
    command: List[str],
    cwd: Optional[str | Path] = None, # Now Path is defined
    env: Optional[Dict[str, str]] = None,
    check: bool = True,
    capture_output: bool = True,
    input_str: Optional[str] = None
) -> SubprocessResult:
    """
    Runs a subprocess command with consistent logging and error handling.
    """
    command_str = shlex.join(command)
    # Ensure cwd is converted to string for subprocess.run if it's a Path object
    cwd_str = str(cwd) if isinstance(cwd, Path) else cwd
    logger.debug(f"Running command: {command_str}" + (f" in {cwd_str}" if cwd_str else ""))

    try:
        process = subprocess.run(
            command,
            cwd=cwd_str, # Use the string version of cwd
            env=env,
            text=True,
            capture_output=capture_output,
            input=input_str,
            check=check
        )
        stdout = process.stdout.strip() if process.stdout else ""
        stderr = process.stderr.strip() if process.stderr else ""
        
        if stdout:
            logger.debug(f"Command stdout: {stdout}")
        if stderr:
            logger.debug(f"Command stderr: {stderr}")

        return SubprocessResult(
            returncode=process.returncode,
            stdout=stdout,
            stderr=stderr,
            command_str=command_str
        )
    except subprocess.CalledProcessError as e:
        stdout = e.stdout.strip() if hasattr(e, 'stdout') and e.stdout else ""
        stderr = e.stderr.strip() if hasattr(e, 'stderr') and e.stderr else ""
        logger.error(f"Command failed with exit code {e.returncode}: {command_str}")
        if stdout:
            logger.error(f"Failed command stdout: {stdout}")
        if stderr:
            logger.error(f"Failed command stderr: {stderr}")
        raise 
    except FileNotFoundError:
        logger.error(f"Command not found: {command[0]} from command: {command_str}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred while running command {command_str}: {e}", exc_info=True)
        raise