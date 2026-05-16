"""Failing tests for GET /api/kanban (sprint-6 Bucket B).

Covers test-kanban-api. Per D-card-data-source the endpoint calls
`build_kanban_state(music_root, loop_state)` and returns the bucketed
DiscCards as JSON. Per D-library-retention-v1 the library bucket is
capped at `KANBAN_LIBRARY_RETENTION` (default 20, newest first).

Impl lands in Wave 2 (impl-kanban-api).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from archivist.service.app import LoopState, create_app


def _write_flac(path: Path, n_bytes: int = 1024) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fLaC" + b"\x00" * n_bytes)


def _write_source(folder: Path, *, track_count: int = 2) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "ripper": {"name": "cd-archivist", "version": "0.1.0", "host": "cm4"},
        "disc": {
            "folder_name": folder.name,
            "disc_counter": 1,
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
            "channels": 2, "track_count": track_count,
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
            "rip_success": True, "photo_success": False, "ready": True,
            "warnings": [], "errors": [],
        },
    }
    (folder / "source.json").write_text(json.dumps(payload))


@pytest.fixture
def music_root(tmp_path: Path) -> Path:
    root = tmp_path / "music"
    for sub in ("inbox", "review", "library", "archive", "failed"):
        (root / sub).mkdir(parents=True)
    return root


@pytest.fixture
def loop_state() -> LoopState:
    return LoopState()


@pytest.fixture
def client(
    music_root: Path, loop_state: LoopState, tmp_path: Path,
) -> TestClient:
    log_path = tmp_path / "archivist.log"
    log_path.write_text("")
    # The kanban endpoint needs the full music_root to walk all five
    # subdirs. New create_app kwarg `music_root` is part of the contract.
    return TestClient(create_app(
        loop_state, log_path,
        discs_root=music_root / "inbox",
        review_root=music_root / "review",
        library_root=music_root / "library",
        music_root=music_root,
    ))


# ---------------- response shape -----------------------------------------


def test_kanban_response_shape(client: TestClient) -> None:
    resp = client.get("/api/kanban")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"buckets"}
    assert set(body["buckets"].keys()) == {"capture", "beets_id", "review", "library"}
    for bucket in body["buckets"].values():
        assert isinstance(bucket, list)


def test_kanban_empty_when_no_discs(client: TestClient) -> None:
    body = client.get("/api/kanban").json()
    assert body["buckets"]["capture"] == []
    assert body["buckets"]["beets_id"] == []
    assert body["buckets"]["review"] == []
    assert body["buckets"]["library"] == []


def test_kanban_review_folder_lands_in_review_bucket(
    client: TestClient, music_root: Path,
) -> None:
    folder = music_root / "review" / "2026-05-16_1200_disc-000001"
    _write_flac(folder / "01.flac")
    _write_source(folder)

    body = client.get("/api/kanban").json()
    assert len(body["buckets"]["review"]) == 1
    card = body["buckets"]["review"][0]
    assert card["folder"] == folder.name
    assert card["bucket"] == "review"


def test_kanban_active_rip_lands_in_capture_with_progress(
    client: TestClient, loop_state: LoopState,
) -> None:
    loop_state.state = "RIP"
    loop_state.disc_id = "disc-000050"
    loop_state.rip_progress = "track 5/12 (42%)"

    body = client.get("/api/kanban").json()
    capture = body["buckets"]["capture"]
    assert len(capture) == 1
    card = capture[0]
    assert card["bucket"] == "capture"
    assert card["disc_id"] == "disc-000050"
    assert "progress" in card and card["progress"] is not None
    assert card["progress"]["percent"] == 42
    assert "current_stage" in card["progress"]


# ---------------- library retention cap ----------------------------------


def test_library_bucket_capped_at_default_retention(
    client: TestClient, music_root: Path,
) -> None:
    """Default KANBAN_LIBRARY_RETENTION == 20. Seed 25 library folders;
    only 20 should surface."""
    for i in range(25):
        folder = music_root / "library" / f"Artist{i:02d}" / f"Album{i:02d}"
        _write_flac(folder / "01.flac")
        _write_source(folder)

    body = client.get("/api/kanban").json()
    assert len(body["buckets"]["library"]) == 20


def test_library_bucket_retention_env_override(
    music_root: Path, loop_state: LoopState, tmp_path: Path,
) -> None:
    for i in range(10):
        folder = music_root / "library" / f"Artist{i:02d}" / f"Album{i:02d}"
        _write_flac(folder / "01.flac")
        _write_source(folder)

    log_path = tmp_path / "archivist.log"
    log_path.write_text("")
    with patch.dict(os.environ, {"KANBAN_LIBRARY_RETENTION": "5"}):
        c = TestClient(create_app(
            loop_state, log_path,
            discs_root=music_root / "inbox",
            review_root=music_root / "review",
            library_root=music_root / "library",
            music_root=music_root,
        ))
        body = c.get("/api/kanban").json()
        assert len(body["buckets"]["library"]) == 5


def test_library_bucket_newest_first(
    client: TestClient, music_root: Path,
) -> None:
    """Library cards are ordered newest mtime first."""
    import time
    for i in range(3):
        folder = music_root / "library" / f"Artist{i}" / f"Album{i}"
        _write_flac(folder / "01.flac")
        _write_source(folder)
        # Stamp each folder's mtime distinctly.
        ts = 1_700_000_000 + i * 1000
        os.utime(folder, (ts, ts))

    body = client.get("/api/kanban").json()
    names = [c["folder"] for c in body["buckets"]["library"]]
    assert names == ["Album2", "Album1", "Album0"]
