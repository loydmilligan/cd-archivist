"""Failing tests for canonical-disc-photo selection (sprint-4).

Per D-canonical-disc-photo:

  - `select_canonical_photo(captures_dir) -> Path | None` picks
    `disc_front_lit_002.jpg` (middle of 3 lit frames) if present;
    falls back to any other lit; returns None if no lit captures.
  - `copy_canonical_photo(disc_dir) -> Path | None` calls the
    selector, copies the chosen file to `<disc_dir>/disc-photo.jpg`,
    returns the new path (or None).

Both helpers live in `archivist/pipeline/capture.py` next to
`capture_disc`. Supplemental frames stay in `captures/` (NOT moved).

Impl lands in Wave 2 (impl-canonical-photo).
"""
from __future__ import annotations

from pathlib import Path

import pytest


def _seed_captures(captures_dir: Path, names: list[str]) -> None:
    captures_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        (captures_dir / name).write_bytes(b"\xff\xd8" + name.encode() + b"\xff\xd9")


# -------- (a) middle lit frame is chosen when all 6 exist ------------


def test_select_picks_middle_lit_when_all_present(tmp_path: Path) -> None:
    from archivist.pipeline.capture import select_canonical_photo

    captures = tmp_path / "captures"
    _seed_captures(captures, [
        "disc_front_ambient_001.jpg",
        "disc_front_ambient_002.jpg",
        "disc_front_ambient_003.jpg",
        "disc_front_lit_001.jpg",
        "disc_front_lit_002.jpg",
        "disc_front_lit_003.jpg",
    ])

    chosen = select_canonical_photo(captures)
    assert chosen is not None
    assert chosen.name == "disc_front_lit_002.jpg"


# -------- (b) fallback to any other lit when middle missing ----------


def test_select_falls_back_when_middle_missing(tmp_path: Path) -> None:
    from archivist.pipeline.capture import select_canonical_photo

    captures = tmp_path / "captures"
    _seed_captures(captures, [
        "disc_front_ambient_001.jpg",
        # only one lit, and it's not the canonical middle
        "disc_front_lit_000.jpg",
    ])

    chosen = select_canonical_photo(captures)
    assert chosen is not None
    assert chosen.name == "disc_front_lit_000.jpg"


# -------- (c) no lit frames → None ----------------------------------


def test_select_returns_none_when_no_lit(tmp_path: Path) -> None:
    from archivist.pipeline.capture import select_canonical_photo

    captures = tmp_path / "captures"
    _seed_captures(captures, [
        "disc_front_ambient_001.jpg",
        "disc_front_ambient_002.jpg",
    ])

    assert select_canonical_photo(captures) is None


def test_select_returns_none_when_captures_dir_missing(tmp_path: Path) -> None:
    from archivist.pipeline.capture import select_canonical_photo

    # No captures dir at all.
    assert select_canonical_photo(tmp_path / "captures") is None


# -------- (d) copy_canonical_photo writes byte-equal disc-photo.jpg --


def test_copy_writes_byte_equal_to_source(tmp_path: Path) -> None:
    from archivist.pipeline.capture import copy_canonical_photo

    disc_dir = tmp_path / "2026-05-14_1832_disc-000001"
    captures = disc_dir / "captures"
    _seed_captures(captures, [
        "disc_front_lit_001.jpg",
        "disc_front_lit_002.jpg",
        "disc_front_lit_003.jpg",
    ])

    result = copy_canonical_photo(disc_dir)
    assert result is not None
    assert result == disc_dir / "disc-photo.jpg"
    assert result.read_bytes() == (captures / "disc_front_lit_002.jpg").read_bytes()


# -------- (e) supplemental captures NOT moved -----------------------


def test_copy_leaves_supplemental_captures_in_place(tmp_path: Path) -> None:
    from archivist.pipeline.capture import copy_canonical_photo

    disc_dir = tmp_path / "disc1"
    captures = disc_dir / "captures"
    names = [
        "disc_front_ambient_001.jpg",
        "disc_front_ambient_002.jpg",
        "disc_front_ambient_003.jpg",
        "disc_front_lit_001.jpg",
        "disc_front_lit_002.jpg",
        "disc_front_lit_003.jpg",
    ]
    _seed_captures(captures, names)

    copy_canonical_photo(disc_dir)

    # All 6 originals still present.
    for n in names:
        assert (captures / n).is_file(), f"{n} was moved/deleted"


# -------- (f) idempotent — second call produces same disc-photo.jpg --


def test_copy_is_idempotent(tmp_path: Path) -> None:
    from archivist.pipeline.capture import copy_canonical_photo

    disc_dir = tmp_path / "disc1"
    captures = disc_dir / "captures"
    _seed_captures(captures, [
        "disc_front_lit_001.jpg",
        "disc_front_lit_002.jpg",
        "disc_front_lit_003.jpg",
    ])

    first = copy_canonical_photo(disc_dir)
    assert first is not None
    first_bytes = first.read_bytes()
    second = copy_canonical_photo(disc_dir)
    assert second == first
    assert second.read_bytes() == first_bytes


# -------- (g) copy returns None when no lit available ---------------


def test_copy_returns_none_and_writes_nothing_when_no_lit(tmp_path: Path) -> None:
    from archivist.pipeline.capture import copy_canonical_photo

    disc_dir = tmp_path / "disc1"
    captures = disc_dir / "captures"
    _seed_captures(captures, [
        "disc_front_ambient_001.jpg",
    ])

    assert copy_canonical_photo(disc_dir) is None
    assert not (disc_dir / "disc-photo.jpg").exists()
