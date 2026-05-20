"""Sprint-9 / shell-route — failing tests for the Library Manager shell.

Covers:
  GET /              — redirects to /rip
  GET /rip           — kanban renders (existing behavior, new mount point)
  GET /library       — Library shell renders (landing viewport)
  GET /library/<v1>  — Library shell renders for v1 panel ids
  GET /library/<v2>  — 404 for v2 panel ids
  shared chassis     — rig-stats group identical across /rip and /library
  drawer idle copy   — verbatim "Select an item to see details."
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
        state_entered_at=datetime(2026, 5, 19, 12, 0, 0),
        last_tick_at=datetime(2026, 5, 19, 12, 0, 0),
    )


@pytest.fixture
def music_root(tmp_path: Path) -> Path:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    return inbox


@pytest.fixture
def client(loop_state, music_root, tmp_path: Path) -> TestClient:
    review = tmp_path / "review"
    review.mkdir()
    app = create_app(
        loop_state=loop_state,
        log_path=tmp_path / "pipeline.log",
        music_root=music_root,
        review_root=review,
        discs_root=music_root,
    )
    return TestClient(app)


def test_root_redirects_to_rip(client: TestClient) -> None:
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 200  # meta-refresh, not 3xx
    assert 'url=/rip' in resp.text


def test_rip_serves_kanban(client: TestClient) -> None:
    resp = client.get("/rip")
    assert resp.status_code == 200
    assert "cda-brand-mark" in resp.text


def test_library_landing_returns_200(client: TestClient) -> None:
    resp = client.get("/library")
    assert resp.status_code == 200
    assert '<body data-surface="library">' in resp.text


def test_library_v1_panels_return_200(client: TestClient) -> None:
    for panel_id in ("downloads", "inbox", "disk", "library"):
        resp = client.get(f"/library/{panel_id}")
        assert resp.status_code == 200, f"panel {panel_id} returned {resp.status_code}"


def test_library_v2_panels_return_404(client: TestClient) -> None:
    for panel_id in ("review", "recent", "cron"):
        resp = client.get(f"/library/{panel_id}")
        assert resp.status_code == 404, f"panel {panel_id} should 404; got {resp.status_code}"


def test_library_drawer_idle_copy(client: TestClient) -> None:
    resp = client.get("/library")
    assert "Select an item to see details." in resp.text


def test_shared_right_drawer_element_id(client: TestClient) -> None:
    # Build-prompt §5: the right drawer is the same DOM id across
    # surfaces so the chassis JS targets the same element.
    rip = client.get("/rip").text
    library = client.get("/library").text
    assert 'id="right-drawer"' in rip
    assert 'id="right-drawer"' in library


def test_shared_bottom_log_element_id(client: TestClient) -> None:
    # Build-prompt §5: bottom daemon log is the SAME element across
    # surfaces — not duplicated per surface.
    rip = client.get("/rip").text
    library = client.get("/library").text
    assert 'id="bottom-drawer"' in rip
    assert 'id="bottom-drawer"' in library
    assert 'id="bottom-drawer-log"' in rip
    assert 'id="bottom-drawer-log"' in library


def test_rig_stats_identical_across_surfaces(client: TestClient) -> None:
    # Build-prompt §2: "The five rig-stats cells stay identical on both
    # surfaces. Don't swap cells out when Library is active." We assert
    # the same cell count + the same cell labels.
    import re
    rip = client.get("/rip").text
    library = client.get("/library").text
    pattern = re.compile(r'class="[^"]*\brig-stat-label\b[^"]*"[^>]*>([^<]+)<')
    rip_labels = pattern.findall(rip)
    library_labels = pattern.findall(library)
    assert rip_labels == library_labels, (
        f"rig-stats labels diverge: rip={rip_labels} library={library_labels}"
    )
