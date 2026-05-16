"""Failing tests for the Review v1 screen (sprint-6 Bucket C).

Covers test-review-page-explainer. The Review v1 page at GET /review
augments each card with:

  - "Why in review" — derived from source.json + beets-import.log
    by archivist.service.review_explainer.explain(folder).
  - "Manual steps" — a <details> block with copy-paste shell
    commands the operator can run on the CM4.

No interactive controls in v1 (in-UI candidate selection is sprint-7).

Impl lands in Wave 2 (impl-review-page-v1).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Module under test for the explainer half of the contract.
from archivist.service.review_explainer import explain  # noqa: E402
from archivist.service.app import LoopState, create_app


def _write_flac(path: Path, n_bytes: int = 1024) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fLaC" + b"\x00" * n_bytes)


def _base_source(
    folder_name: str,
    *,
    disc_id: str | None = None,
    beets_review_reason: str | None = None,
) -> dict:
    payload = {
        "schema_version": 1,
        "ripper": {"name": "cd-archivist", "version": "0.1.0", "host": "cm4"},
        "disc": {
            "folder_name": folder_name, "disc_counter": 1,
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
            "channels": 2, "track_count": 10,
            "total_duration_seconds": 600,
            "secure_rip": True, "accuraterip_verified": None,
        },
        "identifiers": {
            "musicbrainz_disc_id": disc_id, "freedb_disc_id": None,
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
    if beets_review_reason is not None:
        payload["status"]["beets_review_reason"] = beets_review_reason
    return payload


def _seed_review(
    music_root: Path,
    name: str,
    *,
    source: dict | None = None,
    beets_log: str | None = None,
) -> Path:
    folder = music_root / "review" / name
    _write_flac(folder / "01.flac")
    if source is None:
        source = _base_source(name)
    (folder / "source.json").write_text(json.dumps(source))
    if beets_log is not None:
        (folder / "beets-import.log").write_text(beets_log)
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


# ============== explain() — direct unit tests ============================


def test_explain_prefers_beets_review_reason_when_present(
    music_root: Path,
) -> None:
    folder = _seed_review(
        music_root, "disc-x",
        source=_base_source("disc-x", beets_review_reason="beets returned no candidates"),
    )
    msg = explain(folder)
    assert isinstance(msg, str)
    assert "no candidates" in msg.lower()


def test_explain_detects_weak_match_in_beets_log(music_root: Path) -> None:
    log = (
        "import: looking up candidates for /downloads/disc-y\n"
        "match: top score 0.28 below threshold (0.50)\n"
    )
    folder = _seed_review(music_root, "disc-y", beets_log=log)
    msg = explain(folder)
    assert "weak match" in msg.lower() or "0.28" in msg


def test_explain_detects_empty_acoustid_with_tagless_flacs(
    music_root: Path,
) -> None:
    log = "AcoustID: empty match. Source flacs have no tags.\n"
    folder = _seed_review(music_root, "disc-z", beets_log=log)
    msg = explain(folder)
    assert "acoustid" in msg.lower() or "tag" in msg.lower()


def test_explain_falls_back_when_no_signals_available(
    music_root: Path,
) -> None:
    folder = _seed_review(music_root, "disc-nosignal")
    msg = explain(folder)
    # The explainer must always return a non-empty string — never None.
    assert isinstance(msg, str) and msg.strip() != ""


def test_explain_notes_missing_musicbrainz_disc_id(
    music_root: Path,
) -> None:
    """A folder ripped without libdiscid available has no MB disc-id —
    that alone is a meaningful explainer signal."""
    folder = _seed_review(
        music_root, "disc-no-mbid",
        source=_base_source("disc-no-mbid", disc_id=None),
    )
    msg = explain(folder)
    assert "disc-id" in msg.lower() or "musicbrainz" in msg.lower()


# ============== /review page — rendering contract ========================


def test_review_page_renders_why_in_review_per_card(
    client: TestClient, music_root: Path,
) -> None:
    _seed_review(
        music_root, "2026-05-16_1200_disc-r1",
        source=_base_source(
            "2026-05-16_1200_disc-r1",
            beets_review_reason="beets returned no candidates",
        ),
    )
    html = client.get("/review").text
    # The explainer text surfaces in the card body.
    assert "no candidates" in html.lower()


def test_review_page_renders_manual_steps_shell_snippet(
    client: TestClient, music_root: Path,
) -> None:
    folder = _seed_review(
        music_root, "2026-05-16_1200_disc-r2",
        source=_base_source(
            "2026-05-16_1200_disc-r2",
            beets_review_reason="beets returned no candidates",
        ),
    )
    html = client.get("/review").text
    # The card has a <details> block with the literal docker exec command.
    assert "<details" in html
    assert "docker exec" in html
    assert "cd_beets" in html
    assert "beet import" in html
    # The folder name appears in the suggested command.
    assert folder.name in html


def test_review_page_no_interactive_controls_in_v1(
    client: TestClient, music_root: Path,
) -> None:
    """v1 is read-only — no form posts, no in-UI candidate selection."""
    _seed_review(
        music_root, "2026-05-16_1200_disc-r3",
        source=_base_source(
            "2026-05-16_1200_disc-r3",
            beets_review_reason="beets returned no candidates",
        ),
    )
    html = client.get("/review").text
    # No submission targets to the apply / use-as-is endpoints from
    # sprint-5 — the v1 page is explanatory only. We assert the absence
    # of POST forms whose action targets /api/review/.
    assert 'action="/api/review/' not in html


