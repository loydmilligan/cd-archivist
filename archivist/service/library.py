"""Unified disc-folder reader for the library UI.

Per D-library-legacy-adapter. Handles both:
  - legacy `CD_NNNN/manifest.json` (Manifest v0.2)
  - new   `YYYY-MM-DD_HHMM_disc-NNNNNN/source.json` (SourceJson v1)

Returns a small `DiscSummary` dataclass with the fields the UI needs.
When both files exist, prefers `source.json` and logs once.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from archivist.models.manifest import read_manifest
from archivist.models.source import read_source_json

logger = logging.getLogger(__name__)


@dataclass
class DiscSummary:
    disc_id_or_folder: str
    created_at: datetime | None
    rip_success: bool
    track_count: int
    thumbnail: Path | None
    is_legacy: bool


def _thumbnail_for(disc_dir: Path, *, is_legacy: bool) -> Path | None:
    """Best-effort thumbnail pick for the library card.

    New-shape folders: prefer `disc-photo.jpg` at the disc root.
    Legacy folders: first lit capture, else any capture.
    """
    if not is_legacy:
        canon = disc_dir / "disc-photo.jpg"
        if canon.is_file():
            return canon
    captures = disc_dir / "captures"
    if captures.is_dir():
        lit = sorted(captures.glob("disc_front_lit_*.jpg"))
        if lit:
            return lit[0]
        any_jpg = sorted(captures.glob("*.jpg"))
        if any_jpg:
            return any_jpg[0]
    return None


def read_disc_summary(disc_dir: Path) -> DiscSummary | None:
    """Return a DiscSummary or None if the folder has neither schema."""
    manifest_path = disc_dir / "manifest.json"
    source_path = disc_dir / "source.json"

    has_manifest = manifest_path.is_file()
    has_source = source_path.is_file()

    if has_source and has_manifest:
        logger.info(
            "%s has BOTH manifest.json and source.json; preferring source.json",
            disc_dir.name,
        )

    if has_source:
        try:
            src = read_source_json(source_path)
        except (ValueError, OSError):
            logger.exception("failed to read source.json at %s", source_path)
            return None
        return DiscSummary(
            disc_id_or_folder=disc_dir.name,
            created_at=src.disc.inserted_at,
            rip_success=src.status.rip_success,
            track_count=src.audio.track_count,
            thumbnail=_thumbnail_for(disc_dir, is_legacy=False),
            is_legacy=False,
        )

    if has_manifest:
        try:
            m = read_manifest(manifest_path)
        except (ValueError, OSError):
            logger.exception("failed to read manifest.json at %s", manifest_path)
            return None
        rip_success = (
            m.status == "ripped"
            and bool(m.rips)
            and m.rips[0].status == "success"
        )
        return DiscSummary(
            disc_id_or_folder=disc_dir.name,
            created_at=m.created_at,
            rip_success=rip_success,
            track_count=len(m.rips[0].tracks) if m.rips else 0,
            thumbnail=_thumbnail_for(disc_dir, is_legacy=True),
            is_legacy=True,
        )

    return None
