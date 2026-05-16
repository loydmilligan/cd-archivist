"""Failing tests for PATCH /api/disc/<folder>/hints (sprint-6 Bucket B+).

Covers test-operator-hints-api. Per the Contract Changes block
`source.json.operator_hints` is an optional block with toggles
(`various_artists`, `burned_cd`), album-level text fields (`artist`,
`album`), and per-track entries (`tracks: [{track_number, artist,
title}]`). Sprint-6 captures; sprint-7 wires into beets queries.

Merge semantics: only fields present in the request body are
written. `tracks` merges per `track_number` (existing rows updated
in place; new track_numbers appended; rows not in the patch body
preserved unchanged).

Impl lands in Wave 2 (impl-operator-hints).
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


def _base_source(folder_name: str) -> dict:
    return {
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
            "total_duration_seconds": 600,
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
            "rip_success": True, "photo_success": False, "ready": True,
            "warnings": [], "errors": [],
        },
    }


def _seed_disc(music_root: Path, name: str = "disc-x", *, bucket: str = "review") -> Path:
    folder = music_root / bucket / name
    _write_flac(folder / "01.flac")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "source.json").write_text(json.dumps(_base_source(name)))
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


def _read_hints(folder: Path) -> dict:
    payload = json.loads((folder / "source.json").read_text())
    return payload.get("operator_hints", {})


# ---------------- (a) toggle write ---------------------------------------


def test_patch_various_artists_toggle(client: TestClient, music_root: Path) -> None:
    folder = _seed_disc(music_root, "disc-a")
    resp = client.patch(
        f"/api/disc/{folder.name}/hints",
        json={"various_artists": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    # Endpoint returns the full updated operator_hints block.
    assert body["various_artists"] is True
    assert body["burned_cd"] is False
    # Persisted on disk.
    assert _read_hints(folder)["various_artists"] is True


# ---------------- (b) toggle + album-level text not mutually exclusive ---


def test_patch_writes_burned_cd_and_album_fields(
    client: TestClient, music_root: Path,
) -> None:
    folder = _seed_disc(music_root, "disc-b")
    resp = client.patch(
        f"/api/disc/{folder.name}/hints",
        json={"burned_cd": True, "artist": "Foo", "album": "Bar"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["burned_cd"] is True
    assert body["artist"] == "Foo"
    assert body["album"] == "Bar"
    persisted = _read_hints(folder)
    assert persisted["burned_cd"] is True
    assert persisted["artist"] == "Foo"
    assert persisted["album"] == "Bar"


# ---------------- (c) 404 on missing folder ------------------------------


def test_patch_unknown_folder_returns_404(client: TestClient) -> None:
    resp = client.patch(
        "/api/disc/does-not-exist/hints",
        json={"various_artists": True},
    )
    assert resp.status_code == 404


# ---------------- (d) merge semantics, not overwrite ---------------------


def test_patch_preserves_fields_not_in_body(
    client: TestClient, music_root: Path,
) -> None:
    folder = _seed_disc(music_root, "disc-d")
    # First PATCH: set artist + album.
    client.patch(
        f"/api/disc/{folder.name}/hints",
        json={"artist": "FirstArtist", "album": "FirstAlbum"},
    )
    # Second PATCH: flip only the toggle. Artist + album must persist.
    resp = client.patch(
        f"/api/disc/{folder.name}/hints",
        json={"various_artists": True},
    )
    body = resp.json()
    assert body["various_artists"] is True
    assert body["artist"] == "FirstArtist"
    assert body["album"] == "FirstAlbum"


# ---------------- (e) operator_hints surfaces on DiscCard ----------------


def test_operator_hints_surfaces_on_kanban_card(
    client: TestClient, music_root: Path,
) -> None:
    folder = _seed_disc(music_root, "disc-e")
    client.patch(
        f"/api/disc/{folder.name}/hints",
        json={"various_artists": True, "burned_cd": True},
    )

    body = client.get("/api/kanban").json()
    card = next(
        c for c in body["buckets"]["review"] if c["folder"] == folder.name
    )
    assert card["operator_hints"]["various_artists"] is True
    assert card["operator_hints"]["burned_cd"] is True


# ---------------- (f) per-track merge semantics --------------------------


def test_patch_tracks_initial_write_and_per_track_merge(
    client: TestClient, music_root: Path,
) -> None:
    folder = _seed_disc(music_root, "disc-f")
    # Initial PATCH: tracks 1 and 3 set.
    resp = client.patch(
        f"/api/disc/{folder.name}/hints",
        json={"tracks": [
            {"track_number": 1, "artist": "A1", "title": "T1"},
            {"track_number": 3, "title": "T3"},
        ]},
    )
    assert resp.status_code == 200
    tracks = resp.json()["tracks"]
    assert len(tracks) == 2
    by_num = {t["track_number"]: t for t in tracks}
    assert by_num[1]["artist"] == "A1"
    assert by_num[1]["title"] == "T1"
    assert by_num[3]["title"] == "T3"
    assert by_num[3].get("artist") is None

    # Second PATCH: update track 1's title, add track 2, leave track 3 alone.
    resp2 = client.patch(
        f"/api/disc/{folder.name}/hints",
        json={"tracks": [
            {"track_number": 1, "title": "T1-updated"},
            {"track_number": 2, "artist": "A2", "title": "T2"},
        ]},
    )
    tracks2 = resp2.json()["tracks"]
    by_num2 = {t["track_number"]: t for t in tracks2}
    # Track 1: title updated, artist preserved from prior PATCH.
    assert by_num2[1]["title"] == "T1-updated"
    assert by_num2[1]["artist"] == "A1"
    # Track 2: newly appended.
    assert by_num2[2]["artist"] == "A2"
    assert by_num2[2]["title"] == "T2"
    # Track 3: preserved unchanged (not in patch body).
    assert by_num2[3]["title"] == "T3"
    assert set(by_num2.keys()) == {1, 2, 3}


# ---------------- (g) validation: track_number + extra=forbid ------------


def test_patch_rejects_non_positive_track_number(
    client: TestClient, music_root: Path,
) -> None:
    folder = _seed_disc(music_root, "disc-g1")
    resp = client.patch(
        f"/api/disc/{folder.name}/hints",
        json={"tracks": [{"track_number": 0, "title": "x"}]},
    )
    assert resp.status_code in (400, 422)


def test_patch_rejects_unknown_track_field(
    client: TestClient, music_root: Path,
) -> None:
    folder = _seed_disc(music_root, "disc-g2")
    resp = client.patch(
        f"/api/disc/{folder.name}/hints",
        json={"tracks": [
            {"track_number": 1, "title": "x", "bogus": "field"},
        ]},
    )
    assert resp.status_code in (400, 422)


def test_patch_rejects_unknown_top_level_field(
    client: TestClient, music_root: Path,
) -> None:
    folder = _seed_disc(music_root, "disc-g3")
    resp = client.patch(
        f"/api/disc/{folder.name}/hints",
        json={"made_up_field": True},
    )
    assert resp.status_code in (400, 422)
