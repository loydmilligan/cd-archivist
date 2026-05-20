"""Sprint-9 / panel-placeholder — per-panel viewport tests."""
from __future__ import annotations

import pytest

from archivist.service.library_panels import render_panel


@pytest.mark.parametrize(
    "panel_id,eyebrow,title",
    [
        ("downloads", "Downloads · spooty queue", "Spotify → YouTube"),
        ("inbox", "Inbox queue", "Albums waiting to import"),
        ("disk", "Disk usage", "Where the bytes live"),
        ("library", "Library", "Browse · jump to Navidrome"),
    ],
)
def test_v1_panel_header_copy(panel_id: str, eyebrow: str, title: str) -> None:
    html = render_panel(panel_id)
    assert f'<span class="eyebrow">{eyebrow}</span>' in html
    assert f'<h1>{title}</h1>' in html


def test_placeholder_carries_three_ghost_rows() -> None:
    html = render_panel("downloads")
    assert html.count("ghost row · ghost row · ghost row") == 3


def test_placeholder_carries_in_design_tag_and_foot_copy() -> None:
    html = render_panel("inbox")
    assert '<span class="tag">in design</span>' in html
    assert "UX is intentionally undecided in this pass." in html


def test_panel_dashed_container_class_present() -> None:
    # The dashed-border placeholder class is the CSS hook.
    html = render_panel("disk")
    assert 'class="cda-lib-panel-empty"' in html


def test_unknown_v2_id_raises_key_error() -> None:
    # The route handler is responsible for 404'ing v2 ids before
    # calling render_panel. If a v2 id slips through, we raise rather
    # than render to surface the bug loudly. (v2 ids ARE in the
    # inventory so BY_ID lookup succeeds — covered separately.)
    # Truly unknown ids must raise.
    with pytest.raises(KeyError):
        render_panel("nonexistent-id")
