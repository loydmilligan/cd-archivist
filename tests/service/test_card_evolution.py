"""Failing tests for card visual-evolution (sprint-6.5 Bucket B).

Pins the rendering changes per D-card-state-evolution (settled in
brainstorm K1.6) — cards visually mature as they transit the
pipeline:

  - Per-track segments gain `data-track-identified-{N}="true"`
    when beets identified that track.
  - Artist/Album chips render with `chip--confirmed` when beets
    confirmed; `chip--asserted` (dashed border) when operator
    asserted via operator_hints.
  - Cards in failed/partial state get `card--damaged`.
  - Thumbnail src prefers library cover when bucket=="library";
    falls back to disc-photo.jpg.

Impl lands in Wave 2 (impl-card-state-evolution +
D-card-evolution-tokens).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from archivist.service.app import LoopState, create_app


def _write_flac(path: Path, n_bytes: int = 1024) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fLaC" + b"\x00" * n_bytes)


def _base_source(folder_name: str, **overrides) -> dict:
    payload = {
        "schema_version": 1,
        "ripper": {"name": "cd-archivist", "version": "0.1.0", "host": "cm4"},
        "disc": {
            "folder_name": folder_name, "disc_counter": 1,
            "inserted_at": "2026-05-16T10:00:00-07:00",
            "rip_started_at": "2026-05-16T10:00:10-07:00",
            "rip_finished_at": "2026-05-16T10:05:00-07:00",
            "ejected_at": "2026-05-16T10:05:30-07:00",
            "ready_at": "2026-05-16T10:05:45-07:00",
            "timezone": "America/Los_Angeles",
        },
        "drive": {"device": "/dev/sr0", "model": "X", "serial": None, "read_offset": None},
        "audio": {
            "format": "flac", "sample_rate_hz": 44100, "bits_per_sample": 16,
            "channels": 2, "track_count": 3,
            "total_duration_seconds": 480,
            "secure_rip": True, "accuraterip_verified": None,
        },
        "identifiers": {
            "musicbrainz_disc_id": None, "freedb_disc_id": None,
            "cd_toc": None, "upc": None, "isrcs": [],
        },
        "detected_metadata": {
            "album_artist": None, "album": None, "year": None,
            "label": None, "catalog_number": None, "tracks": [],
        },
        "physical_disc": {
            "photo": None, "photo_captured": False,
            "photo_captured_at": None, "photo_device": None,
            "photo_notes": None, "label_text_guess": None,
            "appears_burned": None, "handwritten": None,
        },
        "files": [],
        "status": {
            "rip_success": True, "photo_success": True, "ready": True,
            "warnings": [], "errors": [],
            "partial": False, "failed_tracks": [],
        },
    }
    for k, v in overrides.items():
        if isinstance(v, dict):
            payload[k] = {**payload.get(k, {}), **v}
        else:
            payload[k] = v
    return payload


def _seed(parent: Path, name: str, payload: dict | None = None) -> Path:
    folder = parent / name
    _write_flac(folder / "01.flac")
    folder.mkdir(parents=True, exist_ok=True)
    if payload is None:
        payload = _base_source(name)
    (folder / "source.json").write_text(json.dumps(payload))
    return folder


@pytest.fixture
def music_root(tmp_path: Path) -> Path:
    root = tmp_path / "music"
    for sub in ("inbox", "review", "library", "archive", "failed"):
        (root / sub).mkdir(parents=True)
    return root


@pytest.fixture
def client(music_root: Path, tmp_path: Path) -> TestClient:
    log_path = tmp_path / "archivist.log"
    log_path.write_text("")
    return TestClient(create_app(
        LoopState(), log_path,
        discs_root=music_root / "inbox",
        review_root=music_root / "review",
        library_root=music_root / "library",
        music_root=music_root,
    ))


# ============== (a) per-track identified outline =========================


def test_identified_tracks_carry_data_attribute(
    client: TestClient, music_root: Path,
) -> None:
    """When source.json has a disc-id AND beets-confirmed tracks (via
    detected_metadata.tracks with a `title` per track), each
    track-cell gets data-track-identified-{N}="true"."""
    folder = _seed(music_root / "review", "disc-id1", _base_source(
        "disc-id1",
        identifiers={
            "musicbrainz_disc_id": "mbid-abc", "freedb_disc_id": None,
            "cd_toc": None, "upc": None, "isrcs": [],
        },
        detected_metadata={
            "album_artist": "X", "album": "Y", "year": None,
            "label": None, "catalog_number": None,
            "tracks": [
                {"track": 1, "title": "T1"},
                {"track": 2, "title": "T2"},
                {"track": 3, "title": "T3"},
            ],
        },
    ))
    html = client.get("/").text
    assert 'data-track-identified-1="true"' in html
    assert 'data-track-identified-2="true"' in html
    assert 'data-track-identified-3="true"' in html


def test_unidentified_tracks_do_not_carry_data_attribute(
    client: TestClient, music_root: Path,
) -> None:
    """No disc-id + no detected_metadata.tracks → no track is marked
    identified, regardless of other state."""
    _seed(music_root / "review", "disc-noid")
    html = client.get("/").text
    assert 'data-track-identified-1="true"' not in html


# ============== (b) chip--confirmed when beets confirmed =================


def test_confirmed_chips_carry_confirmed_class(
    client: TestClient, music_root: Path,
) -> None:
    _seed(music_root / "library" / "Foo", "Bar", _base_source(
        "Bar",
        detected_metadata={
            "album_artist": "Foo", "album": "Bar", "year": None,
            "label": None, "catalog_number": None, "tracks": [],
        },
    ))
    html = client.get("/").text
    assert "chip--confirmed" in html


# ============== (c) chip--asserted when operator-only ====================


def test_asserted_chips_carry_asserted_class(
    client: TestClient, music_root: Path,
) -> None:
    """operator_hints.artist set; detected_metadata.album_artist NOT
    confirmed by beets → asserted (dashed border)."""
    _seed(music_root / "review", "disc-asserted", _base_source(
        "disc-asserted",
        operator_hints={
            "various_artists": False, "burned_cd": False,
            "artist": "Hand-Typed", "album": None, "tracks": [],
        },
    ))
    html = client.get("/").text
    assert "chip--asserted" in html
    # The confirmed class must NOT appear for this card — there's no
    # detected_metadata to confirm against.
    assert "chip--confirmed" not in html


def test_confirmed_wins_over_asserted_when_both_present(
    client: TestClient, music_root: Path,
) -> None:
    """If beets confirmed AND operator asserted, the chip is
    confirmed (system trumps operator)."""
    _seed(music_root / "library" / "Foo", "Bar", _base_source(
        "Bar",
        detected_metadata={
            "album_artist": "Foo", "album": "Bar", "year": None,
            "label": None, "catalog_number": None, "tracks": [],
        },
        operator_hints={
            "various_artists": False, "burned_cd": False,
            "artist": "Foo", "album": "Bar", "tracks": [],
        },
    ))
    html = client.get("/").text
    assert "chip--confirmed" in html


# ============== (d) card--damaged when partial / rip_success=False =======


def test_partial_card_carries_damaged_class(
    client: TestClient, music_root: Path,
) -> None:
    _seed(music_root / "failed", "disc-partial", _base_source(
        "disc-partial",
        status={
            "rip_success": False, "photo_success": True, "ready": False,
            "warnings": [], "errors": ["abort at track 3"],
            "partial": True, "failed_tracks": [3, 4, 5],
        },
    ))
    html = client.get("/").text
    assert "card--damaged" in html


def test_healthy_card_does_not_carry_damaged_class(
    client: TestClient, music_root: Path,
) -> None:
    _seed(music_root / "review", "disc-healthy")
    html = client.get("/").text
    assert "card--damaged" not in html


# ============== (e) thumbnail src logic ==================================


def test_library_card_thumbnail_prefers_album_cover(
    client: TestClient, music_root: Path,
) -> None:
    """When bucket=="library" the thumbnail src points at the
    library album-cover endpoint (sprint-5 /library/<disc>/album-cover
    or equivalent), not the disc-photo."""
    folder = _seed(music_root / "library" / "Foo", "Bar", _base_source(
        "Bar",
        detected_metadata={
            "album_artist": "Foo", "album": "Bar", "year": None,
            "label": None, "catalog_number": None, "tracks": [],
        },
    ))
    html = client.get("/").text
    # The library-cover URL convention is the sprint-5 endpoint.
    assert "/library/" in html
    assert "album-cover" in html
    assert folder.name in html


def test_review_card_thumbnail_falls_back_to_disc_photo(
    client: TestClient, music_root: Path,
) -> None:
    """Review-bucket cards (no library entry yet) fall back to the
    disc-photo path under the disc folder."""
    folder = _seed(music_root / "review", "disc-rev1")
    html = client.get("/").text
    # Falls back to disc-photo.jpg under the folder; the exact URL
    # convention may route via /review/<folder>/disc-photo.jpg or a
    # /api/disc/<folder>/photo endpoint — pin the filename so the
    # impl has freedom on the route.
    assert "disc-photo.jpg" in html
    assert folder.name in html
