"""Failing tests for the new disc folder naming scheme (sprint-4).

Per D-folder-naming-migration: new folders are named
`YYYY-MM-DD_HHMM_disc-NNNNNN` (local time, 24-hour, 6-digit
zero-padded monotonic counter). The counter scans inbox folder names
matching the new shape and ignores legacy `CD_NNNN/`.

Helper: `archivist/pipeline/folder_name.py::next_disc_folder_name(
    inbox_root, *, now=None
) -> str`.

Impl lands in Wave 2 (impl-folder-naming).
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pytest


# -------- (a) empty inbox + injected now -----------------------------


def test_empty_inbox_returns_counter_one() -> None:
    from archivist.pipeline.folder_name import next_disc_folder_name

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        inbox = Path(td)
        now = datetime(2026, 5, 14, 18, 32, 0)
        name = next_disc_folder_name(inbox, now=now)
        assert name == "2026-05-14_1832_disc-000001"


# -------- (b) inbox with existing high counter ----------------------


def test_counter_increments_from_highest_existing(tmp_path: Path) -> None:
    from archivist.pipeline.folder_name import next_disc_folder_name

    (tmp_path / "2026-05-13_0900_disc-000420").mkdir()
    (tmp_path / "2026-05-12_1100_disc-000100").mkdir()
    now = datetime(2026, 5, 14, 9, 5, 0)
    name = next_disc_folder_name(tmp_path, now=now)
    assert name == "2026-05-14_0905_disc-000421"


# -------- (c) legacy CD_NNNN folders ignored ------------------------


def test_legacy_folders_do_not_contribute_to_counter(tmp_path: Path) -> None:
    from archivist.pipeline.folder_name import next_disc_folder_name

    (tmp_path / "CD_0018").mkdir()
    (tmp_path / "CD_9999").mkdir()
    now = datetime(2026, 5, 14, 12, 0, 0)
    name = next_disc_folder_name(tmp_path, now=now)
    # Counter starts at 1; legacy folders don't bump it.
    assert name == "2026-05-14_1200_disc-000001"


# -------- (d) 24-hour local time, no AM/PM, no Z ---------------------


def test_24_hour_format_no_ampm_no_utc_suffix(tmp_path: Path) -> None:
    from archivist.pipeline.folder_name import next_disc_folder_name

    now = datetime(2026, 5, 14, 23, 59, 0)  # 11:59 PM
    name = next_disc_folder_name(tmp_path, now=now)
    assert "_2359_" in name
    assert "AM" not in name.upper()
    assert "PM" not in name.upper()
    assert "Z" not in name


# -------- (e) safe characters only (no spaces, no metacharacters) ----


def test_safe_characters_only(tmp_path: Path) -> None:
    from archivist.pipeline.folder_name import next_disc_folder_name

    name = next_disc_folder_name(tmp_path, now=datetime(2026, 5, 14, 12, 0))
    assert " " not in name
    # No shell metacharacters.
    for ch in ('"', "'", "$", "`", "|", "&", ";", "(", ")", "<", ">"):
        assert ch not in name
    # Conformance with the documented regex.
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{4}_disc-\d{6}", name)


# -------- (f) collision guard — bump counter if the name exists ------


def test_collision_guard_bumps_counter(tmp_path: Path) -> None:
    from archivist.pipeline.folder_name import next_disc_folder_name

    # Pre-create the folder the algorithm would otherwise pick.
    (tmp_path / "2026-05-14_1200_disc-000001").mkdir()
    name = next_disc_folder_name(tmp_path, now=datetime(2026, 5, 14, 12, 0, 0))
    # Must bump past the colliding name.
    assert name == "2026-05-14_1200_disc-000002"


# -------- (g) legacy `next_disc_id` still works (regression) ---------


def test_legacy_next_disc_id_still_available(tmp_path: Path) -> None:
    """The legacy CD_NNNN allocator stays available for the legacy path."""
    from archivist.pipeline.disc_id import next_disc_id

    disc_id = next_disc_id(tmp_path)
    assert disc_id == "CD_0001"
    assert (tmp_path / "CD_0001").is_dir()


# -------- (h) returned name is not actually created on disk ----------


def test_next_disc_folder_name_does_not_create_directory(tmp_path: Path) -> None:
    """The naming helper is pure — directory creation is the caller's job.

    (Distinct from `next_disc_id`, which mkdir-s as part of reservation.
    folder_name is the name-only helper; the working_dir-handoff path
    does the mkdir.)
    """
    from archivist.pipeline.folder_name import next_disc_folder_name

    name = next_disc_folder_name(tmp_path, now=datetime(2026, 5, 14, 12, 0, 0))
    assert not (tmp_path / name).exists()


# -------- (i) default `now` uses current local time ------------------


def test_now_defaults_to_local_time(tmp_path: Path) -> None:
    """When `now=None`, the helper resolves to local time."""
    from archivist.pipeline.folder_name import next_disc_folder_name

    name = next_disc_folder_name(tmp_path)
    # Shape conformance regardless of when the test runs.
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{4}_disc-\d{6}", name)
