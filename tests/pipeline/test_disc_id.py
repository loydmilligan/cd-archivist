"""Failing tests for archivist.pipeline.disc_id.next_disc_id.

Implementation lands in Wave 2 (impl-disc-id). Until then these tests
fail at import.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from archivist.pipeline.disc_id import next_disc_id


def test_empty_root_returns_cd_0001(tmp_disc_root) -> None:
    root: Path = tmp_disc_root()
    assert next_disc_id(root) == "CD_0001"


def test_max_plus_one_ignoring_gaps(tmp_disc_root) -> None:
    root: Path = tmp_disc_root()
    (root / "CD_0001").mkdir()
    (root / "CD_0003").mkdir()
    (root / "CD_0007").mkdir()
    assert next_disc_id(root) == "CD_0008"


def test_ignores_non_cd_entries(tmp_disc_root) -> None:
    root: Path = tmp_disc_root()
    (root / "CD_0001").mkdir()
    (root / "scratch").mkdir()
    (root / "README.md").write_text("hello")
    (root / "CD_not_a_number").mkdir()
    (root / "cd_0099").mkdir()  # lowercase — should not count
    assert next_disc_id(root) == "CD_0002"


def test_atomic_under_concurrent_invocation(tmp_disc_root) -> None:
    """Two concurrent callers must each receive a distinct ID.

    The implementation guards `next_disc_id` with an exclusive lockfile
    (`.disc-id.lock` via `fcntl.flock`). Each caller must reserve its ID
    by creating the directory before releasing the lock — otherwise both
    threads would read the same max and return the same value.
    """
    root: Path = tmp_disc_root()

    def reserve() -> str:
        disc_id = next_disc_id(root)
        # Materialize the reservation inside whatever critical section
        # the impl provides; if the impl doesn't reserve, this race is
        # what the test is designed to catch.
        (root / disc_id).mkdir(exist_ok=True)
        return disc_id

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: reserve(), range(2)))

    assert len(set(results)) == 2, f"concurrent callers got duplicate IDs: {results}"
    assert set(results) == {"CD_0001", "CD_0002"}
