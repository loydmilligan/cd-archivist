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


# ============== test-expand-mechanic (sprint-6.5 Bucket B) ==============
#
# Cards become click + spacebar expandable, one-at-a-time, with a `?`
# tooltip surfacing keyboard nav. Per K1.3-A in the brainstorm:
# accordion-style inline expand, spacebar toggle (not Enter — Enter
# is reserved for future activation), preventDefault to suppress page
# scroll on spacebar.


def test_cards_carry_tabindex_for_keyboard_nav(
    client: TestClient, music_root: Path,
) -> None:
    folder = music_root / "review" / "2026-05-16_1200_disc-em1"
    _write_flac(folder / "01.flac")
    _write_source(folder)

    html = client.get("/").text
    # Cards must be focusable for spacebar to land on them.
    assert 'tabindex="0"' in html


def test_keyboard_help_button_renders_with_tooltip_payload(
    client: TestClient,
) -> None:
    html = client.get("/").text
    # Tooltip element: <button aria-label="keyboard help">?</button>
    # carrying a data-keyboard-help attribute with the keymap.
    assert 'aria-label="keyboard help"' in html
    assert "data-keyboard-help" in html
    # The visible glyph is "?".
    assert ">?<" in html


def test_page_emits_module_script_with_spacebar_handler(
    client: TestClient,
) -> None:
    html = client.get("/").text
    assert '<script type="module"' in html
    # Spacebar key check + preventDefault to suppress browser scroll.
    assert "preventDefault" in html
    assert "Space" in html or '" "' in html or "' '" in html


def test_page_js_carries_one_at_a_time_expand_guard(
    client: TestClient,
) -> None:
    """One card may be expanded at a time. The JS source carries a
    module-scope reference tracking the currently-expanded card so
    opening a second one collapses the first."""
    html = client.get("/").text
    # Pin a recognisable marker — the impl module-scope variable name
    # is contractual for this test and called out in the plan.
    assert "currentlyExpanded" in html or "currentExpanded" in html


# ============== test-header-bar (sprint-6.5 Bucket C) ===================
#
# Page header per D-no-alerts-v1: wordmark + daemon-state dot + stats
# (center) + drawer-toggle buttons + nav link-outs (right). No
# notification/alert strip in v1.


def test_header_renders_three_regions(client: TestClient) -> None:
    html = client.get("/").text
    assert "<header" in html
    assert 'class="header-left"' in html
    assert 'class="header-stats"' in html
    assert 'class="header-right"' in html


def test_header_left_carries_wordmark_and_daemon_dot(
    client: TestClient,
) -> None:
    html = client.get("/").text
    assert "cd-archivist" in html
    # Daemon state dot: derives presence from kanban-payload-presence;
    # element carries a discoverable class/marker.
    assert "daemon-state-dot" in html or 'data-daemon-state' in html


def test_header_stats_show_compact_counts(
    client: TestClient, music_root: Path,
) -> None:
    """At least one card so the count badges have something to count."""
    folder = music_root / "review" / "2026-05-16_1200_hb-1"
    _write_flac(folder / "01.flac")
    _write_source(folder)

    html = client.get("/").text
    # Header stats include labels for the three counts called out by
    # the spec; values come from the kanban payload.
    assert "total" in html.lower()
    assert "review" in html.lower()
    assert "partial" in html.lower()


def test_header_right_carries_drawer_toggles_with_aria_controls(
    client: TestClient,
) -> None:
    html = client.get("/").text
    # Two drawer-toggle buttons: one for the right drawer, one for
    # the bottom drawer; both carry aria-controls pointing at the
    # drawer element ids.
    assert 'aria-controls="right-drawer"' in html
    assert 'aria-controls="bottom-drawer"' in html


def test_header_has_no_alert_strip(client: TestClient) -> None:
    """D-no-alerts-v1 — header carries no notification/alert strip."""
    html = client.get("/").text
    # No element with the discoverable alert-strip marker class.
    assert "alert-strip" not in html
    assert 'data-alerts' not in html


# ============== test-column-scroll-badges (sprint-6.5 Bucket C) =========
#
# Each column scrolls independently; column headers stick to the top
# of the column; each header carries a count badge.


def test_column_carries_overflow_y_auto_in_css(
    client: TestClient,
) -> None:
    """The kanban CSS must declare per-column scroll."""
    html = client.get("/").text
    # We pin the CSS rule fragment — the impl can use a selector
    # other than `.column` as long as the overflow rule applies to
    # the per-bucket region. The plan calls out `.column`.
    assert ".column" in html
    assert "overflow-y: auto" in html or "overflow-y:auto" in html


def test_column_header_carries_count_badge(
    client: TestClient, music_root: Path,
) -> None:
    """Header reads e.g. 'REVIEW (6)' via a .count-badge element."""
    # Seed three review folders so the count is unambiguous.
    for i in range(3):
        folder = music_root / "review" / f"2026-05-16_1200_csb-{i}"
        _write_flac(folder / "01.flac")
        _write_source(folder)

    html = client.get("/").text
    assert "count-badge" in html
    # The count "3" appears alongside the bucket label.
    assert ">3<" in html or "(3)" in html


def test_column_header_is_position_sticky(client: TestClient) -> None:
    html = client.get("/").text
    # Sticky header lives in the column CSS — pin the rule fragment.
    assert "position: sticky" in html or "position:sticky" in html


# ============== test-adaptive-polling (sprint-6.5 Bucket E) =============
#
# Page emits both poll intervals; /api/kanban payload gains
# `active_rip: bool`; JS switches the interval based on that field.


def test_page_emits_both_adaptive_poll_meta_tags(
    client: TestClient,
) -> None:
    html = client.get("/").text
    import re
    active = re.search(
        r'<meta\s+name=["\']kanban-poll-ms-active["\']\s+content=["\'](\d+)["\']',
        html,
    )
    idle = re.search(
        r'<meta\s+name=["\']kanban-poll-ms-idle["\']\s+content=["\'](\d+)["\']',
        html,
    )
    assert active is not None, "missing kanban-poll-ms-active meta tag"
    assert idle is not None, "missing kanban-poll-ms-idle meta tag"
    # Defaults per D-adaptive-polling-cadence proposal.
    assert int(active.group(1)) == 1000
    assert int(idle.group(1)) == 5000


def test_kanban_response_carries_active_rip_field(
    client: TestClient,
) -> None:
    body = client.get("/api/kanban").json()
    assert "active_rip" in body
    assert isinstance(body["active_rip"], bool)


def test_active_rip_true_when_capture_bucket_has_in_progress_card(
    client: TestClient, loop_state: LoopState,
) -> None:
    loop_state.state = "RIP"
    loop_state.disc_id = "disc-ap1"
    loop_state.rip_progress = "track 2/10 (20%)"
    body = client.get("/api/kanban").json()
    assert body["active_rip"] is True


def test_active_rip_false_when_idle(client: TestClient) -> None:
    body = client.get("/api/kanban").json()
    assert body["active_rip"] is False


def test_page_js_switches_interval_based_on_active_rip(
    client: TestClient,
) -> None:
    """The JS source contains both interval references and a guard
    that reads `active_rip` from the response."""
    html = client.get("/").text
    assert "active_rip" in html
    # Both interval names referenced so the front-end can flip
    # between them at the end of each response cycle.
    assert "kanban-poll-ms-active" in html
    assert "kanban-poll-ms-idle" in html
