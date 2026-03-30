"""Tests for centralized logging setup with console, debug, and file_logging parameters."""

import logging
import os
import tempfile
from unittest.mock import patch

import pytest

from gesture_keys.logging_setup import setup_logging, CONSOLE_FORMAT, LOG_DATEFMT


@pytest.fixture(autouse=True)
def clean_logger():
    """Clear gesture_keys logger handlers before and after each test."""
    logger = logging.getLogger("gesture_keys")
    logger.handlers.clear()
    yield
    logger.handlers.clear()


@pytest.fixture
def tmp_logs(tmp_path):
    """Patch _logs_dir to return a temp directory."""
    with patch("gesture_keys.logging_setup._logs_dir", return_value=str(tmp_path)):
        yield tmp_path


class TestSetupLogging:
    """Tests for setup_logging() parameter combinations."""

    def test_default_no_args_only_preview_log(self, tmp_logs):
        """setup_logging() with no args creates only preview.log handler, no debug.log, no StreamHandler."""
        setup_logging()
        logger = logging.getLogger("gesture_keys")

        handler_types = [type(h).__name__ for h in logger.handlers]
        assert "RotatingFileHandler" in handler_types
        assert "StreamHandler" not in handler_types

        # Only preview.log file handler, no debug.log
        file_handlers = [
            h for h in logger.handlers
            if type(h).__name__ == "RotatingFileHandler"
        ]
        assert len(file_handlers) == 1
        assert "preview.log" in file_handlers[0].baseFilename
        assert file_handlers[0].level == logging.INFO

    def test_console_true_debug_false(self, tmp_logs):
        """setup_logging(console=True, debug=False) creates preview.log + StreamHandler at INFO."""
        setup_logging(console=True, debug=False)
        logger = logging.getLogger("gesture_keys")

        file_handlers = [
            h for h in logger.handlers
            if type(h).__name__ == "RotatingFileHandler"
        ]
        stream_handlers = [
            h for h in logger.handlers
            if type(h).__name__ == "StreamHandler"
        ]

        assert len(file_handlers) == 1
        assert "preview.log" in file_handlers[0].baseFilename

        assert len(stream_handlers) == 1
        assert stream_handlers[0].level == logging.INFO

    def test_console_true_debug_true(self, tmp_logs):
        """setup_logging(console=True, debug=True) creates preview.log + debug.log + StreamHandler at DEBUG."""
        setup_logging(console=True, debug=True)
        logger = logging.getLogger("gesture_keys")

        file_handlers = [
            h for h in logger.handlers
            if type(h).__name__ == "RotatingFileHandler"
        ]
        stream_handlers = [
            h for h in logger.handlers
            if type(h).__name__ == "StreamHandler"
        ]

        assert len(file_handlers) == 2
        filenames = [h.baseFilename for h in file_handlers]
        assert any("preview.log" in f for f in filenames)
        assert any("debug.log" in f for f in filenames)

        assert len(stream_handlers) == 1
        assert stream_handlers[0].level == logging.DEBUG

    def test_console_false_debug_true(self, tmp_logs):
        """setup_logging(console=False, debug=True) creates preview.log + debug.log, no StreamHandler."""
        setup_logging(console=False, debug=True)
        logger = logging.getLogger("gesture_keys")

        file_handlers = [
            h for h in logger.handlers
            if type(h).__name__ == "RotatingFileHandler"
        ]
        stream_handlers = [
            h for h in logger.handlers
            if type(h).__name__ == "StreamHandler"
        ]

        assert len(file_handlers) == 2
        filenames = [h.baseFilename for h in file_handlers]
        assert any("preview.log" in f for f in filenames)
        assert any("debug.log" in f for f in filenames)

        assert len(stream_handlers) == 0

    def test_no_duplicate_handlers_on_double_call(self, tmp_logs):
        """Calling setup_logging() twice does not duplicate handlers."""
        setup_logging(console=True, debug=True)
        logger = logging.getLogger("gesture_keys")
        count_after_first = len(logger.handlers)

        setup_logging(console=True, debug=True)
        count_after_second = len(logger.handlers)

        assert count_after_first == count_after_second

    def test_default_backward_compatible(self, tmp_logs):
        """Default setup_logging() behaves same as setup_logging(console=False, debug=False)."""
        setup_logging()
        logger_default = logging.getLogger("gesture_keys")
        default_handler_count = len(logger_default.handlers)
        default_handler_types = sorted(type(h).__name__ for h in logger_default.handlers)
        default_handler_levels = sorted(h.level for h in logger_default.handlers)

        # Reset
        logger_default.handlers.clear()

        setup_logging(console=False, debug=False)
        explicit_handler_count = len(logger_default.handlers)
        explicit_handler_types = sorted(type(h).__name__ for h in logger_default.handlers)
        explicit_handler_levels = sorted(h.level for h in logger_default.handlers)

        assert default_handler_count == explicit_handler_count
        assert default_handler_types == explicit_handler_types
        assert default_handler_levels == explicit_handler_levels
