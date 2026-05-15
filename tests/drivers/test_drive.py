"""Failing tests for archivist.drivers.drive.read_drive_status.

Per sprint-1 Wave 1 (test-drive-status). Impl lands in Wave 2 (impl-drive).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from archivist.drivers.drive import eject, read_drive_status

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


def test_missing_device_returns_device_missing(tmp_path: Path) -> None:
    """Missing device node → "device-missing" (sprint-3 contract change).

    Sprint-1 originally bubbled the FileNotFoundError; sprint-3's
    impl-drive-missing reclassifies it as a transient state the loop
    handles via rate-limited logging. Other OSErrors (PermissionError,
    EIO, …) still bubble — covered by test_permission_error_still_raises
    below.
    """
    missing = tmp_path / "does-not-exist"
    assert read_drive_status(missing) == "device-missing"


# -------------------- eject() — shell-out (sprint-4, D-eject-via-shell) ----

# The sprint-2 ioctl-based eject contract is retired here. Real-rig
# finding from 2026-05-15 CD_0018 smoke: the CM4's USB CD drive accepts
# CDROMEJECT (fcntl.ioctl(fd, 0x5309)) and returns success, but the tray
# never physically opens. The shell `eject` binary uses ATAPI
# START STOP UNIT with LoEj+Start bits, which the same drive honors.
# The Python signature is unchanged: eject(device: Path) -> bool.

DEVICE = Path("/dev/sr0")


def test_eject_shell_success_returns_true(fake_subprocess) -> None:
    """eject binary exits 0 → returns True; argv is ["eject", <device>]."""
    fake_subprocess.set_result(returncode=0)
    assert eject(DEVICE) is True
    argv = fake_subprocess.calls[0].args
    flat = list(argv) if isinstance(argv, (list, tuple)) else [argv]
    assert [str(x) for x in flat] == ["eject", str(DEVICE)]


def test_eject_shell_nonzero_returns_false_and_logs(
    fake_subprocess, caplog: pytest.LogCaptureFixture
) -> None:
    """Non-zero returncode → False; stderr surfaced in logs."""
    import logging as _logging

    fake_subprocess.set_result(returncode=1, stderr="eject: unable to open /dev/sr0")
    with caplog.at_level(_logging.WARNING):
        assert eject(DEVICE) is False
    messages = " ".join(r.message for r in caplog.records)
    assert "unable to open" in messages or "eject" in messages.lower()


def test_eject_shell_filenotfound_returns_false(
    fake_subprocess, caplog: pytest.LogCaptureFixture
) -> None:
    """`eject` binary missing on PATH → False, clear log message."""
    import logging as _logging

    fake_subprocess.set_exception(FileNotFoundError("eject"))
    with caplog.at_level(_logging.WARNING):
        assert eject(DEVICE) is False
    assert any("eject" in r.message.lower() for r in caplog.records), (
        f"expected log to name the missing binary; got "
        f"{[r.message for r in caplog.records]!r}"
    )


def test_eject_shell_timeout_returns_false(
    fake_subprocess, caplog: pytest.LogCaptureFixture
) -> None:
    """subprocess.TimeoutExpired → False, logged, never raises."""
    import logging as _logging
    import subprocess as _subprocess

    fake_subprocess.set_exception(
        _subprocess.TimeoutExpired(cmd="eject", timeout=10)
    )
    with caplog.at_level(_logging.WARNING):
        assert eject(DEVICE) is False
    assert any("timeout" in r.message.lower() or "timed out" in r.message.lower()
               for r in caplog.records)


def test_eject_never_raises_on_exotic_errors(fake_subprocess) -> None:
    """Documented invariant: no input/subprocess outcome causes a raise."""
    # PermissionError, BrokenPipeError, OSError — anything the runtime
    # might surface. The state machine depends on never-raises.
    for exc in (PermissionError("denied"), BrokenPipeError(), OSError(28, "ENOSPC")):
        fake_subprocess.set_exception(exc)
        assert eject(DEVICE) is False


# ---------------- "device-missing" literal (sprint-3) ----------------

def test_device_missing_returns_literal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """FileNotFoundError on os.open → 'device-missing' (no exception bubble)."""
    import archivist.drivers.drive as drive_mod

    def fake_open(*_a: object, **_k: object) -> int:
        raise FileNotFoundError("/dev/sr0")

    monkeypatch.setattr(drive_mod.os, "open", fake_open)
    assert read_drive_status(tmp_path / "ignored") == "device-missing"


def test_permission_error_still_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """PermissionError is not transient — it must still bubble."""
    import archivist.drivers.drive as drive_mod

    def fake_open(*_a: object, **_k: object) -> int:
        raise PermissionError("/dev/sr0")

    monkeypatch.setattr(drive_mod.os, "open", fake_open)
    with pytest.raises(PermissionError):
        read_drive_status(tmp_path / "ignored")
