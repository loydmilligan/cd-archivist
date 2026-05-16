"""source.json schema v1 + atomic read/write.

Per D-source-json-v1 and docs/ripper-handoff-for-claude-code.md
§source.json. Pydantic v2 with `extra="forbid"` throughout; writes
use a `.tmp` sibling + `os.replace` mirror of `models/manifest.py`'s
shape.

Coexists with the legacy `Manifest` v0.2 in `models/manifest.py`.
New folders write `source.json`; legacy `CD_NNNN/manifest.json` is
read-only via the library adapter.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

SCHEMA_VERSION: Literal[1] = 1


class _Forbid(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Ripper(_Forbid):
    name: str
    version: str
    host: str


class Disc(_Forbid):
    folder_name: str
    disc_counter: int
    inserted_at: datetime
    rip_started_at: datetime
    rip_finished_at: datetime
    ejected_at: datetime
    ready_at: datetime
    timezone: str


class Drive(_Forbid):
    device: str
    model: str | None = None
    serial: str | None = None
    read_offset: int | None = None


class Audio(_Forbid):
    format: str
    sample_rate_hz: int
    bits_per_sample: int
    channels: int
    track_count: int
    total_duration_seconds: int
    secure_rip: bool
    accuraterip_verified: bool | None = None


class Identifiers(_Forbid):
    musicbrainz_disc_id: str | None = None
    freedb_disc_id: str | None = None
    cd_toc: str | None = None
    upc: str | None = None
    isrcs: list[str] = []


class DetectedTrack(_Forbid):
    track: int
    title: str | None = None
    artist: str | None = None
    duration_seconds: int | None = None
    isrc: str | None = None
    filename: str | None = None


class DetectedMetadata(_Forbid):
    album_artist: str | None = None
    album: str | None = None
    year: int | None = None
    label: str | None = None
    catalog_number: str | None = None
    tracks: list[DetectedTrack] = []


class PhysicalDisc(_Forbid):
    photo: str | None = None
    photo_captured: bool = False
    photo_captured_at: datetime | None = None
    photo_device: str | None = None
    photo_notes: str | None = None
    label_text_guess: str | None = None
    appears_burned: bool | None = None
    handwritten: bool | None = None


class FileEntry(_Forbid):
    path: str
    kind: Literal["audio", "photo", "log"]
    size_bytes: int
    sha256: str | None = None


class Status(_Forbid):
    rip_success: bool
    photo_success: bool
    ready: bool
    warnings: list[str] = []
    errors: list[str] = []
    # Sprint-6 / Contract Changes: partial-rip preservation. Drivers'
    # impl-partial-output-preserve populates these when a rip aborts.
    partial: bool = False
    failed_tracks: list[int] = []
    # Sprint-6: the Review v1 explainer reads this when the post-rip
    # hook chose to write a structured reason. Optional + free-form.
    beets_review_reason: str | None = None


class TrackHint(_Forbid):
    """Per-track operator hint for the mix-CD-on-burned-disc case."""

    track_number: int
    artist: str | None = None
    title: str | None = None


class OperatorHints(_Forbid):
    """Sprint-6 operator-supplied identification fields (Bucket B+).

    Captured by `PATCH /api/disc/<folder>/hints`; sprint-7 wires the
    values into beets search hints. Defaults are all no-op.
    """

    various_artists: bool = False
    burned_cd: bool = False
    artist: str | None = None
    album: str | None = None
    tracks: list[TrackHint] = []


class ProvenanceEntry(_Forbid):
    """Sprint-6 / D-source-json-provenance-schema.

    One entry per rip attempt. `attempt_id` is a uuid4 hex; `tracks`
    lists the track numbers (1-indexed) the attempt produced. Optional
    timestamps stay loose so partial-rerip in either driver or service
    can populate what it has.
    """

    attempt_id: str
    tracks: list[int]
    started_at: datetime | None = None
    ended_at: datetime | None = None


class SourceJson(_Forbid):
    schema_version: Literal[1]
    ripper: Ripper
    disc: Disc
    drive: Drive
    audio: Audio
    identifiers: Identifiers
    detected_metadata: DetectedMetadata
    physical_disc: PhysicalDisc
    files: list[FileEntry]
    status: Status
    operator_hints: OperatorHints = OperatorHints()
    provenance: list[ProvenanceEntry] = []


def read_source_json(path: Path) -> SourceJson:
    """Load and validate a source.json from disk.

    Raises:
        ValueError: schema_version mismatch.
        Exception: on malformed JSON — message references the path.
    """
    try:
        raw = path.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed source.json at {path}: {exc}") from exc

    version = payload.get("schema_version") if isinstance(payload, dict) else None
    if version != SCHEMA_VERSION:
        raise ValueError(
            f"source.json schema_version mismatch: expected {SCHEMA_VERSION!r}, "
            f"got {version!r} at {path}"
        )
    return SourceJson.model_validate(payload)


def write_source_json(path: Path, payload: SourceJson) -> None:
    """Atomic write via `.tmp` sibling + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    blob = payload.model_dump_json(indent=2) + "\n"
    tmp.write_text(blob, encoding="utf-8")
    os.replace(tmp, path)
