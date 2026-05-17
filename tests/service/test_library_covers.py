"""Failing tests for beets-cover-preference on library thumbnails (sprint-5).

Per D-library-cover-preference: when a new-shape disc folder's
`source.json.detected_metadata.{album_artist,album}` is populated AND
`<MUSIC_LIBRARY_DIR>/<album_artist>/<album>/cover.{jpg,png,jpeg,webp}`
exists, the library UI uses that beets-fetched cover as the thumbnail
in preference to the disc-photo.jpg. The detail page renders both
images in distinct "album art" / "physical disc" sections.

Legacy `CD_NNNN/manifest.json` folders never get the library cover —
their manifest doesn't carry detected_metadata; they keep showing
disc-photo.jpg.

Impl lands in Wave 2 (impl-library-prefer-beets-cover).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from archivist.models.manifest import Manifest, RipRecord, write_manifest
from archivist.service.app import LoopState, create_app


def _source_json_dict(
    folder_name: str, *, album_artist: str | None, album: str | None,
) -> dict:
    return {
        "schema_version": 1,
        "ripper": {"name": "x", "version": "0", "host": "h"},
        "disc": {
            "folder_name": folder_name, "disc_counter": 1,
            "inserted_at": "2026-05-16T18:28:03-07:00",
            "rip_started_at": "2026-05-16T18:28:11-07:00",
            "rip_finished_at": "2026-05-16T18:34:44-07:00",
            "ejected_at": "2026-05-16T18:35:02-07:00",
            "ready_at": "2026-05-16T18:35:18-07:00",
            "timezone": "America/Los_Angeles",
        },
        "drive": {"device": "/dev/sr0", "model": "X", "serial": None, "read_offset": None},
        "audio": {
            "format": "flac", "sample_rate_hz": 44100, "bits_per_sample": 16,
            "channels": 2, "track_count": 1, "total_duration_seconds": 60,
            "secure_rip": True, "accuraterip_verified": None,
        },
        "identifiers": {
            "musicbrainz_disc_id": None, "freedb_disc_id": None,
            "cd_toc": None, "upc": None, "isrcs": [],
        },
        "detected_metadata": {
            "album_artist": album_artist, "album": album, "year": None,
            "label": None, "catalog_number": None, "tracks": [],
        },
        "physical_disc": {
            "photo": "disc-photo.jpg", "photo_captured": True,
            "photo_captured_at": "2026-05-16T18:35:12-07:00",
            "photo_device": "cam", "photo_notes": None,
            "label_text_guess": None, "appears_burned": None, "handwritten": None,
        },
        "files": [],
        "status": {
            "rip_success": True, "photo_success": True, "ready": True,
            "warnings": [], "errors": [],
        },
    }


def _legacy_manifest(disc_id: str) -> Manifest:
    return Manifest(
        schema_version="0.2",
        disc_id=disc_id,
        media_type="audio_cd",
        created_at=datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc),
        status="ripped",
        captures=[],
        rips=[RipRecord(status="success", tracks=["audio/track01.flac"], errors=[])],
        pairings=[], metadata={}, errors=[],
    )


@pytest.fixture
def music_dirs(tmp_path: Path) -> tuple[Path, Path]:
    """Returns (inbox_root, library_root)."""
    inbox = tmp_path / "music" / "inbox"
    library = tmp_path / "music" / "library"
    inbox.mkdir(parents=True)
    library.mkdir(parents=True)
    return inbox, library


def _make_client(inbox: Path, library: Path, tmp_path: Path) -> TestClient:
    log = tmp_path / "archivist.log"
    log.write_text("")
    return TestClient(create_app(
        LoopState(), log,
        discs_root=inbox,
        library_root=library,
    ))


# -------- (a) library cover wins on grid thumbnail ------------------


def test_thumbnail_uses_library_cover_when_present(
    music_dirs: tuple[Path, Path], tmp_path: Path,
) -> None:
    inbox, library = music_dirs
    folder = inbox / "2026-05-16_1200_disc-000001"
    folder.mkdir()
    (folder / "source.json").write_text(json.dumps(
        _source_json_dict(folder.name, album_artist="AFI", album="Sing the Sorrow"),
    ))
    (folder / "disc-photo.jpg").write_bytes(b"\xff\xd8\xff\xd9")

    album_dir = library / "AFI" / "Sing the Sorrow"
    album_dir.mkdir(parents=True)
    (album_dir / "cover.jpg").write_bytes(b"\xff\xd8cover")

    client = _make_client(inbox, library, tmp_path)
    body = client.get(f"/library/{folder.name}").text
    assert f"/library/{folder.name}/album-cover" in body


# -------- (b) library dir missing → fall back to disc-photo ---------


def test_thumbnail_falls_back_when_library_dir_absent(
    music_dirs: tuple[Path, Path], tmp_path: Path,
) -> None:
    inbox, library = music_dirs
    folder = inbox / "2026-05-16_1300_disc-000002"
    folder.mkdir()
    (folder / "source.json").write_text(json.dumps(
        _source_json_dict(folder.name, album_artist="STP", album="Core"),
    ))
    (folder / "disc-photo.jpg").write_bytes(b"\xff\xd8\xff\xd9")

    # No library/STP/Core/cover.* — fall back.
    client = _make_client(inbox, library, tmp_path)
    body = client.get(f"/library/{folder.name}").text
    assert f"/library/{folder.name}/photo" in body
    assert f"/library/{folder.name}/album-cover" not in body


# -------- (c) null detected_metadata → disc-photo --------------------


def test_thumbnail_no_library_lookup_when_detected_metadata_null(
    music_dirs: tuple[Path, Path], tmp_path: Path,
) -> None:
    inbox, library = music_dirs
    folder = inbox / "2026-05-16_1400_disc-000003"
    folder.mkdir()
    (folder / "source.json").write_text(json.dumps(
        _source_json_dict(folder.name, album_artist=None, album=None),
    ))
    (folder / "disc-photo.jpg").write_bytes(b"\xff\xd8\xff\xd9")

    client = _make_client(inbox, library, tmp_path)
    body = client.get(f"/library/{folder.name}").text
    assert f"/library/{folder.name}/photo" in body
    assert f"/library/{folder.name}/album-cover" not in body


# -------- (d) legacy CD_NNNN folder never gets library cover --------


def test_legacy_folder_never_resolves_library_cover(
    music_dirs: tuple[Path, Path], tmp_path: Path,
) -> None:
    inbox, library = music_dirs
    folder = inbox / "CD_0001"
    folder.mkdir()
    write_manifest(folder / "manifest.json", _legacy_manifest("CD_0001"))
    (folder / "captures").mkdir()
    (folder / "captures" / "disc_front_lit_001.jpg").write_bytes(b"\xff\xd8\xff\xd9")

    # Even if a coincidentally-named library cover existed, legacy never
    # looks it up.
    client = _make_client(inbox, library, tmp_path)
    body = client.get("/library/CD_0001").text
    assert "/library/CD_0001/album-cover" not in body


# -------- (e) both present → library cover wins ---------------------


def test_library_cover_wins_when_disc_photo_also_present(
    music_dirs: tuple[Path, Path], tmp_path: Path,
) -> None:
    inbox, library = music_dirs
    folder = inbox / "2026-05-16_1500_disc-000004"
    folder.mkdir()
    (folder / "source.json").write_text(json.dumps(
        _source_json_dict(folder.name, album_artist="Tool", album="Lateralus"),
    ))
    (folder / "disc-photo.jpg").write_bytes(b"\xff\xd8disc")
    album_dir = library / "Tool" / "Lateralus"
    album_dir.mkdir(parents=True)
    (album_dir / "cover.png").write_bytes(b"\x89PNGcover")

    client = _make_client(inbox, library, tmp_path)
    body = client.get(f"/library/{folder.name}").text
    assert f"/library/{folder.name}/album-cover" in body


# -------- (f) detail page renders BOTH sections ---------------------


def test_detail_renders_both_album_art_and_physical_disc_sections(
    music_dirs: tuple[Path, Path], tmp_path: Path,
) -> None:
    inbox, library = music_dirs
    folder = inbox / "2026-05-16_1600_disc-000005"
    folder.mkdir()
    (folder / "source.json").write_text(json.dumps(
        _source_json_dict(folder.name, album_artist="Radiohead", album="OK Computer"),
    ))
    (folder / "disc-photo.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    album_dir = library / "Radiohead" / "OK Computer"
    album_dir.mkdir(parents=True)
    (album_dir / "cover.jpg").write_bytes(b"\xff\xd8cover")

    client = _make_client(inbox, library, tmp_path)
    body = client.get(f"/library/{folder.name}").text
    # Both labels appear (sentence case).
    assert "album art" in body.lower()
    assert "physical disc" in body.lower()
    # Both endpoints referenced.
    assert f"/library/{folder.name}/album-cover" in body
    assert f"/library/{folder.name}/photo" in body
