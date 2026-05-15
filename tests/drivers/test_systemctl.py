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


def _find_unit_scope():
    """Lazy import of the not-yet-implemented find_unit_scope.

    Kept lazy so this test module still collects (and the existing 6
    cases still run) before impl-systemctl-scope lands.
    """
    from archivist.drivers.systemctl import find_unit_scope  # noqa: PLC0415

    return find_unit_scope

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


# ---------------------- scope= refactor (D-cdplay-scope) -------------

def test_stop_unit_system_scope_explicit(fake_subprocess) -> None:
    """scope="system" (the default) keeps argv = ["sudo", "systemctl", ...]."""
    fake_subprocess.set_result(returncode=0)
    assert stop_unit(UNIT, scope="system") is True
    argv = _flat(fake_subprocess.calls[0])
    assert argv == ["sudo", "systemctl", "stop", UNIT]


def test_stop_unit_user_scope_skips_sudo(fake_subprocess) -> None:
    """scope="user" → argv = ["systemctl", "--user", ...]; no sudo."""
    fake_subprocess.set_result(returncode=0)
    assert stop_unit(UNIT, scope="user") is True
    argv = _flat(fake_subprocess.calls[0])
    assert argv == ["systemctl", "--user", "stop", UNIT]
    assert "sudo" not in argv


def test_start_unit_user_scope_skips_sudo(fake_subprocess) -> None:
    """scope="user" on start → argv = ["systemctl", "--user", "start", ...]; no sudo."""
    fake_subprocess.set_result(returncode=0)
    assert start_unit(UNIT, scope="user") is True
    argv = _flat(fake_subprocess.calls[0])
    assert argv == ["systemctl", "--user", "start", UNIT]
    assert "sudo" not in argv


def test_find_unit_scope_user_only(fake_subprocess) -> None:
    """find_unit_scope: system is-active fails, user is-active succeeds → "user"."""
    from tests.conftest import FakeCompletedProcess  # noqa: PLC0415

    # Order matches the spec: system first, then user.
    fake_subprocess.queue(FakeCompletedProcess([], returncode=3, stdout="inactive\n"))
    fake_subprocess.queue(FakeCompletedProcess([], returncode=0, stdout="active\n"))

    assert _find_unit_scope()(UNIT) == "user"
    # System call uses no --user; user call includes --user.
    system_call = _flat(fake_subprocess.calls[0])
    user_call = _flat(fake_subprocess.calls[1])
    assert "--user" not in system_call
    assert "--user" in user_call


def test_find_unit_scope_system_wins_on_tie(fake_subprocess) -> None:
    """Both report active → "system" wins."""
    from tests.conftest import FakeCompletedProcess  # noqa: PLC0415

    fake_subprocess.queue(FakeCompletedProcess([], returncode=0, stdout="active\n"))
    fake_subprocess.queue(FakeCompletedProcess([], returncode=0, stdout="active\n"))

    assert _find_unit_scope()(UNIT) == "system"


def test_find_unit_scope_system_only(fake_subprocess) -> None:
    """Only system reports active → "system"."""
    from tests.conftest import FakeCompletedProcess  # noqa: PLC0415

    fake_subprocess.queue(FakeCompletedProcess([], returncode=0, stdout="active\n"))
    fake_subprocess.queue(FakeCompletedProcess([], returncode=3, stdout="inactive\n"))

    assert _find_unit_scope()(UNIT) == "system"


def test_find_unit_scope_neither(fake_subprocess) -> None:
    """Neither reports active → None, never raises."""
    fake_subprocess.set_result(returncode=3, stdout="inactive\n")
    assert _find_unit_scope()(UNIT) is None


def test_find_unit_scope_filenotfound_returns_none(
    fake_subprocess, caplog: pytest.LogCaptureFixture
) -> None:
    """systemctl missing entirely → None, logged, never raises."""
    fake_subprocess.set_exception(FileNotFoundError("systemctl"))
    with caplog.at_level(logging.WARNING):
        assert _find_unit_scope()(UNIT) is None
