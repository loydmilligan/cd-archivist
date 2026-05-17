"""Failing tests for the expanded-card body sections (sprint-6.5 B).

The expanded body holds three labeled <section> elements:

  data-section="hints"            — operator-hints UI (always present)
  data-section="manual-steps"     — review-explainer copy-paste shell
                                    (Review-bucket only)
  data-section="damaged-actions"  — process-partial / redo / rerip
                                    buttons (only when card is damaged)

Impl lands in Wave 2 (impl-expanded-card-sections).
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


# ============== (a) three labeled section elements =======================


def test_expanded_body_renders_hints_section(
    client: TestClient, music_root: Path,
) -> None:
    _seed(music_root / "review", "ec-hints")
    html = client.get("/").text
    assert 'data-section="hints"' in html


def test_expanded_body_renders_manual_steps_section_for_review_card(
    client: TestClient, music_root: Path,
) -> None:
    _seed(music_root / "review", "ec-manual")
    html = client.get("/").text
    assert 'data-section="manual-steps"' in html


def test_expanded_body_renders_damaged_actions_section_for_damaged_card(
    client: TestClient, music_root: Path,
) -> None:
    _seed(music_root / "failed", "ec-damaged", _base_source(
        "ec-damaged",
        status={
            "rip_success": False, "photo_success": True, "ready": False,
            "warnings": [], "errors": [], "partial": True,
            "failed_tracks": [3],
        },
    ))
    html = client.get("/").text
    assert 'data-section="damaged-actions"' in html


# ============== (b) hints section contains the operator-hints UI =========


def test_hints_section_contains_operator_hint_controls(
    client: TestClient, music_root: Path,
) -> None:
    _seed(music_root / "review", "ec-hint-controls")
    html = client.get("/").text
    # The two toggles + two text inputs from impl-operator-hints UI
    # live INSIDE the hints section block. We can't easily scope an
    # HTML substring without DOM parsing, so we pin presence of both
    # markers and rely on impl placement.
    assert 'data-section="hints"' in html
    assert 'name="various_artists"' in html
    assert 'name="burned_cd"' in html
    assert 'name="artist"' in html
    assert 'name="album"' in html


def test_hints_section_per_track_table_appears_when_both_toggles_on(
    client: TestClient, music_root: Path,
) -> None:
    folder = _seed(music_root / "review", "ec-mix", _base_source(
        "ec-mix",
        operator_hints={
            "various_artists": True, "burned_cd": True,
            "artist": None, "album": None, "tracks": [],
        },
    ))
    html = client.get("/").text
    assert 'data-section="hints"' in html
    # Per-track table present (DOM-absent unless both toggles on).
    assert 'name="track-1-artist"' in html
    assert folder.name in html


# ============== (c) manual-steps section absent for non-Review cards ====


def test_manual_steps_section_absent_for_library_card(
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
    # Library bucket doesn't get a manual-steps section.
    assert 'data-section="manual-steps"' not in html


def test_manual_steps_section_pulls_review_explainer_text(
    client: TestClient, music_root: Path,
) -> None:
    _seed(music_root / "review", "ec-explainer", _base_source(
        "ec-explainer",
        status={
            "rip_success": True, "photo_success": True, "ready": True,
            "warnings": [], "errors": [], "partial": False,
            "failed_tracks": [],
            "beets_review_reason": "beets returned no candidates",
        },
    ))
    html = client.get("/").text
    # Explainer text surfaces in the manual-steps section.
    assert "no candidates" in html.lower()


# ============== (d) damaged-actions section conditional ================


def test_damaged_actions_section_absent_for_healthy_card(
    client: TestClient, music_root: Path,
) -> None:
    _seed(music_root / "review", "ec-healthy")
    html = client.get("/").text
    assert 'data-section="damaged-actions"' not in html


def test_damaged_actions_section_present_for_failed_card(
    client: TestClient, music_root: Path,
) -> None:
    _seed(music_root / "failed", "ec-failed", _base_source(
        "ec-failed",
        status={
            "rip_success": False, "photo_success": True, "ready": False,
            "warnings": [], "errors": [], "partial": False,
            "failed_tracks": [],
        },
    ))
    html = client.get("/").text
    assert 'data-section="damaged-actions"' in html
