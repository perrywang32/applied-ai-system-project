"""
Logging configuration for the Music Recommender.

Detailed, timestamped technical events are written to logs/recommender.log while
the user sees only clean console messages (printed by main.py). The log is for
diagnosis; the console is for people.

Design notes:
  - The logs/ directory is created automatically if it does not exist.
  - We log OUTCOMES and COUNTS (songs loaded, confidence, fallback), not raw
    user data dumps, so no secrets and minimal personal information end up in
    the file. There are no passwords/API keys in this app, and we never log the
    full preference profile.
  - The log level can be raised/lowered with the RECOMMENDER_LOG_LEVEL env var
    (default INFO).
"""

import logging
import os
from pathlib import Path

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "recommender.log")
LOGGER_NAME = "recommender"

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def get_logger(name: str = LOGGER_NAME) -> logging.Logger:
    """
    Return the configured recommender logger, creating the log file/dir once.

    Safe to call repeatedly: the file handler is only attached the first time.
    """
    logger = logging.getLogger(name)

    # Already configured -> reuse it (avoids duplicate handlers / duplicate lines).
    if getattr(logger, "_recommender_configured", False):
        return logger

    level = os.environ.get("RECOMMENDER_LOG_LEVEL", "INFO").upper()
    logger.setLevel(level)

    # Create logs/ automatically, then attach a file handler.
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    logger.addHandler(file_handler)

    # Keep our records out of the root logger so WARNING/ERROR lines are not
    # echoed to the console (the user gets our own clean messages instead).
    logger.propagate = False

    logger._recommender_configured = True  # type: ignore[attr-defined]
    return logger
