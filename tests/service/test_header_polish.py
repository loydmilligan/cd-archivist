"""Failing tests for sprint-7 polish hotfix — header live-review feedback.

Two contracts pinned here:

1. **Single state indicator** (D-single-state-indicator). The legacy
   `.daemon-state-dot` (next to the cd-archivist slug) duplicates the
   signal carried by the `.live-status` chip. Sprint-7 polish removes
   the dot — daemon-up is implied by the page loading at all.

2. **Embiggened header** (live-review feedback). The header reads as a
   "dashboard quick view": header height 80px, brand mark at 36px,
   live-status dot 14px / text 16px, rig-stats value 20px+, so an
   operator across the room can read it without leaning in.

The matching impl lives in archivist/service/kanban_page.py + the
recipes in archivist/service/static/css/cda.css.
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


def _cda(client: TestClient) -> str:
    return client.get("/static/css/cda.css").text


# ============== (1) Single state indicator =============================
#
# D-single-state-indicator: only the live-status chip carries
# operational state. daemon-up is implied by page-load. The legacy
# .daemon-state-dot is removed from both the rendered HTML and the
# stylesheet.


def test_daemon_state_dot_removed_from_rendered_html(
    client: TestClient,
) -> None:
    html = client.get("/rip").text
    assert "daemon-state-dot" not in html, (
        "the legacy daemon-state-dot element must be removed; the "
        "live-status chip is the single state indicator per "
        "D-single-state-indicator"
    )


def test_daemon_state_dot_removed_from_cda_css(
    client: TestClient,
) -> None:
    cda = _cda(client)
    # The class name may appear in a `removed` comment but no active
    # rule block.
    rule_block = re.search(r"^\.daemon-state-dot\s*\{", cda, re.MULTILINE)
    assert rule_block is None, (
        "cda.css must not define an active .daemon-state-dot rule "
        "(D-single-state-indicator)"
    )


def test_live_status_chip_still_renders(client: TestClient) -> None:
    """The single remaining state indicator must still be present."""
    html = client.get("/rip").text
    assert 'class="live-status"' in html


# ============== (3) Embiggened header ==================================
#
# The header is now a dashboard quick view. Specific size knobs pinned:
# header padding scales to ~80px effective height; brand mark 36px;
# live-status dot 14px + text 16px; rig-stats value 20px+.


def test_page_header_height_bumped_to_80px(client: TestClient) -> None:
    """The page-header padding declares a min-height token.

    Sprint-7 embiggened to 80px ("dashboard quick view"). Sprint-11.1
    trimmed back to 56px after live-operator feedback that the header
    consumed disproportionate visual real estate on smaller viewports
    once the panel surface had real content to scroll through. The
    canonical band is now 56–80px — pinning a hard floor here keeps
    the header from collapsing to nothing in a future refactor."""
    cda = _cda(client)
    block = re.search(r"\.page-header\s*\{([^}]*)\}", cda, re.DOTALL)
    assert block is not None, "missing .page-header rule"
    body = block.group(1)
    assert "min-height" in body, (
        ".page-header must declare a min-height so the header reads "
        "as a dashboard quick view"
    )
    m = re.search(r"min-height\s*:\s*(\d+)px", body)
    assert m is not None, "expected .page-header min-height in px"
    assert 56 <= int(m.group(1)) <= 80, (
        f".page-header min-height is {m.group(1)}px; must be in the "
        f"56–80 band (sprint-7 embiggen + sprint-11.1 trim)"
    )


def test_brand_mark_header_variant_is_36px(client: TestClient) -> None:
    """.cda-brand-mark--header bumps from 22px → 36px. The chunky-
    extruded recipe in the base .cda-brand-mark stays intact; only
    the font-size scales (with matching stroke/extrude scale)."""
    cda = _cda(client)
    m = re.search(
        r"\.cda-brand-mark--header\s*\{([^}]*)\}", cda, re.DOTALL,
    )
    assert m is not None, "missing .cda-brand-mark--header rule"
    body = m.group(1)
    assert "font-size: 36px" in body, (
        ".cda-brand-mark--header must declare font-size: 36px "
        "per the live-review polish"
    )
    # Base recipe must still carry the chunky-extruded markers.
    base = re.search(r"\.cda-brand-mark\s*\{([^}]*)\}", cda, re.DOTALL)
    assert base is not None
    base_body = base.group(1)
    for marker in (
        "var(--font-display)", "font-weight: 800", "font-style: italic",
        "var(--mash-pulp)", "paint-order: stroke fill", "text-shadow",
    ):
        assert marker in base_body, (
            f".cda-brand-mark base recipe lost {marker!r}; the "
            "chunky-extruded recipe must be preserved when scaling sizes"
        )


def test_live_status_dot_is_14px(client: TestClient) -> None:
    cda = _cda(client)
    block = re.search(
        r"\.live-status\s+\.dot\s*\{([^}]*)\}", cda, re.DOTALL,
    )
    assert block is not None, "missing .live-status .dot rule"
    body = block.group(1)
    assert "width: 14px" in body and "height: 14px" in body, (
        ".live-status .dot must be 14px (was 8px) per the embiggen pass"
    )


def test_live_status_text_is_16px(client: TestClient) -> None:
    cda = _cda(client)
    block = re.search(
        r"\.live-status-text\s*\{([^}]*)\}", cda, re.DOTALL,
    )
    assert block is not None, "missing .live-status-text rule"
    body = block.group(1)
    # The font-shorthand form `font: 500 16px/1 ...` is accepted
    # alongside an explicit `font-size: 16px`.
    has_shorthand_16 = re.search(r"font\s*:\s*[^;]*\b16px\b", body)
    has_explicit_16 = re.search(r"font-size\s*:\s*16px", body)
    assert has_shorthand_16 or has_explicit_16, (
        ".live-status-text must declare 16px (was 12px) per the embiggen pass"
    )


def test_stat_value_is_at_least_20px(client: TestClient) -> None:
    cda = _cda(client)
    block = re.search(r"\.stat-value\s*\{([^}]*)\}", cda, re.DOTALL)
    assert block is not None, "missing .stat-value rule"
    body = block.group(1)
    m = re.search(r"font-size\s*:\s*(\d+)px", body)
    assert m is not None, ".stat-value missing an explicit px font-size"
    assert int(m.group(1)) >= 20, (
        f".stat-value font-size is {m.group(1)}px; the rig-stats numbers "
        "must read at >=20px so they scan as a dashboard quick view"
    )
