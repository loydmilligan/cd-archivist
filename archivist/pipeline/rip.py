"""Rip orchestration — wraps the `Ripper` Protocol into a manifest record.

`rip_disc` calls `ripper.rip(device, disc_dir / "audio")` and translates
the absolute `RipResult.tracks` into POSIX-relative strings under
`audio/` for storage in the manifest.
"""
from __future__ import annotations

import inspect
from collections.abc import Callable
from pathlib import Path

from archivist.drivers.ripper import Ripper
from archivist.models.manifest import RipRecord


def rip_disc(
    disc_dir: Path,
    device: Path,
    *,
    ripper: Ripper,
    progress_callback: Callable[[str], None] | None = None,
) -> RipRecord:
    """Run the rip and translate the result into a manifest RipRecord.

    `progress_callback` is forwarded to `ripper.rip` when the ripper
    accepts the kwarg (sprint-3 / impl-rip-progress: drivers' Popen
    refactor exposes per-line stderr via this callback). Ripper
    implementations without the kwarg still work — we forward
    conditionally via signature inspection.
    """
    audio_dir = disc_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    if progress_callback is not None and _ripper_accepts_progress(ripper):
        result = ripper.rip(device, audio_dir, progress_callback=progress_callback)
    else:
        result = ripper.rip(device, audio_dir)

    tracks = [Path(t).relative_to(disc_dir).as_posix() for t in result.tracks]
    return RipRecord(status=result.status, tracks=tracks, errors=list(result.errors))


def _ripper_accepts_progress(ripper: Ripper) -> bool:
    """True iff `ripper.rip` accepts a `progress_callback` keyword."""
    try:
        sig = inspect.signature(ripper.rip)
    except (TypeError, ValueError):
        return False
    if "progress_callback" in sig.parameters:
        return True
    return any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
