"""Library Manager — panel dispatcher.

Sprint-9 shipped per-panel headers + an "in design" placeholder for all
four v1 panels. Sprint-10 splits the rendering across per-panel
modules (`library_disk_panel.py`, `library_inbox_panel.py`,
`library_downloads_panel.py`, `library_browse_panel.py`) so lane-1
and lane-2 can work in parallel without colliding on this file.

`render_panel(panel_id)` is the stable entrypoint called by
`library_page.py`. It looks up the spec from the inventory, then
delegates to the per-panel module if one is present, falling back to
the sprint-9 placeholder otherwise. The placeholder fallback is what
keeps the existing test suite green between Wave 0 and the per-panel
impl tasks.
"""

from __future__ import annotations

import html as _html
import importlib
from typing import Callable

from archivist.service.library_panel_inventory import BY_ID, PanelSpec


_PLACEHOLDER_FOOT_COPY = (
    "UX is intentionally undecided in this pass. Drill-in actions, "
    "list density, expand-states, and retry/import affordances come "
    "in a per-panel brief."
)


# Panel id → per-panel module name. The `library` panel renders the
# Navidrome browse surface, so its module is `library_browse_panel`
# (not `library_library_panel`).
_PANEL_MODULES: dict[str, str] = {
    "downloads": "archivist.service.library_downloads_panel",
    "inbox": "archivist.service.library_inbox_panel",
    "disk": "archivist.service.library_disk_panel",
    "library": "archivist.service.library_browse_panel",
}


def _ghost_row() -> str:
    return (
        '<div class="row">'
        '<span class="cda-lib-panel-empty-glyph">·</span>'
        '<span><span class="label">ghost row · ghost row · ghost row</span></span>'
        '<span class="cda-lib-panel-empty-dash">—</span>'
        '</div>'
    )


def _render_placeholder(spec: PanelSpec) -> str:
    """Sprint-9 placeholder: panel header + dashed 'in design' card."""
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


def _resolve_panel_renderer(panel_id: str) -> Callable[[PanelSpec], str] | None:
    """Return the per-panel module's `render(spec)` callable if present.

    Returns None when the per-panel module hasn't been written yet, or
    when it exists but doesn't expose a `render` callable — in either
    case the dispatcher falls back to the sprint-9 placeholder. This
    is the seam the Wave 1 panel-impl tasks land into.
    """
    module_name = _PANEL_MODULES.get(panel_id)
    if module_name is None:
        return None
    try:
        module = importlib.import_module(module_name)
    except ImportError:
        return None
    render = getattr(module, "render", None)
    if not callable(render):
        return None
    return render


def render_panel(panel_id: str) -> str:
    """Render the panel viewport for a v1 panel id.

    Caller (route handler) MUST gate v2 ids → 404 before reaching here.
    This function trusts that `panel_id` is one of the v1 ids; an unknown
    id raises KeyError.
    """
    spec = BY_ID[panel_id]
    renderer = _resolve_panel_renderer(panel_id)
    if renderer is not None:
        return renderer(spec)
    return _render_placeholder(spec)
