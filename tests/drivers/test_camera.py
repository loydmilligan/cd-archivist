"""Failing tests for archivist.drivers.camera.capture_frame.

Per sprint-1 Wave 1 (test-camera). Impl lands in Wave 2 (impl-camera).

Invariant under test: capture_frame NEVER raises on subprocess failure.
Returns None on any subprocess error.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import pytest

from archivist.drivers.camera import capture_frame

DEVICE = Path("/dev/video0")


def test_success_returns_out_path(fake_subprocess, tmp_path: Path) -> None:
    """ffmpeg exits 0 → returns out_path. Argv contains ffmpeg + device + out_path."""
    fake_subprocess.set_result(returncode=0)
    out = tmp_path / "captures" / "frame.jpg"

    result = capture_frame(DEVICE, out, frames=15)

    assert result == out
    assert fake_subprocess.calls, "expected subprocess.run to be invoked"
    argv = fake_subprocess.calls[0].args
    # ffmpeg argv per docs/operations/cm4-setup.md:
    #   ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 1280x720 \
    #     -i /dev/video0 -frames:v 15 -y <out_path>
    flat = list(argv) if isinstance(argv, (list, tuple)) else [argv]
    joined = " ".join(str(x) for x in flat)
    assert "ffmpeg" in joined
    assert str(DEVICE) in joined
    assert str(out) in joined


def test_nonzero_exit_returns_none(
    fake_subprocess, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Non-zero ffmpeg exit → None, stderr surfaced in logs."""
    fake_subprocess.set_result(returncode=1, stderr="ffmpeg: Device or resource busy")
    out = tmp_path / "captures" / "frame.jpg"
    with caplog.at_level(logging.WARNING):
        result = capture_frame(DEVICE, out, frames=15)
    assert result is None
    assert any(
        "busy" in r.message.lower() or "ffmpeg" in r.message.lower()
        for r in caplog.records
    ), "expected stderr/ffmpeg to be logged"


def test_ffmpeg_missing_returns_none(
    fake_subprocess, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """FileNotFoundError (ffmpeg not installed) → None, logged, never raises."""
    fake_subprocess.set_exception(FileNotFoundError("ffmpeg"))
    out = tmp_path / "captures" / "frame.jpg"
    with caplog.at_level(logging.WARNING):
        result = capture_frame(DEVICE, out, frames=15)
    assert result is None


def test_creates_parent_dir(fake_subprocess, tmp_path: Path) -> None:
    """out_path.parent is created if missing."""
    fake_subprocess.set_result(returncode=0)
    out = tmp_path / "deep" / "nested" / "captures" / "frame.jpg"
    assert not out.parent.exists()
    capture_frame(DEVICE, out, frames=15)
    assert out.parent.exists()


def test_timeout_returns_none(fake_subprocess, tmp_path: Path) -> None:
    """subprocess.TimeoutExpired → None, never raises."""
    fake_subprocess.set_exception(subprocess.TimeoutExpired(cmd="ffmpeg", timeout=10))
    out = tmp_path / "captures" / "frame.jpg"
    result = capture_frame(DEVICE, out, frames=15)
    assert result is None
