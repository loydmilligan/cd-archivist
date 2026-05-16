"""Failing tests for the kanban HTML page at GET / (sprint-6 Bucket B).

Covers test-kanban-page-render. Per D-live-update-transport-v1 the
page polls `/api/kanban` every 2000ms; the interval lives in a
`<meta name="kanban-poll-ms">` tag so it can be asserted and tuned.

Per D-kanban-buckets-v1 four columns render: Capture, Beets ID,
Review, In Library. Mash Co. tokens (`--ink`, `--ok`, `--warn`,
`--info`) are applied via the existing `static/tokens.css`.

Impl lands in Wave 2 (impl-kanban-page). Additions for
test-operator-hints-card-ui (Bucket B+) land in the same file once
test-operator-hints-api is in.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

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
            "folder_name": folder.name, "disc_counter": 1,
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
    return TestClient(create_app(
        loop_state, log_path,
        discs_root=music_root / "inbox",
        review_root=music_root / "review",
        library_root=music_root / "library",
        music_root=music_root,
    ))


# ---------------- column headers -----------------------------------------


def test_page_renders_four_column_headers(client: TestClient) -> None:
    html = client.get("/").text
    assert "Capture" in html
    assert "Beets ID" in html
    assert "Review" in html
    assert "In Library" in html


# ---------------- collapsed-card markup ----------------------------------


def test_card_renders_collapsed_state_markup(
    client: TestClient, music_root: Path,
) -> None:
    folder = music_root / "review" / "2026-05-16_1200_disc-000001"
    _write_flac(folder / "01.flac")
    _write_source(folder)

    html = client.get("/").text
    # Collapsed-state markup: status line + progress bar + per-track bar.
    assert "track-bar" in html
    assert folder.name in html


def test_card_has_aria_expanded_toggle(
    client: TestClient, music_root: Path,
) -> None:
    folder = music_root / "review" / "2026-05-16_1200_disc-000002"
    _write_flac(folder / "01.flac")
    _write_source(folder)

    html = client.get("/").text
    # Each card carries an aria-expanded attribute (initially "false").
    assert 'aria-expanded="false"' in html


# ---------------- poll-interval meta tag ---------------------------------


def test_page_carries_poll_interval_meta_tag(client: TestClient) -> None:
    html = client.get("/").text
    m = re.search(
        r'<meta\s+name=["\']kanban-poll-ms["\']\s+content=["\'](\d+)["\']',
        html,
    )
    assert m is not None, "missing <meta name='kanban-poll-ms'> tag"
    # Default per D-live-update-transport-v1: 2000ms.
    assert int(m.group(1)) == 2000


# ---------------- Mash Co. tokens ----------------------------------------


def test_page_applies_mash_tokens(client: TestClient) -> None:
    html = client.get("/").text
    # Tokens live in /static/tokens.css — page must link/load it.
    assert "/static/tokens.css" in html
    # Token names referenced in the page CSS (validated by string search;
    # the actual color values come from tokens.css).
    for tok in ("--ink", "--ok", "--warn", "--info"):
        assert tok in html, f"expected Mash token {tok!r} in page CSS"


def test_page_dark_first_theme(client: TestClient) -> None:
    """Mash Co. voice/visual contract: dark-first, data-theme="dark"."""
    html = client.get("/").text
    assert 'data-theme="dark"' in html


# ---------------- active rip surfaces ------------------------------------


def test_active_rip_renders_capture_card_with_progress(
    client: TestClient, loop_state: LoopState,
) -> None:
    loop_state.state = "RIP"
    loop_state.disc_id = "disc-000077"
    loop_state.rip_progress = "track 7/10 (70%)"

    html = client.get("/").text
    assert "disc-000077" in html
    # Progress bar / percentage surfaced in collapsed view.
    assert "70" in html
