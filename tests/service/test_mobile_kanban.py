"""Failing tests for the mobile bucket-tab fallback (sprint-6.5 C).

At narrow viewport (≤720px per the proposed D-mobile-breakpoint-v1),
the four columns collapse into a single column with a segmented
control above it to switch buckets. Tab selection persists in
localStorage.

We assert HTML / CSS / JS-source markers since pytest doesn't drive
a real viewport. Real-rig smoke (Wave 3) validates the visual.

Impl lands in Wave 2 (impl-mobile-bucket-tabs).
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


# ============== (a) bucket-tabs nav present + 720px breakpoint ==========


def test_bucket_tabs_nav_present_in_markup(client: TestClient) -> None:
    html = client.get("/rip").text
    assert 'class="bucket-tabs"' in html or "bucket-tabs" in html
    # Four tabs, one per bucket — pin the bucket labels.
    # Sprint-7 voice pass: "In Library" → "In library" (sentence case).
    for label in ("Capture", "Beets ID", "Review", "In library"):
        assert label in html


def test_mobile_breakpoint_is_720px(client: TestClient) -> None:
    """D-mobile-breakpoint-v1 proposes max-width: 720px. Sprint-7 /
    impl-css-migration moved the @media rule from the inline <style>
    block to /static/css/cda.css (and hard-coded 720px there — see
    D-inline-css-whitelist + the impl-css-migration-brand-mark commit
    message)."""
    cda = client.get("/static/css/cda.css").text
    assert "max-width: 720px" in cda or "max-width:720px" in cda


# ============== (b) tab selection persists in localStorage ==============


def test_bucket_tab_state_persists_in_localstorage(
    client: TestClient,
) -> None:
    html = client.get("/rip").text
    assert "cd-archivist:mobile-bucket" in html


# ============== (c) default tab is Capture ==============================


def test_default_mobile_bucket_is_capture(client: TestClient) -> None:
    html = client.get("/rip").text
    # Pin a discoverable marker — the impl's JS module-scope default
    # value or a data attribute on the tab control.
    assert 'data-default-bucket="capture"' in html or (
        'data-bucket="capture"' in html and 'selected' in html.lower()
    )
