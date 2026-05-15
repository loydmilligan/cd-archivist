"""Failing tests for archivist.drivers.camera.capture_frame_with_recovery.

Per sprint-2 Wave 1 (test-camera-recovery). Impl lands in Wave 2
(impl-camera-recovery).

Invariants under test:
- Never raises.
- Recovery is triggered ONLY by VIDIOC_STREAMON-shaped failures.
- Recovery fires at most once (retries=1).
- Recovery is a no-op when the injected discover_usb_path() yields None.
- Production wires `discover_usb_path = discover_camera_usb_path` from
  impl-usb-discovery (per D-camera-autodiscover).
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import pytest

DEVICE = Path("/dev/video0")
USB_PATH = "1-1.2.2"
STREAMON_ERR = (
    "[video4linux2,v4l2 @ 0xdead] ioctl(VIDIOC_STREAMON): Input/output error"
)


def _capture_with_recovery():
    """Lazy import of the not-yet-implemented capture_frame_with_recovery."""
    from archivist.drivers.camera import capture_frame_with_recovery  # noqa: PLC0415

    return capture_frame_with_recovery


@pytest.fixture
def patched_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Capture time.sleep calls so tests don't actually block."""
    import archivist.drivers.camera as cam_mod  # noqa: PLC0415

    sleeps: list[float] = []
    monkeypatch.setattr(cam_mod.time, "sleep", lambda s: sleeps.append(s))
    return sleeps


def test_first_attempt_success_no_recovery(
    fake_subprocess, patched_sleep: list[float], tmp_path: Path
) -> None:
    """Happy path: ffmpeg succeeds on attempt 1 — no discovery, no sleep, no recovery."""
    fake_subprocess.set_result(returncode=0)
    out = tmp_path / "captures" / "frame.jpg"

    discover_calls: list[bool] = []

    def discover() -> str | None:
        discover_calls.append(True)
        return USB_PATH

    result = _capture_with_recovery()(
        DEVICE, out, frames=15, discover_usb_path=discover, retries=1
    )

    assert result == out
    assert discover_calls == [], "discovery must not be called on first-attempt success"
    assert patched_sleep == [], "no recovery sleep on success"
    # Exactly one ffmpeg call.
    ffmpeg_calls = [c for c in fake_subprocess.calls if _has(c, "ffmpeg")]
    assert len(ffmpeg_calls) == 1


def test_streamon_failure_then_recovery_then_success(
    fake_subprocess, patched_sleep: list[float], tmp_path: Path
) -> None:
    """STREAMON err → discover → unbind → bind → retry succeeds."""
    from tests.conftest import FakeCompletedProcess  # noqa: PLC0415

    out = tmp_path / "captures" / "frame.jpg"
    fake_subprocess.queue(FakeCompletedProcess([], returncode=1, stderr=STREAMON_ERR))
    fake_subprocess.queue(FakeCompletedProcess([], returncode=0))  # unbind
    fake_subprocess.queue(FakeCompletedProcess([], returncode=0))  # bind
    fake_subprocess.queue(FakeCompletedProcess([], returncode=0))  # ffmpeg retry

    discover_calls: list[bool] = []

    def discover() -> str | None:
        discover_calls.append(True)
        return USB_PATH

    result = _capture_with_recovery()(
        DEVICE, out, frames=15, discover_usb_path=discover, retries=1
    )

    assert result == out
    assert discover_calls == [True], "discovery should be called exactly once"
    assert patched_sleep, "expected a settle sleep after unbind/bind"

    # Recovery commands fire with the discovered USB path.
    unbind_calls = [c for c in fake_subprocess.calls if _has(c, "unbind")]
    bind_calls = [
        c for c in fake_subprocess.calls
        if _has(c, "/bind") or (_has(c, "bind") and not _has(c, "unbind"))
    ]
    assert unbind_calls, "expected an unbind write"
    assert bind_calls, "expected a bind write"
    # The discovered bus path appears somewhere in the recovery argv stream.
    flat = " ".join(_joined(c) for c in fake_subprocess.calls)
    assert USB_PATH in flat


def test_non_streamon_failure_no_recovery(
    fake_subprocess, patched_sleep: list[float], tmp_path: Path
) -> None:
    """Non-STREAMON ffmpeg failure (e.g. device busy) → no recovery, returns None."""
    fake_subprocess.set_result(returncode=1, stderr="Device or resource busy")
    out = tmp_path / "captures" / "frame.jpg"

    discover_calls: list[bool] = []

    def discover() -> str | None:
        discover_calls.append(True)
        return USB_PATH

    result = _capture_with_recovery()(
        DEVICE, out, frames=15, discover_usb_path=discover, retries=1
    )

    assert result is None
    assert discover_calls == [], "discovery must not fire for non-STREAMON failures"
    assert patched_sleep == []
    # No unbind/bind commands should appear.
    assert not any(_has(c, "unbind") for c in fake_subprocess.calls)


def test_recovery_attempted_once_then_gives_up(
    fake_subprocess, patched_sleep: list[float], tmp_path: Path
) -> None:
    """Both attempts STREAMON-fail → recovery fires once, then None."""
    from tests.conftest import FakeCompletedProcess  # noqa: PLC0415

    out = tmp_path / "captures" / "frame.jpg"
    fake_subprocess.queue(FakeCompletedProcess([], returncode=1, stderr=STREAMON_ERR))
    fake_subprocess.queue(FakeCompletedProcess([], returncode=0))  # unbind
    fake_subprocess.queue(FakeCompletedProcess([], returncode=0))  # bind
    fake_subprocess.queue(FakeCompletedProcess([], returncode=1, stderr=STREAMON_ERR))

    def discover() -> str | None:
        return USB_PATH

    result = _capture_with_recovery()(
        DEVICE, out, frames=15, discover_usb_path=discover, retries=1
    )

    assert result is None
    # Exactly one recovery cycle: one unbind and one bind, total.
    unbind_calls = [c for c in fake_subprocess.calls if _has(c, "unbind")]
    assert len(unbind_calls) == 1
    # Two ffmpeg attempts only.
    ffmpeg_calls = [c for c in fake_subprocess.calls if _has(c, "ffmpeg")]
    assert len(ffmpeg_calls) == 2


def test_streamon_but_discovery_returns_none(
    fake_subprocess,
    patched_sleep: list[float],
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """STREAMON err + no USB path discovered → no rebind, returns None, warning logged."""
    fake_subprocess.set_result(returncode=1, stderr=STREAMON_ERR)
    out = tmp_path / "captures" / "frame.jpg"

    def discover() -> str | None:
        return None

    with caplog.at_level(logging.WARNING):
        result = _capture_with_recovery()(
            DEVICE, out, frames=15, discover_usb_path=discover, retries=1
        )

    assert result is None
    # No subprocess.run calls for unbind/bind paths.
    assert not any(_has(c, "unbind") for c in fake_subprocess.calls)
    assert not any(_has(c, "/sys/bus/usb") for c in fake_subprocess.calls)
    assert any(
        "discover" in r.message.lower() or "usb" in r.message.lower()
        for r in caplog.records
    )


# ---------------------- helpers --------------------------------------

def _joined(call) -> str:
    args = call.args
    flat = list(args) if isinstance(args, (list, tuple)) else [args]
    return " ".join(str(x) for x in flat)


def _has(call, needle: str) -> bool:
    return needle in _joined(call)


# Touch `subprocess` so a stale import lint warning doesn't bite when impl is empty.
_ = subprocess
