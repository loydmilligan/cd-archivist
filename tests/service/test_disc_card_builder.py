"""Failing tests for the kanban disc-card builder (sprint-6 Bucket B).

Covers test-disc-card-builder. Module under test:
`archivist.service.disc_card_builder`. Per D-card-data-source the
builder walks the music root for terminal-state cards (Review /
Library / Archive) and layers the active rip from `LoopState` as
a Capture-bucket card.

Per-track bar state map (D-kanban-buckets-v1 derivative):
    success     → green
    fail        → red
    in_progress → blue
    pending     → empty

Impl lands in Wave 2 (impl-disc-card-builder).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# These imports MUST fail in Wave 1 (module doesn't exist yet) — that's
# the failing-test contract for impl-disc-card-builder.
from archivist.service.disc_card_builder import (  # noqa: E402
    DiscCard,
    KanbanState,
    build_kanban_state,
    track_bar_from_counts,
)
from archivist.service.app import LoopState


# ---------------- fixtures ------------------------------------------------


def _write_flac(path: Path, n_bytes: int = 1024) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fLaC" + b"\x00" * n_bytes)


def _base_source_json(folder_name: str, *, track_count: int = 2) -> dict:
    return {
        "schema_version": 1,
        "ripper": {"name": "cd-archivist", "version": "0.1.0", "host": "cm4"},
        "disc": {
            "folder_name": folder_name,
            "disc_counter": 1,
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
            "musicbrainz_disc_id": "abc-disc-id",
            "freedb_disc_id": None, "cd_toc": None, "upc": None, "isrcs": [],
        },
        "detected_metadata": {
            "album_artist": None, "album": None, "year": None,
            "label": None, "catalog_number": None, "tracks": [],
        },
        "physical_disc": {
            "photo": "captures/disc-photo.jpg", "photo_captured": True,
            "photo_captured_at": "2026-05-16T10:00:05-07:00",
            "photo_device": "/dev/video0",
            "photo_notes": None, "label_text_guess": None,
            "appears_burned": None, "handwritten": None,
        },
        "files": [],
        "status": {
            "rip_success": True, "photo_success": True, "ready": True,
            "warnings": [], "errors": [],
        },
    }


def _write_source(folder: Path, payload: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "source.json").write_text(json.dumps(payload))


@pytest.fixture
def music_root(tmp_path: Path) -> Path:
    root = tmp_path / "music"
    for sub in ("inbox", "review", "library", "archive", "failed"):
        (root / sub).mkdir(parents=True)
    return root


# ---------------- (a) directory walk → buckets ----------------------------


def test_walks_review_folder_into_review_bucket(music_root: Path) -> None:
    folder = music_root / "review" / "2026-05-16_1200_disc-000001"
    _write_flac(folder / "01.flac")
    _write_source(folder, _base_source_json(folder.name))

    state = build_kanban_state(music_root, loop_state=None)

    assert isinstance(state, KanbanState)
    cards = state.buckets["review"]
    assert len(cards) == 1
    card = cards[0]
    assert isinstance(card, DiscCard)
    assert card.folder == folder.name
    assert card.bucket == "review"
    assert card.archived is False


def test_walks_library_album_into_library_bucket(music_root: Path) -> None:
    folder = music_root / "library" / "Foo Artist" / "Foo Album"
    _write_flac(folder / "01.flac")
    _write_source(folder, _base_source_json("Foo Artist - Foo Album"))

    state = build_kanban_state(music_root, loop_state=None)

    library_cards = state.buckets["library"]
    assert len(library_cards) == 1
    assert library_cards[0].bucket == "library"
    assert library_cards[0].archived is False


def test_walks_archive_folder_into_library_bucket_archived(
    music_root: Path,
) -> None:
    folder = music_root / "archive" / "CD_0007"
    _write_flac(folder / "01.flac")
    _write_source(folder, _base_source_json("CD_0007"))

    state = build_kanban_state(music_root, loop_state=None)

    library_cards = state.buckets["library"]
    assert len(library_cards) == 1
    assert library_cards[0].archived is True


# ---------------- (b) source.json field plumbing --------------------------


def test_card_fields_derived_from_source_json(music_root: Path) -> None:
    folder = music_root / "review" / "2026-05-16_1200_disc-000002"
    _write_flac(folder / "01.flac")
    _write_flac(folder / "02.flac")
    payload = _base_source_json(folder.name, track_count=2)
    _write_source(folder, payload)

    state = build_kanban_state(music_root, loop_state=None)
    card = state.buckets["review"][0]

    assert card.source_json is not None
    assert card.source_json["audio"]["track_count"] == 2
    # disc-id surfaced from source.json identifiers
    assert card.disc_id == "abc-disc-id"
    # photo_path is the relative path under the disc folder
    assert card.photo_path is not None
    assert card.photo_path.endswith("disc-photo.jpg")
    # timestamps surfaced as ISO strings (or datetimes — pinning the keys)
    assert card.rip_started_at is not None
    assert card.rip_finished_at is not None


def test_card_without_source_json_still_renders(music_root: Path) -> None:
    """Legacy CD_NNNN folders may have manifest.json instead of source.json.
    The card builder must not crash; source_json is None."""
    folder = music_root / "archive" / "CD_0042"
    _write_flac(folder / "01.flac")
    # No source.json on disk.

    state = build_kanban_state(music_root, loop_state=None)
    card = next(
        c for c in state.buckets["library"] if c.folder.endswith("CD_0042")
    )
    assert card.source_json is None
    assert card.archived is True


# ---------------- (c) LoopState overlay → Capture bucket ------------------


def test_active_rip_overlays_as_capture_card(music_root: Path) -> None:
    """When LoopState.state == 'RIP' the active disc must surface as a
    Capture-bucket card with the in-flight rip progress."""
    loop_state = LoopState()
    loop_state.state = "RIP"
    loop_state.disc_id = "disc-000099"
    loop_state.rip_progress = "track 3/10 (32%)"

    state = build_kanban_state(music_root, loop_state=loop_state)

    capture_cards = state.buckets["capture"]
    assert len(capture_cards) == 1
    card = capture_cards[0]
    assert card.bucket == "capture"
    assert card.disc_id == "disc-000099"
    assert card.progress is not None
    # Progress carries percent + current_stage label per kanban-api spec.
    assert card.progress["percent"] == 32
    assert "track 3" in card.progress["current_stage"]


def test_no_active_rip_means_empty_capture_bucket(music_root: Path) -> None:
    loop_state = LoopState()  # IDLE
    state = build_kanban_state(music_root, loop_state=loop_state)
    assert state.buckets["capture"] == []


def test_loop_state_none_means_empty_capture_bucket(music_root: Path) -> None:
    state = build_kanban_state(music_root, loop_state=None)
    assert state.buckets["capture"] == []


# ---------------- (d) per-track bar color map -----------------------------


def test_track_bar_from_counts_maps_states_to_colors() -> None:
    """track_bar_from_counts(successful, failed, in_progress_idx, total)
    returns a list[TrackState] (str labels) of length `total`.

    Layout: [success]*len(successful) before [in_progress?] before
    [pending]*remaining. `failed` indices override to 'fail' regardless
    of position. Color map is enforced downstream in CSS — the builder
    just emits the state labels."""
    # 10-track disc, tracks 1..5 succeeded, track 6 in progress, 7..10 pending.
    bar = track_bar_from_counts(
        total=10,
        successful=[1, 2, 3, 4, 5],
        failed=[],
        in_progress=6,
    )
    assert bar == [
        "success", "success", "success", "success", "success",
        "in_progress",
        "pending", "pending", "pending", "pending",
    ]


def test_track_bar_failed_tracks_override() -> None:
    bar = track_bar_from_counts(
        total=4,
        successful=[1, 2, 4],
        failed=[3],
        in_progress=None,
    )
    assert bar == ["success", "success", "fail", "success"]


def test_track_bar_all_pending_when_no_progress() -> None:
    bar = track_bar_from_counts(
        total=3, successful=[], failed=[], in_progress=None,
    )
    assert bar == ["pending", "pending", "pending"]


# ============== test-fix-phantom-audio (sprint-6.5 Bucket A) ==============
#
# Regression-pin the bug observed live on cda.mattmariani.com on
# 2026-05-16: build_kanban_state walked into each disc folder's
# `audio/` (and `captures/`, `logs/`, `review/`) subdirectory and
# treated them as their own disc folders. Every real disc surfaced
# 4-5 times.


def _seed_full_disc_layout(parent: Path, name: str) -> Path:
    """Mirror the production on-disk layout for one disc."""
    folder = parent / name
    (folder / "audio").mkdir(parents=True)
    (folder / "captures").mkdir()
    (folder / "logs").mkdir()
    (folder / "review").mkdir()
    _write_flac(folder / "audio" / "track01.flac")
    _write_flac(folder / "audio" / "track02.flac")
    (folder / "captures" / "disc-photo.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    (folder / "logs" / "rip.log").write_text("ok\n")
    (folder / "review" / ".gitkeep").write_text("")
    _write_source(folder, _base_source_json(name, track_count=2))
    return folder


def test_full_disc_layout_produces_exactly_one_card(music_root: Path) -> None:
    folder = _seed_full_disc_layout(
        music_root / "review", "2026-05-16_1408_disc-000123",
    )
    state = build_kanban_state(music_root, loop_state=None)
    review_cards = state.buckets["review"]
    assert len(review_cards) == 1, (
        f"expected exactly one card; got {len(review_cards)}: "
        f"{[c.folder for c in review_cards]}"
    )
    assert review_cards[0].folder == folder.name


def test_subdirs_audio_captures_logs_review_not_treated_as_discs(
    music_root: Path,
) -> None:
    """The four well-known disc-internal subdirs must never surface as
    cards in their own right — neither when source.json exists at the
    parent nor when it doesn't."""
    _seed_full_disc_layout(music_root / "review", "disc-α")
    state = build_kanban_state(music_root, loop_state=None)
    names = {c.folder for c in state.buckets["review"]}
    for forbidden in ("audio", "captures", "logs", "review"):
        assert forbidden not in names, (
            f"subdir name {forbidden!r} leaked into kanban as a card"
        )


def test_card_audio_count_reflects_flac_count_not_subdir_count(
    music_root: Path,
) -> None:
    """The card's per-track bar (audio count) must come from .flac
    files under the disc folder, not from a recursive count of
    subdirectories."""
    folder = _seed_full_disc_layout(
        music_root / "review", "disc-β",
    )
    # Add a third flac so the count is unambiguous (3, not 2/4/etc.).
    _write_flac(folder / "audio" / "track03.flac")
    payload = json.loads((folder / "source.json").read_text())
    payload["audio"]["track_count"] = 0  # force the flac-fallback path
    (folder / "source.json").write_text(json.dumps(payload))

    state = build_kanban_state(music_root, loop_state=None)
    card = state.buckets["review"][0]
    # Length of the per-track bar is the audio count (flac fallback).
    assert len(card.track_bar) == 3
