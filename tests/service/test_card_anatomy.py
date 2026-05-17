"""Failing tests for the sprint-7 card anatomy refactor (Bucket C).

Locks the spec in the Mash Co. build prompt:

    Header row → Track bar → Status line → Chip row

(per build prompt §"Card anatomy"). The lane-2 impl-card-anatomy
will move these out of the inline `<style>` blob into a
card-render module + `cda.css` selectors.

Impl lands in Wave 2 (impl-card-anatomy + status_line.format +
track_identification.identified_tracks + per-column accent classes).
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


def _base_source(name: str, *, track_count: int = 3, **overrides) -> dict:
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


def _read_cda_css() -> str:
    """Load the migrated cda.css — Bucket B lane-1 ships it. The
    file may not exist yet today; tests then fail with a clear
    "where is cda.css?" message."""
    path = Path(__file__).resolve().parents[2] / (
        "archivist/service/static/css/cda.css"
    )
    if not path.is_file():
        pytest.fail(
            f"cda.css not found at {path} — lane-1 impl-asset-wire-up "
            "must land first"
        )
    return path.read_text(encoding="utf-8")


# ============== (1) test-card-header-row ================================
#
# .card-head with 56×56 .thumb (img or .thumb--placeholder) + .slug
# eyebrow + .title + .artist; thumbnail-left text-block-right; slug
# uses --font-mono.


def test_card_head_renders_for_each_card(
    client: TestClient, music_root: Path,
) -> None:
    _seed(music_root / "review", "2026-05-16_1200_disc-h1")
    html = client.get("/").text
    assert 'class="card-head"' in html


def test_card_head_carries_56x56_thumb(
    client: TestClient, music_root: Path,
) -> None:
    """The thumb is either <img class="thumb"> with a src OR a
    placeholder <div class="thumb thumb--placeholder">."""
    _seed(music_root / "review", "2026-05-16_1200_disc-h2")
    html = client.get("/").text
    assert 'class="thumb"' in html or 'class="thumb ' in html


def test_card_head_renders_slug_title_artist(
    client: TestClient, music_root: Path,
) -> None:
    folder = _seed(music_root / "library" / "Foo", "Bar", _base_source(
        "Bar",
        detected_metadata={
            "album_artist": "Foo", "album": "Bar", "year": None,
            "label": None, "catalog_number": None, "tracks": [],
        },
    ))
    html = client.get("/").text
    assert 'class="slug"' in html
    assert 'class="title"' in html
    assert 'class="artist"' in html
    assert folder.name in html


def test_thumb_uses_placeholder_when_no_photo(
    client: TestClient, music_root: Path,
) -> None:
    _seed(music_root / "review", "2026-05-16_1200_disc-h3")
    html = client.get("/").text
    assert "thumb--placeholder" in html


def test_slug_styled_with_font_mono(client: TestClient) -> None:
    css = _read_cda_css()
    assert ".slug" in css
    # The slug eyebrow is in JetBrains Mono per the build prompt.
    pat = re.compile(
        r"\.slug\b[^{]*\{[^}]*font-family:\s*var\(--font-mono\)[^}]*\}",
        re.S,
    )
    assert pat.search(css), (
        "expected `.slug { ... font-family: var(--font-mono) ... }` in cda.css"
    )


# ============== (2) test-status-line ===================================
#
# Per-state status line formats matching the build prompt exactly.
# All use .cda-status mono class.


def test_status_line_uses_cda_status_class(
    client: TestClient, music_root: Path,
) -> None:
    _seed(music_root / "review", "2026-05-16_1200_disc-sl1")
    html = client.get("/").text
    assert 'class="cda-status"' in html


def test_status_line_capture_active(
    client: TestClient, loop_state: LoopState,
) -> None:
    """Format from the build prompt:
    'ripping track 7 · sector 24,318 · 1 retry · 04:12 elapsed'"""
    loop_state.state = "RIP"
    loop_state.disc_id = "disc-sl-active"
    loop_state.rip_progress = "track 7/10 (32%)"
    # Drivers' DriveStatus populates the precise per-rip numbers.
    snap = getattr(loop_state, "drive_status", None)
    if snap is not None:
        snap.state = "ripping"
        snap.current_track = 7
        snap.sector_current = 24318
        snap.retries_on_current_track = 1
        snap.elapsed_seconds = 252.0  # 04:12
        snap.current_disc = "disc-sl-active"

    body = client.get("/").text
    assert "ripping track 7" in body
    assert "sector 24,318" in body
    assert "1 retry" in body
    assert "04:12 elapsed" in body


def test_status_line_review_weak_match(
    client: TestClient, music_root: Path,
) -> None:
    """Format: 'weak match · beets returned 0.42'"""
    _seed(music_root / "review", "disc-weak", _base_source(
        "disc-weak",
        status={
            "rip_success": True, "photo_success": True, "ready": True,
            "warnings": [], "errors": [], "partial": False,
            "failed_tracks": [],
            "beets_review_reason": "weak match: score 0.42 below threshold",
        },
    ))
    html = client.get("/").text
    assert "weak match" in html
    assert "0.42" in html


def test_status_line_review_no_match(
    client: TestClient, music_root: Path,
) -> None:
    """Format: 'no match · 13 tracks · no embedded tags'"""
    _seed(music_root / "review", "disc-nomatch", _base_source(
        "disc-nomatch", track_count=13,
        status={
            "rip_success": True, "photo_success": True, "ready": True,
            "warnings": [], "errors": [], "partial": False,
            "failed_tracks": [],
            "beets_review_reason": "beets returned no candidates",
        },
    ))
    html = client.get("/").text
    assert "no match" in html
    assert "13 tracks" in html


def test_status_line_library_stored(
    client: TestClient, music_root: Path,
) -> None:
    """Format: 'stored · matched 0.97 · imported 2026-05-16 13:18'"""
    folder = music_root / "library" / "Foo" / "Bar"
    _write_flac(folder / "01.flac")
    folder.mkdir(parents=True, exist_ok=True)
    payload = _base_source(
        "Bar",
        detected_metadata={
            "album_artist": "Foo", "album": "Bar", "year": 2024,
            "label": None, "catalog_number": None, "tracks": [],
        },
    )
    (folder / "source.json").write_text(json.dumps(payload))
    # Top candidate sidecar — score surfaces in the status line.
    (folder / "top_candidate.json").write_text(json.dumps({
        "mbid": "abc", "score": 0.97,
    }))

    html = client.get("/").text
    assert "stored" in html
    assert "0.97" in html


def test_status_line_capture_damaged(
    client: TestClient, music_root: Path,
) -> None:
    """Format: 'halted · 3 unrecoverable sectors · track 6'"""
    _seed(music_root / "failed", "disc-halted", _base_source(
        "disc-halted",
        status={
            "rip_success": False, "photo_success": True, "ready": False,
            "warnings": [], "errors": ["halted at track 6: 3 sectors"],
            "partial": True, "failed_tracks": [6],
        },
    ))
    html = client.get("/").text
    assert "halted" in html
    assert "track 6" in html


def test_cda_status_class_uses_mono_font(client: TestClient) -> None:
    css = _read_cda_css()
    pat = re.compile(
        r"\.cda-status\b[^{]*\{[^}]*font-family:\s*var\(--font-mono\)[^}]*\}",
        re.S,
    )
    assert pat.search(css)


# ============== (3) test-chip-row ======================================
#
# .chip-row holds 0-4 chips; VA / BURNED / MIX / WEAK MATCH /
# MUSICBRAINZ; .chip--asserted (dashed) vs .chip--confirmed (solid +
# halo); per-card left-border accent classes per the build prompt table.


def test_chip_row_element_renders(
    client: TestClient, music_root: Path,
) -> None:
    _seed(music_root / "review", "disc-cr1")
    html = client.get("/").text
    assert 'class="chip-row"' in html


def test_va_chip_when_various_artists_set(
    client: TestClient, music_root: Path,
) -> None:
    _seed(music_root / "review", "disc-va", _base_source(
        "disc-va",
        operator_hints={
            "various_artists": True, "burned_cd": False,
            "artist": None, "album": None, "tracks": [],
        },
    ))
    html = client.get("/").text
    assert "VA" in html
    # Operator-asserted → dashed.
    assert "chip--asserted" in html


def test_burned_chip_when_burned_cd_set(
    client: TestClient, music_root: Path,
) -> None:
    _seed(music_root / "review", "disc-burn", _base_source(
        "disc-burn",
        operator_hints={
            "various_artists": False, "burned_cd": True,
            "artist": None, "album": None, "tracks": [],
        },
    ))
    html = client.get("/").text
    assert "BURNED" in html


def test_mix_chip_when_both_va_and_burned(
    client: TestClient, music_root: Path,
) -> None:
    _seed(music_root / "review", "disc-mix", _base_source(
        "disc-mix",
        operator_hints={
            "various_artists": True, "burned_cd": True,
            "artist": None, "album": None, "tracks": [],
        },
    ))
    html = client.get("/").text
    assert "MIX" in html


def test_weak_match_chip_renders_with_score(
    client: TestClient, music_root: Path,
) -> None:
    """Build-prompt example: 'WEAK MATCH · 0.42' chip."""
    folder = _seed(music_root / "review", "disc-weak-chip", _base_source(
        "disc-weak-chip",
        status={
            "rip_success": True, "photo_success": True, "ready": True,
            "warnings": [], "errors": [], "partial": False,
            "failed_tracks": [],
            "beets_review_reason": "weak match: score 0.42 below threshold",
        },
    ))
    (folder / "top_candidate.json").write_text(json.dumps({
        "mbid": "x", "score": 0.42,
    }))
    html = client.get("/").text
    assert "WEAK MATCH" in html
    assert "0.42" in html


def test_musicbrainz_chip_renders_for_disc_id_match(
    client: TestClient, music_root: Path,
) -> None:
    """When the card has both a disc-id and a high-confidence match,
    the MUSICBRAINZ confirmed chip surfaces."""
    folder = music_root / "library" / "Foo" / "Bar"
    folder.mkdir(parents=True, exist_ok=True)
    _write_flac(folder / "01.flac")
    payload = _base_source(
        "Bar",
        identifiers={
            "musicbrainz_disc_id": "abc-mbid", "freedb_disc_id": None,
            "cd_toc": None, "upc": None, "isrcs": [],
        },
        detected_metadata={
            "album_artist": "Foo", "album": "Bar", "year": None,
            "label": None, "catalog_number": None, "tracks": [],
        },
    )
    (folder / "source.json").write_text(json.dumps(payload))
    (folder / "top_candidate.json").write_text(json.dumps({
        "mbid": "abc-mbid", "score": 0.97,
    }))
    html = client.get("/").text
    assert "MUSICBRAINZ" in html
    # System-confirmed → solid + halo.
    assert "chip--confirmed" in html


def test_chip_classes_styled_in_cda_css(client: TestClient) -> None:
    css = _read_cda_css()
    # Dashed border for asserted.
    assert ".chip--asserted" in css
    assert "dashed" in css
    # Solid + halo (box-shadow) for confirmed.
    assert ".chip--confirmed" in css


def test_card_carries_per_column_accent_class(
    client: TestClient, music_root: Path,
) -> None:
    """Per the build-prompt table: pulp (Capture default) /
    pulp-ripping / ember-damaged / sky (Beets ID) / amber or ember
    (Review) / moss (Library). Cards are tagged with classes like
    .card--accent-pulp etc."""
    # Library card → accent-moss.
    folder = music_root / "library" / "Foo" / "Bar"
    folder.mkdir(parents=True, exist_ok=True)
    _write_flac(folder / "01.flac")
    (folder / "source.json").write_text(json.dumps(_base_source("Bar")))

    # Damaged Capture card → accent-ember-damaged.
    _seed(music_root / "failed", "disc-acc-dmg", _base_source(
        "disc-acc-dmg",
        status={
            "rip_success": False, "photo_success": True, "ready": False,
            "warnings": [], "errors": [], "partial": True,
            "failed_tracks": [3],
        },
    ))

    # Review card with weak match → accent-amber.
    _seed(music_root / "review", "disc-acc-amber", _base_source(
        "disc-acc-amber",
        status={
            "rip_success": True, "photo_success": True, "ready": True,
            "warnings": [], "errors": [], "partial": False,
            "failed_tracks": [],
            "beets_review_reason": "weak match: score 0.42",
        },
    ))

    html = client.get("/").text
    assert "card--accent-moss" in html
    assert "card--accent-ember-damaged" in html
    assert "card--accent-amber" in html


# ============== (4) test-track-segments =================================
#
# .track-bar with style="--track-count: N"; per-cell state classes
# (--clean / --recovered / --unrecoverable / --pending / --ripping);
# in-flight cell carries style="--progress: X%";
# .track-cell--identified gets the 1px white inset 2px outline.


def test_track_bar_carries_track_count_custom_property(
    client: TestClient, music_root: Path,
) -> None:
    """The CSS-custom-property-as-data pattern (D-inline-css-whitelist):
    `style="--track-count: N"` is the allowed inline-style shape."""
    _seed(music_root / "review", "disc-tc1", _base_source(
        "disc-tc1", track_count=7,
    ))
    html = client.get("/").text
    assert 'class="track-bar"' in html
    assert "--track-count: 7" in html or "--track-count:7" in html


def test_clean_tracks_carry_clean_state_class(
    client: TestClient, music_root: Path,
) -> None:
    _seed(music_root / "library" / "Art", "Alb", _base_source("Alb"))
    html = client.get("/").text
    assert "track-cell--clean" in html


def test_unrecoverable_tracks_carry_unrecoverable_state_class(
    client: TestClient, music_root: Path,
) -> None:
    _seed(music_root / "failed", "disc-unrec", _base_source(
        "disc-unrec", track_count=5,
        status={
            "rip_success": False, "photo_success": True, "ready": False,
            "warnings": [], "errors": [], "partial": True,
            "failed_tracks": [3, 4, 5],
        },
    ))
    html = client.get("/").text
    assert "track-cell--unrecoverable" in html


def test_ripping_cell_carries_progress_custom_property(
    client: TestClient, loop_state: LoopState,
) -> None:
    loop_state.state = "RIP"
    loop_state.disc_id = "disc-tc-prog"
    loop_state.rip_progress = "track 3/10 (65%)"
    snap = getattr(loop_state, "drive_status", None)
    if snap is not None:
        snap.state = "ripping"
        snap.current_track = 3
        snap.track_total = 10
        snap.current_disc = "disc-tc-prog"

    html = client.get("/").text
    assert "track-cell--ripping" in html
    # The in-flight cell carries the progress custom prop (whitelisted).
    assert "--progress: 65%" in html or "--progress:65%" in html


def test_pending_tracks_carry_pending_state_class(
    client: TestClient, loop_state: LoopState,
) -> None:
    loop_state.state = "RIP"
    loop_state.disc_id = "disc-tc-pend"
    loop_state.rip_progress = "track 2/8 (10%)"
    snap = getattr(loop_state, "drive_status", None)
    if snap is not None:
        snap.state = "ripping"
        snap.current_track = 2
        snap.track_total = 8
        snap.current_disc = "disc-tc-pend"
    html = client.get("/").text
    assert "track-cell--pending" in html


def test_identified_track_carries_identified_class(
    client: TestClient, music_root: Path,
) -> None:
    """When a track has been beets-identified, the cell gets the
    .track-cell--identified class (cda.css gives it the 1px white
    inset outline). Source of identification is left to the impl
    (D-track-identification-source) — the test just pins that when
    detected_metadata.tracks carries a title for track N AND a
    disc-id exists, the corresponding cell is marked."""
    folder = music_root / "library" / "Foo" / "Bar"
    folder.mkdir(parents=True, exist_ok=True)
    _write_flac(folder / "01.flac")
    (folder / "source.json").write_text(json.dumps(_base_source(
        "Bar",
        identifiers={
            "musicbrainz_disc_id": "abc-mbid", "freedb_disc_id": None,
            "cd_toc": None, "upc": None, "isrcs": [],
        },
        detected_metadata={
            "album_artist": "Foo", "album": "Bar", "year": None,
            "label": None, "catalog_number": None,
            "tracks": [
                {"track": 1, "title": "T1"},
                {"track": 2, "title": "T2"},
                {"track": 3, "title": "T3"},
            ],
        },
    )))
    html = client.get("/").text
    assert "track-cell--identified" in html


def test_identified_class_styled_with_inset_outline(client: TestClient) -> None:
    css = _read_cda_css()
    assert ".track-cell--identified" in css
    # Per build prompt: "1px white outline (inset 2px)".
    pat = re.compile(
        r"\.track-cell--identified\b[^{]*\{[^}]*box-shadow:\s*inset[^}]*\}",
        re.S,
    )
    assert pat.search(css), (
        "expected `.track-cell--identified { ... box-shadow: inset ... }` "
        "in cda.css"
    )
