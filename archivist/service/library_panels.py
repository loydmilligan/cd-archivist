"""Library Manager — per-panel header + "in design" placeholder.

Sprint-9 / panel-placeholder per
docs/reference/mashco-design-system/cd-archivist-library/handoff/build-prompt.md §4.

Each v1 panel renders: panel header (eyebrow + h1 + sub) + honest
placeholder card (dashed-border, 3 ghost rows, `tag: in design`
foot). Per-panel UX is intentionally deferred to follow-up briefs.
"""

from __future__ import annotations

import html as _html

from archivist.service.library_panel_inventory import BY_ID


_PLACEHOLDER_FOOT_COPY = (
    "UX is intentionally undecided in this pass. Drill-in actions, "
    "list density, expand-states, and retry/import affordances come "
    "in a per-panel brief."
)


def _ghost_row() -> str:
    return (
        '<div class="row">'
        '<span class="cda-lib-panel-empty-glyph">·</span>'
        '<span><span class="label">ghost row · ghost row · ghost row</span></span>'
        '<span class="cda-lib-panel-empty-dash">—</span>'
        '</div>'
    )


def render_panel(panel_id: str) -> str:
    """Render the panel viewport for a v1 panel id.

    Caller (route handler) MUST gate v2 ids → 404 before reaching here.
    This function trusts that `panel_id` is one of the v1 ids; an unknown
    id raises KeyError.
    """
    spec = BY_ID[panel_id]
    ghost_rows = _ghost_row() * 3
    return (
        '<section class="cda-lib-viewport">'
        '<div class="cda-lib-panel">'
        '<header class="cda-lib-panel-head">'
        '<div class="cda-lib-panel-head-left">'
        f'<span class="eyebrow">{_html.escape(spec["eyebrow"])}</span>'
        f'<h1>{_html.escape(spec["title"])}</h1>'
        f'<p class="sub">{_html.escape(spec["summary"])}</p>'
        '</div>'
        '</header>'
        '<div class="cda-lib-panel-empty">'
        f'{ghost_rows}'
        '<div class="cda-lib-panel-empty-foot">'
        '<span class="tag">in design</span>'
        f'<span>{_html.escape(_PLACEHOLDER_FOOT_COPY)}</span>'
        '</div>'
        '</div>'
        '</div>'
        '</section>'
    )
