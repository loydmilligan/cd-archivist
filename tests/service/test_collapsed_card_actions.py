"""Failing tests for high-leverage collapsed-card actions (sprint-6.5 B).

Two button affordances surface directly on the collapsed card so the
operator can drive the manual-rescue flow without expanding:

  - Capture-bucket damaged cards: "Process partial" +
    "Redo" buttons targeting the sprint-6 endpoints.
  - Review-bucket cards with a high-confidence candidate
    (top_candidate_score >= 0.85): "Accept top match" button
    targeting the new /api/disc/<folder>/accept-top-candidate
    endpoint.

Non-damaged Capture cards and low-confidence Review cards render no
collapsed-card buttons (no false-affordances).

Impl lands in Wave 2 (impl-collapsed-card-actions +
D-accept-top-candidate-threshold).
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


def _base_source(name: str, **overrides) -> dict:
    payload = {
        "schema_version": 1,
        "ripper": {"name": "cd-archivist", "version": "0.1.0", "host": "cm4"},
        "disc": {
            "folder_name": name, "disc_counter": 1,
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


# ============== (a) Damaged Capture card: process-partial + redo =========


def test_damaged_capture_card_renders_process_partial_button(
    client: TestClient, music_root: Path,
) -> None:
    folder = _seed(music_root / "failed", "cca-1", _base_source(
        "cca-1",
        status={
            "rip_success": False, "photo_success": True, "ready": False,
            "warnings": [], "errors": [], "partial": True,
            "failed_tracks": [3],
        },
    ))
    html = client.get("/rip").text
    assert "Process partial" in html
    assert f"/api/disc/{folder.name}/process-partial" in html


def test_damaged_capture_card_renders_redo_button(
    client: TestClient, music_root: Path,
) -> None:
    folder = _seed(music_root / "failed", "cca-2", _base_source(
        "cca-2",
        status={
            "rip_success": False, "photo_success": True, "ready": False,
            "warnings": [], "errors": [], "partial": True,
            "failed_tracks": [3],
        },
    ))
    html = client.get("/rip").text
    assert "Redo" in html
    assert f"/api/disc/{folder.name}/redo?confirm=true" in html


# ============== (b) High-confidence Review card: accept-top-match =======


def test_high_confidence_review_renders_accept_top_match_button(
    client: TestClient, music_root: Path,
) -> None:
    """top_candidate_score >= 0.85 surfaces the one-click accept
    button. The score lives on the DiscCard, populated by the kanban
    builder from a cache file or the source.json (impl decides) — for
    the test we seed it via a sidecar `top_candidate.json` the impl
    can choose to read."""
    folder = _seed(music_root / "review", "cca-hi")
    (folder / "top_candidate.json").write_text(json.dumps({
        "mbid": "abc-mbid",
        "score": 0.91,
        "artist": "Foo",
        "album": "Bar",
    }))
    html = client.get("/rip").text
    assert "Accept top match" in html
    assert f"/api/disc/{folder.name}/accept-top-candidate" in html


def test_low_confidence_review_does_not_render_accept_button(
    client: TestClient, music_root: Path,
) -> None:
    folder = _seed(music_root / "review", "cca-lo")
    (folder / "top_candidate.json").write_text(json.dumps({
        "mbid": "abc-mbid",
        "score": 0.42,
        "artist": "Foo",
        "album": "Bar",
    }))
    html = client.get("/rip").text
    assert "Accept top match" not in html
    assert f"/api/disc/{folder.name}/accept-top-candidate" not in html


def test_review_card_with_no_candidate_does_not_render_accept_button(
    client: TestClient, music_root: Path,
) -> None:
    _seed(music_root / "review", "cca-no-cand")
    html = client.get("/rip").text
    assert "Accept top match" not in html


# ============== (c) No false-affordances on healthy cards ===============


def test_healthy_capture_card_renders_no_action_buttons(
    client: TestClient, music_root: Path,
) -> None:
    _seed(music_root / "inbox", "cca-ok")
    html = client.get("/rip").text
    # Healthy Capture card surfaces no collapsed-card action buttons.
    assert "Process partial" not in html
    assert "Redo" not in html
    # Sanity: the folder is present in the rendered page (card
    # actually rendered, just without action buttons).
    assert "cca-ok" in html


def test_library_card_renders_no_action_buttons(
    client: TestClient, music_root: Path,
) -> None:
    _seed(music_root / "library" / "Foo", "Bar", _base_source(
        "Bar",
        detected_metadata={
            "album_artist": "Foo", "album": "Bar", "year": None,
            "label": None, "catalog_number": None, "tracks": [],
        },
    ))
    html = client.get("/rip").text
    assert "Process partial" not in html
    assert "Redo" not in html
    assert "Accept top match" not in html
