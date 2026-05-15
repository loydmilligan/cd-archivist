"""Failing tests for the fire-and-forget post-rip hook (sprint-4 / D-process-ready-trigger).

After the atomic READY rename in the state machine, cd-archivist
invokes the music-pipeline's `process-ready-auto` script so the
import kicks off with zero latency. The hook is fire-and-forget
(`subprocess.Popen` without `.wait()`); FileNotFoundError and
PermissionError are swallowed-and-warned so a missing importer
never poisons the state machine.

Impl lands in Wave 2 (impl-process-ready-hook).
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# -------- (a) hook_cmd is None → early return ----------------------


def test_none_hook_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    from archivist.pipeline.post_rip_hook import run_process_ready_hook

    popen = MagicMock()
    monkeypatch.setattr(subprocess, "Popen", popen)
    run_process_ready_hook(None)
    popen.assert_not_called()


# -------- (b) empty string → early return --------------------------


def test_empty_string_hook_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    from archivist.pipeline.post_rip_hook import run_process_ready_hook

    popen = MagicMock()
    monkeypatch.setattr(subprocess, "Popen", popen)
    run_process_ready_hook("")
    popen.assert_not_called()


# -------- (c) bare path → Popen(argv) without shell ----------------


def test_bare_command_fires_popen_argv_form(monkeypatch: pytest.MonkeyPatch) -> None:
    from archivist.pipeline.post_rip_hook import run_process_ready_hook

    proc = MagicMock()
    popen = MagicMock(return_value=proc)
    monkeypatch.setattr(subprocess, "Popen", popen)

    run_process_ready_hook("/srv/cd-music-stack/bin/process-ready-auto")

    popen.assert_called_once()
    args, kwargs = popen.call_args
    assert args[0] == ["/srv/cd-music-stack/bin/process-ready-auto"], (
        f"expected argv form, got args={args}"
    )
    # shell=False (default) — and definitely not True.
    assert kwargs.get("shell") in (False, None), f"shell must NOT be True; got {kwargs!r}"
    # Fire-and-forget: helper must NOT call .wait() / .communicate().
    proc.wait.assert_not_called()
    proc.communicate.assert_not_called()


# -------- (d) FileNotFoundError → warn-and-swallow ------------------


def test_file_not_found_warns_and_swallows(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    from archivist.pipeline.post_rip_hook import run_process_ready_hook

    def boom(*args, **kwargs):
        raise FileNotFoundError("/missing/process-ready-auto")

    monkeypatch.setattr(subprocess, "Popen", boom)

    with caplog.at_level(logging.WARNING):
        # Must NOT raise.
        run_process_ready_hook("/missing/process-ready-auto")

    # Warning mentions the offending command.
    assert any(
        "/missing/process-ready-auto" in r.message
        for r in caplog.records
        if r.levelno >= logging.WARNING
    ), f"expected WARNING mentioning command; got {[r.message for r in caplog.records]}"


# -------- (e) PermissionError → warn-and-swallow -------------------


def test_permission_error_warns_and_swallows(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    from archivist.pipeline.post_rip_hook import run_process_ready_hook

    def boom(*args, **kwargs):
        raise PermissionError("script not executable")

    monkeypatch.setattr(subprocess, "Popen", boom)

    with caplog.at_level(logging.WARNING):
        run_process_ready_hook("/srv/cd-music-stack/bin/process-ready-auto")

    assert any(
        "process-ready-auto" in r.message
        for r in caplog.records
        if r.levelno >= logging.WARNING
    )


# -------- (f) command with args is shlex.split, not shelled --------


def test_command_with_args_split_via_shlex(monkeypatch: pytest.MonkeyPatch) -> None:
    from archivist.pipeline.post_rip_hook import run_process_ready_hook

    popen = MagicMock(return_value=MagicMock())
    monkeypatch.setattr(subprocess, "Popen", popen)

    cmd = "/usr/bin/env bash -lc /srv/cd-music-stack/bin/process-ready-auto"
    run_process_ready_hook(cmd)

    args, kwargs = popen.call_args
    assert args[0] == [
        "/usr/bin/env", "bash", "-lc",
        "/srv/cd-music-stack/bin/process-ready-auto",
    ], f"command must be shlex.split, not handed raw to a shell; got {args[0]!r}"
    assert kwargs.get("shell") in (False, None)
