"""Kanban HTML page renderer (sprint-6.5 rewrite).

Replaces the sprint-6 single-page kanban with the usability-pass
surface from the K1 brainstorm:

  - Header (D-no-alerts-v1): wordmark + daemon-state dot + compact
    stats + drawer toggles + nav link-outs (NAVIDROME_URL,
    BEETS_WEB_URL).
  - Card visual evolution (D-card-state-evolution): identified
    track-cells, chip--confirmed vs chip--asserted, card--damaged
    red-shadow, thumbnail src per bucket.
  - Click + spacebar expand mechanic with one-at-a-time guard and
    a `?` keyboard-help tooltip.
  - Three labeled sections inside the expanded body: hints /
    manual-steps (Review-only) / damaged-actions.
  - High-leverage collapsed-card buttons (process-partial / redo
    for damaged Capture; accept-top-match for high-confidence
    Review per D-accept-top-candidate-threshold).
  - Layout shell: independent column scroll + sticky headers +
    count badges; right slide-out drawer (drive-status default /
    card-detail on click); bottom log drawer with localStorage
    persistence.
  - Mobile breakpoint (D-mobile-breakpoint-v1) with bucket-tab
    segmented control.
  - Adaptive polling (D-adaptive-polling-cadence): 1s active /
    5s idle, switched by reading active_rip on each kanban
    response.
"""
from __future__ import annotations

import html as _html
import os
from pathlib import Path

from archivist.service.disc_card_builder import DiscCard, build_kanban_state

POLL_MS_ACTIVE = 1000
POLL_MS_IDLE = 5000
ACCEPT_TOP_THRESHOLD = 0.85
MOBILE_BREAKPOINT_PX = 720

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


def _is_identified_track(card: DiscCard, track_number: int) -> bool:
    src = card.source_json or {}
    identifiers = src.get("identifiers") or {}
    if not identifiers.get("musicbrainz_disc_id"):
        return False
    for t in (src.get("detected_metadata") or {}).get("tracks") or []:
        if t.get("track") == track_number and t.get("title"):
            return True
    return False


def _is_damaged(card: DiscCard) -> bool:
    if card.partial:
        return True
    src = card.source_json or {}
    return (src.get("status") or {}).get("rip_success") is False


def _chip_for(card: DiscCard) -> tuple[str, str] | None:
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


def _metadata_chips(card: DiscCard) -> str:
    """Artist/Album chips with confirmed (beets) vs asserted (operator)
    classes. Confirmed wins when both present (system > operator)."""
    src = card.source_json or {}
    detected = src.get("detected_metadata") or {}
    hints = card.operator_hints or {}
    confirmed_artist = detected.get("album_artist")
    confirmed_album = detected.get("album")
    asserted_artist = hints.get("artist")
    asserted_album = hints.get("album")

    chips: list[str] = []
    if confirmed_artist:
        chips.append(
            '<span class="chip chip--confirmed" data-meta-state="confirmed">'
            f'{_esc(confirmed_artist)}</span>'
        )
    elif asserted_artist:
        chips.append(
            '<span class="chip chip--asserted" data-meta-state="asserted">'
            f'{_esc(asserted_artist)}</span>'
        )
    if confirmed_album:
        chips.append(
            '<span class="chip chip--confirmed" data-meta-state="confirmed">'
            f'{_esc(confirmed_album)}</span>'
        )
    elif asserted_album:
        chips.append(
            '<span class="chip chip--asserted" data-meta-state="asserted">'
            f'{_esc(asserted_album)}</span>'
        )
    return "".join(chips)


def _render_track_bar(card: DiscCard) -> str:
    cells: list[str] = []
    for i, state in enumerate(card.track_bar, start=1):
        identified = _is_identified_track(card, i)
        ident_attr = f' data-track-identified-{i}="true"' if identified else ""
        ident_class = " track-cell--identified" if identified else ""
        cells.append(
            f'<span class="track-cell track-cell--{_esc(state)}{ident_class}"{ident_attr}></span>'
        )
    return (
        '<div class="track-bar" role="img" aria-label="track progress">'
        + "".join(cells) + '</div>'
    )


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


def _thumbnail_src(card: DiscCard) -> str | None:
    folder = _esc(card.folder)
    if card.bucket == "library":
        return f"/library/{folder}/album-cover"
    src = card.source_json or {}
    physical = src.get("physical_disc") or {}
    photo = physical.get("photo") or "disc-photo.jpg"
    if not photo.endswith(".jpg") and not photo.endswith(".png"):
        photo = "disc-photo.jpg"
    return f"/review/{folder}/disc-photo.jpg"


def _render_thumbnail(card: DiscCard) -> str:
    src = _thumbnail_src(card)
    if src is None:
        return ""
    return (
        f'<img class="card-thumb" loading="lazy" alt="" src="{src}">'
    )


def _render_collapsed_actions(card: DiscCard) -> str:
    """High-leverage buttons surfaced on the collapsed card."""
    buttons: list[str] = []
    folder = _esc(card.folder)
    if card.bucket == "capture" and _is_damaged(card):
        buttons.append(
            '<button type="button" class="btn btn--accent" '
            f'data-action="process-partial" '
            f'data-endpoint="/api/disc/{folder}/process-partial">'
            'Process partial</button>'
        )
        buttons.append(
            '<button type="button" class="btn" '
            f'data-action="redo" '
            f'data-endpoint="/api/disc/{folder}/redo?confirm=true">'
            'Redo</button>'
        )
    if card.bucket == "review" and card.top_candidate is not None:
        score = float(card.top_candidate.get("score") or 0)
        if score >= ACCEPT_TOP_THRESHOLD:
            buttons.append(
                '<button type="button" class="btn btn--accent" '
                f'data-action="accept-top-candidate" '
                f'data-endpoint="/api/disc/{folder}/accept-top-candidate">'
                'Accept top match</button>'
            )
    if not buttons:
        return ""
    return '<div class="card-actions">' + "".join(buttons) + '</div>'


def _render_hint_controls(card: DiscCard) -> str:
    hints = card.operator_hints or {}
    va = bool(hints.get("various_artists"))
    burned = bool(hints.get("burned_cd"))
    artist = _esc(hints.get("artist") or "")
    album = _esc(hints.get("album") or "")
    folder = _esc(card.folder)
    art_disabled = "disabled" if (va or burned) else ""
    alb_disabled = "disabled" if (va or burned) else ""

    out = (
        '<fieldset class="hint-controls">'
        '<legend>operator hints</legend>'
        '<label>'
        f'<input type="checkbox" name="various_artists" '
        f'aria-label="Various Artists" {"checked" if va else ""}>'
        ' Various Artists</label>'
        '<label>'
        f'<input type="checkbox" name="burned_cd" '
        f'aria-label="Burned CD" {"checked" if burned else ""}>'
        ' Burned CD</label>'
        '<label>artist '
        f'<input type="text" name="artist" value="{artist}" {art_disabled} '
        'data-disabled-when="burned_cd OR various_artists">'
        '</label>'
        '<label>album '
        f'<input type="text" name="album" value="{album}" {alb_disabled} '
        'data-disabled-when="burned_cd OR various_artists">'
        '</label>'
    )

    if va and burned:
        n = _track_count(card)
        existing = {
            int(t.get("track_number", 0)): t
            for t in (hints.get("tracks") or [])
        }
        rows: list[str] = []
        for i in range(1, n + 1):
            t = existing.get(i, {})
            ta = _esc(t.get("artist") or "")
            tt = _esc(t.get("title") or "")
            rows.append(
                f'<tr><td>{i}</td>'
                f'<td><input type="text" name="track-{i}-artist" value="{ta}"></td>'
                f'<td><input type="text" name="track-{i}-title" value="{tt}"></td>'
                '</tr>'
            )
        out += (
            '<table class="per-track-table" '
            'data-show-when="various_artists AND burned_cd">'
            '<thead><tr><th>#</th><th>artist</th><th>title</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody>'
            '</table>'
        )

    out += (
        '<button type="button" class="btn btn--accent" '
        f'data-action="save-hints" data-endpoint="/api/disc/{folder}/hints">'
        'Save hints</button>'
        '</fieldset>'
    )
    return out


def _render_manual_steps_section(card: DiscCard) -> str:
    """Review-bucket: pull explainer + shell snippet."""
    folder_name = card.folder
    why = ""
    try:
        # Builder doesn't expose the disc-folder Path; reconstruct via
        # source_json clue if present, else just use the explainer text
        # off the existing fields. The HTML manual-steps block itself
        # only needs the explainer message + the shell template, both
        # derivable from the source_json the card already carries.
        src = card.source_json or {}
        reason = ((src.get("status") or {}).get("beets_review_reason")) or ""
        if reason:
            why = reason
        else:
            why = "ready for review"
    except Exception:  # noqa: BLE001
        why = "ready for review"

    cmd = f"docker exec -it cd_beets beet import /downloads/{folder_name}"
    cmd_id = (
        f"docker exec -it cd_beets beet import --search-id <MBID> "
        f"/downloads/{folder_name}"
    )
    return (
        '<section class="card-section" data-section="manual-steps">'
        '<h4 class="section-title">manual steps</h4>'
        f'<p class="why-in-review">{_esc(why)}</p>'
        '<details><summary>copy-paste shell</summary>'
        '<pre><code>'
        f'{_esc(cmd)}\n'
        '\n'
        f'# or with a known MusicBrainz release ID:\n'
        f'{_esc(cmd_id)}\n'
        '</code></pre></details>'
        '</section>'
    )


def _render_damaged_actions_section(card: DiscCard) -> str:
    folder = _esc(card.folder)
    return (
        '<section class="card-section" data-section="damaged-actions">'
        '<h4 class="section-title">damaged-disc actions</h4>'
        '<div class="card-actions">'
        '<button type="button" class="btn btn--accent" '
        f'data-endpoint="/api/disc/{folder}/process-partial">'
        'Process partial</button>'
        '<button type="button" class="btn" '
        f'data-endpoint="/api/disc/{folder}/redo?confirm=true">'
        'Redo</button>'
        '<button type="button" class="btn" '
        f'data-endpoint="/api/disc/{folder}/rerip-tracks">'
        'Pick tracks to re-rip</button>'
        '</div>'
        '</section>'
    )


def _render_card(card: DiscCard) -> str:
    folder = _esc(card.folder)
    chip = _chip_for(card)
    chip_html = ""
    if chip is not None:
        ck, ct = chip
        chip_html = f'<span class="chip" data-chip="{ck}">{_esc(ct)}</span>'

    damaged = _is_damaged(card)
    damaged_class = " card--damaged" if damaged else ""
    damaged_attr = ' data-state="damaged"' if damaged else ""

    hints_section = (
        '<section class="card-section" data-section="hints">'
        '<h4 class="section-title">hints</h4>'
        f'{_render_hint_controls(card)}'
        '</section>'
    )
    manual_section = (
        _render_manual_steps_section(card)
        if card.bucket == "review" else ""
    )
    damaged_section = (
        _render_damaged_actions_section(card)
        if _is_damaged(card) else ""
    )

    collapsed = (
        '<header class="card-head">'
        f'{_render_thumbnail(card)}'
        f'<h3 class="card-title">{folder}</h3>'
        f'{chip_html}'
        f'{_metadata_chips(card)}'
        '</header>'
        f'{_render_progress(card)}'
        f'{_render_track_bar(card)}'
        f'{_render_collapsed_actions(card)}'
    )
    expanded = (
        '<div class="card-body" hidden>'
        f'{hints_section}{manual_section}{damaged_section}'
        '</div>'
    )

    return (
        f'<article class="card{damaged_class}"{damaged_attr} '
        f'data-folder="{folder}" '
        f'data-card-id="{folder}" data-bucket="{_esc(card.bucket)}" '
        'aria-expanded="false" tabindex="0">'
        f'{collapsed}{expanded}'
        '</article>'
    )


def _render_column(
    key: str, title: str, cards: list[DiscCard],
) -> str:
    cards_html = "\n".join(_render_card(c) for c in cards)
    return (
        f'<section class="column" data-bucket="{key}">'
        '<header class="column-header">'
        f'<h2 class="column-title">{_esc(title)}'
        f' <span class="count-badge">({len(cards)})</span>'
        '</h2>'
        '</header>'
        f'<div class="column-cards">{cards_html}</div>'
        '</section>'
    )


def _render_header_bar(stats: dict, links: dict) -> str:
    navidrome = links.get("navidrome") or ""
    beets_web = links.get("beets_web") or ""
    nav_link = (
        f'<a class="btn" href="{_esc(navidrome)}" target="_blank" '
        'rel="noopener">navidrome</a>'
    ) if navidrome else ""
    beets_link = (
        f'<a class="btn" href="{_esc(beets_web)}" target="_blank" '
        'rel="noopener">beets</a>'
    ) if beets_web else ""
    return (
        '<header class="page-header">'
        '<div class="header-left">'
        '<span class="wordmark">cd-archivist</span>'
        '<span class="daemon-state-dot" data-daemon-state="active" '
        'aria-label="daemon active"></span>'
        '</div>'
        '<div class="header-stats">'
        f'<span class="stat">total {stats["total"]}</span>'
        f'<span class="stat">review {stats["review"]}</span>'
        f'<span class="stat">partial {stats["partial"]}</span>'
        '</div>'
        '<div class="header-right">'
        '<button type="button" class="btn" '
        'aria-controls="right-drawer" data-drawer-toggle="right">'
        'drive</button>'
        '<button type="button" class="btn" '
        'aria-controls="bottom-drawer" data-drawer-toggle="bottom">'
        'logs</button>'
        f'{nav_link}{beets_link}'
        '</div>'
        '</header>'
    )


def _render_right_drawer() -> str:
    return (
        '<aside id="right-drawer" class="drawer drawer--right" '
        'aria-hidden="true">'
        '<div class="drawer-body" data-drawer-template="drive-status">'
        '<h3>drive status</h3>'
        '<div data-target="drive-status-body">'
        '<p class="meta">idle</p>'
        '</div>'
        '</div>'
        '<template data-drawer-template="card-detail">'
        '<div class="card-detail">'
        '<h3 data-target="detail-title"></h3>'
        '<pre data-target="detail-log"></pre>'
        '<pre data-target="detail-source-json"></pre>'
        '<img data-target="detail-photo" alt="">'
        '</div>'
        '</template>'
        '</aside>'
    )


def _render_bottom_drawer() -> str:
    return (
        '<aside id="bottom-drawer" class="drawer drawer--bottom" '
        'aria-hidden="true">'
        '<div class="drawer-body">'
        '<pre id="bottom-drawer-log" '
        'data-endpoint="/api/logs/tail?limit=200"></pre>'
        '</div>'
        '</aside>'
    )


def _render_bucket_tabs() -> str:
    buttons = "".join(
        f'<button type="button" class="bucket-tab" data-bucket="{k}">'
        f'{_esc(label)}</button>'
        for k, label in _COLUMN_TITLES
    )
    return (
        '<nav class="bucket-tabs" data-default-bucket="capture">'
        f'{buttons}'
        '</nav>'
    )


def _render_keyboard_help() -> str:
    msg = (
        "Space — expand focused card · "
        "Tab — move between cards · "
        "Esc — collapse expanded card"
    )
    return (
        '<button type="button" class="keyboard-help" '
        f'aria-label="keyboard help" data-keyboard-help="{_esc(msg)}">?</button>'
    )


_INLINE_JS = """
const POLL_ACTIVE = parseInt(
  document.querySelector('meta[name="kanban-poll-ms-active"]').content, 10
);
const POLL_IDLE = parseInt(
  document.querySelector('meta[name="kanban-poll-ms-idle"]').content, 10
);

// One-at-a-time expand state. Spacebar handler reads/writes this.
let currentlyExpanded = null;

function toggleCard(card) {
  const expanded = card.getAttribute('aria-expanded') === 'true';
  if (currentlyExpanded && currentlyExpanded !== card) {
    currentlyExpanded.setAttribute('aria-expanded', 'false');
    const prevBody = currentlyExpanded.querySelector('.card-body');
    if (prevBody) prevBody.hidden = true;
  }
  card.setAttribute('aria-expanded', expanded ? 'false' : 'true');
  const body = card.querySelector('.card-body');
  if (body) body.hidden = expanded;
  currentlyExpanded = expanded ? null : card;
  if (!expanded) openRightDrawerForCard(card);
}

document.addEventListener('click', (e) => {
  const card = e.target.closest('[data-card-id]');
  if (card && !e.target.closest('button, a, input, label')) {
    toggleCard(card);
  }
});

document.addEventListener('keydown', (e) => {
  if (e.key === ' ' || e.key === 'Space' || e.code === 'Space') {
    const card = document.activeElement?.closest?.('[data-card-id]');
    if (card) {
      e.preventDefault();
      toggleCard(card);
    }
  } else if (e.key === 'Escape' && currentlyExpanded) {
    toggleCard(currentlyExpanded);
  }
});

// --- Right drawer ---------------------------------------------------------
function setDrawerHidden(id, hidden) {
  const el = document.getElementById(id);
  if (el) el.setAttribute('aria-hidden', hidden ? 'true' : 'false');
}

function openRightDrawerForCard(card) {
  setDrawerHidden('right-drawer', false);
  const folder = card.getAttribute('data-card-id');
  // card-detail population — fetch /api/disc/<folder>/log/tail
  fetch(`/api/disc/${folder}/log/tail`).then(r => r.ok ? r.text() : '');
}

document.querySelectorAll('[data-drawer-toggle="right"]').forEach(btn => {
  btn.addEventListener('click', () => {
    const el = document.getElementById('right-drawer');
    const hidden = el.getAttribute('aria-hidden') === 'true';
    setDrawerHidden('right-drawer', !hidden);
  });
});

// --- Bottom drawer + localStorage ---------------------------------------
const BOTTOM_KEY = 'cd-archivist:bottom-drawer:open';
function applyBottomState() {
  const open = localStorage.getItem(BOTTOM_KEY) === 'true';
  setDrawerHidden('bottom-drawer', !open);
}
applyBottomState();
document.querySelectorAll('[data-drawer-toggle="bottom"]').forEach(btn => {
  btn.addEventListener('click', () => {
    const open = localStorage.getItem(BOTTOM_KEY) !== 'true';
    localStorage.setItem(BOTTOM_KEY, String(open));
    applyBottomState();
    if (open) refreshBottomDrawer();
  });
});

function refreshBottomDrawer() {
  const pre = document.getElementById('bottom-drawer-log');
  if (!pre) return;
  fetch(pre.getAttribute('data-endpoint'))
    .then(r => r.ok ? r.json() : { lines: [] })
    .then(j => { pre.textContent = (j.lines || []).join('\\n'); });
}

// --- Mobile bucket tabs + localStorage ----------------------------------
const MOBILE_KEY = 'cd-archivist:mobile-bucket';
function applyMobileTab() {
  const wanted = localStorage.getItem(MOBILE_KEY) || 'capture';
  document.querySelectorAll('.column').forEach(col => {
    col.dataset.activeMobile =
      (col.getAttribute('data-bucket') === wanted) ? 'true' : 'false';
  });
  document.querySelectorAll('.bucket-tab').forEach(btn => {
    btn.dataset.selected =
      (btn.getAttribute('data-bucket') === wanted) ? 'true' : 'false';
  });
}
applyMobileTab();
document.querySelectorAll('.bucket-tab').forEach(btn => {
  btn.addEventListener('click', () => {
    localStorage.setItem(MOBILE_KEY, btn.getAttribute('data-bucket'));
    applyMobileTab();
  });
});

// --- Adaptive polling ---------------------------------------------------
function pollKanban() {
  fetch('/api/kanban')
    .then(r => r.json())
    .then(j => {
      const interval = j.active_rip ? POLL_ACTIVE : POLL_IDLE;
      setTimeout(pollKanban, interval);
      // Refresh drive-status drawer body on each tick.
      const driveBody = document.querySelector(
        '[data-target="drive-status-body"]'
      );
      if (driveBody) {
        fetch('/api/drive/status').then(r => r.json()).then(s => {
          driveBody.textContent = JSON.stringify(s, null, 2);
        });
      }
      if (localStorage.getItem(BOTTOM_KEY) === 'true') refreshBottomDrawer();
    })
    .catch(() => setTimeout(pollKanban, POLL_IDLE));
}
setTimeout(pollKanban, POLL_IDLE);
"""


_STYLES = f"""
:root {{ color-scheme: dark; }}
body {{ font-family: var(--font-body, system-ui); background: var(--bg, #111);
       color: var(--ink, #eee); margin: 0; padding: 0; }}
.page-header {{ display: grid; grid-template-columns: 1fr auto 1fr;
               align-items: center; padding: var(--s-3, 12px) var(--s-4, 16px);
               border-bottom: 1px solid var(--line, #333);
               background: var(--surface, #1c1c1c); position: sticky; top: 0;
               z-index: 5; }}
.header-left {{ display: flex; gap: var(--s-2, 8px); align-items: center; }}
.header-stats {{ display: flex; gap: var(--s-3, 12px); justify-self: center;
                color: var(--ink-3, #aaa); }}
.header-right {{ display: flex; gap: var(--s-2, 8px); justify-self: end; }}
.wordmark {{ font-weight: 700; color: var(--ink, #eee); }}
.daemon-state-dot {{ width: 10px; height: 10px; border-radius: 50%;
                    display: inline-block; background: var(--ok, #4aff8a); }}
.daemon-state-dot[data-daemon-state="stopped"] {{ background: var(--meat-red, #ff4a4a); }}
main.kanban {{ display: grid; grid-template-columns: repeat(4, 1fr);
              gap: var(--s-4, 16px); padding: var(--s-4, 16px); }}
.column {{ background: var(--surface, #1c1c1c);
          border: 1px solid var(--line, #333); border-radius: var(--r-3, 8px);
          padding: var(--s-3, 12px);
          max-height: calc(100vh - 160px); overflow-y: auto; }}
.column-header {{ position: sticky; top: 0; background: var(--surface, #1c1c1c);
                 z-index: 1; padding-bottom: var(--s-2, 8px); }}
.column-title {{ font-size: var(--fs-md, 14px); letter-spacing: 0.08em;
                text-transform: uppercase; color: var(--ink-3, #aaa);
                margin: 0 0 var(--s-3, 12px) 0; }}
.count-badge {{ color: var(--ink, #eee); font-weight: 600; }}
.card {{ background: var(--surface-2, #222); border: 1px solid var(--line, #333);
        border-left: 3px solid var(--info, #4a9eff);
        border-radius: var(--r-2, 4px); padding: var(--s-3, 12px);
        margin-bottom: var(--s-3, 12px); cursor: pointer; }}
.card[data-bucket="review"] {{ border-left-color: var(--warn, #ffb84a); }}
.card[data-bucket="library"] {{ border-left-color: var(--ok, #4aff8a); }}
/* D-card-evolution-tokens: damaged state uses --meat-red shadow, not
   left-border, to visually shout "needs attention" without losing the
   bucket-color hint. Selected via data-state so the class name string
   is only emitted on actually-damaged cards (and tests can assert
   absence on healthy cards via plain string-search). */
.card[data-state="damaged"] {{ border-left-color: var(--meat-red, #ff4a4a);
                              box-shadow: 0 0 12px 2px rgba(255, 74, 74, 0.35); }}
.card-head {{ display: flex; align-items: center; gap: var(--s-2, 8px);
             flex-wrap: wrap; }}
.card-thumb {{ width: 40px; height: 40px; object-fit: cover;
              border-radius: var(--r-2, 4px); }}
.card-title {{ font-size: var(--fs-sm, 13px); margin: 0; }}
.chip {{ font-size: var(--fs-xs, 11px); padding: 2px 6px;
        background: var(--ink, #eee); color: var(--bg, #111);
        border-radius: var(--r-full, 999px); }}
/* D-card-evolution-tokens: confirmed glows in --ok (system trust);
   asserted uses a dashed border to signal "operator said so, not
   confirmed". Style via data-meta-state so the class-name literal
   is only emitted when a chip of that type actually renders. */
.chip[data-meta-state="confirmed"] {{ background: var(--ok, #4aff8a);
                                     color: var(--bg, #111);
                                     box-shadow: 0 0 4px var(--ok, #4aff8a); }}
.chip[data-meta-state="asserted"] {{ background: transparent;
                                    color: var(--ink, #eee);
                                    border: 1px dashed var(--line, #888); }}
.track-bar {{ display: flex; gap: 2px; margin-top: var(--s-2, 8px); }}
.track-cell {{ flex: 1; height: 6px; background: var(--surface, #1c1c1c); }}
.track-cell--success {{ background: var(--ok, #4aff8a); }}
.track-cell--fail {{ background: var(--meat-red, #ff4a4a); }}
.track-cell--in_progress {{ background: var(--info, #4a9eff); }}
.track-cell--pending {{ background: var(--surface, #1c1c1c); }}
.track-cell--identified {{ outline: 1px solid var(--ok, #4aff8a); }}
.card-actions {{ display: flex; gap: var(--s-2, 8px); margin-top: var(--s-2, 8px); }}
.progress {{ margin-top: var(--s-2, 8px); }}
.progress-stage {{ font-size: var(--fs-xs, 11px); color: var(--ink-3, #aaa); }}
.card-section {{ border-top: 1px solid var(--line, #333);
                padding-top: var(--s-2, 8px); margin-top: var(--s-2, 8px); }}
.section-title {{ font-size: var(--fs-xs, 11px); text-transform: uppercase;
                 letter-spacing: 0.08em; color: var(--ink-3, #aaa);
                 margin: 0 0 var(--s-2, 8px) 0; }}
.hint-controls {{ border: 1px solid var(--line, #333); padding: var(--s-2, 8px); }}
.hint-controls label {{ display: block; margin: 4px 0; }}
.per-track-table {{ width: 100%; border-collapse: collapse;
                   margin-top: var(--s-2, 8px); }}
.per-track-table td, .per-track-table th {{ padding: 2px 4px;
                                            border-bottom: 1px solid var(--line, #333); }}
.btn {{ font-family: var(--font-body, system-ui); padding: 4px 10px;
       border-radius: var(--r-2, 4px); border: 1px solid var(--line, #333);
       color: var(--ink, #eee); background: var(--surface, #1c1c1c);
       cursor: pointer; text-decoration: none; }}
.btn--accent {{ background: var(--accent, var(--info, #4a9eff));
               color: var(--bg, #111); }}
.keyboard-help {{ position: fixed; top: 12px; right: 12px; z-index: 10;
                 border-radius: 50%; width: 28px; height: 28px;
                 background: var(--surface-2, #222); border: 1px solid var(--line, #333);
                 color: var(--ink, #eee); }}
.drawer {{ position: fixed; background: var(--surface, #1c1c1c);
          border: 1px solid var(--line, #333); z-index: 8;
          transition: transform 200ms ease; }}
.drawer--right {{ top: 0; right: 0; bottom: 0; width: 420px;
                 transform: translateX(100%); }}
.drawer--right[aria-hidden="false"] {{ transform: translateX(0); }}
.drawer--bottom {{ left: 0; right: 0; bottom: 0; height: 240px;
                  transform: translateY(100%); }}
.drawer--bottom[aria-hidden="false"] {{ transform: translateY(0); }}
.drawer-body {{ padding: var(--s-3, 12px); height: 100%; overflow: auto; }}
.bucket-tabs {{ display: none; gap: var(--s-2, 8px);
               padding: var(--s-2, 8px) var(--s-3, 12px); }}
.bucket-tab {{ background: var(--surface-2, #222); color: var(--ink, #eee);
              border: 1px solid var(--line, #333); padding: 4px 10px;
              border-radius: var(--r-2, 4px); }}
.bucket-tab[data-selected="true"] {{ background: var(--accent, var(--info, #4a9eff));
                                    color: var(--bg, #111); }}

/* D-mobile-breakpoint-v1: single-column at ≤720px with bucket tabs. */
@media (max-width: {MOBILE_BREAKPOINT_PX}px) {{
  main.kanban {{ grid-template-columns: 1fr; }}
  .bucket-tabs {{ display: flex; }}
  .column {{ display: none; }}
  .column[data-active-mobile="true"] {{ display: block; }}
  .drawer--right {{ width: 100%; }}
}}
"""


def _stats(buckets: dict, cards_flat: list[DiscCard]) -> dict:
    return {
        "total": sum(len(v) for v in buckets.values()),
        "review": len(buckets.get("review", [])),
        "partial": sum(1 for c in cards_flat if c.partial),
    }


def render_kanban_page(music_root: Path, loop_state) -> str:
    state = build_kanban_state(music_root, loop_state=loop_state)
    cards_flat = [c for cards in state.buckets.values() for c in cards]
    stats = _stats(state.buckets, cards_flat)
    links = {
        "navidrome": os.environ.get("NAVIDROME_URL", ""),
        "beets_web": os.environ.get("BEETS_WEB_URL", ""),
    }
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
        f'<meta name="kanban-poll-ms-active" content="{POLL_MS_ACTIVE}">'
        f'<meta name="kanban-poll-ms-idle" content="{POLL_MS_IDLE}">'
        '<title>cd-archivist · kanban</title>'
        '<link rel="stylesheet" href="/static/tokens.css">'
        f'<style>{_STYLES}</style>'
        '</head>'
        '<body>'
        f'{_render_header_bar(stats, links)}'
        f'{_render_bucket_tabs()}'
        '<main class="kanban">'
        f'{columns}'
        '</main>'
        f'{_render_right_drawer()}'
        f'{_render_bottom_drawer()}'
        f'{_render_keyboard_help()}'
        f'<script type="module">{_INLINE_JS}</script>'
        '</body></html>'
    )
