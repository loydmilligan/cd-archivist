"""Sprint-9 / sidebar-panels — Library Manager sidebar tests."""
from __future__ import annotations

import re

from archivist.service.library_sidebar import render_sidebar


def test_renders_four_group_labels_in_order() -> None:
    html = render_sidebar()
    pos_queues = html.find('cda-lib-side-group">Queues')
    pos_health = html.find('cda-lib-side-group">Health')
    pos_browse = html.find('cda-lib-side-group">Browse')
    pos_coming = html.find('cda-lib-side-group">Coming · v2')
    assert pos_queues != -1
    assert pos_health != -1
    assert pos_browse != -1
    assert pos_coming != -1
    assert pos_queues < pos_health < pos_browse < pos_coming


def test_v1_panels_render_as_anchors() -> None:
    html = render_sidebar()
    for panel_id in ("downloads", "inbox", "disk", "library"):
        assert f'href="/library/{panel_id}"' in html, f"missing v1 anchor for {panel_id}"


def test_v2_ghosts_render_as_non_anchor_disabled() -> None:
    html = render_sidebar()
    # v2 entries: NOT anchors, carry aria-disabled, render `soon` chip
    for panel_id in ("review", "recent", "cron"):
        assert f'href="/library/{panel_id}"' not in html, (
            f"v2 panel {panel_id} should not be an anchor"
        )
        assert f'data-panel-id="{panel_id}"' in html
    # exactly three .is-ghost rows
    assert len(re.findall(r'class="[^"]*\bis-ghost\b', html)) == 3
    # exactly three `soon` chips
    assert html.count('<span class="soon">soon</span>') == 3
    # aria-disabled on each ghost
    assert html.count('aria-disabled="true"') == 3


def test_active_panel_id_marks_one_row_active() -> None:
    html = render_sidebar(active_panel_id="inbox")
    # exactly one is-active row
    is_active_matches = re.findall(r'class="[^"]*\bis-active\b', html)
    assert len(is_active_matches) == 1
    # and it's the inbox anchor
    inbox_match = re.search(
        r'<a[^>]*class="[^"]*\bis-active\b[^"]*"[^>]*data-panel-id="inbox"',
        html,
    )
    assert inbox_match is not None


def test_no_active_when_active_panel_id_is_none() -> None:
    html = render_sidebar(active_panel_id=None)
    assert "is-active" not in html


def test_active_panel_id_on_ghost_does_not_mark_active() -> None:
    # Defensive: even if a v2 id is passed, ghost rows never go active.
    html = render_sidebar(active_panel_id="review")
    assert "is-active" not in html


def test_per_row_sub_lines_render() -> None:
    html = render_sidebar()
    expected_subs = {
        "downloads": "spooty queue",
        "inbox": "cd rips · downloads",
        "disk": "usage",
        "library": "browse + jump",
    }
    for sub in expected_subs.values():
        assert sub in html, f"missing sub-line: {sub}"


def test_count_badge_renders_only_when_count_is_set() -> None:
    html = render_sidebar()
    # Downloads (count=1) and Inbox (count=3) have count badges; Disk
    # and Library do not.
    assert '<span class="count">1</span>' in html
    assert '<span class="count">3</span>' in html
    # Exactly two count badges total in the sidebar.
    assert html.count('class="count"') == 2
