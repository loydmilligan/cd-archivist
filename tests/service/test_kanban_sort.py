"""Failing tests for per-bucket default sort (sprint-6.5 Bucket A).

Pins the algorithm specified by the planner:

- Capture:   active-rip overlay pinned at index 0; then
             failed/partial cards newest-first; then successful
             cards newest-first.
- Beets ID:  newest-first.
- Review:    by "why in review" priority enum (PARTIAL=0,
             WEAK_MATCH=1, NO_MATCH=2, NO_ID_NO_TAGS=3); then
             newest-first within priority.
- Library:   newest-first.

The priority enum is exposed as `DiscCard.review_priority` (int) so
the UI can render a chip label without re-deriving it.

Impl lands in Wave 2 (impl-per-bucket-sort + D-default-sort-v1).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from archivist.service.app import LoopState
from archivist.service.disc_card_builder import build_kanban_state


def _review_priority():
    """Import lazily so suite collection succeeds before impl lands."""
    from archivist.service.disc_card_builder import ReviewPriority
    return ReviewPriority


def _write_flac(path: Path, n_bytes: int = 1024) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fLaC" + b"\x00" * n_bytes)


def _base_source(
    folder_name: str,
    *,
    partial: bool = False,
    rip_success: bool = True,
    disc_id: str | None = "test-disc-id",
    beets_review_reason: str | None = None,
    has_beets_log: bool = False,
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
            "channels": 2, "track_count": 2,
            "total_duration_seconds": 480,
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
            "rip_success": rip_success, "photo_success": True, "ready": True,
            "warnings": [], "errors": [],
            "partial": partial, "failed_tracks": [],
        },
    }
    if beets_review_reason is not None:
        payload["status"]["beets_review_reason"] = beets_review_reason
    return payload


def _seed(
    parent: Path, name: str, *, payload: dict | None = None, mtime: float = 0,
    beets_log: str | None = None,
) -> Path:
    folder = parent / name
    _write_flac(folder / "01.flac")
    folder.mkdir(parents=True, exist_ok=True)
    if payload is None:
        payload = _base_source(name)
    (folder / "source.json").write_text(json.dumps(payload))
    if beets_log is not None:
        (folder / "beets-import.log").write_text(beets_log)
    if mtime:
        os.utime(folder, (mtime, mtime))
    return folder


@pytest.fixture
def music_root(tmp_path: Path) -> Path:
    root = tmp_path / "music"
    for sub in ("inbox", "review", "library", "archive", "failed"):
        (root / sub).mkdir(parents=True)
    return root


# ============== (a) Capture bucket: active pinned, then damaged, then ok =


def test_capture_bucket_pins_active_rip_first(music_root: Path) -> None:
    loop = LoopState()
    loop.state = "RIP"
    loop.disc_id = "disc-active"
    loop.rip_progress = "track 2/8 (25%)"

    # Seed nothing else — the active rip is the only capture-bucket card.
    state = build_kanban_state(music_root, loop_state=loop)
    capture = state.buckets["capture"]
    assert len(capture) >= 1
    assert capture[0].disc_id == "disc-active"


def test_capture_bucket_orders_damaged_before_successful_newest_first(
    music_root: Path,
) -> None:
    """Failed/partial cards sort before successful, each tier
    newest-first. Capture-bucket terminal cards come from the
    `failed/` and `inbox/` subdirs (per the kanban-bucket model)."""
    # Three failed/partial cards with distinct mtimes; one successful
    # capture card.
    _seed(music_root / "failed", "fail-old",
          payload=_base_source("fail-old", partial=True, rip_success=False),
          mtime=1_700_000_000)
    _seed(music_root / "failed", "fail-new",
          payload=_base_source("fail-new", partial=True, rip_success=False),
          mtime=1_700_002_000)
    _seed(music_root / "failed", "fail-mid",
          payload=_base_source("fail-mid", partial=True, rip_success=False),
          mtime=1_700_001_000)
    _seed(music_root / "inbox", "ok-new",
          payload=_base_source("ok-new", rip_success=True),
          mtime=1_700_003_000)

    state = build_kanban_state(music_root, loop_state=None)
    names = [c.folder for c in state.buckets["capture"]]
    # Damaged tier newest-first, then successful tier newest-first.
    assert names == ["fail-new", "fail-mid", "fail-old", "ok-new"]


# ============== (b) Beets-ID bucket newest-first ========================


def test_beets_id_bucket_sorts_newest_first(music_root: Path) -> None:
    """Beets-ID cards are the (currently empty) middle bucket; sort
    is newest-first. Seed via inbox folders carrying a marker the
    builder treats as beets-ID-in-flight (READY but no PROCESSING)
    — when there are no such markers the bucket is empty."""
    # No cards: sorted newest-first is trivially [].
    state = build_kanban_state(music_root, loop_state=None)
    assert state.buckets["beets_id"] == []


# ============== (c) Review bucket: priority then newest =================


def test_review_bucket_sorts_by_priority_then_mtime(
    music_root: Path,
) -> None:
    """Priority order (lowest enum value first):
        PARTIAL (0) → WEAK_MATCH (1) → NO_MATCH (2) → NO_ID_NO_TAGS (3)
    """
    # PARTIAL: status.partial=True
    _seed(music_root / "review", "rev-partial",
          payload=_base_source("rev-partial", partial=True),
          mtime=1_700_000_000)
    # WEAK_MATCH: beets-import.log has weak score
    _seed(music_root / "review", "rev-weak",
          payload=_base_source(
              "rev-weak", beets_review_reason="weak match: score 0.32",
          ),
          mtime=1_700_002_000)
    # NO_MATCH: beets-import.log says no candidates
    _seed(music_root / "review", "rev-nomatch",
          payload=_base_source(
              "rev-nomatch", beets_review_reason="beets returned no candidates",
          ),
          mtime=1_700_003_000)
    # NO_ID_NO_TAGS: no disc-id captured
    _seed(music_root / "review", "rev-noid",
          payload=_base_source("rev-noid", disc_id=None),
          mtime=1_700_004_000)

    state = build_kanban_state(music_root, loop_state=None)
    names = [c.folder for c in state.buckets["review"]]
    assert names == ["rev-partial", "rev-weak", "rev-nomatch", "rev-noid"]


def test_review_bucket_priority_breaks_ties_with_mtime(
    music_root: Path,
) -> None:
    """Two NO_MATCH cards — newer surfaces first inside the priority
    tier."""
    _seed(music_root / "review", "nm-old",
          payload=_base_source(
              "nm-old", beets_review_reason="beets returned no candidates",
          ),
          mtime=1_700_000_000)
    _seed(music_root / "review", "nm-new",
          payload=_base_source(
              "nm-new", beets_review_reason="beets returned no candidates",
          ),
          mtime=1_700_002_000)

    names = [c.folder for c in build_kanban_state(music_root).buckets["review"]]
    assert names == ["nm-new", "nm-old"]


# ============== (d) Library bucket newest-first =========================


def test_library_bucket_sorts_newest_first(music_root: Path) -> None:
    _seed(music_root / "library" / "ArtA", "AlbA",
          mtime=1_700_000_000)
    _seed(music_root / "library" / "ArtB", "AlbB",
          mtime=1_700_002_000)
    _seed(music_root / "library" / "ArtC", "AlbC",
          mtime=1_700_001_000)
    names = [
        c.folder for c in build_kanban_state(music_root).buckets["library"]
    ]
    assert names == ["AlbB", "AlbC", "AlbA"]


# ============== (e) ReviewPriority enum exposed to the UI ===============


def test_review_priority_enum_values_are_stable() -> None:
    """Enum order is contractual — the UI keys chip labels off it."""
    ReviewPriority = _review_priority()
    assert ReviewPriority.PARTIAL.value == 0
    assert ReviewPriority.WEAK_MATCH.value == 1
    assert ReviewPriority.NO_MATCH.value == 2
    assert ReviewPriority.NO_ID_NO_TAGS.value == 3


def test_review_card_carries_review_priority_attribute(
    music_root: Path,
) -> None:
    _seed(music_root / "review", "rev-1",
          payload=_base_source(
              "rev-1", beets_review_reason="weak match: score 0.32",
          ))
    ReviewPriority = _review_priority()
    card = build_kanban_state(music_root).buckets["review"][0]
    assert card.review_priority == ReviewPriority.WEAK_MATCH.value


def test_non_review_cards_have_null_review_priority(
    music_root: Path,
) -> None:
    _seed(music_root / "library" / "Art", "Alb")
    card = build_kanban_state(music_root).buckets["library"][0]
    assert card.review_priority is None
