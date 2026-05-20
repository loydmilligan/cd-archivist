"""Sprint-9 / landing-grid — Library Manager landing card grid tests."""
from __future__ import annotations

import re

from archivist.service.library_landing import render_landing_grid


def test_renders_four_v1_card_anchors() -> None:
    html = render_landing_grid()
    for panel_id in ("downloads", "inbox", "disk", "library"):
        # each v1 card is an anchor to /library/{id}
        match = re.search(
            rf'<a class="cda-lib-card[^"]*"[^>]*href="/library/{panel_id}"',
            html,
        )
        assert match is not None, f"missing v1 anchor card for {panel_id}"


def test_renders_three_v2_ghost_cards() -> None:
    html = render_landing_grid()
    ghosts = re.findall(r'class="cda-lib-card is-ghost"', html)
    assert len(ghosts) == 3
    # ghost cards carry the "soon · v2" chip
    assert html.count('cda-lib-card-soon">soon · v2</span>') == 3
    # ghost cards have aria-disabled
    assert html.count('aria-disabled="true"') >= 3


def test_v2_ghosts_are_not_anchors() -> None:
    html = render_landing_grid()
    for panel_id in ("review", "recent", "cron"):
        # not an <a> with href to that panel; rendered as <article>
        assert f'<a class="cda-lib-card is-ghost" href="/library/{panel_id}"' not in html


def test_each_v1_card_carries_preview_shape() -> None:
    html = render_landing_grid()
    # Build-prompt §2 named hints. Each v1 card carries a preview-shape
    # class so the per-panel hint is identifiable from the DOM.
    assert 'cda-lib-card-preview--pip-strip' in html       # downloads
    assert 'cda-lib-card-preview--inbox-rows' in html      # inbox
    assert 'cda-lib-card-preview--usage-bars' in html      # disk
    assert 'cda-lib-card-preview--recent-list' in html     # library


def test_eyebrow_title_and_sub_present_for_v1_cards() -> None:
    html = render_landing_grid()
    expected = [
        ("Downloads · spooty queue", "Spotify → YouTube"),
        ("Inbox queue", "Albums waiting to import"),
        ("Disk usage", "Where the bytes live"),
        ("Library", "Browse · jump to Navidrome"),
    ]
    for eyebrow, title in expected:
        assert eyebrow in html, f"missing eyebrow: {eyebrow}"
        assert title in html, f"missing title: {title}"


def test_landing_header_copy_present() -> None:
    html = render_landing_grid()
    assert "Library manager · cm4 music stack" in html
    assert "The post-rip side of the rig" in html


def test_disk_preview_amber_bar_marks_high_usage() -> None:
    # Build-prompt §3 disk decision: 60-85% → amber. The mocked
    # /mnt/archive at 78% must carry the amber class.
    html = render_landing_grid()
    assert 'class="is-amber"' in html
