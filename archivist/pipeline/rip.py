"""Rip orchestration — wraps the `Ripper` Protocol into a manifest record.

`rip_disc` calls `ripper.rip(device, disc_dir / "audio")` and translates
the absolute `RipResult.tracks` into POSIX-relative strings under
`audio/` for storage in the manifest.
"""
from __future__ import annotations

from pathlib import Path

from archivist.drivers.ripper import Ripper
from archivist.models.manifest import RipRecord


def rip_disc(disc_dir: Path, device: Path, *, ripper: Ripper) -> RipRecord:
    audio_dir = disc_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    result = ripper.rip(device, audio_dir)

    tracks = [Path(t).relative_to(disc_dir).as_posix() for t in result.tracks]
    return RipRecord(status=result.status, tracks=tracks, errors=list(result.errors))
