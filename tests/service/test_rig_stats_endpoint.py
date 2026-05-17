"""Failing tests for GET /api/rig/stats (sprint-7 Bucket E lane-3).

Contract:
  {
    "storage": {"used_bytes": int, "total_bytes": int,
                "human": "26.4 GB / 64.0 GB"},
    "uptime":  {"seconds": int, "human": "1d 22h"}
  }

Storage derives from shutil.disk_usage(music_root). Uptime derives
from a module-init time.monotonic timestamp captured at app.py
import time. Human strings follow the build-prompt mono-shorthand
rules ("26.4 GB / 64.0 GB", "1d 22h", "47m", etc.).

Impl lands in Wave 2 (impl-rig-stats-endpoint).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from archivist.service.app import LoopState, create_app


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


# ============== (a) response shape =====================================


def test_rig_stats_response_shape(client: TestClient) -> None:
    res = client.get("/api/rig/stats")
    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body.keys()) >= {"storage", "uptime"}
    storage = body["storage"]
    assert set(storage.keys()) >= {"used_bytes", "total_bytes", "human"}
    assert isinstance(storage["used_bytes"], int)
    assert isinstance(storage["total_bytes"], int)
    assert isinstance(storage["human"], str)
    uptime = body["uptime"]
    assert set(uptime.keys()) >= {"seconds", "human"}
    assert isinstance(uptime["seconds"], int)
    assert isinstance(uptime["human"], str)


# ============== (b) storage derived from shutil.disk_usage(music_root) ==


def test_storage_values_match_shutil_disk_usage(
    client: TestClient, music_root: Path,
) -> None:
    import shutil

    expected = shutil.disk_usage(music_root)
    body = client.get("/api/rig/stats").json()
    # Drive total is stable across the test call; used drifts a hair.
    # The endpoint MUST be reporting the music_root drive, not "/".
    assert body["storage"]["total_bytes"] == expected.total
    # Allow a small skew on used since other tests may write tmp files.
    assert abs(body["storage"]["used_bytes"] - expected.used) < 50 * 1024 * 1024


# ============== (c) uptime via monotonic — non-negative + grows ========


def test_uptime_seconds_non_negative_and_monotonic(
    client: TestClient,
) -> None:
    import time

    first = client.get("/api/rig/stats").json()["uptime"]["seconds"]
    assert first >= 0
    time.sleep(1.1)
    second = client.get("/api/rig/stats").json()["uptime"]["seconds"]
    assert second >= first
    # The uptime is bounded reasonably; can't be a giant unix-epoch number.
    assert second < 60 * 60 * 24 * 365  # < 1 year


# ============== (d) human strings follow mono-shorthand format =========


_STORAGE_HUMAN_RE = re.compile(
    r"^\d+(?:\.\d+)?\s?(?:B|KB|MB|GB|TB)\s/\s\d+(?:\.\d+)?\s?(?:B|KB|MB|GB|TB)$"
)
_UPTIME_HUMAN_RE = re.compile(
    r"^(?:\d+d\s\d+h|\d+h\s\d+m|\d+m|\d+s)$"
)


def test_storage_human_matches_mono_shorthand(client: TestClient) -> None:
    human = client.get("/api/rig/stats").json()["storage"]["human"]
    assert _STORAGE_HUMAN_RE.match(human), (
        f"storage.human {human!r} does not match expected format "
        f"'X.X GB / Y.Y GB'"
    )


def test_uptime_human_matches_mono_shorthand(client: TestClient) -> None:
    human = client.get("/api/rig/stats").json()["uptime"]["human"]
    assert _UPTIME_HUMAN_RE.match(human), (
        f"uptime.human {human!r} does not match one of "
        f"'Nd Nh', 'Nh Nm', 'Nm', 'Ns'"
    )
