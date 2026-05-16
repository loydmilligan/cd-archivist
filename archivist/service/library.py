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


_COVER_NAMES = ("cover.jpg", "cover.jpeg", "cover.png", "cover.webp")


@dataclass
class DiscSummary:
    disc_id_or_folder: str
    created_at: datetime | None
    rip_success: bool
    track_count: int
    thumbnail: Path | None
    is_legacy: bool
    # Sprint-5 / D-library-cover-preference: beets-fetched cover at
    # <library_root>/<album_artist>/<album>/cover.{jpg,png,jpeg,webp}.
    # When set, the library UI prefers this over disc-photo.jpg.
    library_cover_path: Path | None = None


def _find_library_cover(
    library_root: Path | None,
    album_artist: str | None,
    album: str | None,
) -> Path | None:
    """Per D-library-cover-preference: walk
    `<library_root>/<album_artist>/<album>/cover.{jpg,jpeg,png,webp}`.

    Both `album_artist` and `album` must be populated; otherwise the
    derivation is skipped (no inventing).
    """
    if library_root is None or not album_artist or not album:
        return None
    if not library_root.is_dir():
        return None
    album_dir = library_root / album_artist / album
    if not album_dir.is_dir():
        return None
    for name in _COVER_NAMES:
        candidate = album_dir / name
        if candidate.is_file():
            return candidate
    return None


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


def read_disc_summary(
    disc_dir: Path,
    *,
    library_root: Path | None = None,
) -> DiscSummary | None:
    """Return a DiscSummary or None if the folder has neither schema.

    When `library_root` is provided AND the folder has `source.json`
    with non-null `detected_metadata.{album_artist, album}`, the
    summary's `library_cover_path` is populated if a cover image
    exists at `<library_root>/<artist>/<album>/cover.{jpg,jpeg,png,
    webp}` (D-library-cover-preference).
    """
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
        library_cover = _find_library_cover(
            library_root,
            src.detected_metadata.album_artist,
            src.detected_metadata.album,
        )
        return DiscSummary(
            disc_id_or_folder=disc_dir.name,
            created_at=src.disc.inserted_at,
            rip_success=src.status.rip_success,
            track_count=src.audio.track_count,
            thumbnail=_thumbnail_for(disc_dir, is_legacy=False),
            is_legacy=False,
            library_cover_path=library_cover,
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
        # Legacy folders NEVER resolve a library cover — their
        # manifest.json doesn't carry detected_metadata.
        return DiscSummary(
            disc_id_or_folder=disc_dir.name,
            created_at=m.created_at,
            rip_success=rip_success,
            track_count=len(m.rips[0].tracks) if m.rips else 0,
            thumbnail=_thumbnail_for(disc_dir, is_legacy=True),
            is_legacy=True,
            library_cover_path=None,
        )

    return None
