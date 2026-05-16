"""Kanban HTML page renderer (sprint-6 Bucket B / B+).

Renders the four-column kanban at GET /. Each card collapses by
default; the expanded body includes the operator-hint controls
(two toggles + two text inputs + optional per-track table when both
toggles are on).

Polling is declared via <meta name="kanban-poll-ms" content="2000">
(D-live-update-transport-v1). The actual fetch+diff JS is intentionally
minimal — sprint-6 ships polling at 2s; SSE deferred per the design.
"""
from __future__ import annotations

import html as _html
from pathlib import Path

from archivist.service.disc_card_builder import DiscCard, build_kanban_state

POLL_MS = 2000

_COLUMN_TITLES: list[tuple[str, str]] = [
    ("capture", "Capture"),
    ("beets_id", "Beets ID"),
    ("review", "Review"),
    ("library", "In Library"),
]


def _esc(s: object) -> str:
    return _html.escape("" if s is None else str(s), quote=True)


def _track_count(card: DiscCard) -> int:
    return len(card.track_bar)


def _chip_for(card: DiscCard) -> tuple[str, str] | None:
    """Returns (data-chip value, display text) or None if no chip."""
    hints = card.operator_hints or {}
    va = bool(hints.get("various_artists"))
    burned = bool(hints.get("burned_cd"))
    artist = hints.get("artist")
    album = hints.get("album")
    if va and burned:
        return "mix", f"Mix CD ({_track_count(card)} tracks)"
    if va:
        return "va", "VA"
    if burned:
        return "burned", "burned"
    if artist or album:
        parts = [str(artist or "").strip(), str(album or "").strip()]
        return "album", " — ".join(p for p in parts if p)
    return None


def _render_track_bar(card: DiscCard) -> str:
    cells = "".join(
        f'<span class="track-cell track-cell--{_esc(s)}"></span>'
        for s in card.track_bar
    )
    return f'<div class="track-bar" role="img" aria-label="track progress">{cells}</div>'


def _render_progress(card: DiscCard) -> str:
    if not card.progress:
        return ""
    pct = int(card.progress.get("percent", 0))
    stage = _esc(card.progress.get("current_stage", ""))
    return (
        f'<div class="progress" data-percent="{pct}">'
        f'<progress max="100" value="{pct}"></progress>'
        f'<span class="progress-stage">{stage} — {pct}%</span>'
        '</div>'
    )


def _render_hint_controls(card: DiscCard) -> str:
    hints = card.operator_hints or {}
    va = bool(hints.get("various_artists"))
    burned = bool(hints.get("burned_cd"))
    artist = _esc(hints.get("artist") or "")
    album = _esc(hints.get("album") or "")
    folder = _esc(card.folder)

    artist_disabled = "disabled" if (va or burned) else ""
    album_disabled = "disabled" if (va or burned) else ""

    controls = (
        '<fieldset class="hint-controls">'
        '<legend>operator hints</legend>'
        '<label>'
        f'<input type="checkbox" name="various_artists" '
        f'aria-label="Various Artists" {"checked" if va else ""}>'
        ' Various Artists'
        '</label>'
        '<label>'
        f'<input type="checkbox" name="burned_cd" '
        f'aria-label="Burned CD" {"checked" if burned else ""}>'
        ' Burned CD'
        '</label>'
        '<label>artist '
        f'<input type="text" name="artist" value="{artist}" '
        f'{artist_disabled} '
        'data-disabled-when="burned_cd OR various_artists">'
        '</label>'
        '<label>album '
        f'<input type="text" name="album" value="{album}" '
        f'{album_disabled} '
        'data-disabled-when="burned_cd OR various_artists">'
        '</label>'
    )

    if va and burned:
        n = _track_count(card)
        existing_tracks = {
            int(t.get("track_number", 0)): t
            for t in (hints.get("tracks") or [])
        }
        rows: list[str] = []
        for i in range(1, n + 1):
            t = existing_tracks.get(i, {})
            t_artist = _esc(t.get("artist") or "")
            t_title = _esc(t.get("title") or "")
            rows.append(
                f'<tr><td>{i}</td>'
                f'<td><input type="text" name="track-{i}-artist" value="{t_artist}"></td>'
                f'<td><input type="text" name="track-{i}-title" value="{t_title}"></td>'
                '</tr>'
            )
        controls += (
            '<table class="per-track-table" '
            'data-show-when="various_artists AND burned_cd">'
            '<thead><tr><th>#</th><th>artist</th><th>title</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody>'
            '</table>'
        )

    controls += (
        '<button type="button" class="btn btn--accent" '
        f'data-action="save-hints" data-endpoint="/api/disc/{folder}/hints">'
        'Save hints</button>'
        '</fieldset>'
    )
    return controls


def _render_card(card: DiscCard) -> str:
    folder = _esc(card.folder)
    chip = _chip_for(card)
    chip_html = ""
    if chip is not None:
        ck, ct = chip
        chip_html = f'<span class="chip" data-chip="{ck}">{_esc(ct)}</span>'

    collapsed = (
        '<header class="card-head">'
        f'<h3 class="card-title">{folder}</h3>'
        f'{chip_html}'
        '</header>'
        f'{_render_progress(card)}'
        f'{_render_track_bar(card)}'
    )

    expanded = (
        '<div class="card-body" hidden>'
        f'{_render_hint_controls(card)}'
        '</div>'
    )

    return (
        f'<article class="card" data-folder="{folder}" '
        f'data-bucket="{_esc(card.bucket)}" aria-expanded="false">'
        f'{collapsed}'
        f'{expanded}'
        '</article>'
    )


def _render_column(key: str, title: str, cards: list[DiscCard]) -> str:
    cards_html = "\n".join(_render_card(c) for c in cards)
    return (
        f'<section class="column" data-bucket="{key}">'
        f'<h2 class="column-title">{_esc(title)}</h2>'
        f'<div class="column-cards">{cards_html}</div>'
        '</section>'
    )


_STYLES = """
:root { color-scheme: dark; }
body { font-family: var(--font-body, system-ui); background: var(--bg, #111);
       color: var(--ink, #eee); margin: 0; padding: 0; }
main.kanban { display: grid; grid-template-columns: repeat(4, 1fr);
              gap: var(--s-4, 16px); padding: var(--s-4, 16px); }
.column { background: var(--surface, #1c1c1c);
          border: 1px solid var(--line, #333); border-radius: var(--r-3, 8px);
          padding: var(--s-3, 12px); }
.column-title { font-size: var(--fs-md, 14px); letter-spacing: 0.08em;
                text-transform: uppercase; color: var(--ink-3, #aaa);
                margin: 0 0 var(--s-3, 12px) 0; }
.card { background: var(--surface-2, #222); border: 1px solid var(--line, #333);
        border-left: 3px solid var(--info, #4a9eff);
        border-radius: var(--r-2, 4px); padding: var(--s-3, 12px);
        margin-bottom: var(--s-3, 12px); }
.card[data-bucket="review"] { border-left-color: var(--warn, #ffb84a); }
.card[data-bucket="library"] { border-left-color: var(--ok, #4aff8a); }
.card-head { display: flex; align-items: center; gap: var(--s-2, 8px); }
.card-title { font-size: var(--fs-sm, 13px); margin: 0; }
.chip { font-size: var(--fs-xs, 11px); padding: 2px 6px;
        background: var(--ink, #eee); color: var(--bg, #111);
        border-radius: var(--r-full, 999px); }
.track-bar { display: flex; gap: 2px; margin-top: var(--s-2, 8px); }
.track-cell { flex: 1; height: 6px; background: var(--surface, #1c1c1c); }
.track-cell--success { background: var(--ok, #4aff8a); }
.track-cell--fail { background: var(--meat-red, #ff4a4a); }
.track-cell--in_progress { background: var(--info, #4a9eff); }
.track-cell--pending { background: var(--surface, #1c1c1c); }
.progress { margin-top: var(--s-2, 8px); }
.progress-stage { font-size: var(--fs-xs, 11px); color: var(--ink-3, #aaa); }
.hint-controls { border: 1px solid var(--line, #333); padding: var(--s-2, 8px);
                 margin-top: var(--s-2, 8px); }
.hint-controls label { display: block; margin: 4px 0; }
.per-track-table { width: 100%; border-collapse: collapse;
                   margin-top: var(--s-2, 8px); }
.per-track-table td, .per-track-table th { padding: 2px 4px;
                                           border-bottom: 1px solid var(--line, #333); }
.btn { font-family: var(--font-body, system-ui); padding: 4px 10px;
       border-radius: var(--r-2, 4px); border: 1px solid var(--line, #333);
       color: var(--ink, #eee); background: var(--surface, #1c1c1c);
       cursor: pointer; }
.btn--accent { background: var(--accent, #4a9eff); color: var(--bg, #111); }
"""


def render_kanban_page(music_root: Path, loop_state) -> str:
    state = build_kanban_state(music_root, loop_state=loop_state)
    columns = "\n".join(
        _render_column(key, title, state.buckets.get(key, []))
        for key, title in _COLUMN_TITLES
    )
    return (
        '<!doctype html>'
        '<html lang="en" data-theme="dark">'
        '<head>'
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<meta name="kanban-poll-ms" content="{POLL_MS}">'
        '<title>cd-archivist · kanban</title>'
        '<link rel="stylesheet" href="/static/tokens.css">'
        f'<style>{_STYLES}</style>'
        '</head>'
        '<body>'
        '<main class="kanban">'
        f'{columns}'
        '</main>'
        '</body></html>'
    )
