"""
tests/test_logging_utils.py - Unit tests for logging utilities.
"""
import logging
import pytest
import sys
import os
from gh-aur-updater.logging_utils import GitHubActionsFormatter, setup_logging, IS_GHA

# To capture log output
from io import StringIO

@pytest.fixture
def gha_formatter():
    return GitHubActionsFormatter()

@pytest.fixture(autouse=True)
def reset_root_logger_handlers():
    """Ensures root logger is clean before each test for setup_logging."""
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    yield # Run the test
    for handler in root_logger.handlers[:]: # Cleanup after test
        root_logger.removeHandler(handler)


def test_gha_formatter_debug(gha_formatter):
    record = logging.LogRecord(
        name='test_logger', level=logging.DEBUG, pathname='test.py', lineno=10,
        msg='Debug message with % \r \n special chars', args=(), exc_info=None, func='test_func'
    )
    expected = "::debug file=test.py,line=10::Debug message with %25 %0D %0A special chars"
    assert gha_formatter.format(record) == expected

def test_gha_formatter_info_as_notice(gha_formatter):
    record = logging.LogRecord(
        name='test_logger.module', level=logging.INFO, pathname='another.py', lineno=20,
        msg='Info message', args=(), exc_info=None, func='test_func'
    )
    expected = "::notice file=another.py,line=20,title=test_logger.module::Info message"
    assert gha_formatter.format(record) == expected

def test_gha_formatter_warning(gha_formatter):
    record = logging.LogRecord(
        name='test_logger', level=logging.WARNING, pathname='warn.py', lineno=30,
        msg='Warning message', args=(), exc_info=None, func='test_func'
    )
    expected = "::warning file=warn.py,line=30::Warning message"
    assert gha_formatter.format(record) == expected

def test_gha_formatter_error(gha_formatter):
    record = logging.LogRecord(
        name='test_logger', level=logging.ERROR, pathname='err.py', lineno=40,
        msg='Error message', args=(), exc_info=None, func='test_func'
    )
    expected = "::error file=err.py,line=40::Error message"
    assert gha_formatter.format(record) == expected

# In tests/test_logging_utils.py
def test_setup_logging_gha_mode_info(monkeypatch): # Renamed to reflect it tests INFO level
    monkeypatch.setattr("gh-aur-updater.logging_utils.IS_GHA", True)
    log_capture_string = StringIO()
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]: root_logger.removeHandler(handler)

    setup_logging(debug_enabled=False) # Test INFO level in GHA (debug_enabled=False means INFO)
    
    assert len(root_logger.handlers) >= 1
    original_stream = root_logger.handlers[0].stream
    root_logger.handlers[0].stream = log_capture_string
    
    logger_to_test = logging.getLogger("my_app_gha_test")
    logger_to_test.info("GHA info test message.")
    # The problematic assertion was checking for "::debug" when an INFO message was logged
    # logger_to_test.debug("GHA debug.") # This line was present in a previous test version

    root_logger.handlers[0].stream = original_stream 
    output = log_capture_string.getvalue()

    # This was the assertion that likely failed if the .debug() call was removed
    # assert "::debug file=" in output and "::GHA debug." in output 
    
    # Corrected assertions for an INFO level message:
    assert "::notice file=" in output 
    assert "title=my_app_gha_test::GHA info test message.".replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A') in output
    assert root_logger.level == logging.INFO 

def test_setup_logging_debug_mode(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "false") # Test local formatting
    log_stream = StringIO()
    
    # Temporarily redirect handler to StringIO
    original_stream_handler = logging.StreamHandler
    logging.StreamHandler = lambda stream=None: original_stream_handler(log_stream if stream is sys.stderr else stream)

    setup_logging(debug_enabled=True, force_gha_logging=False)
    
    logger = logging.getLogger("test_setup")
    logger.debug("This is a debug log for setup test.")
    logger.info("This is an info log for setup test.")

    logging.StreamHandler = original_stream_handler # Restore
    
    output = log_stream.getvalue()
    assert "DEBUG" in output # Level was set
    assert "This is a debug log for setup test." in output
    assert "This is an info log for setup test." in output
    assert "::debug" not in output # Should use standard formatter

# In tests/test_logging_utils.py

def test_setup_logging_gha_mode_info_as_notice(monkeypatch): # Test INFO logs become ::notice
    monkeypatch.setattr("gh-aur-updater.logging_utils.IS_GHA", True)
    log_capture_string = StringIO()
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]: root_logger.removeHandler(handler)

    setup_logging(debug_enabled=False) # Logging level set to INFO

    assert len(root_logger.handlers) >= 1
    original_stream = root_logger.handlers[0].stream
    root_logger.handlers[0].stream = log_capture_string
    
    logger_to_test = logging.getLogger("my_app_gha_info_test")
    logger_to_test.info("GHA info actual message.")
    
    root_logger.handlers[0].stream = original_stream 
    output = log_capture_string.getvalue()

    # Sanitize expected message parts for comparison if needed
    expected_message_part = "GHA info actual message.".replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
    
    assert "::notice file=" in output
    assert f"title=my_app_gha_info_test::{expected_message_part}" in output
    assert root_logger.level == logging.INFO

def test_setup_logging_gha_mode_debug(monkeypatch): # Test DEBUG logs become ::debug
    monkeypatch.setattr("gh-aur-updater.logging_utils.IS_GHA", True)
    log_capture_string = StringIO()
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]: root_logger.removeHandler(handler)

    setup_logging(debug_enabled=True) # Logging level set to DEBUG

    assert len(root_logger.handlers) >= 1
    original_stream = root_logger.handlers[0].stream
    root_logger.handlers[0].stream = log_capture_string
    
    logger_to_test = logging.getLogger("my_app_gha_debug_test")
    logger_to_test.debug("GHA debug actual message.") # This will now be logged
    
    root_logger.handlers[0].stream = original_stream 
    output = log_capture_string.getvalue()
    
    expected_message_part = "GHA debug actual message.".replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')

    assert "::debug file=" in output
    assert f"::{expected_message_part}" in output # No title for debug
    assert root_logger.level == logging.DEBUG
