"""Failing tests for the unified library reader (sprint-4 / D-library-legacy-adapter).

`archivist/service/library.py::read_disc_summary(disc_dir) -> DiscSummary | None`
returns a small dataclass the library UI consumes. Handles BOTH:

  - legacy `CD_NNNN/manifest.json` (v0.2)
  - new   `YYYY-MM-DD_HHMM_disc-NNNNNN/source.json` (v1)

When both files exist (defense-in-depth shouldn't-happen case), prefer
`source.json` and log once. When neither exists, return None.

Impl lands in Wave 2 (impl-library-legacy-adapter).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from archivist.models.manifest import Manifest, RipRecord, write_manifest


def _legacy_manifest(disc_id: str, *, rip_success: bool, tracks: int = 1) -> Manifest:
    return Manifest(
        schema_version="0.2",
        disc_id=disc_id,
        media_type="audio_cd",
        created_at=datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc),
        status="ripped" if rip_success else "rip_failed",
        captures=[],
        rips=[RipRecord(
            status="success" if rip_success else "fail",
            tracks=[f"audio/track{i:02d}.flac" for i in range(1, tracks + 1)],
            errors=[],
        )],
        pairings=[],
        metadata={},
        errors=[],
    )


def _source_json_dict(folder_name: str, *, rip_success: bool, tracks: int = 1) -> dict:
    return {
        "schema_version": 1,
        "ripper": {"name": "cd-archivist", "version": "0.1.0", "host": "cm4"},
        "disc": {
            "folder_name": folder_name,
            "disc_counter": 1,
            "inserted_at": "2026-05-14T18:28:03-07:00",
            "rip_started_at": "2026-05-14T18:28:11-07:00",
            "rip_finished_at": "2026-05-14T18:34:44-07:00",
            "ejected_at": "2026-05-14T18:35:02-07:00",
            "ready_at": "2026-05-14T18:35:18-07:00",
            "timezone": "America/Los_Angeles",
        },
        "drive": {"device": "/dev/sr0", "model": "X", "serial": None, "read_offset": None},
        "audio": {
            "format": "flac",
            "sample_rate_hz": 44100,
            "bits_per_sample": 16,
            "channels": 2,
            "track_count": tracks,
            "total_duration_seconds": 240,
            "secure_rip": True,
            "accuraterip_verified": None,
        },
        "identifiers": {
            "musicbrainz_disc_id": None,
            "freedb_disc_id": None,
            "cd_toc": None,
            "upc": None,
            "isrcs": [],
        },
        "detected_metadata": {
            "album_artist": None,
            "album": None,
            "year": None,
            "label": None,
            "catalog_number": None,
            "tracks": [],
        },
        "physical_disc": {
            "photo": "disc-photo.jpg" if rip_success else None,
            "photo_captured": rip_success,
            "photo_captured_at": "2026-05-14T18:35:12-07:00" if rip_success else None,
            "photo_device": "usb-microdia" if rip_success else None,
            "photo_notes": None,
            "label_text_guess": None,
            "appears_burned": None,
            "handwritten": None,
        },
        "files": [],
        "status": {
            "rip_success": rip_success,
            "photo_success": rip_success,
            "ready": rip_success,
            "warnings": [],
            "errors": [] if rip_success else ["bad sectors"],
        },
    }


# -------- (a) legacy-only folder ------------------------------------


def test_legacy_only_returns_is_legacy_true(tmp_path: Path) -> None:
    from archivist.service.library import read_disc_summary

    d = tmp_path / "CD_0018"
    d.mkdir()
    (d / "captures").mkdir()
    (d / "captures" / "disc_front_lit_001.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    write_manifest(d / "manifest.json", _legacy_manifest("CD_0018", rip_success=True, tracks=3))

    summary = read_disc_summary(d)
    assert summary is not None
    assert summary.is_legacy is True
    assert summary.rip_success is True
    assert summary.track_count == 3
    assert summary.disc_id_or_folder == "CD_0018"


def test_legacy_rip_failed_reported_correctly(tmp_path: Path) -> None:
    from archivist.service.library import read_disc_summary

    d = tmp_path / "CD_0019"
    d.mkdir()
    write_manifest(d / "manifest.json", _legacy_manifest("CD_0019", rip_success=False))

    summary = read_disc_summary(d)
    assert summary is not None
    assert summary.is_legacy is True
    assert summary.rip_success is False


# -------- (b) new-only folder ---------------------------------------


def test_new_source_json_only_returns_is_legacy_false(tmp_path: Path) -> None:
    from archivist.service.library import read_disc_summary

    name = "2026-05-15_1432_disc-000001"
    d = tmp_path / name
    d.mkdir()
    payload = _source_json_dict(name, rip_success=True, tracks=12)
    (d / "source.json").write_text(json.dumps(payload))
    (d / "disc-photo.jpg").write_bytes(b"\xff\xd8\xff\xd9")

    summary = read_disc_summary(d)
    assert summary is not None
    assert summary.is_legacy is False
    assert summary.rip_success is True
    assert summary.track_count == 12
    assert summary.disc_id_or_folder == name


# -------- (c) both present → prefer source.json ---------------------


def test_both_files_present_prefer_source_json(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    from archivist.service.library import read_disc_summary

    name = "2026-05-15_1500_disc-000002"
    d = tmp_path / name
    d.mkdir()
    # Legacy says rip_success=False; new says True. The new one wins.
    write_manifest(d / "manifest.json", _legacy_manifest("CD_X", rip_success=False))
    (d / "source.json").write_text(json.dumps(_source_json_dict(name, rip_success=True)))

    summary = read_disc_summary(d)
    assert summary is not None
    assert summary.is_legacy is False
    assert summary.rip_success is True  # came from source.json


# -------- (d) neither present → None --------------------------------


def test_neither_file_returns_none(tmp_path: Path) -> None:
    from archivist.service.library import read_disc_summary

    d = tmp_path / "stray_folder"
    d.mkdir()
    assert read_disc_summary(d) is None


# -------- (e) folder-name parsing for both shapes -------------------


def test_disc_id_or_folder_field_for_both_shapes(tmp_path: Path) -> None:
    from archivist.service.library import read_disc_summary

    legacy = tmp_path / "CD_0018"
    legacy.mkdir()
    write_manifest(legacy / "manifest.json", _legacy_manifest("CD_0018", rip_success=True))

    new_name = "2026-05-15_1432_disc-000001"
    new_dir = tmp_path / new_name
    new_dir.mkdir()
    (new_dir / "source.json").write_text(json.dumps(_source_json_dict(new_name, rip_success=True)))

    legacy_summary = read_disc_summary(legacy)
    new_summary = read_disc_summary(new_dir)
    assert legacy_summary is not None and legacy_summary.disc_id_or_folder == "CD_0018"
    assert new_summary is not None and new_summary.disc_id_or_folder == new_name
