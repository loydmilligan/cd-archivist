"""Failing tests for archivist.models.source.SourceJson (sprint-4 schema v1).

Per D-source-json-v1 and the handoff doc §source.json. New Pydantic v2
model coexists with the legacy Manifest v0.2 in
`archivist/models/manifest.py` — both live side by side.

Impl lands in Wave 2 (impl-source-json-model + impl-source-json-write).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


# Minimal example mirrors handoff-doc §"Minimal valid source.json".
# This is the lower bound the model must accept.
def _minimal_payload() -> dict:
    return {
        "schema_version": 1,
        "ripper": {
            "name": "cd-archivist",
            "version": "0.1.0",
            "host": "cm4",
        },
        "disc": {
            "folder_name": "2026-05-14_1832_disc-000421",
            "disc_counter": 421,
            "inserted_at": "2026-05-14T18:28:03-07:00",
            "rip_started_at": "2026-05-14T18:28:11-07:00",
            "rip_finished_at": "2026-05-14T18:34:44-07:00",
            "ejected_at": "2026-05-14T18:35:02-07:00",
            "ready_at": "2026-05-14T18:35:18-07:00",
            "timezone": "America/Los_Angeles",
        },
        "drive": {
            "device": "/dev/sr0",
            "model": "PIONEER BD-RW BDR-XD07",
            "serial": None,
            "read_offset": None,
        },
        "audio": {
            "format": "flac",
            "sample_rate_hz": 44100,
            "bits_per_sample": 16,
            "channels": 2,
            "track_count": 1,
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
            "photo": "disc-photo.jpg",
            "photo_captured": True,
            "photo_captured_at": "2026-05-14T18:35:12-07:00",
            "photo_device": "usb-microdia",
            "photo_notes": None,
            "label_text_guess": None,
            "appears_burned": None,
            "handwritten": None,
        },
        "files": [
            {
                "path": "01 Track.flac",
                "kind": "audio",
                "size_bytes": 25123456,
                "sha256": None,
            },
            {
                "path": "rip.log",
                "kind": "log",
                "size_bytes": 12345,
            },
        ],
        "status": {
            "rip_success": True,
            "photo_success": True,
            "ready": True,
            "warnings": [],
            "errors": [],
        },
    }


# -------- (a) minimal round-trip ------------------------------------


def test_minimal_payload_round_trips() -> None:
    from archivist.models.source import SourceJson

    payload = _minimal_payload()
    s = SourceJson.model_validate(payload)
    dumped = json.loads(s.model_dump_json())
    s2 = SourceJson.model_validate(dumped)
    assert s == s2


# -------- (b) full handoff-doc example round-trips ------------------


def test_full_payload_round_trips() -> None:
    from archivist.models.source import SourceJson

    payload = _minimal_payload()
    # Extend with the full example shape — detected_metadata tracks
    # populated, files with sha256.
    payload["detected_metadata"]["tracks"] = [
        {
            "track": 1,
            "title": None,
            "artist": None,
            "duration_seconds": 241,
            "isrc": None,
            "filename": "01 Track.flac",
        },
    ]
    payload["files"].append({
        "path": "disc-photo.jpg",
        "kind": "photo",
        "size_bytes": 1048576,
        "sha256": "a" * 64,
    })

    s = SourceJson.model_validate(payload)
    re_loaded = SourceJson.model_validate_json(s.model_dump_json())
    assert re_loaded == s


# -------- (c) schema_version mismatch raises ------------------------


def test_schema_version_mismatch_raises() -> None:
    from archivist.models.source import SourceJson

    payload = _minimal_payload()
    payload["schema_version"] = 2
    with pytest.raises(Exception):
        SourceJson.model_validate(payload)


# -------- (d) extra fields rejected (extra="forbid") ----------------


def test_extra_fields_rejected() -> None:
    from archivist.models.source import SourceJson

    payload = _minimal_payload()
    payload["unexpected_top_level_key"] = "boom"
    with pytest.raises(Exception):
        SourceJson.model_validate(payload)


def test_extra_fields_rejected_nested() -> None:
    from archivist.models.source import SourceJson

    payload = _minimal_payload()
    payload["ripper"]["mystery"] = 1
    with pytest.raises(Exception):
        SourceJson.model_validate(payload)


# -------- (e) ISO timestamps preserve timezone offsets --------------


def test_timestamps_serialize_with_offsets() -> None:
    """Per handoff doc: local time with offset, not naive, not Z."""
    from archivist.models.source import SourceJson

    s = SourceJson.model_validate(_minimal_payload())
    blob = s.model_dump_json()
    # The serialized form must carry an explicit `+` or `-` offset.
    # We assert on the disc.inserted_at field as a representative case.
    payload = json.loads(blob)
    inserted = payload["disc"]["inserted_at"]
    assert "+" in inserted or inserted.count("-") >= 3, (
        f"expected offset in {inserted!r} (no 'Z', no naive)"
    )
    assert not inserted.endswith("Z")


# -------- (f) status booleans are required --------------------------


def test_status_rip_and_photo_success_required() -> None:
    from archivist.models.source import SourceJson

    payload = _minimal_payload()
    del payload["status"]["rip_success"]
    with pytest.raises(Exception):
        SourceJson.model_validate(payload)

    payload2 = _minimal_payload()
    del payload2["status"]["photo_success"]
    with pytest.raises(Exception):
        SourceJson.model_validate(payload2)


# -------- (g) files entries: path, kind enum, size_bytes, optional sha256


def test_files_entries_required_fields() -> None:
    from archivist.models.source import SourceJson

    # `kind` must be one of audio/photo/log.
    payload = _minimal_payload()
    payload["files"][0]["kind"] = "wat"
    with pytest.raises(Exception):
        SourceJson.model_validate(payload)


def test_files_sha256_defaults_to_none() -> None:
    from archivist.models.source import SourceJson

    payload = _minimal_payload()
    # `sha256` may be omitted entirely.
    for entry in payload["files"]:
        entry.pop("sha256", None)
    s = SourceJson.model_validate(payload)
    for entry in s.files:
        assert entry.sha256 is None


# -------- write/read helpers (test-source-json-write) ---------------


def test_write_then_read_round_trip(tmp_path: Path) -> None:
    from archivist.models.source import SourceJson, read_source_json, write_source_json

    s = SourceJson.model_validate(_minimal_payload())
    out = tmp_path / "source.json"
    write_source_json(out, s)
    assert out.is_file()
    loaded = read_source_json(out)
    assert loaded == s


def test_write_is_atomic_via_tmp_sibling(tmp_path: Path) -> None:
    """write_source_json must write to <path>.tmp then os.replace."""
    from archivist.models.source import SourceJson, write_source_json

    s = SourceJson.model_validate(_minimal_payload())
    out = tmp_path / "source.json"

    # Capture os.replace to confirm the .tmp → final atomic move.
    seen: list[tuple[str, str]] = []
    real_replace = os.replace

    def spy(src, dst):  # type: ignore[no-untyped-def]
        seen.append((str(src), str(dst)))
        return real_replace(src, dst)

    import archivist.models.source as src_mod

    src_mod.os.replace = spy  # type: ignore[attr-defined]
    try:
        write_source_json(out, s)
    finally:
        src_mod.os.replace = real_replace  # type: ignore[attr-defined]

    assert seen, "os.replace was not called — write is not atomic"
    src_path, dst_path = seen[-1]
    assert src_path.endswith(".tmp")
    assert dst_path == str(out)


def test_read_rejects_schema_mismatch(tmp_path: Path) -> None:
    from archivist.models.source import read_source_json

    bad = tmp_path / "source.json"
    payload = _minimal_payload()
    payload["schema_version"] = 99
    bad.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        read_source_json(bad)


def test_read_rejects_malformed_json_with_path(tmp_path: Path) -> None:
    from archivist.models.source import read_source_json

    bad = tmp_path / "source.json"
    bad.write_text("{not json")
    with pytest.raises(Exception) as exc_info:
        read_source_json(bad)
    # Error message should reference the path.
    assert str(bad) in str(exc_info.value) or "source.json" in str(exc_info.value)
