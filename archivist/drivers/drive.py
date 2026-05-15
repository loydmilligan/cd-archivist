"""CD drive state probe + tray eject.

`read_drive_status` (sprint-1 impl-drive, sprint-3 impl-drive-missing)
issues the Linux `CDROM_DRIVE_STATUS` ioctl and maps the kernel return
codes to a public state literal.

`eject` (sprint-1 impl-eject, sprint-4 impl-eject-reliability) shells
out to the `eject` binary. Sprint-1's ioctl-based impl
(`fcntl.ioctl(fd, CDROMEJECT)` / 0x5309) reported success on the
dogfood USB drive but the tray never physically opened — a drive-
firmware quirk where `CDROMEJECT` is silently ignored
(real-rig finding from CD_0018 smoke, 2026-05-15, per `D-eject-via-
shell`). The shell `eject` binary uses ATAPI `START STOP UNIT` with
LoEj+Start, which the same drive honors, and handles fallback paths
(LOAD/UNLOAD, etc.) we'd otherwise have to reimplement. The function
signature is unchanged so neither the state machine nor existing
tests need to know about the impl swap. The `eject` binary is part
of Debian's default install set, including the CM4.
"""
from __future__ import annotations

import fcntl
import logging
import os
import subprocess
from pathlib import Path
from typing import Literal

_logger = logging.getLogger(__name__)
_EJECT_TIMEOUT_SECONDS = 10.0

# include/uapi/linux/cdrom.h
CDROM_DRIVE_STATUS = 0x5326

CDS_NO_INFO = 0
CDS_NO_DISC = 1
CDS_TRAY_OPEN = 2
CDS_DRIVE_NOT_READY = 3
CDS_DISC_OK = 4

DriveStatus = Literal["no-disc", "tray-open", "drive-not-ready", "disc-ok", "device-missing"]

_STATUS_MAP: dict[int, DriveStatus] = {
    CDS_NO_DISC: "no-disc",
    CDS_TRAY_OPEN: "tray-open",
    CDS_DRIVE_NOT_READY: "drive-not-ready",
    CDS_DISC_OK: "disc-ok",
}


def read_drive_status(device: Path) -> DriveStatus:
    """Return the current CDROM drive state.

    Opens the device non-blocking (so the kernel doesn't wait for media),
    issues CDROM_DRIVE_STATUS, and maps the result to one of five
    documented states.

    Returns `"device-missing"` when the device node does not exist
    (FileNotFoundError on os.open) — this is the transient
    USB-disconnect / drive-not-yet-enumerated case that the state-
    machine loop treats as IDLE-with-rate-limited-warning rather than
    a hard error. Other OSErrors (PermissionError, EIO, …) still raise
    — those are real failures the loop should see.
    """
    try:
        fd = os.open(device, os.O_RDONLY | os.O_NONBLOCK)
    except FileNotFoundError:
        return "device-missing"
    try:
        code = fcntl.ioctl(fd, CDROM_DRIVE_STATUS)
    finally:
        os.close(fd)
    try:
        return _STATUS_MAP[code]
    except KeyError as exc:
        raise ValueError(f"unexpected CDROM_DRIVE_STATUS code: {code}") from exc


def eject(device: Path) -> bool:
    """Eject the disc tray via the shell `eject` binary.

    Returns `True` on `eject(1)` returncode 0, `False` on any failure
    (non-zero returncode, `FileNotFoundError`, `subprocess.Timeout
    Expired`, or any other exception the runtime might surface).
    Never raises — the state machine relies on this invariant.

    See module docstring for the rationale on shell-out vs. the
    sprint-1 `CDROMEJECT` ioctl.
    """
    argv = ["eject", str(device)]
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=_EJECT_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        _logger.warning("eject %s failed: `eject` binary missing on PATH: %s", device, exc)
        return False
    except subprocess.TimeoutExpired as exc:
        _logger.warning(
            "eject %s timed out after %ss: %s", device, _EJECT_TIMEOUT_SECONDS, exc,
        )
        return False
    except Exception as exc:  # noqa: BLE001 — never-raises invariant
        _logger.warning("eject %s failed (unexpected): %s", device, exc)
        return False

    if result.returncode != 0:
        _logger.warning(
            "eject %s exit %s: %s",
            device, result.returncode, (result.stderr or "").strip(),
        )
        return False
    return True
