"""Library Manager — Disk panel.

Sprint-10 / disk-impl. Replaces the sprint-9 "in design" placeholder
for `panel_id == "disk"` via the dispatcher in `library_panels.py`.

Renders:
  - Panel header (eyebrow / h1 / sub) — same shape as the placeholder
  - Polling meta tags consumed by chassis_js (30s cadence,
    /api/library/disk endpoint)
  - Three usage-bar rows (one per mount in the snapshot order: /,
    /mnt/seagate, /mnt/archive)
  - A per-surface drilldown table (one row per mount, columns:
    inbox / library / archive / spooty)

Threshold classes (`is-pulp` / `is-amber` / `is-ember`) come from
`disk_client.threshold_class` so the mapping is single-sourced.
"""

from __future__ import annotations

import html as _html

from archivist.service.clients.disk_client import (
    MountUsage,
    format_bytes,
    get_disk_usage,
    threshold_class,
)
from archivist.service.library_panel_inventory import PanelSpec


_POLL_MS = 30000
_POLL_ENDPOINT = "/api/library/disk"

_SURFACE_ORDER: tuple[str, ...] = ("inbox", "library", "archive", "spooty")


def _render_mount_row(m: MountUsage) -> str:
    if not m.mounted:
        return (
            '<div class="cda-lib-disk-row is-unmounted">'
            f'<div class="cda-lib-disk-row-head">'
            f'<span class="path">{_html.escape(m.mount_path)}</span>'
            f'<span class="state">not mounted</span>'
            f'</div>'
            '<div class="cda-lib-disk-bar"><div class="cda-lib-disk-bar-fill" style="width:0%"></div></div>'
            '</div>'
        )
    cls = threshold_class(m.pct_used)
    pct_str = f"{m.pct_used:.1f}%"
    used_str = format_bytes(m.used_bytes)
    total_str = format_bytes(m.total_bytes)
    bar_width = min(max(m.pct_used, 0.0), 100.0)
    return (
        f'<div class="cda-lib-disk-row {cls}">'
        '<div class="cda-lib-disk-row-head">'
        f'<span class="path">{_html.escape(m.mount_path)}</span>'
        f'<span class="usage">{_html.escape(used_str)} / {_html.escape(total_str)}'
        f' · {_html.escape(pct_str)}</span>'
        '</div>'
        '<div class="cda-lib-disk-bar">'
        f'<div class="cda-lib-disk-bar-fill" style="width:{bar_width:.1f}%"></div>'
        '</div>'
        '</div>'
    )


def _render_drilldown(mounts: list[MountUsage]) -> str:
    head_cells = "".join(f'<th>{_html.escape(n)}</th>' for n in _SURFACE_ORDER)
    rows: list[str] = []
    for m in mounts:
        cells: list[str] = []
        for s in _SURFACE_ORDER:
            b = m.surfaces.get(s, 0)
            if b == 0:
                cells.append('<td class="empty">—</td>')
            else:
                cells.append(f'<td>{_html.escape(format_bytes(b))}</td>')
        path_cell = _html.escape(m.mount_path)
        rows.append(f'<tr><th scope="row">{path_cell}</th>{"".join(cells)}</tr>')
    return (
        '<table class="cda-lib-disk-drilldown">'
        '<thead>'
        f'<tr><th scope="col">mount</th>{head_cells}</tr>'
        '</thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        '</table>'
    )


def render(spec: PanelSpec) -> str:
    snap = get_disk_usage()
    rows_html = "".join(_render_mount_row(m) for m in snap.mounts)
    drilldown_html = _render_drilldown(snap.mounts)
    return (
        '<section class="cda-lib-viewport">'
        f'<meta name="library-poll-ms" content="{_POLL_MS}">'
        f'<meta name="library-poll-endpoint" content="{_POLL_ENDPOINT}">'
        '<div class="cda-lib-panel">'
        '<header class="cda-lib-panel-head">'
        '<div class="cda-lib-panel-head-left">'
        f'<span class="eyebrow">{_html.escape(spec["eyebrow"])}</span>'
        f'<h1>{_html.escape(spec["title"])}</h1>'
        f'<p class="sub">{_html.escape(spec["summary"])}</p>'
        '</div>'
        '</header>'
        f'<div class="cda-lib-disk-bars">{rows_html}</div>'
        f'{drilldown_html}'
        '</div>'
        '</section>'
    )
