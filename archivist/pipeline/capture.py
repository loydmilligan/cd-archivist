"""Capture pipeline — LED dance + camera burst orchestration.

Implements the documented sequence from
docs/operations/cm4-setup.md §"Capture pipeline LED dance":

    led off  → settle → ambient burst (3 frames) →
    led on   → settle → lit burst (3 frames)     →
    led off (failsafe, in finally)

`camera` and `led` are injected — production wires in
`archivist.drivers.camera.capture_frame_with_recovery` (or plain
`capture_frame`) and `archivist.drivers.led.LEDPanel`. LED failures
are best-effort: a Tasmota timeout never blocks captures.
"""
from __future__ import annotations

import logging
import shutil
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from archivist.models.manifest import CaptureRecord

_CANONICAL_PHOTO_NAME = "disc-photo.jpg"
_LIT_FRAME_GLOB = "disc_front_lit_*.jpg"
_PREFERRED_LIT_FRAME = "disc_front_lit_002.jpg"

logger = logging.getLogger(__name__)

FRAMES_PER_BURST = 3
_DEFAULT_VIDEO_DEVICE = Path("/dev/video0")


class _LEDLike(Protocol):
    def power_on(self) -> bool: ...
    def power_off(self) -> bool: ...
    def status(self) -> str: ...


CameraCallable = Callable[..., "Path | None"]


def _burst(
    lighting: str,
    disc_dir: Path,
    camera: CameraCallable,
    video_device: Path,
) -> CaptureRecord:
    captures_dir = disc_dir / "captures"
    captures_dir.mkdir(parents=True, exist_ok=True)

    landed: list[str] = []
    for i in range(1, FRAMES_PER_BURST + 1):
        filename = f"disc_front_{lighting}_{i:03d}.jpg"
        out_path = captures_dir / filename
        result = camera(video_device, out_path, frames=1)
        if result is not None:
            landed.append(f"captures/{filename}")

    capture_id = f"{lighting}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    return CaptureRecord(capture_id=capture_id, lighting=lighting, image_paths=landed)


def capture_disc(
    disc_dir: Path,
    *,
    camera: CameraCallable,
    led: _LEDLike,
    settle_seconds: float = 0.5,
    video_device: Path = _DEFAULT_VIDEO_DEVICE,
) -> list[CaptureRecord]:
    records: list[CaptureRecord] = []
    try:
        # LED off → settle → ambient burst.
        if not led.power_off():
            logger.warning("LED power_off failed before ambient burst (continuing)")
        if settle_seconds > 0:
            time.sleep(settle_seconds)
        records.append(_burst("ambient", disc_dir, camera, video_device))

        # LED on → settle → lit burst.
        if not led.power_on():
            logger.warning(
                "LED power_on failed before lit burst — proceeding anyway (LED is best-effort)"
            )
        if settle_seconds > 0:
            time.sleep(settle_seconds)
        records.append(_burst("lit", disc_dir, camera, video_device))
    finally:
        # Failsafe: LED off no matter what. Never leave the panel on.
        try:
            led.power_off()
        except Exception:
            logger.exception("LED power_off in finally raised — swallowing")
    return records


def select_canonical_photo(captures_dir: Path) -> Path | None:
    """Pick the canonical disc photo per D-canonical-disc-photo.

    Prefers `disc_front_lit_002.jpg` (the middle of the 3 lit frames);
    falls back to any `disc_front_lit_*.jpg`; returns `None` if no
    lit captures exist (or the captures dir is missing).
    """
    if not captures_dir.is_dir():
        return None
    preferred = captures_dir / _PREFERRED_LIT_FRAME
    if preferred.is_file():
        return preferred
    lits = sorted(captures_dir.glob(_LIT_FRAME_GLOB))
    return lits[0] if lits else None


def copy_canonical_photo(disc_dir: Path) -> Path | None:
    """Copy the chosen lit frame to `<disc_dir>/disc-photo.jpg`.

    Per D-canonical-disc-photo. Returns the new path on success, `None`
    when no lit frame is available. Supplemental captures stay in
    `captures/` for the operator. Idempotent — re-running produces an
    identical byte-equal copy.
    """
    chosen = select_canonical_photo(disc_dir / "captures")
    if chosen is None:
        return None
    target = disc_dir / _CANONICAL_PHOTO_NAME
    shutil.copyfile(chosen, target)
    return target
