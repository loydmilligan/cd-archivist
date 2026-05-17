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


# Sprint-7 polish hotfix — D-card-toggle-removed. The .drawer-toggle--card
# button had no coherent affordance (clicking a card auto-opens the drawer
# in card-mode, and there's no obvious "go back to drive mode" action
# that warrants its own button). The card-toggle was removed entirely;
# the drive-toggle below is the single explicit drawer-open affordance.


def test_drawer_card_toggle_button_removed(client: TestClient) -> None:
    """D-card-toggle-removed: the .drawer-toggle--card button must
    NOT appear in the rendered header nav."""
    html = client.get("/").text
    assert "drawer-toggle--card" not in html, (
        "the .drawer-toggle--card button was removed per "
        "D-card-toggle-removed; the click-card-to-open + click-outside"
        "-to-close flow replaces it"
    )


def test_drive_toggle_is_a_real_toggle_in_js(client: TestClient) -> None:
    """The .drawer-toggle--drive button must round-trip: clicking it
    while the drawer is open closes it; clicking it while closed
    opens it (mirrors the bottom-drawer toggle behavior). The JS
    source must reference the drawer's open/closed state so the
    handler can branch on it."""
    html = client.get("/").text
    assert ".drawer-toggle--drive" in html, (
        "JS missing querySelector for `.drawer-toggle--drive`"
    )
    # The handler reads aria-hidden on #right-drawer to decide
    # whether to open or close.
    assert "right-drawer" in html
    # Some kind of round-trip / toggle logic — accept either an
    # explicit `aria-hidden` read or a toggle-flag literal.
    assert (
        "aria-hidden" in html or "toggleDrawer" in html
    ), "drive-toggle handler must round-trip the drawer state"


# ============== Sprint-7 polish hotfix — drawer close affordances =========
#
# Two new affordances added per live-review feedback:
#   (a) explicit `.drawer-close` button at the top-right of the drawer
#       head — large enough to tap (44px target)
#   (b) click-outside-to-close handler on the kanban JS — clicks not
#       inside #right-drawer and not on .drawer-toggle--drive close
#       the drawer.


def test_right_drawer_renders_explicit_close_button(
    client: TestClient,
) -> None:
    html = client.get("/").text
    assert "drawer-close" in html, (
        "right drawer must render an explicit .drawer-close button "
        "at the top-right of its head"
    )
    m = re.search(r'<button[^>]*\bdrawer-close\b[^>]*>([^<]*)</button>', html)
    assert m is not None, "expected <button class=\"drawer-close\">…</button>"
    glyph = m.group(1).strip()
    # Allowed Unicode glyphs only per voice rules (× / ✕ / ✖ are
    # acceptable; ASCII X is also fine; no emoji).
    assert glyph and glyph not in ("​",), (
        "drawer-close button must carry a visible glyph"
    )
    # The button must target the drawer aria-state — either by id ref
    # or by a JS-readable data attribute.
    btn_open_tag = re.search(
        r'<button[^>]*\bdrawer-close\b[^>]*>', html,
    ).group(0)
    assert (
        "aria-controls" in btn_open_tag
        or "data-drawer-close" in btn_open_tag
    ), "drawer-close button must reference the drawer it closes"


def test_drawer_close_button_styled_for_tap_target(
    client: TestClient,
) -> None:
    """The .drawer-close button must be at least 44px on each side so
    it is a real touch target per WCAG 2.1 sizing guidance."""
    cda = client.get("/static/css/cda.css").text
    block = re.search(r"\.drawer-close\s*\{([^}]*)\}", cda, re.DOTALL)
    assert block is not None, "missing .drawer-close rule in cda.css"
    body = block.group(1)
    wm = re.search(r"(?:min-)?width\s*:\s*(\d+)px", body)
    hm = re.search(r"(?:min-)?height\s*:\s*(\d+)px", body)
    assert wm is not None and hm is not None, (
        ".drawer-close must set explicit width/height (or min-width/min-height)"
    )
    assert int(wm.group(1)) >= 44 and int(hm.group(1)) >= 44, (
        f".drawer-close sized {wm.group(1)}x{hm.group(1)}; both axes "
        "must be >=44px for tap-target accessibility"
    )


def test_click_outside_handler_referenced_in_js(
    client: TestClient,
) -> None:
    """The kanban JS must wire a click-outside handler that closes the
    right drawer. Asserted via source content."""
    html = client.get("/").text
    # The handler is a document-level click listener that checks
    # whether the event target is inside #right-drawer / on the
    # drive-toggle. Pin the marker string the impl uses so the
    # contract is observable.
    assert "closeRightDrawer" in html or "drawer-click-outside" in html, (
        "JS missing click-outside handler that closes the right drawer"
    )
    # The handler must reference both anchors that DON'T trigger close.
    assert "right-drawer" in html
    assert ".drawer-toggle--drive" in html or "drawer-toggle--drive" in html


def test_drive_toggle_hidden_while_drawer_open(
    client: TestClient,
) -> None:
    """When the drawer is open, the .drawer-toggle--drive button is
    visually hidden so it cannot overlap the close button — asserted
    via the CSS rule that hides it under the [aria-hidden=\"false\"]
    drawer-open state."""
    cda = client.get("/static/css/cda.css").text
    # The hide rule must reference BOTH the drawer-open state AND
    # the drawer-toggle selector in a single rule. Accept either:
    #   - a `:has(.drawer--right[aria-hidden="false"])` ancestor query
    #   - a `body[data-right-drawer-open="true"]` JS-applied marker
    #   - a sibling combinator from .drawer--right[aria-hidden=...]
    # The impl picks one; the test just requires that some selector
    # couples the two and sets display:none on the toggle.
    coupled = re.findall(
        r"([^{}]*\.drawer-toggle--drive[^{}]*)\{([^}]*)\}",
        cda, re.DOTALL,
    )
    found = False
    for selector, body in coupled:
        if "display: none" not in body and "display:none" not in body:
            continue
        if (
            "aria-hidden" in selector
            or "drawer-open" in selector
            or ":has(" in selector
        ):
            found = True
            break
    assert found, (
        "cda.css must hide .drawer-toggle--drive while the right "
        "drawer is open (e.g. a `:has(.drawer--right[aria-hidden=\"false\"])` "
        "ancestor selector or a body[data-right-drawer-open] marker)"
    )
