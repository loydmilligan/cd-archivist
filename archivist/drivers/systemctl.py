"""Thin wrapper around `sudo systemctl start|stop <unit>`.

Per sprint-2 task impl-systemctl. The archivist needs to stop
`cdplay.service` to claim `/dev/sr0` and restart it after eject.

Requires the NOPASSWD sudoers fragment from
`docs/operations/cm4-setup.md` §"NOPASSWD sudo fragment" — installed by
hand on the CM4 the first time the rig is wired up. The invariant is
that neither `stop_unit` nor `start_unit` ever raises; failures are
logged and surfaced as `False`.
"""
from __future__ import annotations

import logging
import subprocess
from typing import Literal

_logger = logging.getLogger(__name__)
_TIMEOUT_SECONDS = 10.0


def stop_unit(name: str) -> bool:
    return _run("stop", name)


def start_unit(name: str) -> bool:
    return _run("start", name)


def _run(action: Literal["stop", "start"], name: str) -> bool:
    argv = ["sudo", "systemctl", action, name]
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        _logger.warning("systemctl %s %s failed (sudo/systemctl missing): %s", action, name, exc)
        return False
    except subprocess.TimeoutExpired as exc:
        _logger.warning("systemctl %s %s timed out: %s", action, name, exc)
        return False

    if result.returncode != 0:
        _logger.warning(
            "systemctl %s %s exit %s: %s",
            action,
            name,
            result.returncode,
            result.stderr.strip(),
        )
        return False
    return True
