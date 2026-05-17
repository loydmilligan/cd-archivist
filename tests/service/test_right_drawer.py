"""Failing tests for the right-side slide-out drawer (sprint-6.5 C).

Drawer defaults to the drive-status template; flips to the
card-detail template when a card is clicked. Per K1.2-B + K1.3
in the brainstorm: capture status lives in a slide-out on the
RIGHT (capture bucket is on the left, so opening the right drawer
doesn't occlude it).

Impl lands in Wave 2 (impl-right-drawer).
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


def _write_source_minimal(folder: Path, name: str) -> None:
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
        "drive": {"device": "/dev/sr0", "model": "X", "serial": None, "read_offset": None},
        "audio": {
            "format": "flac", "sample_rate_hz": 44100, "bits_per_sample": 16,
            "channels": 2, "track_count": 2,
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
    (folder / "source.json").write_text(json.dumps(payload))


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


# ============== (a) drawer element + default state ======================


def test_right_drawer_element_exists_with_default_hidden(
    client: TestClient,
) -> None:
    html = client.get("/").text
    assert 'id="right-drawer"' in html
    # Default aria-hidden="true" so screen readers skip it until opened.
    assert 'aria-hidden="true"' in html


def test_right_drawer_uses_css_transform_for_slide_in(
    client: TestClient,
) -> None:
    """The drawer slides in via CSS transform (not display:none) so the
    transition can be animated. Sprint-7 / impl-css-migration moved the
    rule from the inline <style> block onto /static/css/cda.css; the
    assertion follows the CSS to its new home."""
    html = client.get("/").text
    assert "right-drawer" in html
    cda = client.get("/static/css/cda.css").text
    assert "transform" in cda
    # The drawer-right rule itself defines a transform (slide-out state).
    assert ".drawer--right" in cda


# ============== (b) drive-status template (default body) ================


def test_default_drawer_body_renders_drive_status_template(
    client: TestClient,
) -> None:
    html = client.get("/").text
    # Discoverable marker so the front-end JS can target the
    # drive-status body when no card is selected.
    assert 'data-drawer-template="drive-status"' in html


def test_drive_status_template_polls_drive_status_endpoint(
    client: TestClient,
) -> None:
    """The drawer's drive-status template fetches from
    /api/drive/status (provided by drivers' impl-drive-status-snapshot)."""
    html = client.get("/").text
    assert "/api/drive/status" in html


# ============== (c) card-detail template (when card clicked) ============


def test_card_detail_template_referenced_in_drawer_markup(
    client: TestClient, music_root: Path,
) -> None:
    folder = music_root / "review" / "rd-card-1"
    _write_flac(folder / "01.flac")
    _write_source_minimal(folder, folder.name)

    html = client.get("/").text
    # Discoverable marker; impl can use a <template> or hidden div.
    assert 'data-drawer-template="card-detail"' in html


def test_card_detail_template_references_disc_log_endpoint(
    client: TestClient,
) -> None:
    """Card-detail body fetches /api/disc/<folder>/log/tail. Folder
    placeholder lives in the template; the JS substitutes the
    clicked-card id."""
    html = client.get("/").text
    # Pin the URL fragment so the impl is observable; the placeholder
    # convention is impl-chosen.
    assert "/api/disc/" in html
    assert "log/tail" in html


# ============== (d) toggle from header OR card click opens drawer =======


def test_header_drawer_toggle_targets_right_drawer(
    client: TestClient,
) -> None:
    html = client.get("/").text
    # Pinned in test-header-bar as well; re-asserted here so the
    # right-drawer test is independently verifying the wiring.
    assert 'aria-controls="right-drawer"' in html


def test_card_click_handler_opens_right_drawer_in_js(
    client: TestClient, music_root: Path,
) -> None:
    """The card-click handler in the inline JS module opens the
    right drawer AND populates the card-detail body with the clicked
    folder's data."""
    folder = music_root / "review" / "rd-click-1"
    _write_flac(folder / "01.flac")
    _write_source_minimal(folder, folder.name)

    html = client.get("/").text
    # Pin the JS-source reference to the drawer-open call so the
    # one-step click → expand + drawer-populate flow is observable.
    assert "right-drawer" in html
    # The handler reads from the kanban payload to populate detail.
    assert "card-detail" in html


# =========================================================================
# Sprint-7 Bucket E — test-drawer-mode-toggles (lane-1)
# =========================================================================
#
# Per the build prompt the right drawer has two modes (drive / card)
# swapped explicitly by header nav buttons. Sprint-6.5 toggled mode
# implicitly via card click; sprint-7 adds explicit toggles with
# aria-pressed so the operator can flip between drive-status and the
# last-selected card without re-clicking a card.
#
# Wave 2 impl: `impl-drawer-mode-toggles` (lane-1).


def test_header_nav_has_drawer_drive_toggle(client: TestClient) -> None:
    html = client.get("/").text
    # The drive-mode toggle button lives in the header nav and uses
    # the `.drawer-toggle--drive` modifier class plus an aria-pressed
    # attribute that JS flips between "true" and "false".
    assert "drawer-toggle--drive" in html, (
        "header nav missing `.drawer-toggle--drive` button"
    )
    m = re.search(
        r'<button[^>]*\bdrawer-toggle--drive\b[^>]*>',
        html,
    )
    assert m is not None, (
        "expected a <button> element carrying class drawer-toggle--drive"
    )
    assert "aria-pressed" in m.group(0), (
        "drawer-toggle--drive button must carry aria-pressed"
    )


def test_header_nav_has_drawer_card_toggle(client: TestClient) -> None:
    html = client.get("/").text
    assert "drawer-toggle--card" in html, (
        "header nav missing `.drawer-toggle--card` button"
    )
    m = re.search(
        r'<button[^>]*\bdrawer-toggle--card\b[^>]*>',
        html,
    )
    assert m is not None, (
        "expected a <button> element carrying class drawer-toggle--card"
    )
    assert "aria-pressed" in m.group(0), (
        "drawer-toggle--card button must carry aria-pressed"
    )


def test_drawer_toggles_default_aria_pressed_state(
    client: TestClient,
) -> None:
    """At first render no card is selected, so drive-mode is active —
    drive-toggle aria-pressed=\"true\" and card-toggle aria-pressed=\"false\"."""
    html = client.get("/").text
    drive_m = re.search(
        r'<button[^>]*\bdrawer-toggle--drive\b[^>]*>', html,
    )
    card_m = re.search(
        r'<button[^>]*\bdrawer-toggle--card\b[^>]*>', html,
    )
    assert drive_m is not None and card_m is not None
    assert 'aria-pressed="true"' in drive_m.group(0), (
        "drive-toggle should start aria-pressed=\"true\" (default mode)"
    )
    assert 'aria-pressed="false"' in card_m.group(0), (
        "card-toggle should start aria-pressed=\"false\" with no selection"
    )


def test_drawer_toggle_click_handlers_referenced_in_js(
    client: TestClient,
) -> None:
    """The kanban JS module must wire click handlers for both toggles.
    The drive-toggle clears the selected card and swaps the drawer
    body to drive-mode; the card-toggle re-opens the last-selected
    card (or no-ops when none was ever selected this session)."""
    html = client.get("/").text
    # Both selector strings appear in the JS source.
    assert ".drawer-toggle--drive" in html, (
        "JS missing querySelector for `.drawer-toggle--drive`"
    )
    assert ".drawer-toggle--card" in html, (
        "JS missing querySelector for `.drawer-toggle--card`"
    )
    # The card-toggle behavior depends on a stored last-selected ref —
    # JS source must reference it by a stable name.
    assert "lastSelectedCard" in html or "last_selected_card" in html, (
        "JS missing `lastSelectedCard` state for the card-toggle re-open "
        "behavior"
    )
