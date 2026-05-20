"""Library Manager surface — `/library` shell.

Sprint-9 shell-only scope per
docs/reference/mashco-design-system/cd-archivist-library/handoff/build-prompt.md.

This module renders the chassis (shared header · sidebar slot · viewport ·
right-drawer idle · bottom-log mount) plus a viewport that delegates to:
- `library_landing.render_landing_grid` when no panel is selected
- `library_panels.render_panel` for a v1 panel id
- the lane-2 modules — not yet written; this module renders an empty
  viewport until those land.

Sidebar markup is delegated to `library_sidebar.render_sidebar` (lane-2).
"""

from __future__ import annotations

import os
from pathlib import Path

from archivist.service.disc_card_builder import build_kanban_state
from archivist.service.kanban_page import (
    _render_bottom_drawer,
    _render_header_bar,
    _stats,
)

V1_PANEL_IDS: tuple[str, ...] = ("downloads", "inbox", "disk", "library")


def _switcher_js() -> str:
    """Lazy switcher-JS lookup; mirrors kanban_page._switcher_js."""
    from archivist.service.library_switcher import SWITCHER_JS
    return SWITCHER_JS


def _render_library_right_drawer() -> str:
    """Library shell's right drawer idle state.

    Per build-prompt §5, every Library route in sprint-9 renders the
    same idle copy. Per-panel drawer modes come in follow-up briefs.
    Same DOM id as kanban's drawer (`right-drawer`) so the shared
    chassis JS targets the same element across surfaces.
    """
    return (
        '<aside id="right-drawer" class="drawer drawer--right" '
        'aria-hidden="true">'
        '<div class="drawer-head">'
        '<button type="button" class="drawer-close" '
        'aria-controls="right-drawer" aria-label="close drawer">'
        '×'
        '</button>'
        '</div>'
        '<div class="drawer-body" data-drawer-template="library-idle">'
        '<p class="meta">Select an item to see details.</p>'
        '</div>'
        '</aside>'
    )


def render_library_page(
    music_root: Path,
    loop_state,
    *,
    panel_id: str | None = None,
) -> str:
    """Render the Library Manager shell.

    `panel_id` is None for the landing grid; one of V1_PANEL_IDS for a
    selected panel. v2 panel ids (`review`, `recent`, `cron`) are not
    addressable yet — the route handler 404s before calling this.
    """
    state = build_kanban_state(music_root, loop_state=loop_state)
    cards_flat = [c for cards in state.buckets.values() for c in cards]
    stats = _stats(state.buckets, cards_flat)
    capture = state.buckets.get("capture", [])
    active_card = next((c for c in capture if c.progress is not None), None)
    active_rip = active_card is not None
    active_disc = active_card.disc_id if active_card else None
    links = {
        "navidrome": os.environ.get("NAVIDROME_URL", ""),
        "beets_web": os.environ.get("BEETS_WEB_URL", ""),
    }

    # Sprint-9 / breadcrumb-switcher telemetry — same shape as kanban.
    # Rip-side: live `N ripping · M review`. Library-side: placeholder
    # per build-prompt §2 (per-panel briefs revisit).
    rip_telemetry = (
        f'{"1" if active_rip else "0"} ripping · {stats["review"]} review'
    )
    library_telemetry = "3 inbox · 1 download"

    # Lane-2 module imports are lazy + tolerated-missing so this shell
    # can land independently. Once lane-2's modules ship, these become
    # eager imports at module top.
    try:
        from archivist.service.library_sidebar import render_sidebar
        sidebar_html = render_sidebar(active_panel_id=panel_id)
    except ImportError:
        sidebar_html = (
            '<aside class="cda-lib-sidebar" data-stub="sidebar-pending">'
            '<p class="meta">sidebar — pending lane-2</p>'
            '</aside>'
        )

    if panel_id is None:
        try:
            from archivist.service.library_landing import render_landing_grid
            viewport_html = render_landing_grid()
        except ImportError:
            viewport_html = (
                '<section class="cda-lib-viewport" '
                'data-stub="landing-grid-pending">'
                '<p class="meta">landing card grid — pending lane-2</p>'
                '</section>'
            )
    else:
        try:
            from archivist.service.library_panels import render_panel
            viewport_html = render_panel(panel_id)
        except ImportError:
            viewport_html = (
                '<section class="cda-lib-viewport" '
                f'data-stub="panel-{panel_id}-pending">'
                f'<p class="meta">panel {panel_id} — pending lane-2</p>'
                '</section>'
            )

    return (
        '<!doctype html>'
        '<html lang="en" data-theme="dark">'
        '<head>'
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>cd-archivist · library</title>'
        '<link rel="icon" type="image/png" sizes="32x32" '
        'href="/static/img/brand/cd-a-favicon-32x32.png">'
        '<link rel="icon" type="image/png" sizes="64x64" '
        'href="/static/img/brand/cd-a-favicon-64x64.png">'
        '<link rel="icon" type="image/png" sizes="256x256" '
        'href="/static/img/brand/cd-a-favicon-256x256.png">'
        '<link rel="apple-touch-icon" sizes="180x180" '
        'href="/static/img/brand/cd-a-apple-touch-180.png">'
        '<link rel="manifest" href="/static/manifest.webmanifest">'
        '<meta name="theme-color" content="#07090c">'
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link rel="stylesheet" '
        'href="https://fonts.googleapis.com/css2'
        '?family=Bricolage+Grotesque:wght@600;800&display=swap">'
        '<link rel="stylesheet" '
        'href="https://fonts.googleapis.com/css2'
        '?family=Inter+Tight:wght@400;500;700&display=swap">'
        '<link rel="stylesheet" '
        'href="https://fonts.googleapis.com/css2'
        '?family=JetBrains+Mono:wght@400;500&display=swap">'
        '<link rel="stylesheet" href="/static/css/tokens.css">'
        '<link rel="stylesheet" href="/static/css/cda.css">'
        '<link rel="stylesheet" href="/static/css/library.css">'
        '</head>'
        '<body data-surface="library">'
        f'{_render_header_bar(stats, links, active_rip=active_rip, active_disc=active_disc, active_surface="library", rip_telemetry=rip_telemetry, library_telemetry=library_telemetry)}'
        '<main class="cda-lib-main">'
        f'{sidebar_html}'
        f'{viewport_html}'
        '</main>'
        f'{_render_library_right_drawer()}'
        f'{_render_bottom_drawer()}'
        f'<script>{_switcher_js()}</script>'
        '</body></html>'
    )
