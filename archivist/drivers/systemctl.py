"""Thin wrapper around `systemctl start|stop <unit>` with scope awareness.

Per sprint-2 task impl-systemctl + sprint-3 task impl-systemctl-scope
(D-cdplay-scope). The archivist needs to stop `cdplay.service` to claim
`/dev/sr0` and restart it after eject — but on the dogfood CM4 cdplay
lives in the user manager (launched via `systemd-run --user`), not the
system manager. Sprint-3 adds:

- a keyword-only `scope` parameter on `stop_unit` / `start_unit`
  selecting between system- and user-manager argv shapes; and
- `find_unit_scope(name)` which probes both managers for `is-active`
  and returns whichever one reports the unit (system wins on a tie).

`scope="system"` requires the NOPASSWD sudoers fragment from
`docs/operations/cm4-setup.md` §"NOPASSWD sudo fragment". `scope="user"`
does NOT need sudo — the user manager is per-uid. The invariant is that
neither call ever raises; failures are logged and surfaced as `False`
(or `None` for `find_unit_scope` on no match).
"""
from __future__ import annotations

import logging
import subprocess
from typing import Literal

_logger = logging.getLogger(__name__)
_TIMEOUT_SECONDS = 10.0

Scope = Literal["system", "user"]


def stop_unit(name: str, *, scope: Scope = "system") -> bool:
    return _run("stop", name, scope)


def start_unit(name: str, *, scope: Scope = "system") -> bool:
    return _run("start", name, scope)


def find_unit_scope(name: str) -> Scope | None:
    """Return which systemd manager has `name` active, or `None`.

    Probes `systemctl is-active <name>` then `systemctl --user is-active
    <name>`. System scope wins on a tie. Returns `None` if neither
    manager reports the unit `active`, or if `systemctl` is missing
    entirely. Never raises.
    """
    if _is_active(["systemctl", "is-active", name]):
        return "system"
    if _is_active(["systemctl", "--user", "is-active", name]):
        return "user"
    return None


def _is_active(argv: list[str]) -> bool:
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as exc:
        _logger.warning("systemctl is-active probe failed (missing binary): %s", exc)
        return False
    except subprocess.TimeoutExpired as exc:
        _logger.warning("systemctl is-active probe timed out: %s", exc)
        return False
    # `is-active` exits 0 and prints "active" when active. Trust both.
    return result.returncode == 0 and result.stdout.strip() == "active"


def _argv(action: Literal["stop", "start"], name: str, scope: Scope) -> list[str]:
    if scope == "user":
        return ["systemctl", "--user", action, name]
    return ["sudo", "systemctl", action, name]


def _run(action: Literal["stop", "start"], name: str, scope: Scope) -> bool:
    argv = _argv(action, name, scope)
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        _logger.warning(
            "systemctl %s %s [%s] failed (sudo/systemctl missing): %s",
            action, name, scope, exc,
        )
        return False
    except subprocess.TimeoutExpired as exc:
        _logger.warning("systemctl %s %s [%s] timed out: %s", action, name, scope, exc)
        return False

    if result.returncode != 0:
        _logger.warning(
            "systemctl %s %s [%s] exit %s: %s",
            action, name, scope, result.returncode, result.stderr.strip(),
        )
        return False
    return True
