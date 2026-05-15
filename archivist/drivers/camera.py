"""Single-frame webcam capture via ffmpeg v4l2, with optional USB-rebind recovery.

`capture_frame` is the leaf operation (sprint-1 impl-camera). The
documented invariant is that it never raises on subprocess failure —
it logs and returns `None`.

`capture_frame_with_recovery` (sprint-2 impl-camera-recovery) wraps
`capture_frame` with a one-shot recovery for the `VIDIOC_STREAMON`
failure mode that the documented Microdia rig exhibits after long
idle. Recovery resolves the USB bus path via an injected
`discover_usb_path` callable (production wires in
`archivist.drivers.usb_discovery.discover_camera_usb_path` per
D-camera-autodiscover), then performs an `unbind` / `bind` cycle
against `/sys/bus/usb/drivers/usb/` and retries.

NOPASSWD sudo against `tee /sys/bus/usb/drivers/usb/{unbind,bind}` is
required on the CM4 — see `docs/operations/cm4-setup.md` §"NOPASSWD
sudo fragment".
"""
from __future__ import annotations

import logging
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

_logger = logging.getLogger(__name__)
_TIMEOUT_SECONDS = 30.0
_REBIND_SETTLE_SECONDS = 2.0
_STREAMON_MARKER = "VIDIOC_STREAMON"


def capture_frame(
    device: Path,
    out_path: Path,
    *,
    frames: int = 15,
) -> Path | None:
    """Capture `frames` frames from `device` via ffmpeg, keeping the last.

    Returns `out_path` on success, `None` on any subprocess failure.
    """
    result, _ = _run_ffmpeg(device, out_path, frames)
    return result


def capture_frame_with_recovery(
    device: Path,
    out_path: Path,
    *,
    frames: int = 15,
    discover_usb_path: Callable[[], str | None] | None = None,
    retries: int = 1,
) -> Path | None:
    """Capture with one-shot recovery for VIDIOC_STREAMON failures.

    On the first ffmpeg failure whose stderr contains "VIDIOC_STREAMON",
    if `retries > 0` and `discover_usb_path()` returns a non-`None` path,
    issues a USB unbind/bind cycle against that path, sleeps to let the
    device re-enumerate, and retries `capture_frame` once. All other
    failure modes return `None` immediately. Never raises.
    """
    result, stderr = _run_ffmpeg(device, out_path, frames)
    if result is not None:
        return result

    if retries <= 0 or _STREAMON_MARKER not in stderr:
        return None

    if discover_usb_path is None:
        _logger.warning("camera recovery: no discover_usb_path callable wired")
        return None

    usb_path = discover_usb_path()
    if not usb_path:
        _logger.warning("camera recovery: discover_usb_path returned None, skipping rebind")
        return None

    if not _rebind_usb(usb_path):
        return None

    time.sleep(_REBIND_SETTLE_SECONDS)
    result, _ = _run_ffmpeg(device, out_path, frames)
    return result


def _run_ffmpeg(
    device: Path,
    out_path: Path,
    frames: int,
) -> tuple[Path | None, str]:
    """Single ffmpeg invocation. Returns (out_path or None, stderr)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    argv = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-f", "v4l2",
        "-video_size", "1280x720",
        "-i", str(device),
        "-frames:v", str(frames),
        "-y", str(out_path),
    ]
    try:
        result = subprocess.run(
            argv, capture_output=True, text=True, timeout=_TIMEOUT_SECONDS
        )
    except FileNotFoundError as exc:
        _logger.warning("ffmpeg not found: %s", exc)
        return None, str(exc)
    except subprocess.TimeoutExpired as exc:
        _logger.warning("ffmpeg timed out after %ss: %s", _TIMEOUT_SECONDS, exc)
        return None, str(exc)

    stderr = result.stderr or ""
    if result.returncode != 0:
        _logger.warning("ffmpeg exit %s: %s", result.returncode, stderr.strip())
        return None, stderr
    return out_path, stderr


def _rebind_usb(usb_path: str) -> bool:
    """Write `usb_path` to /sys/bus/usb/drivers/usb/{unbind,bind} via sudo.

    Uses `sh -c` so the USB path appears in argv (lets tests assert the
    discovered path made it through) and so a single sudo can perform the
    redirect into the sysfs file. NOPASSWD sudo required for tee.
    """
    for action in ("unbind", "bind"):
        argv = [
            "sudo", "sh", "-c",
            f"echo {usb_path} | sudo tee /sys/bus/usb/drivers/usb/{action} > /dev/null",
        ]
        try:
            result = subprocess.run(
                argv, capture_output=True, text=True, timeout=_TIMEOUT_SECONDS
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            _logger.warning("USB %s of %s failed: %s", action, usb_path, exc)
            return False
        if result.returncode != 0:
            _logger.warning(
                "USB %s of %s exit %s: %s",
                action, usb_path, result.returncode, (result.stderr or "").strip(),
            )
            return False
    return True
