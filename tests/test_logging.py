"""
Tests for logging integration (src/logging_config.py + main()).

Uses pytest's caplog. Because the recommender logger does not propagate to the
root logger (so it stays out of the console), we attach caplog's handler to the
recommender logger directly for the duration of each test.
"""

import logging
import os

import pytest

from src.logging_config import get_logger, LOG_FILE


def _capture_recommender_logs(caplog):
    """Route the recommender logger's records into caplog."""
    logger = get_logger()
    caplog.set_level(logging.INFO, logger="recommender")
    logger.addHandler(caplog.handler)
    return logger


def test_main_logs_key_events(caplog):
    logger = _capture_recommender_logs(caplog)
    try:
        from src import main as main_module
        main_module.main()  # default profile: strong match, no fallback
    finally:
        logger.removeHandler(caplog.handler)

    text = " ".join(r.getMessage() for r in caplog.records).lower()
    assert "startup" in text                 # application startup
    assert "dataset loaded" in text          # dataset loading + song count
    assert "evaluating" in text              # number of songs evaluated
    assert "recommendation complete" in text # recommendation completion
    assert "confidence" in text              # confidence level


def test_log_file_is_created():
    get_logger().info("touch log file")
    assert os.path.exists(LOG_FILE)


def test_unexpected_error_is_logged(caplog, capsys, monkeypatch):
    logger = _capture_recommender_logs(caplog)
    from src import main as main_module

    def boom(*args, **kwargs):
        raise RuntimeError("simulated failure")

    # Force an unexpected error mid-workflow.
    monkeypatch.setattr(main_module, "recommend_songs", boom)

    try:
        with pytest.raises(SystemExit):
            main_module.main()
    finally:
        logger.removeHandler(caplog.handler)

    # User sees a calm message; the log keeps the technical detail.
    assert "See logs/recommender.log" in capsys.readouterr().out
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert any("unexpected error" in r.getMessage().lower() for r in errors)


def test_conflict_and_fallback_events_are_logged(caplog, monkeypatch):
    from src import main as main_module
    from src.conflicts import Conflict
    from src.fallback import FallbackResult

    logger = _capture_recommender_logs(caplog)

    # Force a conflict and a triggered fallback so those log branches run.
    monkeypatch.setattr(
        main_module, "detect_conflicts",
        lambda prefs, songs: [Conflict("test_conflict", "synthetic conflict")],
    )
    monkeypatch.setattr(
        main_module, "build_fallback",
        lambda prefs, recs, conf: FallbackResult(
            triggered=True, threshold=0.5, confidence=conf.value,
            message="No strong complete match was found.", alternatives=[],
        ),
    )

    try:
        main_module.main()
    finally:
        logger.removeHandler(caplog.handler)

    text = " ".join(r.getMessage().lower() for r in caplog.records)
    assert "profile conflicts detected" in text     # conflict warnings
    assert "conflict [test_conflict]" in text
    assert "fallback activated" in text             # fallback activation


def test_validation_failure_is_logged(caplog, capsys, monkeypatch):
    from src.validation import ProfileValidationError
    logger = _capture_recommender_logs(caplog)
    from src import main as main_module

    def bad_prefs(*args, **kwargs):
        raise ProfileValidationError("simulated bad profile")

    monkeypatch.setattr(main_module, "validate_user_prefs", bad_prefs)

    try:
        with pytest.raises(SystemExit):
            main_module.main()
    finally:
        logger.removeHandler(caplog.handler)

    assert "[Input Error]" in capsys.readouterr().out
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("validation failed" in r.getMessage().lower() for r in warnings)
