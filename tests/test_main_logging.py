"""Failing tests for the graceful-degradation path in _configure_logging.

When the log directory cannot be created (e.g. running on a laptop dev
shell against the default `/srv/cd-archivist/logs/`), the entrypoint
must fall back to stderr-only logging — never raise. Impl in Wave 2.
"""
from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from archivist.__main__ import _configure_logging


@pytest.fixture(autouse=True)
def _reset_root_logger():
    """Detach all handlers between tests so basicConfig actually re-configs."""
    root = logging.getLogger()
    saved = root.handlers[:]
    root.handlers.clear()
    yield
    root.handlers.clear()
    root.handlers.extend(saved)


def _handler_types() -> set[str]:
    return {type(h).__name__ for h in logging.getLogger().handlers}


def test_writable_parent_attaches_both_handlers(tmp_path: Path) -> None:
    log_path = tmp_path / "logs" / "archivist.log"
    _configure_logging(log_path)
    types = _handler_types()
    assert "StreamHandler" in types
    assert "FileHandler" in types
    assert log_path.parent.is_dir()


def test_mkdir_permission_error_falls_back_to_stderr(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Parent dir mkdir raising PermissionError → stderr-only handler.

    A clear warning naming the path and ARCHIVIST_LOG_PATH env var is
    logged. The function never raises.
    """
    log_path = tmp_path / "denied" / "archivist.log"

    def _raise(*_a, **_kw):
        raise PermissionError("no")

    caplog.set_level(logging.WARNING)
    with patch.object(Path, "mkdir", side_effect=_raise):
        _configure_logging(log_path)

    types = _handler_types()
    assert "StreamHandler" in types
    assert "FileHandler" not in types
    # Warning mentions the path and the env var.
    messages = " ".join(r.getMessage() for r in caplog.records)
    assert str(log_path) in messages
    assert "ARCHIVIST_LOG_PATH" in messages


def test_filehandler_oserror_falls_back_to_stderr(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Parent exists but FileHandler construction fails → stderr-only."""
    log_path = tmp_path / "logs" / "archivist.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    real_filehandler = logging.FileHandler

    def _raise(*_a, **_kw):
        raise OSError("disk gone")

    caplog.set_level(logging.WARNING)
    with patch("logging.FileHandler", side_effect=_raise):
        _configure_logging(log_path)
    # sanity — patch was scoped
    assert logging.FileHandler is real_filehandler

    types = _handler_types()
    assert "StreamHandler" in types
    assert "FileHandler" not in types
    messages = " ".join(r.getMessage() for r in caplog.records)
    assert str(log_path) in messages
