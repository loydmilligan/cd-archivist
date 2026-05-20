"""Library Manager — landing card grid.

Sprint-9 / landing-grid per
docs/reference/mashco-design-system/cd-archivist-library/handoff/build-prompt.md §2.

Renders the four v1 panel cards (each with a hint-shape preview) plus
the three v2 ghost cards beneath. Card clicks navigate to
`/library/{panelId}`.
"""

from __future__ import annotations

import html as _html

from archivist.service.library_panel_inventory import (
    GHOSTS,
    PRIMARY,
    PanelSpec,
)


def _downloads_preview() -> str:
    # 24 pips, mostly ok, one active, one error — matches the JSX preview.
    pips = []
    for i in range(24):
        cls = "cda-prev-pl-pip"
        if i < 18:
            cls += " is-ok"
        elif i == 18:
            cls += " is-active"
        elif i == 22:
            cls += " is-err"
        pips.append(f'<span class="{cls}"></span>')
    return (
        '<div class="cda-lib-card-preview cda-lib-card-preview--pip-strip">'
        '<div class="cda-prev-pl-row">'
        '<span>liked songs · 47 tracks</span>'
        '<span class="cda-prev-pl-progress">32/47</span>'
        '</div>'
        f'<div class="cda-prev-pl-pips">{"".join(pips)}</div>'
        '</div>'
    )


def _inbox_preview() -> str:
    rows = [
        ("Wilco · A Ghost Is Born", "421 MB", True),
        ("Aimee Mann · Bachelor No. 2", "312 MB", False),
        ("spooty/ Caribou playlist", "128 MB", True),
    ]
    items = "".join(
        '<div class="cda-prev-inbox-row">'
        f'<span><span class="name">{_html.escape(name)}</span></span>'
        f'<span class="size">{_html.escape(size)}</span>'
        f'{"<span class=\"ready\">ready</span>" if ready else "<span class=\"cda-prev-inbox-dash\">—</span>"}'
        '</div>'
        for name, size, ready in rows
    )
    return (
        '<div class="cda-lib-card-preview cda-lib-card-preview--inbox-rows">'
        f'{items}'
        '</div>'
    )


def _disk_preview() -> str:
    rows = [
        ("/", 44, ""),
        ("/mnt/seagate", 23, ""),
        ("/mnt/archive", 78, "is-amber"),
    ]
    items = "".join(
        '<div class="cda-prev-disk-row">'
        f'<span class="mount">{_html.escape(mount)}</span>'
        f'<span class="bar"><i class="{_html.escape(cls)}" style="width:{pct}%"></i></span>'
        f'<span class="val">{pct}%</span>'
        '</div>'
        for mount, pct, cls in rows
    )
    return (
        '<div class="cda-lib-card-preview cda-lib-card-preview--usage-bars cda-prev-disk">'
        f'{items}'
        '</div>'
    )


def _library_preview() -> str:
    recent = [
        ("Tom Waits · Mule Variations", "14m"),
        ("Miles Davis · Kind of Blue", "1h"),
        ("Big Thief · Two Hands", "2d"),
    ]
    items = "".join(
        '<div class="cda-prev-lib-row">'
        '<span class="cda-prev-lib-thumb"></span>'
        f'<span class="name">{_html.escape(name)}</span>'
        f'<span class="when">{_html.escape(when)}</span>'
        '</div>'
        for name, when in recent
    )
    return (
        '<div class="cda-lib-card-preview cda-lib-card-preview--recent-list">'
        f'{items}'
        '</div>'
    )


def _ghost_preview() -> str:
    return (
        '<div class="cda-lib-card-preview cda-lib-card-preview--ghost">'
        '<span class="cda-prev-ghost-line"></span>'
        '<span class="cda-prev-ghost-line is-mid"></span>'
        '<span class="cda-prev-ghost-line is-short"></span>'
        '</div>'
    )


_PREVIEW_BY_ID = {
    "downloads": _downloads_preview,
    "inbox": _inbox_preview,
    "disk": _disk_preview,
    "library": _library_preview,
}


def _card(spec: PanelSpec, *, ghost: bool) -> str:
    classes = ["cda-lib-card"]
    if ghost:
        classes.append("is-ghost")
    class_attr = " ".join(classes)

    soon_chip = (
        '<span class="cda-lib-card-soon">soon · v2</span>' if ghost else ""
    )
    preview_fn = _ghost_preview if ghost else _PREVIEW_BY_ID[spec["id"]]
    preview_html = preview_fn()

    # v1 cards are anchor-wrapped so card-clicks navigate.
    inner = (
        '<header class="cda-lib-card-head">'
        f'<span class="cda-lib-card-eyebrow">{_html.escape(spec["eyebrow"])}</span>'
        f'{soon_chip}'
        '</header>'
        f'<h3 class="cda-lib-card-title">{_html.escape(spec["title"])}</h3>'
        f'<p class="cda-lib-card-sub">{_html.escape(spec["summary"])}</p>'
        f'{preview_html}'
    )

    if ghost:
        return (
            f'<article class="{class_attr}" aria-disabled="true" '
            f'data-panel-id="{_html.escape(spec["id"])}">'
            f'{inner}'
            '</article>'
        )

    return (
        f'<a class="{class_attr}" href="/library/{_html.escape(spec["id"])}" '
        f'data-panel-id="{_html.escape(spec["id"])}">'
        f'{inner}'
        '</a>'
    )


def render_landing_grid() -> str:
    """Render the landing viewport: header + 4 v1 cards + 3 v2 ghost cards."""
    v1_cards = "".join(_card(p, ghost=False) for p in PRIMARY)
    v2_cards = "".join(_card(p, ghost=True) for p in GHOSTS)
    return (
        '<section class="cda-lib-viewport">'
        '<div class="cda-lib-panel">'
        '<header class="cda-lib-landing-h">'
        '<p class="eyebrow">Library manager · cm4 music stack</p>'
        '<h1>The post-rip side of the rig</h1>'
        '<p>'
        'Queues, disk, scheduled jobs, library browse. Four panels live '
        'now, three coming. Pick one from the menu on the left or start '
        'with a card below.'
        '</p>'
        '</header>'
        '<div class="cda-lib-landing-grid">'
        f'{v1_cards}'
        f'{v2_cards}'
        '</div>'
        '</div>'
        '</section>'
    )
