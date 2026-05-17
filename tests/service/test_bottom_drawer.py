"""Failing tests for the bottom log drawer (sprint-6.5 Bucket C).

Bottom drawer holds the global daemon-log tail (K1.1-B in the
brainstorm). Collapsed default (~32px just the toggle bar);
expanded ~240px tailing /api/logs/tail at the kanban poll cadence.
Drawer state persists in localStorage.

Impl lands in Wave 2 (impl-bottom-drawer).
"""
from __future__ import annotations

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


# ============== (a) drawer element with collapsed default ===============


def test_bottom_drawer_element_exists_with_default_hidden(
    client: TestClient,
) -> None:
    html = client.get("/").text
    assert 'id="bottom-drawer"' in html
    # Default aria-hidden="true" — collapsed by default.
    assert 'aria-hidden="true"' in html


def test_bottom_drawer_slide_up_uses_css_transform(
    client: TestClient,
) -> None:
    html = client.get("/").text
    assert "bottom-drawer" in html
    assert "transform" in html


# ============== (b) tails /api/logs/tail when expanded ==================


def test_bottom_drawer_references_logs_tail_endpoint(
    client: TestClient,
) -> None:
    html = client.get("/").text
    assert "/api/logs/tail" in html
    # Default tail size: 200 lines per the test-logs-tail-endpoint
    # contract (matches the plan).
    assert "limit=200" in html


def test_bottom_drawer_body_uses_pre_element(
    client: TestClient,
) -> None:
    """Tail content renders inside a <pre> so formatting (and the
    monospace voice) is preserved."""
    html = client.get("/").text
    # The drawer body markup includes a <pre> (id or class observable).
    assert "<pre" in html
    # Pinned to the drawer scope so it's clear which <pre>.
    assert "bottom-drawer" in html


# ============== (c) localStorage persistence ============================


def test_bottom_drawer_state_persists_in_localstorage(
    client: TestClient,
) -> None:
    """The JS reads/writes localStorage under
    'cd-archivist:bottom-drawer:open' to remember the drawer state
    across reloads."""
    html = client.get("/").text
    assert "localStorage" in html
    assert "cd-archivist:bottom-drawer:open" in html
