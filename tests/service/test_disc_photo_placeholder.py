"""Failing tests for the CSS-drawn disc-photo placeholder (sprint-7).

Per build-prompt: cards without a real pi-camera photo render a
`<div class="thumb thumb--placeholder">` instead of `<img>`. The
`.thumb--placeholder` rule in `cda.css` uses a conic-gradient glow.
The right-drawer drive-mode body uses a larger variant of the same
placeholder when no card is selected.

Impl lands in Wave 2 (impl-disc-photo-placeholder).
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
        "drive": {"device": "/dev/sr0", "model": "X", "serial": None,
                  "read_offset": None},
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
        if isinstance(v, dict) and isinstance(payload.get(k), dict):
            payload[k] = {**payload[k], **v}
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


# ============== (a) cards without a real photo render placeholder div ===


def test_card_without_disc_photo_renders_placeholder_div(
    client: TestClient, music_root: Path,
) -> None:
    _seed(music_root / "review", "thumb-none")
    html = client.get("/rip").text
    assert 'class="thumb thumb--placeholder"' in html or \
           'thumb thumb--placeholder' in html
    # And the placeholder must NOT be wrapped in an <img> tag.
    assert '<img class="thumb thumb--placeholder"' not in html


# ============== (b) cda.css styles .thumb--placeholder w/ conic-gradient =


def test_thumb_placeholder_uses_conic_gradient_in_css() -> None:
    css_path = (
        Path(__file__).resolve().parents[2]
        / "archivist" / "service" / "static" / "css" / "cda.css"
    )
    assert css_path.is_file(), (
        f"expected {css_path} to exist (lane-1 vendors cda.css in Bucket A)"
    )
    css = css_path.read_text(encoding="utf-8")
    assert ".thumb--placeholder" in css
    # conic-gradient is the build-prompt-mandated background.
    block_start = css.find(".thumb--placeholder")
    block_window = css[block_start:block_start + 600]
    assert "conic-gradient" in block_window


# ============== (c) right-drawer drive-mode uses larger variant =========


def test_right_drawer_drive_mode_uses_placeholder_variant(
    client: TestClient,
) -> None:
    html = client.get("/rip").text
    # The drive-mode drawer body shows the placeholder so the operator
    # sees the disc-photo slot even when no card is selected. A larger
    # size variant lives on cda.css; the markup tags both the size-
    # variant modifier AND the base class for fall-through styling.
    assert "thumb--placeholder" in html
    # The drive-mode body marker carries the placeholder too.
    assert 'data-drawer-template="drive-status"' in html
    # A larger-size variant marker is observable in the markup.
    assert ("thumb--placeholder--lg" in html
            or "thumb--lg" in html
            or "thumb--placeholder thumb--placeholder--lg" in html
            or "thumb thumb--placeholder thumb--placeholder--lg" in html)
