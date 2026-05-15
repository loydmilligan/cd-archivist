"""Disc folder skeleton: canonical layout + initial manifest."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from archivist.models.manifest import SCHEMA_VERSION, Manifest, write_manifest

_SUBDIRS = ("captures", "audio", "logs", "review")


def prepare_disc_folder(disc_id: str, discs_root: Path) -> Path:
    """Create ``<discs_root>/<disc_id>/`` with canonical subdirs + manifest.

    Idempotent: if ``manifest.json`` already exists in the target,
    returns the target unchanged without touching its contents.
    """
    target = discs_root / disc_id
    manifest_path = target / "manifest.json"

    if manifest_path.exists():
        return target

    target.mkdir(parents=True, exist_ok=True)
    for sub in _SUBDIRS:
        (target / sub).mkdir(parents=True, exist_ok=True)

    initial = Manifest(
        schema_version=SCHEMA_VERSION,
        disc_id=disc_id,
        media_type="audio_cd",
        created_at=datetime.now(UTC),
        status="created",
        captures=[],
        rips=[],
        pairings=[],
        metadata={},
        errors=[],
    )
    write_manifest(manifest_path, initial)
    return target
