"""Rip orchestration — wraps the `Ripper` Protocol into a manifest record.

`rip_disc` calls `ripper.rip(device, disc_dir / "audio")` and translates
the absolute `RipResult.tracks` into POSIX-relative strings under
`audio/` for storage in the manifest.
"""
from __future__ import annotations

import inspect
import re
from collections.abc import Callable
from pathlib import Path

from archivist.drivers.ripper import Ripper
from archivist.models.manifest import RipRecord

_CDDA_FLAC_RE = re.compile(r"^track(\d{2})\.cdda\.flac$")
_CANONICAL_FLAC_RE = re.compile(r"^(\d{2}) Track\.flac$")


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


def rename_tracks_to_canonical(audio_dir: Path) -> list[Path]:
    """Rename `trackNN.cdda.flac` → `NN Track.flac` in `audio_dir`.

    Returns the new paths sorted by track number. Idempotent on an
    already-canonical directory. Raises `FileExistsError` if a target
    name already exists (refuses to overwrite; source file preserved
    for operator triage).
    """
    pairs: list[tuple[int, Path, Path]] = []
    existing_canonical: dict[int, Path] = {}

    for p in audio_dir.iterdir():
        if not p.is_file():
            continue
        m_cdda = _CDDA_FLAC_RE.match(p.name)
        if m_cdda:
            n = int(m_cdda.group(1))
            pairs.append((n, p, audio_dir / f"{n:02d} Track.flac"))
            continue
        m_canon = _CANONICAL_FLAC_RE.match(p.name)
        if m_canon:
            existing_canonical[int(m_canon.group(1))] = p

    # Collision pre-check (refuse to overwrite anything).
    for n, src, dst in pairs:
        if dst.exists() and dst != src:
            raise FileExistsError(
                f"refusing to rename {src.name} → {dst.name}: target exists"
            )

    for _n, src, dst in pairs:
        src.rename(dst)

    final: dict[int, Path] = {n: dst for n, _src, dst in pairs}
    for n, p in existing_canonical.items():
        final.setdefault(n, p)
    return [final[n] for n in sorted(final)]


def _ripper_accepts_progress(ripper: Ripper) -> bool:
    """True iff `ripper.rip` accepts a `progress_callback` keyword."""
    try:
        sig = inspect.signature(ripper.rip)
    except (TypeError, ValueError):
        return False
    if "progress_callback" in sig.parameters:
        return True
    return any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
