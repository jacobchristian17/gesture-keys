"""Logging configuration for gesture-keys.

Sets up file handlers that write to logs/ next to the executable (frozen)
or next to the project root (development).

Two log files are produced:
- preview.log  — INFO-level messages (signals, motion, config events)
- debug.log    — DEBUG-level messages (every frame's gesture and state)
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

LOG_FORMAT = "[%(asctime)s] %(levelname)s %(message)s"
LOG_DATEFMT = "%H:%M:%S"
MAX_BYTES = 5 * 1024 * 1024  # 5 MB per file
BACKUP_COUNT = 3


def _logs_dir() -> str:
    """Return the logs directory path, creating it if needed."""
    if getattr(sys, "frozen", False):
        # PyInstaller onedir: exe lives in dist/GestureKeys/
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        # Development: project root (parent of gesture_keys/)
        base = os.path.dirname(os.path.abspath(__file__))
        base = os.path.join(base, os.pardir)
    path = os.path.join(base, "logs")
    os.makedirs(path, exist_ok=True)
    return path


def setup_logging() -> None:
    """Configure the 'gesture_keys' logger with rotating file handlers.

    Both preview.log (INFO) and debug.log (DEBUG) are always written
    simultaneously while the program is running.
    """
    logger = logging.getLogger("gesture_keys")
    logger.setLevel(logging.DEBUG)

    # Avoid adding duplicate handlers on repeated calls
    if logger.handlers:
        return

    logs = _logs_dir()
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT)

    # preview.log — INFO and above
    preview_handler = RotatingFileHandler(
        os.path.join(logs, "preview.log"),
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    preview_handler.setLevel(logging.INFO)
    preview_handler.setFormatter(formatter)
    logger.addHandler(preview_handler)

    # debug.log — DEBUG and above
    debug_handler = RotatingFileHandler(
        os.path.join(logs, "debug.log"),
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(formatter)
    logger.addHandler(debug_handler)
