"""Failing tests for the beets-candidates section in the expanded card.

Per Bucket D / impl-candidates-section-ui. The expanded body's
candidates section renders only when the /candidates endpoint returns
a non-empty list (the JS source contains the guard); each row carries
a .score-chip + .candidate-meta + .apply-btn; the top row has class
.candidate--top (amber-tinted via cda.css); Apply buttons hold a
data-mbid attribute and POST to /api/disc/<folder>/accept-top-candidate
with {mbid: data-mbid} as the JSON body.

Impl lands in Wave 2 (impl-candidates-section-ui).
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


def _seed_review_card(parent: Path, name: str) -> Path:
    folder = parent / name
    _write_flac(folder / "01.flac")
    folder.mkdir(parents=True, exist_ok=True)
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
        "drive": {"device": "/dev/sr0", "model": "X", "serial": None,
                  "read_offset": None},
        "audio": {
            "format": "flac", "sample_rate_hz": 44100, "bits_per_sample": 16,
            "channels": 2, "track_count": 10,
            "total_duration_seconds": 2400,
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


# ============== (a) section renders only when endpoint non-empty =========


def test_candidates_section_js_conditional_render_guard(
    client: TestClient, music_root: Path,
) -> None:
    """Asserted via JS source content: the kanban page's JS fetches
    /api/disc/<folder>/candidates on expand and only renders the section
    when the candidates array is non-empty."""
    _seed_review_card(music_root / "review", "cs-guard")
    html = client.get("/").text
    assert "/candidates" in html, "candidates endpoint URL not referenced"
    # Conditional render guard discoverable in JS source.
    lower = html.lower()
    assert "candidates" in lower
    assert ("candidates.length" in html
            or "candidates && candidates.length" in html
            or "if (candidates" in html
            or "data.candidates" in html)


# ============== (b) up to 5 rows w/ score-chip · meta · apply ============


def test_candidates_section_row_anatomy_classes_present(
    client: TestClient, music_root: Path,
) -> None:
    _seed_review_card(music_root / "review", "cs-rows")
    html = client.get("/").text
    # The JS template strings reference the three row-anatomy class names.
    assert "score-chip" in html
    assert "candidate-meta" in html
    assert "apply-btn" in html


# ============== (c) top candidate row gets .candidate--top ==============


def test_candidates_section_top_row_marker_class(
    client: TestClient, music_root: Path,
) -> None:
    _seed_review_card(music_root / "review", "cs-top")
    html = client.get("/").text
    assert "candidate--top" in html


# ============== (d) Apply button posts to accept-top-candidate w/ mbid ==


def test_apply_button_posts_to_accept_top_candidate_with_mbid_body(
    client: TestClient, music_root: Path,
) -> None:
    _seed_review_card(music_root / "review", "cs-apply")
    html = client.get("/").text
    # Endpoint reference present.
    assert "accept-top-candidate" in html
    # data-mbid attribute is the wire from row → button click.
    assert "data-mbid" in html
    # The JS sends the picked MBID as a JSON body field.
    assert "mbid" in html
    # POST verb is observable in the fetch call.
    assert "POST" in html or "method:\"POST\"" in html or "method: 'POST'" in html
