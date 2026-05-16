"""Failing tests for /review HTML pages (sprint-5 / impl-review-pages).

Covers test-review-ui-list + test-review-ui-detail. Mash Co.
invariants asserted: dark theme, sentence case, eyebrows, accent
button, --ink-3 secondary, no decorative emoji.

Impl lands in Wave 2 (impl-review-pages).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from archivist.service.app import LoopState, create_app

_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "]"
)


def _write_flac(path: Path, n_bytes: int = 1024) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fLaC" + b"\x00" * n_bytes)


def _write_source_json(folder: Path) -> None:
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
            "channels": 2, "track_count": 2, "total_duration_seconds": 480,
            "secure_rip": True, "accuraterip_verified": None,
        },
        "identifiers": {"musicbrainz_disc_id": None, "freedb_disc_id": None,
                        "cd_toc": None, "upc": None, "isrcs": []},
        "detected_metadata": {"album_artist": None, "album": None, "year": None,
                              "label": None, "catalog_number": None, "tracks": []},
        "physical_disc": {"photo": None, "photo_captured": False,
                          "photo_captured_at": None, "photo_device": None,
                          "photo_notes": None, "label_text_guess": None,
                          "appears_burned": None, "handwritten": None},
        "files": [],
        "status": {"rip_success": True, "photo_success": False, "ready": True,
                   "warnings": [], "errors": []},
    }
    (folder / "source.json").write_text(json.dumps(payload))


@pytest.fixture
def music_roots(tmp_path: Path) -> tuple[Path, Path]:
    review = tmp_path / "music" / "review"
    inbox = tmp_path / "music" / "inbox"
    review.mkdir(parents=True)
    inbox.mkdir(parents=True)
    return review, inbox


@pytest.fixture
def client(
    music_roots: tuple[Path, Path], tmp_path: Path,
) -> TestClient:
    review_root, inbox_root = music_roots
    log = tmp_path / "archivist.log"
    log.write_text("")
    return TestClient(create_app(
        LoopState(), log,
        discs_root=inbox_root,
        review_root=review_root,
    ))


def _strip_styles_scripts(html: str) -> str:
    out = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
    out = re.sub(r"<style\b[^>]*>.*?</style>", " ", out, flags=re.S | re.I)
    return out


# ============== test-review-ui-list (5 cases) =======================


def test_review_list_empty_renders_empty_state(client: TestClient) -> None:
    resp = client.get("/review")
    assert resp.status_code == 200
    body = resp.text
    # Empty-state hint uses sentence-case body copy.
    assert "nothing to review" in body.lower() or "no folders" in body.lower()
    # Muted color hint per Mash Co. — --ink-3 token referenced inline OR in styles.
    assert "--ink-3" in body or "fg-quiet" in body or "fg-muted" in body


def test_review_list_two_folders_render_cards(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    review_root, _ = music_roots
    for name in ("2026-05-16_1200_disc-000001", "2026-05-16_1300_disc-000002"):
        folder = review_root / name
        _write_flac(folder / "01 Track.flac")
        _write_source_json(folder)

    body = client.get("/review").text
    for name in ("2026-05-16_1200_disc-000001", "2026-05-16_1300_disc-000002"):
        assert name in body
        assert f'/review/{name}' in body


def test_review_list_mash_invariants(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    review_root, _ = music_roots
    folder = review_root / "afi-sing-the-sorrow"
    _write_flac(folder / "01 Track.flac")
    _write_source_json(folder)

    body = client.get("/review").text
    assert 'data-theme="dark"' in body
    assert _EMOJI_RE.findall(body) == []
    # Eyebrow class present.
    assert 'class="eyebrow"' in body
    # No 3+-word ALL CAPS in visible text.
    visible = re.sub(r"<[^>]+>", " ", _strip_styles_scripts(body))
    assert re.findall(r"\b[A-Z]{2,}(?:\s+[A-Z]{2,}){2,}\b", visible) == []
    # CTA button references accent token.
    assert "--accent" in body


def test_review_list_inbox_stuck_card_marked(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    review_root, inbox_root = music_roots
    review_folder = review_root / "from-review"
    _write_flac(review_folder / "01 Track.flac")
    _write_source_json(review_folder)

    inbox_folder = inbox_root / "from-inbox-stuck"
    _write_flac(inbox_folder / "01 Track.flac")
    (inbox_folder / "READY").write_text("ready_at=...\n")
    _write_source_json(inbox_folder)

    body = client.get("/review").text
    assert "from-review" in body
    assert "from-inbox-stuck" in body
    # Inbox-stuck cards distinguished — either data-source attr OR
    # the literal string "inbox-stuck" / "stuck" inline.
    assert (
        'data-source="inbox-stuck"' in body
        or "inbox-stuck" in body
        or "stuck" in body.lower()
    )


def test_review_list_nav_back_to_library(client: TestClient) -> None:
    body = client.get("/review").text
    assert 'href="/library"' in body


# ============== test-review-ui-detail (6 cases) =====================


def test_detail_empty_query_renders_shell(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    review_root, _ = music_roots
    folder = review_root / "stp"
    _write_flac(folder / "01 Track.flac")
    _write_source_json(folder)

    resp = client.get(f"/review/{folder.name}")
    assert resp.status_code == 200
    body = resp.text
    # Search form present.
    assert "<form" in body
    # No candidates yet.
    assert "candidate" not in body.lower() or "no candidates" in body.lower() or "search MB" in body or "search mb" in body


def test_detail_search_renders_candidate_card(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    review_root, _ = music_roots
    folder = review_root / "stp"
    _write_flac(folder / "01 Track.flac", n_bytes=120 * 44100 * 4)
    _write_source_json(folder)

    fake_mb = MagicMock()
    fake_mb.search_releases.return_value = {
        "release-list": [{
            "id": "some-mbid",
            "ext:score": "85",
            "title": "Core",
            "artist-credit-phrase": "Stone Temple Pilots",
            "date": "1992",
            "label-info-list": [{"label": {"name": "Atlantic"}}],
            "medium-list": [{
                "track-list": [
                    {"position": "1", "recording": {
                        "title": "Dead & Bloated", "length": "300000",
                    }},
                ],
            }],
        }],
    }
    with patch("archivist.service.beets_review.get_mb_client", return_value=fake_mb):
        body = client.get(f"/review/{folder.name}?search=stp").text

    assert "some-mbid" in body
    assert "Core" in body
    assert "Stone Temple Pilots" in body


def test_detail_mash_invariants(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    review_root, _ = music_roots
    folder = review_root / "afi"
    _write_flac(folder / "01 Track.flac")
    _write_source_json(folder)

    body = client.get(f"/review/{folder.name}").text
    assert 'data-theme="dark"' in body
    assert _EMOJI_RE.findall(body) == []
    assert 'class="eyebrow"' in body
    # Apply / Use-as-is buttons should reference --accent and --ink-3
    # somewhere in the rendered HTML (inline style or class).
    assert "--accent" in body
    assert "--ink-3" in body or "ink-3" in body


def test_detail_track_diff_table_monospace_filename_and_warn_class(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    review_root, _ = music_roots
    folder = review_root / "stp"
    _write_flac(folder / "01 Track.flac", n_bytes=120 * 44100 * 4)
    _write_source_json(folder)

    # MB candidate with a track length 8s longer than the FLAC (5s threshold).
    fake_mb = MagicMock()
    fake_mb.search_releases.return_value = {
        "release-list": [{
            "id": "mbid-warn",
            "ext:score": "75",
            "title": "Core",
            "artist-credit-phrase": "STP",
            "date": "1992",
            "medium-list": [{
                "track-list": [
                    {"position": "1", "recording": {
                        "title": "Dead and Bloated", "length": "320000",
                    }},
                ],
            }],
        }],
    }
    with patch("archivist.service.beets_review.get_mb_client", return_value=fake_mb):
        body = client.get(f"/review/{folder.name}?search=stp").text

    # Filename rendered in monospace — either <code> wrap or 'mono' token.
    assert "<code>" in body or "font-mono" in body or "--font-mono" in body
    # Warning row class for >5s delta.
    assert "row--warn" in body


def test_detail_unknown_folder_404(client: TestClient) -> None:
    resp = client.get("/review/does-not-exist")
    assert resp.status_code == 404


def test_detail_audio_preview_per_track(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    review_root, _ = music_roots
    folder = review_root / "afi"
    _write_flac(folder / "01 Track.flac")
    _write_flac(folder / "02 Track.flac")
    _write_source_json(folder)

    body = client.get(f"/review/{folder.name}").text
    # Two audio tags, one per FLAC file in the folder.
    assert body.count("<audio") >= 2
