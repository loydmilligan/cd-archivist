"""Failing tests for archivist.drivers.drive.read_drive_status.

Per sprint-1 Wave 1 (test-drive-status). Impl lands in Wave 2 (impl-drive).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from archivist.drivers.drive import read_drive_status

# Linux CDROM eject ioctl.
CDROMEJECT = 0x5309


def _eject():
    """Lazy import of archivist.drivers.drive.eject.

    Kept lazy so this test module still collects (and the existing 5
    read_drive_status tests still run) before `eject` lands in Wave 2.
    """
    from archivist.drivers.drive import eject  # noqa: PLC0415

    return eject

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


# -------------------------- eject() ---------------------------------

def test_eject_issues_cdromeject(
    monkeypatch: pytest.MonkeyPatch, fake_device: Path
) -> None:
    """eject() must issue the CDROMEJECT ioctl (0x5309)."""
    calls = _patch_ioctl(monkeypatch, 0)  # ioctl returns 0 on success
    assert _eject()(fake_device) is True
    assert calls, "expected fcntl.ioctl to be invoked"
    _, request, _ = calls[0]
    assert request == CDROMEJECT


def test_eject_returns_false_on_oserror(
    monkeypatch: pytest.MonkeyPatch,
    fake_device: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """eject() returns False when the drive is busy / ioctl raises OSError."""
    import logging as _logging

    import archivist.drivers.drive as drive_mod

    def boom(*_a: object, **_k: object) -> int:
        raise OSError("drive busy")

    monkeypatch.setattr(drive_mod.fcntl, "ioctl", boom)
    with caplog.at_level(_logging.WARNING):
        assert _eject()(fake_device) is False
    assert any("eject" in r.message.lower() for r in caplog.records)


def test_eject_opens_device_nonblocking(
    monkeypatch: pytest.MonkeyPatch, fake_device: Path
) -> None:
    """eject() must os.open with O_RDONLY|O_NONBLOCK, matching read_drive_status."""
    import os as _os

    import archivist.drivers.drive as drive_mod

    captured: dict[str, int] = {}
    real_open = _os.open

    def spy_open(path: object, flags: int, *args: int) -> int:
        captured["flags"] = flags
        return real_open(path, flags, *args)

    monkeypatch.setattr(drive_mod.os, "open", spy_open)
    monkeypatch.setattr(drive_mod.fcntl, "ioctl", lambda *a, **k: 0)
    _eject()(fake_device)
    assert captured["flags"] & _os.O_NONBLOCK
    assert captured["flags"] & _os.O_RDONLY == _os.O_RDONLY


def test_eject_returns_true_on_zero_ioctl(
    monkeypatch: pytest.MonkeyPatch, fake_device: Path
) -> None:
    """ioctl returning 0 → eject returns True."""
    _patch_ioctl(monkeypatch, 0)
    assert _eject()(fake_device) is True
