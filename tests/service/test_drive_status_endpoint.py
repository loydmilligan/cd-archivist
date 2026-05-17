"""Failing tests for GET /api/drive/status (sprint-6.5 Bucket D).

Pipeline-side endpoint that reads from `loop_state.drive_status`
(populated by drivers' impl-drive-status-snapshot in Bucket F).
This test file covers the endpoint contract; drivers' Bucket F
tests cover the snapshot dataclass + thread-safety.

For Wave 1 we synthesise a DriveStatus-like object on LoopState
via setattr so the endpoint can be exercised without depending on
drivers' Wave 2 landing.

Impl lands in Wave 2 (impl-drive-status-endpoint).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pytest
from fastapi.testclient import TestClient

from archivist.service.app import LoopState, create_app


@dataclass
class _FakeDriveStatus:
    """Stand-in matching the field set drivers' real DriveStatus will
    ship. Drivers' Wave 2 lands the canonical dataclass; the endpoint
    just JSON-dumps whatever shape is attached."""

    state: str = "idle"
    current_disc: Optional[str] = None
    current_track: Optional[int] = None
    track_total: Optional[int] = None
    sector_current: Optional[int] = None
    sector_total: Optional[int] = None
    retries_on_current_track: Optional[int] = None
    photo_state: Optional[str] = None
    elapsed_seconds: Optional[float] = None


@pytest.fixture
def music_root(tmp_path: Path) -> Path:
    root = tmp_path / "music"
    for sub in ("inbox", "review", "library", "archive", "failed"):
        (root / sub).mkdir(parents=True)
    return root


@pytest.fixture
def loop_state() -> LoopState:
    state = LoopState()
    # Drivers' Bucket F adds `drive_status` to LoopState; until then
    # the endpoint impl must fall back to a default-idle snapshot
    # when the attribute is missing. The two tests below cover both
    # paths (attribute present + absent).
    return state


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


# ============== (a) contract shape ======================================


_REQUIRED_FIELDS = {
    "state", "current_disc", "current_track", "track_total",
    "sector_current", "sector_total", "retries_on_current_track",
    "photo_state", "elapsed_seconds",
}


def test_drive_status_response_carries_all_contract_fields(
    client: TestClient, loop_state: LoopState,
) -> None:
    loop_state.drive_status = _FakeDriveStatus(  # type: ignore[attr-defined]
        state="ripping",
        current_disc="2026-05-16_1408_disc-000123",
        current_track=7, track_total=13,
        sector_current=132481, sector_total=238224,
        retries_on_current_track=2,
        photo_state="done",
        elapsed_seconds=242.5,
    )
    body = client.get("/api/drive/status").json()
    assert set(body.keys()) >= _REQUIRED_FIELDS
    assert body["state"] == "ripping"
    assert body["current_disc"] == "2026-05-16_1408_disc-000123"
    assert body["current_track"] == 7
    assert body["track_total"] == 13
    assert body["sector_current"] == 132481
    assert body["sector_total"] == 238224
    assert body["retries_on_current_track"] == 2
    assert body["photo_state"] == "done"
    assert body["elapsed_seconds"] == pytest.approx(242.5)


# ============== (b) default-idle when state is idle =====================


def test_drive_status_idle_returns_nulls_for_transients(
    client: TestClient, loop_state: LoopState,
) -> None:
    loop_state.drive_status = _FakeDriveStatus(state="idle")  # type: ignore[attr-defined]
    body = client.get("/api/drive/status").json()
    assert body["state"] == "idle"
    for field_name in _REQUIRED_FIELDS - {"state"}:
        assert body[field_name] is None, (
            f"{field_name} must be None when state=='idle'"
        )


def test_drive_status_idle_when_attribute_missing(
    client: TestClient,
) -> None:
    """Drivers' Wave 2 lands `LoopState.drive_status`. Until then the
    endpoint must return a default-idle snapshot rather than
    500-ing."""
    body = client.get("/api/drive/status").json()
    assert body["state"] == "idle"


# ============== (c) state value enum ===================================


@pytest.mark.parametrize("state_value", [
    "idle", "ripping", "stabilizing", "capturing",
])
def test_drive_status_state_values_round_trip(
    client: TestClient, loop_state: LoopState, state_value: str,
) -> None:
    loop_state.drive_status = _FakeDriveStatus(state=state_value)  # type: ignore[attr-defined]
    body = client.get("/api/drive/status").json()
    assert body["state"] == state_value
