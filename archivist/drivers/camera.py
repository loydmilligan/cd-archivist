"""Single-frame webcam capture via ffmpeg v4l2.

Per sprint-1 task impl-camera. The documented invariant is that
`capture_frame` never raises on subprocess failure — it logs and returns
`None`. USB unbind/rebind recovery is sprint-2 scope.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

_logger = logging.getLogger(__name__)
_TIMEOUT_SECONDS = 30.0


def capture_frame(
    device: Path,
    out_path: Path,
    *,
    frames: int = 15,
) -> Path | None:
    """Capture `frames` frames from `device` via ffmpeg, keeping the last.

    Returns `out_path` on success, `None` on any subprocess failure
    (non-zero exit, ffmpeg missing, timeout). Creates `out_path.parent`
    if missing.
    """
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
        result = subprocess.run(argv, capture_output=True, text=True, timeout=_TIMEOUT_SECONDS)
    except FileNotFoundError as exc:
        _logger.warning("ffmpeg not found: %s", exc)
        return None
    except subprocess.TimeoutExpired as exc:
        _logger.warning("ffmpeg timed out after %ss: %s", _TIMEOUT_SECONDS, exc)
        return None

    if result.returncode != 0:
        _logger.warning("ffmpeg exit %s: %s", result.returncode, result.stderr.strip())
        return None
    return out_path
