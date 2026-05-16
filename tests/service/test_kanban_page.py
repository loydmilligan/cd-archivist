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


# ============== test-operator-hints-card-ui (Bucket B+) ==================
#
# Additions for the expanded card's hint controls + collapsed-card chip.
# Per Contract Changes: operator_hints with toggles + album-level
# artist/album + per-track tracks[]. Per-track table is present in the
# DOM only when both toggles are ON; "absent — not just hidden".


def _patch_hints(client: TestClient, folder_name: str, body: dict) -> None:
    resp = client.patch(f"/api/disc/{folder_name}/hints", json=body)
    assert resp.status_code == 200, resp.text


# ---------------- (h) two checkbox controls ------------------------------


def test_expanded_card_renders_hint_checkboxes(
    client: TestClient, music_root: Path,
) -> None:
    folder = music_root / "review" / "2026-05-16_1200_disc-h1"
    _write_flac(folder / "01.flac")
    _write_source(folder)

    html = client.get("/").text
    # Each checkbox carries name= matching the PATCH body shape and an
    # accessible label.
    assert 'name="various_artists"' in html
    assert 'name="burned_cd"' in html
    assert 'type="checkbox"' in html
    assert 'aria-label="Various Artists"' in html
    assert 'aria-label="Burned CD"' in html


# ---------------- (i) text inputs with data-disabled-when ----------------


def test_expanded_card_renders_artist_album_text_inputs(
    client: TestClient, music_root: Path,
) -> None:
    folder = music_root / "review" / "2026-05-16_1200_disc-i1"
    _write_flac(folder / "01.flac")
    _write_source(folder)

    html = client.get("/").text
    assert 'name="artist"' in html
    assert 'name="album"' in html
    # Front-end disables these when either toggle is checked.
    assert 'data-disabled-when="burned_cd OR various_artists"' in html


# ---------------- (j) save-hints button targets PATCH endpoint -----------


def test_save_hints_button_targets_patch_endpoint(
    client: TestClient, music_root: Path,
) -> None:
    folder = music_root / "review" / "2026-05-16_1200_disc-j1"
    _write_flac(folder / "01.flac")
    _write_source(folder)

    html = client.get("/").text
    # Form / button references the PATCH route. We don't pin verb-in-HTML
    # specifics (forms POST in raw HTML; JS handler issues PATCH) — we
    # require the endpoint URL to be present.
    assert f"/api/disc/{folder.name}/hints" in html
    assert "Save hints" in html


# ---------------- (k) collapsed-card chip rendering ----------------------


def test_collapsed_card_chip_various_artists_only(
    client: TestClient, music_root: Path,
) -> None:
    folder = music_root / "review" / "2026-05-16_1200_disc-k1"
    _write_flac(folder / "01.flac")
    _write_source(folder)
    _patch_hints(client, folder.name, {"various_artists": True})

    html = client.get("/").text
    # Chip on the collapsed card shows the VA label.
    assert "VA" in html


def test_collapsed_card_chip_burned_only(
    client: TestClient, music_root: Path,
) -> None:
    folder = music_root / "review" / "2026-05-16_1200_disc-k2"
    _write_flac(folder / "01.flac")
    _write_source(folder)
    _patch_hints(client, folder.name, {"burned_cd": True})

    html = client.get("/").text
    assert "burned" in html.lower()


def test_collapsed_card_chip_album_text_when_no_toggles(
    client: TestClient, music_root: Path,
) -> None:
    folder = music_root / "review" / "2026-05-16_1200_disc-k3"
    _write_flac(folder / "01.flac")
    _write_source(folder)
    _patch_hints(client, folder.name, {"artist": "Foo", "album": "Bar"})

    html = client.get("/").text
    # Chip shows the artist/album text when no toggle is set.
    assert "Foo" in html
    assert "Bar" in html


def test_collapsed_card_no_chip_when_hints_empty(
    client: TestClient, music_root: Path,
) -> None:
    folder = music_root / "review" / "2026-05-16_1200_disc-k4"
    _write_flac(folder / "01.flac")
    _write_source(folder)
    # No PATCH — hints stay defaulted.

    html = client.get("/").text
    # No chip text — assert the marker class is absent for this card.
    # (We don't pin the marker class name; we pin behavior: none of the
    # toggle labels surface for a hint-less card.)
    # The folder name appears once (in the card title) but neither
    # "VA" nor "burned" should surface as a chip.
    # Coarse: count chip-marker tokens — when hints are empty no chip
    # element renders. The page-level markup may still mention these
    # tokens elsewhere; this assertion is scoped to the card.
    assert 'data-chip="va"' not in html
    assert 'data-chip="burned"' not in html


# ---------------- (l) per-track rows only when both toggles ON -----------


def test_per_track_table_absent_when_only_va(
    client: TestClient, music_root: Path,
) -> None:
    folder = music_root / "review" / "2026-05-16_1200_disc-l1"
    _write_flac(folder / "01.flac")
    _write_source(folder)
    _patch_hints(client, folder.name, {"various_artists": True})

    html = client.get("/").text
    # Per-track inputs are absent from the DOM when only one toggle is on.
    assert 'name="track-1-artist"' not in html
    assert 'name="track-1-title"' not in html


def test_per_track_table_absent_when_only_burned(
    client: TestClient, music_root: Path,
) -> None:
    folder = music_root / "review" / "2026-05-16_1200_disc-l2"
    _write_flac(folder / "01.flac")
    _write_source(folder)
    _patch_hints(client, folder.name, {"burned_cd": True})

    html = client.get("/").text
    assert 'name="track-1-artist"' not in html


def test_per_track_table_present_when_both_on(
    client: TestClient, music_root: Path,
) -> None:
    folder = music_root / "review" / "2026-05-16_1200_disc-l3"
    _write_flac(folder / "01.flac")
    _write_flac(folder / "02.flac")
    _write_source(folder, track_count=2)
    _patch_hints(client, folder.name, {
        "various_artists": True, "burned_cd": True,
    })

    html = client.get("/").text
    # One row per track, with artist + title inputs named per spec.
    assert 'name="track-1-artist"' in html
    assert 'name="track-1-title"' in html
    assert 'name="track-2-artist"' in html
    assert 'name="track-2-title"' in html
    # Container also carries the show-when marker for the JS handler.
    assert 'data-show-when="various_artists AND burned_cd"' in html


# ---------------- (m) TOC-vs-audio-count fallback for row count ----------


def test_per_track_table_row_count_from_toc_when_present(
    client: TestClient, music_root: Path,
) -> None:
    """When source.json carries the TOC track count (audio.track_count > 0),
    the row count comes from that source — preferred over the on-disk
    audio file count."""
    folder = music_root / "review" / "2026-05-16_1200_disc-m1"
    # Seed with track_count=4 in source.json but only 1 flac on disk.
    _write_flac(folder / "01.flac")
    _write_source(folder, track_count=4)
    _patch_hints(client, folder.name, {
        "various_artists": True, "burned_cd": True,
    })

    html = client.get("/").text
    assert 'name="track-4-artist"' in html
    # Fifth track must NOT render — TOC count is 4.
    assert 'name="track-5-artist"' not in html


def test_per_track_table_row_count_falls_back_to_audio_file_count(
    client: TestClient, music_root: Path,
) -> None:
    """When the TOC is absent (audio.track_count == 0 — pre-rip or legacy),
    the row count comes from the count of flacs in the folder."""
    folder = music_root / "review" / "2026-05-16_1200_disc-m2"
    _write_flac(folder / "01.flac")
    _write_flac(folder / "02.flac")
    _write_flac(folder / "03.flac")
    # TOC absent: track_count=0.
    _write_source(folder, track_count=0)
    _patch_hints(client, folder.name, {
        "various_artists": True, "burned_cd": True,
    })

    html = client.get("/").text
    assert 'name="track-1-artist"' in html
    assert 'name="track-3-artist"' in html
    assert 'name="track-4-artist"' not in html


# ---------------- (n) collapsed-card badge — mix-CD count ----------------


def test_collapsed_card_chip_mix_cd_count_when_both_on(
    client: TestClient, music_root: Path,
) -> None:
    folder = music_root / "review" / "2026-05-16_1200_disc-n1"
    _write_flac(folder / "01.flac")
    _write_source(folder, track_count=8)
    _patch_hints(client, folder.name, {
        "various_artists": True, "burned_cd": True,
    })

    html = client.get("/").text
    # Per spec: "Mix CD ({N} tracks)" — N sourced from TOC (track_count).
    assert "Mix CD (8 tracks)" in html
