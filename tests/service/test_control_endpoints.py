"""Failing tests for /api/control/* manual-mode endpoints (sprint-4 / D-manual-mode).

New endpoints on the FastAPI surface:

  POST /api/control/mode?mode=auto|manual
  POST /api/control/start-rip
  POST /api/control/eject
  POST /api/control/capture
  POST /api/control/reset

Per the decision log:
  - mode toggle: 200 / 400 on garbage
  - state triggers in manual mode: 200 / 409 on state mismatch
  - state triggers in auto mode: 403 (manual-only)
  - reset is always allowed (operator escape hatch)
  - /api/status includes `mode: "auto"|"manual"`

Impl lands in Wave 2 (impl-manual-mode-endpoints).
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from archivist.service.app import LoopState, create_app


@pytest.fixture
def loop_state() -> LoopState:
    return LoopState()


@pytest.fixture
def client(loop_state: LoopState, tmp_path: Path) -> TestClient:
    log = tmp_path / "archivist.log"
    log.write_text("")
    return TestClient(create_app(loop_state, log))


# -------- (a) mode flip to manual -----------------------------------


def test_mode_flip_to_manual(client: TestClient, loop_state: LoopState) -> None:
    resp = client.post("/api/control/mode?mode=manual")
    assert resp.status_code == 200, resp.text
    assert loop_state.mode == "manual"


# -------- (b) mode flip back to auto --------------------------------


def test_mode_flip_to_auto(client: TestClient, loop_state: LoopState) -> None:
    loop_state.mode = "manual"
    resp = client.post("/api/control/mode?mode=auto")
    assert resp.status_code == 200, resp.text
    assert loop_state.mode == "auto"


# -------- (c) mode=garbage → 400 ------------------------------------


def test_mode_invalid_value_400(client: TestClient) -> None:
    resp = client.post("/api/control/mode?mode=banana")
    assert resp.status_code == 400


# -------- (d) start-rip in manual + STABILIZE advances --------------


def test_start_rip_in_manual_stabilize_advances(
    client: TestClient, loop_state: LoopState,
) -> None:
    loop_state.mode = "manual"
    loop_state.state = "STABILIZE"
    resp = client.post("/api/control/start-rip")
    assert resp.status_code == 200, resp.text


# -------- (e) start-rip in manual + IDLE → 409 ----------------------


def test_start_rip_in_manual_idle_409(
    client: TestClient, loop_state: LoopState,
) -> None:
    loop_state.mode = "manual"
    loop_state.state = "IDLE"
    resp = client.post("/api/control/start-rip")
    assert resp.status_code == 409


# -------- (f) start-rip in auto mode → 403 --------------------------


def test_state_triggers_403_when_mode_is_auto(
    client: TestClient, loop_state: LoopState,
) -> None:
    loop_state.mode = "auto"
    loop_state.state = "STABILIZE"
    resp = client.post("/api/control/start-rip")
    assert resp.status_code == 403, (
        "manual-only trigger must be refused in auto mode"
    )


def test_eject_403_in_auto(client: TestClient, loop_state: LoopState) -> None:
    loop_state.mode = "auto"
    loop_state.state = "RIP"
    assert client.post("/api/control/eject").status_code == 403


def test_capture_403_in_auto(client: TestClient, loop_state: LoopState) -> None:
    loop_state.mode = "auto"
    loop_state.state = "EJECT"
    assert client.post("/api/control/capture").status_code == 403


# -------- (g) reset works in either mode + any state ----------------


def test_reset_works_in_any_mode_and_state(
    client: TestClient, loop_state: LoopState,
) -> None:
    for mode in ("auto", "manual"):
        for state in ("IDLE", "STABILIZE", "RIP", "EJECT", "CAPTURE", "ERROR"):
            loop_state.mode = mode
            loop_state.state = state
            resp = client.post("/api/control/reset")
            assert resp.status_code == 200, (
                f"reset must always be allowed; failed at mode={mode} state={state}"
            )


# -------- (h) /api/status includes `mode` ---------------------------


def test_status_response_includes_mode(client: TestClient, loop_state: LoopState) -> None:
    loop_state.mode = "manual"
    body = client.get("/api/status").json()
    assert "mode" in body
    assert body["mode"] == "manual"

    loop_state.mode = "auto"
    body = client.get("/api/status").json()
    assert body["mode"] == "auto"
