"""Assemble a populated `SourceJson` from per-cycle state.

The state machine calls `build_source_json(disc_dir, *, ...)` after a
cycle completes (or fails). The builder:

  - walks `disc_dir` to populate `files[]` (FLACs + photo + rip.log)
    with size_bytes; sha256 stays None this sprint (stretch).
  - derives `status.rip_success` / `status.photo_success` /
    `status.ready` from the rip_record + capture_result.
  - per D-source-json-v1: detected_metadata fields stay all-null
    (no inventing — sprint-5 brings OCR/MB-disc-id).
  - per D-source-json-v1: physical_disc.{label_text_guess,
    appears_burned, handwritten} stay null in sprint-4.

The builder is a pure function — no I/O beyond stat() walks over
the existing disc folder. Atomic write happens elsewhere (the
state machine calls `write_source_json` after `build_source_json`).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from archivist.models.source import (
    Audio,
    DetectedMetadata,
    Disc,
    Drive,
    FileEntry,
    Identifiers,
    PhysicalDisc,
    Ripper,
    SourceJson,
    Status,
)

# cdparanoia CDDA assumptions — held constant in sprint-4.
_CDDA_SAMPLE_RATE_HZ = 44100
_CDDA_BITS_PER_SAMPLE = 16
_CDDA_CHANNELS = 2
# Audio CD spec: each sector is 1/75 s of 16-bit-stereo @ 44.1 kHz.
# duration_seconds ≈ flac_size / (sample_rate * bytes_per_sample * channels).
# We use the FLAC file size as a coarse proxy; sprint-5 may parse via mutagen.
_BYTES_PER_SECOND = _CDDA_SAMPLE_RATE_HZ * (_CDDA_BITS_PER_SAMPLE // 8) * _CDDA_CHANNELS


def _files_in(disc_dir: Path) -> list[FileEntry]:
    entries: list[FileEntry] = []
    for p in sorted(disc_dir.iterdir()):
        if not p.is_file():
            continue
        name = p.name
        if name.endswith(".flac"):
            kind = "audio"
        elif name == "disc-photo.jpg":
            kind = "photo"
        elif name == "rip.log":
            kind = "log"
        else:
            # Skip everything else — markers (READY/FAILED), source.json itself,
            # cue sheets, .tmp leftovers, etc. The handoff contract names the
            # three file kinds explicitly.
            continue
        entries.append(FileEntry(
            path=name,
            kind=kind,  # type: ignore[arg-type]
            size_bytes=p.stat().st_size,
            sha256=None,
        ))
    return entries


def _audio_summary(disc_dir: Path) -> Audio:
    flacs = sorted(p for p in disc_dir.glob("*.flac") if p.is_file())
    total_bytes = sum(p.stat().st_size for p in flacs)
    return Audio(
        format="flac",
        sample_rate_hz=_CDDA_SAMPLE_RATE_HZ,
        bits_per_sample=_CDDA_BITS_PER_SAMPLE,
        channels=_CDDA_CHANNELS,
        track_count=len(flacs),
        total_duration_seconds=max(0, total_bytes // _BYTES_PER_SECOND),
        secure_rip=True,  # cdparanoia secure mode is sprint-2's default
        accuraterip_verified=None,  # stretch
    )


def build_source_json(
    disc_dir: Path,
    *,
    ripper_name: str,
    ripper_version: str,
    hostname: str,
    drive_info: Any,
    rip_record: Any,
    capture_result: Any,
    ready_at: datetime,
    timestamps: Any,
    mb_disc_id: str | None = None,
) -> SourceJson:
    # Sprint-5 / D-disc-id-libdiscid: normalise empty/whitespace to None
    # (libdiscid emits an empty result on a marginal read).
    if mb_disc_id is not None:
        stripped = mb_disc_id.strip()
        mb_disc_id = stripped if stripped else None

    rip_success = bool(getattr(rip_record, "status", "") == "success")
    photo_success = bool(getattr(capture_result, "photo_path", None) is not None)
    ready = rip_success  # photo failure does NOT block READY (handoff contract)

    warnings: list[str] = []
    errors: list[str] = list(getattr(rip_record, "errors", []) or [])

    if rip_success and not photo_success:
        err = getattr(capture_result, "error", None) or "photo capture failed"
        warnings.append(err)
    if not rip_success:
        errors.append(f"rip status: {getattr(rip_record, 'status', 'unknown')}")

    # photo_captured_at: defer to timestamps when capture succeeded.
    pc_at = getattr(timestamps, "photo_captured_at", None) if photo_success else None

    return SourceJson(
        schema_version=1,
        ripper=Ripper(name=ripper_name, version=ripper_version, host=hostname),
        disc=Disc(
            folder_name=disc_dir.name,
            disc_counter=_counter_from_folder(disc_dir.name),
            inserted_at=timestamps.inserted_at,
            rip_started_at=timestamps.rip_started_at,
            rip_finished_at=timestamps.rip_finished_at,
            ejected_at=timestamps.ejected_at,
            ready_at=ready_at,
            timezone=str(getattr(ready_at, "tzinfo", "") or "UTC"),
        ),
        drive=Drive(
            device=getattr(drive_info, "device", "/dev/sr0"),
            model=getattr(drive_info, "model", None),
            serial=getattr(drive_info, "serial", None),
            read_offset=getattr(drive_info, "read_offset", None),
        ),
        audio=_audio_summary(disc_dir),
        identifiers=Identifiers(musicbrainz_disc_id=mb_disc_id),
        detected_metadata=DetectedMetadata(),  # all-null per D-source-json-v1
        physical_disc=PhysicalDisc(
            photo="disc-photo.jpg" if photo_success else None,
            photo_captured=photo_success,
            photo_captured_at=pc_at,
            photo_device=getattr(capture_result, "photo_device", None),
        ),
        files=_files_in(disc_dir),
        status=Status(
            rip_success=rip_success,
            photo_success=photo_success,
            ready=ready,
            warnings=warnings,
            errors=errors,
        ),
    )


def _counter_from_folder(folder_name: str) -> int:
    """Pull the trailing `disc-NNNNNN` counter out of the folder name."""
    import re
    m = re.search(r"disc-(\d+)$", folder_name)
    return int(m.group(1)) if m else 0
