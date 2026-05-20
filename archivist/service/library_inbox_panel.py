"""Inbox panel — `/library/inbox` viewport.

Sprint-10 / inbox-impl. Renders one row per pending album folder under
``$MUSIC_INBOX_DIR``, plus a per-row "import now" button that POSTs to
``/api/library/inbox/import-now`` to kick the beets importer for that
folder.

Polling contract: emits the two meta tags consumed by
``chassis_js.CHASSIS_JS``'s per-panel poll dispatcher so the viewport
refreshes against ``/api/library/inbox`` every 5s. See
``chassis_js.py``'s docstring for the meta-tag contract.

When the inbox root is missing or unreadable, the panel degrades to an
empty state (the chassis is the source of truth — we never crash the
page on a missing mount).
"""

from __future__ import annotations

import html
from typing import Iterable

from archivist.service.clients.inbox_client import (
    InboxFolder,
    InboxUnavailable,
    list_inbox_folders,
)
from archivist.service.library_panel_inventory import PanelSpec


POLL_MS = 5000
POLL_ENDPOINT = "/api/library/inbox"


def _format_bytes(n: int) -> str:
    abs_n = abs(int(n))
    if abs_n < 1024:
        return f"{abs_n} B"
    kb = abs_n / 1024
    if kb < 1024:
        return f"{kb:.1f} KB"
    mb = kb / 1024
    if mb < 1024:
        return f"{mb:.1f} MB"
    gb = mb / 1024
    return f"{gb:.1f} GB"


def _source_tag(source: str) -> str:
    """`cd_rip` and `spooty` get distinct tag classes for visual sort."""
    label = "cd rip" if source == "cd_rip" else "spooty"
    return (
        f'<span class="tag tag--{html.escape(source)}">'
        f"{html.escape(label)}"
        "</span>"
    )


def _ready_pip(present: bool) -> str:
    """Pip styling matches the kanban's READY/pending convention."""
    if present:
        return (
            '<span class="pip pip--ready" title="READY marker present">'
            "READY"
            "</span>"
        )
    return (
        '<span class="pip pip--pending" title="no READY marker">'
        "pending"
        "</span>"
    )


def _row(folder: InboxFolder) -> str:
    return (
        '<tr class="cda-inbox-row" '
        f'data-folder="{html.escape(folder.name)}" '
        f'data-source="{html.escape(folder.source)}">'
        f'<td class="cda-inbox-name">{html.escape(folder.name)}</td>'
        f"<td>{_source_tag(folder.source)}</td>"
        f'<td class="num">{folder.file_count}</td>'
        f'<td class="num">{_format_bytes(folder.size_bytes)}</td>'
        f'<td class="mono">{html.escape(folder.last_modified)}</td>'
        f"<td>{_ready_pip(folder.ready_marker_present)}</td>"
        "<td>"
        '<button type="button" class="btn btn--small cda-inbox-import" '
        f'data-folder="{html.escape(folder.name)}">'
        "import now"
        "</button>"
        "</td>"
        "</tr>"
    )


def _rows(folders: Iterable[InboxFolder]) -> str:
    return "".join(_row(f) for f in folders)


def _empty_state(message: str) -> str:
    return (
        '<div class="cda-lib-panel-empty">'
        '<div class="cda-lib-panel-empty-foot">'
        '<span class="tag">empty</span>'
        f"<span>{html.escape(message)}</span>"
        "</div>"
        "</div>"
    )


def _table(folders: list[InboxFolder]) -> str:
    if not folders:
        return _empty_state(
            "no pending folders — the inbox is empty or all folders "
            "have already been imported."
        )
    return (
        '<table class="cda-inbox-table">'
        "<thead><tr>"
        "<th>folder</th>"
        "<th>source</th>"
        '<th class="num">files</th>'
        '<th class="num">size</th>'
        "<th>last modified</th>"
        "<th>state</th>"
        "<th></th>"
        "</tr></thead>"
        f"<tbody>{_rows(folders)}</tbody>"
        "</table>"
    )


def render(spec: PanelSpec) -> str:
    """Render the Inbox panel viewport.

    Called by ``library_panels.render_panel("inbox")``. Pulls the
    current folder listing (or an empty list on InboxUnavailable),
    renders the panel header + rows table, and emits the polling
    meta tags so the chassis dispatcher refreshes us every 5s.
    """
    try:
        folders = list_inbox_folders()
        body_html = _table(folders)
    except InboxUnavailable as exc:
        folders = []
        body_html = _empty_state(f"inbox unavailable — {exc}")

    return (
        '<section class="cda-lib-viewport" data-panel="inbox">'
        f'<meta name="library-poll-ms" content="{POLL_MS}">'
        f'<meta name="library-poll-endpoint" content="{POLL_ENDPOINT}">'
        '<div class="cda-lib-panel">'
        '<header class="cda-lib-panel-head">'
        '<div class="cda-lib-panel-head-left">'
        f'<span class="eyebrow">{html.escape(spec["eyebrow"])}</span>'
        f'<h1>{html.escape(spec["title"])}</h1>'
        f'<p class="sub">{html.escape(spec["summary"])}</p>'
        "</div>"
        '<div class="cda-lib-panel-head-right">'
        f'<span class="meta cda-inbox-count">{len(folders)} folders</span>'
        "</div>"
        "</header>"
        f'<div class="cda-inbox-body">{body_html}</div>'
        "</div>"
        "</section>"
    )
