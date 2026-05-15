"""Failing tests for the source.json assembler (sprint-4 / impl-source-json-builder).

`build_source_json(disc_dir, *, ripper_name, ripper_version, hostname,
drive_info, rip_record, capture_result, ready_at, timestamps) ->
SourceJson` turns the state-machine's per-cycle bookkeeping into a
populated `SourceJson`.

Lives in `archivist/pipeline/source_json.py` (new file).
Impl lands in Wave 2.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


# Small fixture types used by the builder API — represent what the
# state machine has on hand when it calls `build_source_json`.
@dataclass
class _DriveInfo:
    device: str = "/dev/sr0"
    model: str = "PIONEER BD-RW BDR-XD07"
    serial: str | None = None
    read_offset: int | None = None


@dataclass
class _Timestamps:
    inserted_at: datetime
    rip_started_at: datetime
    rip_finished_at: datetime
    ejected_at: datetime
    photo_captured_at: datetime | None


@dataclass
class _CaptureResult:
    photo_path: Path | None  # None on failure
    photo_device: str | None
    error: str | None = None


def _tzaware(offset_hours: int = -7) -> datetime:
    return datetime(2026, 5, 14, 18, 28, 0, tzinfo=timezone(timedelta(hours=offset_hours)))


def _make_disc_dir(tmp_path: Path) -> Path:
    """Builds an inbox-shape disc folder with 2 FLACs and a disc-photo."""
    d = tmp_path / "2026-05-14_1832_disc-000421"
    d.mkdir(parents=True)
    (d / "01 Track.flac").write_bytes(b"fLaC" + b"\x00" * 100)
    (d / "02 Track.flac").write_bytes(b"fLaC" + b"\x00" * 200)
    (d / "rip.log").write_text("[ts] rip start\n[ts] rip end\n")
    (d / "disc-photo.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    return d


def _ripper_rec(*, status: str = "success", n_tracks: int = 2) -> object:
    """Build a RipRecord-like object the builder consumes.

    The builder doesn't care if it's the legacy `RipRecord` from
    `archivist.models.manifest` or a sprint-4 equivalent — duck-typed
    on `.status` and `.tracks`.
    """
    from archivist.models.manifest import RipRecord
    tracks = [f"audio/track{i:02d}.flac" for i in range(1, n_tracks + 1)]
    return RipRecord(status=status, tracks=tracks, errors=[])


def _timestamps_happy() -> _Timestamps:
    base = _tzaware()
    return _Timestamps(
        inserted_at=base,
        rip_started_at=base + timedelta(seconds=8),
        rip_finished_at=base + timedelta(minutes=6, seconds=33),
        ejected_at=base + timedelta(minutes=7, seconds=0),
        photo_captured_at=base + timedelta(minutes=7, seconds=10),
    )


# -------- (a) happy path — full population --------------------------


def test_happy_path_populates_status_and_files(tmp_path: Path) -> None:
    from archivist.pipeline.source_json import build_source_json

    disc_dir = _make_disc_dir(tmp_path)
    ts = _timestamps_happy()
    capture = _CaptureResult(
        photo_path=disc_dir / "disc-photo.jpg",
        photo_device="usb-microdia",
    )
    ready_at = ts.photo_captured_at + timedelta(seconds=6)

    s = build_source_json(
        disc_dir,
        ripper_name="cd-archivist",
        ripper_version="0.1.0",
        hostname="cm4",
        drive_info=_DriveInfo(),
        rip_record=_ripper_rec(),
        capture_result=capture,
        ready_at=ready_at,
        timestamps=ts,
    )

    assert s.status.rip_success is True
    assert s.status.photo_success is True
    assert s.status.ready is True
    assert s.physical_disc.photo == "disc-photo.jpg"
    assert s.audio.track_count == 2

    # files[] lists every audio file + the photo + rip.log.
    paths = {f.path for f in s.files}
    assert "01 Track.flac" in paths
    assert "02 Track.flac" in paths
    assert "disc-photo.jpg" in paths
    assert "rip.log" in paths
    # size_bytes populated, sha256 default None.
    for f in s.files:
        assert f.size_bytes > 0
        assert f.sha256 is None


# -------- (b) photo failure — rip success, photo_success=False ------


def test_photo_failure_sets_photo_success_false_but_ready_true(tmp_path: Path) -> None:
    from archivist.pipeline.source_json import build_source_json

    disc_dir = _make_disc_dir(tmp_path)
    # Remove the photo to simulate capture failure.
    (disc_dir / "disc-photo.jpg").unlink()
    ts = _timestamps_happy()
    ts.photo_captured_at = None

    capture = _CaptureResult(
        photo_path=None,
        photo_device=None,
        error="camera unreachable: ffmpeg returned 1",
    )
    ready_at = ts.rip_finished_at + timedelta(seconds=30)

    s = build_source_json(
        disc_dir,
        ripper_name="cd-archivist",
        ripper_version="0.1.0",
        hostname="cm4",
        drive_info=_DriveInfo(),
        rip_record=_ripper_rec(),
        capture_result=capture,
        ready_at=ready_at,
        timestamps=ts,
    )

    assert s.status.rip_success is True
    assert s.status.photo_success is False
    assert s.physical_disc.photo is None
    assert s.status.ready is True  # photo failure does NOT block READY
    # Warning string surfaces the failure.
    assert any("camera" in w.lower() or "photo" in w.lower() for w in s.status.warnings)


# -------- (c) rip failure — rip_success=False, ready=False ----------


def test_rip_failure_sets_rip_success_false_and_not_ready(tmp_path: Path) -> None:
    from archivist.pipeline.source_json import build_source_json

    disc_dir = _make_disc_dir(tmp_path)
    ts = _timestamps_happy()
    capture = _CaptureResult(photo_path=None, photo_device=None)
    s = build_source_json(
        disc_dir,
        ripper_name="cd-archivist",
        ripper_version="0.1.0",
        hostname="cm4",
        drive_info=_DriveInfo(),
        rip_record=_ripper_rec(status="fail"),
        capture_result=capture,
        ready_at=ts.rip_finished_at,
        timestamps=ts,
    )

    assert s.status.rip_success is False
    assert s.status.ready is False
    assert s.status.errors  # populated


# -------- (d) detected_metadata is always all-nulls in sprint-4 -----


def test_detected_metadata_is_all_nulls(tmp_path: Path) -> None:
    from archivist.pipeline.source_json import build_source_json

    disc_dir = _make_disc_dir(tmp_path)
    ts = _timestamps_happy()
    capture = _CaptureResult(photo_path=disc_dir / "disc-photo.jpg", photo_device="cam")

    s = build_source_json(
        disc_dir,
        ripper_name="cd-archivist",
        ripper_version="0.1.0",
        hostname="cm4",
        drive_info=_DriveInfo(),
        rip_record=_ripper_rec(),
        capture_result=capture,
        ready_at=ts.rip_finished_at,
        timestamps=ts,
    )

    dm = s.detected_metadata
    assert dm.album_artist is None
    assert dm.album is None
    assert dm.year is None
    assert dm.label is None
    assert dm.catalog_number is None
    assert dm.tracks == []


# -------- (e) physical_disc burned/handwritten always null in sprint-4 ---


def test_physical_disc_label_fields_are_null(tmp_path: Path) -> None:
    from archivist.pipeline.source_json import build_source_json

    disc_dir = _make_disc_dir(tmp_path)
    ts = _timestamps_happy()
    capture = _CaptureResult(photo_path=disc_dir / "disc-photo.jpg", photo_device="cam")

    s = build_source_json(
        disc_dir,
        ripper_name="cd-archivist",
        ripper_version="0.1.0",
        hostname="cm4",
        drive_info=_DriveInfo(),
        rip_record=_ripper_rec(),
        capture_result=capture,
        ready_at=ts.rip_finished_at,
        timestamps=ts,
    )

    pd = s.physical_disc
    assert pd.label_text_guess is None
    assert pd.appears_burned is None
    assert pd.handwritten is None


# -------- (f) timestamps include local timezone offsets -------------


def test_timestamps_carry_offsets(tmp_path: Path) -> None:
    from archivist.pipeline.source_json import build_source_json

    disc_dir = _make_disc_dir(tmp_path)
    ts = _timestamps_happy()
    capture = _CaptureResult(photo_path=disc_dir / "disc-photo.jpg", photo_device="cam")

    s = build_source_json(
        disc_dir,
        ripper_name="cd-archivist",
        ripper_version="0.1.0",
        hostname="cm4",
        drive_info=_DriveInfo(),
        rip_record=_ripper_rec(),
        capture_result=capture,
        ready_at=ts.rip_finished_at,
        timestamps=ts,
    )

    blob = s.model_dump_json()
    inserted = ts.inserted_at.isoformat()
    # The source datetime carries an offset.
    assert "+" in inserted or "-" in inserted[-6:]
    # And the serialized JSON preserves it — no naive `Z` suffix on
    # the timestamp.
    assert '"inserted_at":' in blob
    assert "Z\"" not in blob
