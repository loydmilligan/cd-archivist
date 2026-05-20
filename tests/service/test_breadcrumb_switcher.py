"""Sprint-9 / breadcrumb-switcher — surface picker tests."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from archivist.service.app import LoopState, create_app
from archivist.service.library_switcher import render_switcher


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
def client(loop_state, tmp_path: Path) -> TestClient:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    review = tmp_path / "review"
    review.mkdir()
    app = create_app(
        loop_state=loop_state,
        log_path=tmp_path / "pipeline.log",
        music_root=inbox,
        review_root=review,
        discs_root=inbox,
    )
    return TestClient(app)


# ---- render_switcher unit tests ----------------------------------------------


def test_switcher_carries_brand_mark_and_separator() -> None:
    html = render_switcher(active="rip")
    assert 'cda-brand-mark cda-brand-mark--header' in html
    assert 'cda-switcher-sep' in html


def test_switcher_button_label_matches_active_surface() -> None:
    rip_html = render_switcher(active="rip")
    lib_html = render_switcher(active="library")
    # button text contains the active label
    rip_btn = re.search(r'class="cda-switcher-btn"[^>]*>([^<]+)<', rip_html)
    lib_btn = re.search(r'class="cda-switcher-btn"[^>]*>([^<]+)<', lib_html)
    assert rip_btn and "rip" in rip_btn.group(1)
    assert lib_btn and "library" in lib_btn.group(1)


def test_switcher_marks_active_row_with_is_on() -> None:
    html = render_switcher(active="rip")
    # exactly one is-on row
    matches = re.findall(r'class="cda-switcher-row\s+is-on"', html)
    assert len(matches) == 1
    # and that row is the rip row
    assert re.search(
        r'class="cda-switcher-row\s+is-on"[^>]*data-surface="rip"', html
    )


def test_switcher_rows_link_to_surface_roots() -> None:
    html = render_switcher(active="library")
    assert 'href="/rip"' in html
    assert 'href="/library"' in html


def test_switcher_telemetry_renders_in_meta_spans() -> None:
    html = render_switcher(
        active="rip", rip_telemetry="4 ripping · 2 review",
        library_telemetry="3 inbox · 1 download",
    )
    assert '<span class="meta">4 ripping · 2 review</span>' in html
    assert '<span class="meta">3 inbox · 1 download</span>' in html


def test_switcher_dropdown_starts_collapsed() -> None:
    html = render_switcher(active="rip")
    # The popover must carry the `hidden` attribute on initial render
    # (the inline JS removes it when the button is clicked).
    assert re.search(r'id="surface-switcher-pop"[^>]*hidden', html)
    # button aria-expanded is false
    assert 'aria-expanded="false"' in html


def test_switcher_rejects_unknown_active_surface() -> None:
    with pytest.raises(ValueError):
        render_switcher(active="nonsense")


# ---- integration: switcher renders on both /rip and /library ----------------


def test_switcher_present_on_rip_with_rip_active(client: TestClient) -> None:
    html = client.get("/rip").text
    assert 'data-surface-switcher' in html
    # rip row marked is-on
    assert re.search(
        r'class="cda-switcher-row\s+is-on"[^>]*data-surface="rip"', html
    )


def test_switcher_present_on_library_with_library_active(client: TestClient) -> None:
    html = client.get("/library").text
    assert 'data-surface-switcher' in html
    assert re.search(
        r'class="cda-switcher-row\s+is-on"[^>]*data-surface="library"', html
    )


def test_switcher_js_injected_on_both_surfaces(client: TestClient) -> None:
    # Inline JS that wires the dropdown toggle. Same string both sides.
    needle = "data-surface-switcher"  # JS queries this attr
    rip_html = client.get("/rip").text
    lib_html = client.get("/library").text
    # The JS body contains the IIFE for the toggle handler.
    assert "data-switcher-toggle" in rip_html
    assert "data-switcher-toggle" in lib_html
    # The CSS-selector hook appears in both pages (one in the switcher
    # DOM, one in the IIFE).
    assert rip_html.count(needle) >= 2
    assert lib_html.count(needle) >= 2


def test_legacy_inline_brand_mark_replaced_by_switcher(client: TestClient) -> None:
    # The old bare brand-mark span (without switcher wrapper) must NOT
    # appear on /rip — the switcher's brand mark is the new canonical.
    # We check by counting cda-brand-mark--header occurrences: exactly
    # one (inside the switcher), not two (legacy + new).
    html = client.get("/rip").text
    assert html.count('cda-brand-mark cda-brand-mark--header') == 1
