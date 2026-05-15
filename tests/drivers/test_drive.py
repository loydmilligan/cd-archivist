"""Failing tests for archivist.drivers.drive.read_drive_status.

Per sprint-1 Wave 1 (test-drive-status). Impl lands in Wave 2 (impl-drive).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from archivist.drivers.drive import read_drive_status

# Linux CDROM ioctl return codes (include/uapi/linux/cdrom.h).
CDS_NO_INFO = 0
CDS_NO_DISC = 1
CDS_TRAY_OPEN = 2
CDS_DRIVE_NOT_READY = 3
CDS_DISC_OK = 4


@pytest.fixture
def fake_device(tmp_path: Path) -> Path:
    """A real file we can os.open() — stands in for /dev/sr0."""
    p = tmp_path / "sr0"
    p.write_bytes(b"")
    return p


def _patch_ioctl(monkeypatch: pytest.MonkeyPatch, return_value: int) -> list[tuple]:
    """Replace fcntl.ioctl in the drive module; record calls."""
    import archivist.drivers.drive as drive_mod

    calls: list[tuple] = []

    def fake_ioctl(fd: int, request: int, arg: int = 0) -> int:
        calls.append((fd, request, arg))
        return return_value

    monkeypatch.setattr(drive_mod.fcntl, "ioctl", fake_ioctl)
    return calls


def test_no_disc(monkeypatch: pytest.MonkeyPatch, fake_device: Path) -> None:
    _patch_ioctl(monkeypatch, CDS_NO_DISC)
    assert read_drive_status(fake_device) == "no-disc"


def test_tray_open(monkeypatch: pytest.MonkeyPatch, fake_device: Path) -> None:
    _patch_ioctl(monkeypatch, CDS_TRAY_OPEN)
    assert read_drive_status(fake_device) == "tray-open"


def test_drive_not_ready(monkeypatch: pytest.MonkeyPatch, fake_device: Path) -> None:
    _patch_ioctl(monkeypatch, CDS_DRIVE_NOT_READY)
    assert read_drive_status(fake_device) == "drive-not-ready"


def test_disc_ok(monkeypatch: pytest.MonkeyPatch, fake_device: Path) -> None:
    _patch_ioctl(monkeypatch, CDS_DISC_OK)
    assert read_drive_status(fake_device) == "disc-ok"


def test_missing_device_raises(tmp_path: Path) -> None:
    """OSError from os.open() must bubble up — no swallowing."""
    missing = tmp_path / "does-not-exist"
    with pytest.raises(OSError):
        read_drive_status(missing)
