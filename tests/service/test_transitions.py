"""Failing tests for card transitions + live-update flash
(sprint-7 Bucket F, lane-2).

Per the build prompt §"Live updates — polling cadence":

    Cards entering a new column should fade-in (200ms `--ease-out`).
    Cards leaving fade out then remove. Track segments fill smoothly
    — no "step animation" on the segment progress.

    When something is "live updating", flash a 200ms `var(--moss)`
    border, then fade. Don't slide.

Impl lands in Wave 2 (impl-transitions). The CSS keyframes live in
cda.css (lane-1 vendored); the kanban-page JS module adds the
classes on diff.
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


def _read_cda_css() -> str:
    path = Path(__file__).resolve().parents[2] / (
        "archivist/service/static/css/cda.css"
    )
    if not path.is_file():
        pytest.fail(
            f"cda.css not found at {path} — lane-1 impl-asset-wire-up "
            "must land first"
        )
    return path.read_text(encoding="utf-8")


# ============== (a) .card--entering with fadeIn ========================


def test_card_entering_class_defined_with_fade_in(client: TestClient) -> None:
    css = _read_cda_css()
    assert ".card--entering" in css
    # animation: fadeIn 200ms var(--ease-out)
    pat = re.compile(
        r"\.card--entering\b[^{]*\{[^}]*animation:\s*fadeIn\s+200ms[^}]*\}",
        re.S,
    )
    assert pat.search(css), (
        "expected `.card--entering { ... animation: fadeIn 200ms ... }` "
        "in cda.css"
    )
    # The fadeIn keyframes must also exist.
    assert "@keyframes fadeIn" in css


def test_card_entering_uses_ease_out_timing(client: TestClient) -> None:
    css = _read_cda_css()
    pat = re.compile(
        r"\.card--entering\b[^{]*\{[^}]*var\(--ease-out\)[^}]*\}", re.S,
    )
    assert pat.search(css)


# ============== (b) .card--leaving with fadeOut ========================


def test_card_leaving_class_defined_with_fade_out(client: TestClient) -> None:
    css = _read_cda_css()
    assert ".card--leaving" in css
    pat = re.compile(
        r"\.card--leaving\b[^{]*\{[^}]*animation:\s*fadeOut\s+200ms[^}]*\}",
        re.S,
    )
    assert pat.search(css), (
        "expected `.card--leaving { ... animation: fadeOut 200ms ... }` "
        "in cda.css"
    )
    assert "@keyframes fadeOut" in css


# ============== (c) .flash-moss with moss-border pulse =================


def test_flash_moss_class_defined(client: TestClient) -> None:
    css = _read_cda_css()
    assert ".flash-moss" in css


def test_flash_moss_uses_moss_token_in_keyframes(client: TestClient) -> None:
    """Build prompt: 200ms `var(--moss)` border flash, then fade.
    Style via a box-shadow keyframe that references the moss token."""
    css = _read_cda_css()
    # Either an inline animation declaration on .flash-moss that
    # references the moss token, OR a named keyframes block (e.g.
    # @keyframes flash-moss) whose body uses var(--moss).
    direct = re.compile(
        r"\.flash-moss\b[^{]*\{[^}]*var\(--moss\)[^}]*\}", re.S,
    )
    kf = re.compile(
        r"@keyframes\s+(?:flash[_-]?moss|flashMoss)\b[^{]*\{[^}]*"
        r"var\(--moss\)[^}]*\}",
        re.S,
    )
    assert direct.search(css) or kf.search(css), (
        "expected .flash-moss (or its @keyframes) to reference "
        "var(--moss) in cda.css"
    )


# ============== (d) kanban JS adds entering/flash classes on diff ======


def test_kanban_js_adds_card_entering_to_new_cards(
    client: TestClient,
) -> None:
    """The inline JS poll handler diffs each kanban response against
    the previous and adds `.card--entering` to cards that did not
    exist last cycle."""
    html = client.get("/rip").text
    assert "card--entering" in html


def test_kanban_js_adds_flash_moss_to_changed_cards(
    client: TestClient,
) -> None:
    """`.flash-moss` lands on cards whose source.json hash (or
    equivalent diff key) changed since the previous poll."""
    html = client.get("/rip").text
    assert "flash-moss" in html


def test_kanban_js_removes_leaving_cards_after_animation(
    client: TestClient,
) -> None:
    """`.card--leaving` lands on cards present last cycle but absent
    this cycle; the JS removes them from the DOM after the 200ms
    animation completes."""
    html = client.get("/rip").text
    assert "card--leaving" in html
