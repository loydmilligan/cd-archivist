"""Failing tests for archivist.service.app — FastAPI status surface.

Covers (this file, test-service-status):
  GET /api/status — JSON snapshot of LoopState
  GET /api/log    — text/plain tail of pipeline log

test-service-ui adds GET / (HTML page) tests below in a separate commit.

Impl lands in Wave 2 (impl-service). LoopState lives in
archivist.service.app (or a sibling state.py — author's call; tests
import from the top-level package).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from archivist.service.app import LoopState, create_app


@pytest.fixture
def loop_state() -> LoopState:
    return LoopState(
        state="IDLE",
        disc_id=None,
        last_rip_status=None,
        last_updated=datetime(2026, 5, 14, 12, 0, 0),
    )


@pytest.fixture
def log_path(tmp_path: Path) -> Path:
    p = tmp_path / "archivist.log"
    p.write_text("\n".join(f"line {i}" for i in range(1, 501)) + "\n")
    return p


# -------------------------- /api/status -------------------------------


def test_api_status_returns_loop_state_snapshot(loop_state: LoopState, log_path: Path) -> None:
    client = TestClient(create_app(loop_state, log_path))
    resp = client.get("/api/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "IDLE"
    assert body["disc_id"] is None
    assert body["last_rip_status"] is None
    assert "last_updated" in body


def test_api_status_reflects_live_updates(loop_state: LoopState, log_path: Path) -> None:
    """Mutating loop_state between calls must surface — no stale caching."""
    client = TestClient(create_app(loop_state, log_path))
    assert client.get("/api/status").json()["state"] == "IDLE"

    loop_state.state = "RIP"
    loop_state.disc_id = "CD_0001"
    loop_state.last_rip_status = "success"

    body = client.get("/api/status").json()
    assert body["state"] == "RIP"
    assert body["disc_id"] == "CD_0001"
    assert body["last_rip_status"] == "success"


# -------------------------- /api/log ----------------------------------


def test_api_log_default_tails_200_lines(loop_state: LoopState, log_path: Path) -> None:
    client = TestClient(create_app(loop_state, log_path))
    resp = client.get("/api/log")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    lines = [ln for ln in resp.text.splitlines() if ln]
    assert len(lines) == 200
    assert lines[0] == "line 301"
    assert lines[-1] == "line 500"


def test_api_log_lines_param_capped_at_1000(loop_state: LoopState, log_path: Path) -> None:
    client = TestClient(create_app(loop_state, log_path))
    # Ask for far more than the cap.
    resp = client.get("/api/log", params={"lines": 100000})
    assert resp.status_code == 200
    lines = [ln for ln in resp.text.splitlines() if ln]
    # Cap is 1000; log only has 500 → all 500 returned (not 100000).
    assert len(lines) == 500


def test_api_log_missing_file_returns_empty_200(loop_state: LoopState, tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.log"
    client = TestClient(create_app(loop_state, missing))
    resp = client.get("/api/log")
    assert resp.status_code == 200
    assert resp.text == ""
