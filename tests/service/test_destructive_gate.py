"""Failing tests for the second-click destructive-action gate
(sprint-7 Bucket F, lane-2).

Per the build prompt §"Expanded card body":

    Destructive actions (redo, rerip, skip, delete) require a second
    click to confirm. Render the gate hint below them:
    "Destructive actions require a second click to confirm. The
    partial flac files stay on disk until you choose."

Mechanics: first click arms the button (label swaps to
`confirm: <action>`, class gains `.btn--confirm-armed`); second
click within 5 seconds fires the actual POST; >5s or clicking
elsewhere reverts.

Impl lands in Wave 2 (impl-destructive-gate). Test assertions are
HTML + JS-source assertions; real-rig clicks are covered in Wave 3.
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
            "channels": 2, "track_count": 5,
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


def _seed_damaged(parent: Path, name: str) -> Path:
    folder = parent / name
    folder.mkdir(parents=True, exist_ok=True)
    _write_flac(folder / "01.flac")
    payload = _base_source(
        name,
        status={
            "rip_success": False, "photo_success": True, "ready": False,
            "warnings": [], "errors": ["halted at track 3"],
            "partial": True, "failed_tracks": [3, 4, 5],
        },
    )
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


# ============== (a) destructive buttons render as gateable =============


def test_destructive_buttons_carry_destructive_marker(
    client: TestClient, music_root: Path,
) -> None:
    """Each destructive action button (redo / rerip-tracks / skip /
    delete) carries a discoverable marker so the gate JS can attach.
    The plan calls out `data-destructive="true"`."""
    _seed_damaged(music_root / "failed", "dg-1")
    html = client.get("/rip").text
    # At least the redo + rerip-tracks buttons (sprint-6 endpoints
    # already wired) surface on a damaged card. They must carry
    # data-destructive="true" so the gate handler picks them up.
    assert 'data-destructive="true"' in html


def test_destructive_button_action_names_present(
    client: TestClient, music_root: Path,
) -> None:
    """The gate's `confirm: <action>` armed-label needs an action
    name to interpolate. Each destructive button carries
    data-action="<name>" naming the action."""
    _seed_damaged(music_root / "failed", "dg-2")
    html = client.get("/rip").text
    # Both redo + rerip-tracks render in the damaged-actions section.
    assert 'data-action="redo"' in html
    assert 'data-action="rerip-tracks"' in html


# ============== (b) arm-then-fire JS source contract ===================


def test_kanban_js_arms_button_on_first_click(client: TestClient) -> None:
    """Gate logic lives in the inline <script type="module"> JS source.
    First click swaps the label to `confirm: <action>` and toggles
    `.btn--confirm-armed`."""
    html = client.get("/rip").text
    assert "btn--confirm-armed" in html
    # The label-swap template `confirm: <action>` is a string literal
    # in the JS source.
    assert "confirm:" in html


def test_kanban_js_disarms_after_5_seconds(client: TestClient) -> None:
    """The arm window is 5000ms. JS source contains a setTimeout
    (or equivalent) keyed to a 5-second revert."""
    html = client.get("/rip").text
    # Either literal `5000` near a setTimeout, or a named constant.
    assert "5000" in html or "5 * 1000" in html or "CONFIRM_TIMEOUT" in html


def test_kanban_js_disarms_on_click_elsewhere(client: TestClient) -> None:
    """Clicking elsewhere reverts an armed button. The JS source
    listens at the document level so any outside click resets."""
    html = client.get("/rip").text
    # Pin a document-level click handler that the gate uses to revert.
    assert "document.addEventListener('click'" in html or (
        'document.addEventListener("click"' in html
    )


# ============== (c) confirm-hint paragraph ==============================


def test_confirm_hint_paragraph_renders_with_verbatim_text(
    client: TestClient, music_root: Path,
) -> None:
    """Build prompt: a <p class="confirm-hint"> renders below the
    destructive buttons with the literal text:

    'Destructive actions require a second click to confirm. The
     partial flac files stay on disk until you choose.'
    """
    _seed_damaged(music_root / "failed", "dg-hint")
    html = client.get("/rip").text
    assert 'class="confirm-hint"' in html
    assert "Destructive actions require a second click to confirm" in html
    assert "The partial flac files stay on disk until you choose" in html


def test_confirm_hint_absent_on_healthy_card(
    client: TestClient, music_root: Path,
) -> None:
    """The hint paragraph rides with the damaged-actions section;
    a healthy card has no destructive buttons and therefore no
    hint."""
    folder = music_root / "library" / "Art" / "Alb"
    folder.mkdir(parents=True, exist_ok=True)
    _write_flac(folder / "01.flac")
    (folder / "source.json").write_text(json.dumps(_base_source("Alb")))

    html = client.get("/rip").text
    # Library-only seed → no damaged-actions section → no hint
    # paragraph. Pin via the hint class so the test doesn't trip on
    # the literal hint text appearing elsewhere (it shouldn't, but
    # the class assertion is the contract).
    assert 'class="confirm-hint"' not in html
