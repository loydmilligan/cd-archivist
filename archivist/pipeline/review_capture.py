"""Operator review-recapture — single-shot off→on→off pair into review/.

Distinct from `archivist.pipeline.capture.capture_disc` (the multi-frame
auto pipeline run at EJECT time). This helper is the manual-trigger
counterpart: one ambient still, one lit still, both into
`CD_NNNN/review/` with a shared ISO timestamp so they sort as a pair.

Per D-review-recapture-mvp (sprint-3): no manifest write — the library
detail page surfaces review/ files from a directory listing. Sprint-4
promotes review/ files into the manifest when album-art lands.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)

_DEFAULT_VIDEO_DEVICE = Path("/dev/video0")


class _LEDLike(Protocol):
    def power_on(self) -> bool: ...
    def power_off(self) -> bool: ...


CameraCallable = Callable[..., "Path | None"]


@dataclass
class ReviewRecaptureResult:
    ambient: str  # "review/review_ambient_<ts>.jpg"
    lit: str      # "review/review_lit_<ts>.jpg"
    errors: list[str] = field(default_factory=list)


def _filesystem_safe_iso_ts() -> str:
    # ":" is unsafe on FAT/SMB; replace once at the source.
    return datetime.now(UTC).isoformat(timespec="seconds").replace(":", "-")


def _try_led(op_name: str, fn: Callable[[], bool], errors: list[str]) -> None:
    try:
        fn()
    except Exception as exc:  # never-raises invariant
        msg = f"led {op_name} failed: {exc}"
        logger.warning(msg)
        errors.append(msg)


def recapture_review(
    disc_dir: Path,
    *,
    camera: CameraCallable,
    led: _LEDLike,
    video_device: Path = _DEFAULT_VIDEO_DEVICE,
) -> ReviewRecaptureResult:
    review_dir = disc_dir / "review"
    review_dir.mkdir(parents=True, exist_ok=True)

    ts = _filesystem_safe_iso_ts()
    ambient_name = f"review_ambient_{ts}.jpg"
    lit_name = f"review_lit_{ts}.jpg"
    errors: list[str] = []

    try:
        _try_led("power_off", led.power_off, errors)
        camera(video_device, review_dir / ambient_name, frames=15)
        _try_led("power_on", led.power_on, errors)
        camera(video_device, review_dir / lit_name, frames=15)
    finally:
        _try_led("power_off", led.power_off, errors)

    return ReviewRecaptureResult(
        ambient=f"review/{ambient_name}",
        lit=f"review/{lit_name}",
        errors=errors,
    )
