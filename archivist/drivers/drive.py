"""CD drive state probe via Linux CDROM_DRIVE_STATUS ioctl.

Per sprint-1 task impl-drive. Maps the four documented kernel return
codes to the public state literal. The OSError path from os.open
bubbles up untouched — callers decide how to handle a missing or
permission-denied device node.
"""
from __future__ import annotations

import fcntl
import logging
import os
from pathlib import Path
from typing import Literal

_logger = logging.getLogger(__name__)

# include/uapi/linux/cdrom.h
CDROM_DRIVE_STATUS = 0x5326
CDROMEJECT = 0x5309

CDS_NO_INFO = 0
CDS_NO_DISC = 1
CDS_TRAY_OPEN = 2
CDS_DRIVE_NOT_READY = 3
CDS_DISC_OK = 4

DriveStatus = Literal["no-disc", "tray-open", "drive-not-ready", "disc-ok"]

_STATUS_MAP: dict[int, DriveStatus] = {
    CDS_NO_DISC: "no-disc",
    CDS_TRAY_OPEN: "tray-open",
    CDS_DRIVE_NOT_READY: "drive-not-ready",
    CDS_DISC_OK: "disc-ok",
}


def read_drive_status(device: Path) -> DriveStatus:
    """Return the current CDROM drive state.

    Opens the device non-blocking (so the kernel doesn't wait for media),
    issues CDROM_DRIVE_STATUS, and maps the result to one of four
    documented states. Raises OSError if the device path cannot be
    opened (missing, no permission, etc.).
    """
    fd = os.open(device, os.O_RDONLY | os.O_NONBLOCK)
    try:
        code = fcntl.ioctl(fd, CDROM_DRIVE_STATUS)
    finally:
        os.close(fd)
    try:
        return _STATUS_MAP[code]
    except KeyError as exc:
        raise ValueError(f"unexpected CDROM_DRIVE_STATUS code: {code}") from exc


def eject(device: Path) -> bool:
    """Eject the disc tray. Returns True on success, False on OSError.

    Never raises. The common failure is `OSError: drive busy` while a
    rip is in flight; callers retry after the rip releases the device.
    """
    try:
        fd = os.open(device, os.O_RDONLY | os.O_NONBLOCK)
    except OSError as exc:
        _logger.warning("eject %s failed (open): %s", device, exc)
        return False
    try:
        fcntl.ioctl(fd, CDROMEJECT)
    except OSError as exc:
        _logger.warning("eject %s failed: %s", device, exc)
        return False
    finally:
        os.close(fd)
    return True
