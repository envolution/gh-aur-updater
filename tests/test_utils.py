"""
tests/test_utils.py - Unit tests for utility functions.
"""
import pytest
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

from gh-aur-updater.utils import run_subprocess
from gh-aur-updater.models import SubprocessResult


@patch('subprocess.run')
def test_run_subprocess_success(mock_subprocess_run):
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout = "Success output\n"
    mock_process.stderr = "Warning output\n"
    mock_subprocess_run.return_value = mock_process

    command = ["ls", "-l"]
    result = run_subprocess(command, cwd="/tmp", check=True)

    mock_subprocess_run.assert_called_once_with(
        command, cwd="/tmp", env=None, text=True,
        capture_output=True, input=None, check=True
    )
    assert isinstance(result, SubprocessResult)
    assert result.returncode == 0
    assert result.stdout == "Success output"
    assert result.stderr == "Warning output"
    assert result.command_str == "ls -l"

@patch('subprocess.run')
def test_run_subprocess_failure_check_true(mock_subprocess_run):
    # Configure the mock to simulate CalledProcessError by raising it when check=True
    # and the mocked process has a non-zero return code.
    # subprocess.run itself raises CalledProcessError if check=True and returncode is non-zero.
    # So, we make our mock behave like the real subprocess.run.
    mock_process_fail = MagicMock()
    mock_process_fail.returncode = 1
    mock_process_fail.stdout = "Error output"
    mock_process_fail.stderr = "Failure details"
    mock_process_fail.cmd = ["failing_cmd"] # Used by CalledProcessError
    
    # Make subprocess.run raise the error if its 'check' arg is True
    def side_effect_for_run(*args, **kwargs):
        if kwargs.get('check') and mock_process_fail.returncode != 0:
            raise subprocess.CalledProcessError(
                mock_process_fail.returncode, 
                mock_process_fail.cmd,
                output=mock_process_fail.stdout, # CalledProcessError uses 'output' for stdout
                stderr=mock_process_fail.stderr
            )
        return mock_process_fail
        
    mock_subprocess_run.side_effect = side_effect_for_run

    command = ["failing_cmd", "--arg"]
    with pytest.raises(subprocess.CalledProcessError) as excinfo:
        run_subprocess(command, check=True)
    
    assert excinfo.value.returncode == 1
    assert excinfo.value.output == "Error output" # CalledProcessError uses .output for stdout
    assert excinfo.value.stderr == "Failure details"

@patch('subprocess.run')
def test_run_subprocess_failure_check_false(mock_subprocess_run):
    mock_process = MagicMock()
    mock_process.returncode = 127
    mock_process.stdout = ""
    mock_process.stderr = "Command not found"
    mock_subprocess_run.return_value = mock_process

    command = ["non_existent_cmd"]
    result = run_subprocess(command, check=False) # check=False, so no exception raised by run_subprocess itself

    assert result.returncode == 127
    assert result.stderr == "Command not found"

@patch('subprocess.run', side_effect=FileNotFoundError("Mocked FileNotFoundError"))
def test_run_subprocess_filenotfound(mock_subprocess_run_filenotfound):
    command = ["ghost_command"]
    with pytest.raises(FileNotFoundError):
        run_subprocess(command)