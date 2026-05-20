"""Library Manager — grouped 7-panel sidebar.

Sprint-9 / sidebar-panels per
docs/reference/mashco-design-system/cd-archivist-library/handoff/build-prompt.md §3.

Renders four groups (QUEUES / HEALTH / BROWSE / COMING · v2) with seven
total rows: four v1 primaries (anchor links to `/library/{id}`) and
three v2 ghosts (`aria-disabled="true"`, non-interactive, soon chip).
"""

from __future__ import annotations

import html as _html

from archivist.service.library_panel_inventory import (
    GHOSTS,
    PRIMARY,
    PanelSpec,
)


def _row(spec: PanelSpec, *, active_panel_id: str | None, ghost: bool) -> str:
    is_active = (active_panel_id == spec["id"]) and not ghost
    classes = ["cda-lib-row"]
    if is_active:
        classes.append("is-active")
    if ghost:
        classes.append("is-ghost")
    class_attr = " ".join(classes)

    count_or_soon = ""
    if ghost:
        count_or_soon = '<span class="soon">soon</span>'
    elif spec["count"]:
        count_or_soon = f'<span class="count">{_html.escape(spec["count"])}</span>'

    label_html = (
        '<span class="label">'
        f'<span class="name">{_html.escape(spec["name"])}</span>'
        f'<span class="sub">{_html.escape(spec["sub"])}</span>'
        '</span>'
    )
    glyph_html = f'<span class="glyph">{_html.escape(spec["glyph"])}</span>'

    if ghost:
        return (
            f'<div class="{class_attr}" '
            f'aria-disabled="true" '
            f'data-panel-id="{_html.escape(spec["id"])}">'
            f'{glyph_html}{label_html}{count_or_soon}'
            '</div>'
        )

    return (
        f'<a class="{class_attr}" '
        f'href="/library/{_html.escape(spec["id"])}" '
        f'data-panel-id="{_html.escape(spec["id"])}">'
        f'{glyph_html}{label_html}{count_or_soon}'
        '</a>'
    )


def render_sidebar(*, active_panel_id: str | None = None) -> str:
    """Render the grouped sidebar.

    `active_panel_id` marks one v1 entry as the current selection (visual
    treatment via `.is-active`). Pass `None` on the landing route — no
    row is marked active.
    """
    # Groups per build-prompt §2 visual recipe + JSX reference:
    #   QUEUES  → downloads, inbox
    #   HEALTH  → disk
    #   BROWSE  → library
    #   COMING · v2 → review, recent, cron (all ghosts)
    queues = PRIMARY[0:2]
    health = PRIMARY[2:3]
    browse = PRIMARY[3:4]

    def _group(label: str, specs, *, ghost: bool) -> str:
        rows = "".join(
            _row(s, active_panel_id=active_panel_id, ghost=ghost)
            for s in specs
        )
        return (
            f'<div class="cda-lib-side-group">{_html.escape(label)}</div>'
            f'{rows}'
        )

    return (
        '<aside class="cda-lib-sidebar">'
        f'{_group("Queues", queues, ghost=False)}'
        f'{_group("Health", health, ghost=False)}'
        f'{_group("Browse", browse, ghost=False)}'
        f'{_group("Coming · v2", GHOSTS, ghost=True)}'
        '</aside>'
    )
