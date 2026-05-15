"""Failing tests for archivist.drivers.systemctl.

Per sprint-2 Wave 1 (test-systemctl). Impl lands in Wave 2 (impl-systemctl).

Invariant under test: stop_unit / start_unit never raise. Failures are
logged and surfaced as `False`. argv shape: ["sudo", "systemctl",
"stop"|"start", <name>].
"""
from __future__ import annotations

import logging
import subprocess

import pytest

from archivist.drivers.systemctl import start_unit, stop_unit

UNIT = "cdplay.service"


# ---------------------------- stop_unit ------------------------------

def test_stop_unit_success(fake_subprocess) -> None:
    fake_subprocess.set_result(returncode=0)
    assert stop_unit(UNIT) is True
    argv = _flat(fake_subprocess.calls[0])
    assert argv[:3] == ["sudo", "systemctl", "stop"]
    assert argv[3] == UNIT


def test_stop_unit_nonzero_returns_false(
    fake_subprocess, caplog: pytest.LogCaptureFixture
) -> None:
    fake_subprocess.set_result(returncode=1, stderr="Unit not found")
    with caplog.at_level(logging.WARNING):
        assert stop_unit(UNIT) is False
    assert any("systemctl" in r.message.lower() or "unit" in r.message.lower()
               for r in caplog.records)


def test_stop_unit_filenotfound_returns_false(
    fake_subprocess, caplog: pytest.LogCaptureFixture
) -> None:
    """sudo/systemctl missing (non-Pi dev machine) → False, never raises."""
    fake_subprocess.set_exception(FileNotFoundError("sudo"))
    with caplog.at_level(logging.WARNING):
        assert stop_unit(UNIT) is False
    assert any("sudo" in r.message.lower() or "systemctl" in r.message.lower()
               for r in caplog.records)


# ---------------------------- start_unit -----------------------------

def test_start_unit_success(fake_subprocess) -> None:
    fake_subprocess.set_result(returncode=0)
    assert start_unit(UNIT) is True
    argv = _flat(fake_subprocess.calls[0])
    assert argv[:3] == ["sudo", "systemctl", "start"]
    assert argv[3] == UNIT


def test_start_unit_nonzero_returns_false(
    fake_subprocess, caplog: pytest.LogCaptureFixture
) -> None:
    fake_subprocess.set_result(returncode=1, stderr="Failed to start")
    with caplog.at_level(logging.WARNING):
        assert start_unit(UNIT) is False


def test_start_unit_filenotfound_returns_false(
    fake_subprocess, caplog: pytest.LogCaptureFixture
) -> None:
    fake_subprocess.set_exception(FileNotFoundError("sudo"))
    with caplog.at_level(logging.WARNING):
        assert start_unit(UNIT) is False


# ---------------------- helpers --------------------------------------

def _flat(call) -> list[str]:
    args = call.args
    return [str(x) for x in (args if isinstance(args, (list, tuple)) else [args])]


_ = subprocess  # keep import; impl will use it via the fake fixture
