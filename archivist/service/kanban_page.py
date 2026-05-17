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
    ("library", "In library"),
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


# Sprint-7 impl-card-anatomy: map the disc-card-builder's terminal
# state labels to the build-prompt-spec cell-state names. The
# recovered state isn't currently distinguishable from clean at the
# builder level — drivers' DriveStatus doesn't track per-track
# recovery yet — so success → clean today; sprint-8 may light up
# recovered once that signal exists.
_TRACK_STATE_MAP = {
    "success": "clean",
    "fail": "unrecoverable",
    "in_progress": "ripping",
    "pending": "pending",
}


def _render_track_bar(card: DiscCard) -> str:
    from archivist.service.track_identification import identified_tracks
    ident_set = identified_tracks(source_json=card.source_json)
    progress_pct = 0
    if card.progress is not None:
        try:
            progress_pct = int(card.progress.get("percent", 0))
        except (TypeError, ValueError):
            progress_pct = 0

    cells: list[str] = []
    for i, state in enumerate(card.track_bar, start=1):
        cell_state = _TRACK_STATE_MAP.get(state, state)
        identified = i in ident_set
        ident_attr = f' data-track-identified-{i}="true"' if identified else ""
        ident_class = " track-cell--identified" if identified else ""
        progress_attr = ""
        if cell_state == "ripping":
            # D-inline-css-whitelist: CSS-custom-property-as-data
            # pattern allowed.
            progress_attr = f' style="--progress: {progress_pct}%"'
        cells.append(
            f'<span class="track-cell track-cell--{_esc(cell_state)}'
            f'{ident_class}"{ident_attr}{progress_attr}></span>'
        )
    track_count = len(card.track_bar)
    return (
        '<div class="track-bar" role="img" aria-label="track progress" '
        f'style="--track-count: {track_count}">'
        + "".join(cells) + '</div>'
    )


def _accent_class(card: DiscCard) -> str:
    """Per the build-prompt §kanban table:

        Capture default → pulp; capture+ripping → pulp-ripping
        Capture+damaged → ember-damaged
        Beets ID        → sky
        Review weak     → amber; Review no-match → ember
        Library         → moss
    """
    bucket = card.bucket
    if bucket == "library":
        return "card--accent-moss"
    if bucket == "capture":
        if _is_damaged(card):
            return "card--accent-ember-damaged"
        if card.progress is not None:
            return "card--accent-pulp-ripping"
        return "card--accent-pulp"
    if bucket == "beets_id":
        return "card--accent-sky"
    if bucket == "review":
        # Review priority: NO_MATCH / NO_ID_NO_TAGS → ember; others → amber.
        pri = card.review_priority
        # ReviewPriority: PARTIAL=0, WEAK_MATCH=1, NO_MATCH=2, NO_ID_NO_TAGS=3
        if pri is not None and pri >= 2:
            return "card--accent-ember"
        return "card--accent-amber"
    return ""


def _card_title(card: DiscCard) -> str:
    src = card.source_json or {}
    album = (src.get("detected_metadata") or {}).get("album")
    return _esc(album) if album else _esc(card.folder)


def _card_artist(card: DiscCard) -> str:
    src = card.source_json or {}
    artist = (src.get("detected_metadata") or {}).get("album_artist")
    if not artist:
        hint_artist = (card.operator_hints or {}).get("artist")
        return _esc(hint_artist) if hint_artist else ""
    return _esc(artist)


def _render_card_head(card: DiscCard) -> str:
    return (
        '<header class="card-head">'
        f'{_render_thumbnail(card)}'
        '<div class="card-head-text">'
        f'<span class="slug">{_esc(card.folder)}</span>'
        f'<h3 class="title">{_card_title(card)}</h3>'
        f'<div class="artist">{_card_artist(card)}</div>'
        '</div>'
        '</header>'
    )


def _render_status_line(card: DiscCard) -> str:
    from archivist.service import status_line as _sl
    text = _sl.format(card)
    if not text:
        return ""
    return f'<div class="cda-status">{_esc(text)}</div>'


def _render_chip_row(card: DiscCard) -> str:
    """0–4 chips per the build prompt: VA / BURNED / MIX / WEAK MATCH /
    MUSICBRAINZ. Operator-asserted (hint-derived) chips get
    .chip--asserted; system-confirmed ones get .chip--confirmed."""
    chips: list[str] = []
    hints = card.operator_hints or {}
    va = bool(hints.get("various_artists"))
    burned = bool(hints.get("burned_cd"))

    # Mix CD is the special-case both-on chip per sprint-6.5; build
    # prompt also lists MIX as its own chip. Emit MIX when both toggles
    # ON (replaces VA + BURNED separately), else emit individually.
    if va and burned:
        chips.append(
            '<span class="chip chip--asserted" '
            f'data-chip="mix">MIX · Mix CD ({_track_count(card)} tracks)</span>'
        )
    else:
        if va:
            chips.append(
                '<span class="chip chip--asserted" '
                'data-chip="va">VA</span>'
            )
        if burned:
            chips.append(
                '<span class="chip chip--asserted" '
                'data-chip="burned">BURNED</span>'
            )

    # Beets-side scores: WEAK MATCH for review-bucket weak matches,
    # MUSICBRAINZ for library-bucket disc-id-confirmed.
    top = card.top_candidate or {}
    score = top.get("score") if isinstance(top, dict) else None
    src = card.source_json or {}
    identifiers = src.get("identifiers") or {}
    has_disc_id = bool(identifiers.get("musicbrainz_disc_id"))

    if card.bucket == "review" and isinstance(score, (int, float)) and score < 0.85:
        chips.append(
            '<span class="chip chip--asserted" data-chip="weak">'
            f'WEAK MATCH · {score:.2f}</span>'
        )
    elif card.bucket == "library" and has_disc_id and isinstance(score, (int, float)):
        chips.append(
            '<span class="chip chip--confirmed" data-chip="musicbrainz">'
            f'MUSICBRAINZ · {score:.2f}</span>'
        )
    return '<div class="chip-row">' + "".join(chips) + '</div>'


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
    # Sprint-7: only emit an <img> when a photo was actually captured;
    # otherwise fall through to the conic-gradient placeholder so the
    # card doesn't render a broken-image icon.
    if physical.get("photo_captured"):
        return f"/review/{folder}/disc-photo.jpg"
    return None


def _render_thumbnail(card: DiscCard) -> str:
    src = _thumbnail_src(card)
    if src is None:
        # Sprint-7 / impl-disc-photo-placeholder: CSS-drawn conic-gradient
        # glow stands in until the pi-camera photo lands on disk. We
        # still encode the would-be photo URL as a data attribute so
        # the front-end (and tests) can find it.
        folder = _esc(card.folder)
        return (
            '<div class="thumb thumb--placeholder" '
            f'data-photo-src="/review/{folder}/disc-photo.jpg" '
            'aria-hidden="true"></div>'
        )
    return (
        f'<img class="thumb card-thumb" loading="lazy" alt="" src="{src}">'
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


_CONFIRM_HINT_TEXT = (
    "Destructive actions require a second click to confirm. "
    "The partial flac files stay on disk until you choose."
)


def _render_damaged_actions_section(card: DiscCard) -> str:
    folder = _esc(card.folder)
    return (
        '<section class="card-section" data-section="damaged-actions">'
        '<h4 class="section-title">damaged-disc actions</h4>'
        '<div class="card-actions">'
        # Process partial is non-destructive (moves data forward); no gate.
        '<button type="button" class="btn btn--accent" '
        f'data-endpoint="/api/disc/{folder}/process-partial">'
        'Process partial</button>'
        # Redo deletes the partial folder — gated.
        '<button type="button" class="btn" '
        f'data-destructive="true" data-action="redo" '
        f'data-endpoint="/api/disc/{folder}/redo?confirm=true">'
        'Redo</button>'
        # Rerip-tracks re-runs cdparanoia over a track subset — gated.
        '<button type="button" class="btn" '
        f'data-destructive="true" data-action="rerip-tracks" '
        f'data-endpoint="/api/disc/{folder}/rerip-tracks">'
        'Pick tracks to re-rip</button>'
        '</div>'
        f'<p class="confirm-hint">{_esc(_CONFIRM_HINT_TEXT)}</p>'
        '</section>'
    )


def _render_card(card: DiscCard) -> str:
    folder = _esc(card.folder)
    damaged = _is_damaged(card)
    damaged_class = " card--damaged" if damaged else ""
    damaged_attr = ' data-state="damaged"' if damaged else ""
    accent_class = _accent_class(card)
    accent_segment = f" {accent_class}" if accent_class else ""

    # Sprint-7 / impl-candidates-section-ui: placeholder is rendered
    # server-side; the kanban JS fetches /api/disc/<folder>/candidates
    # on first expand and replaces the inner body when the response
    # carries a non-empty candidates list. The section element is
    # hidden until the fetch resolves with results so cards without
    # candidates don't leave an empty header sitting around.
    candidates_section = (
        '<section class="card-section" data-section="candidates" '
        f'data-candidates-folder="{folder}" hidden>'
        '<h4 class="section-title">beets candidates</h4>'
        '<div class="candidate-rows" data-target="candidate-rows"></div>'
        '</section>'
    )
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
        f'{_render_card_head(card)}'
        f'{_render_track_bar(card)}'
        f'{_render_status_line(card)}'
        f'{_render_chip_row(card)}'
        f'{_render_collapsed_actions(card)}'
    )
    expanded = (
        '<div class="card-body" hidden>'
        f'{candidates_section}{hints_section}{manual_section}{damaged_section}'
        '</div>'
    )

    return (
        f'<article class="card{damaged_class}{accent_segment}"{damaged_attr} '
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


def _render_live_status(active: bool, disc_slug: str | None) -> str:
    """Header live-status chip per the build prompt §"Header bar":
    pulsing green dot + "ripping · DISC-<slug>" active, "idle" idle."""
    if active:
        text = f"ripping · {disc_slug or 'disc'}"
        dot_class = "dot dot--pulse-moss"
    else:
        text = "idle"
        dot_class = "dot dot--quiet"
    return (
        '<span class="live-status">'
        f'<span class="{dot_class}" aria-hidden="true"></span>'
        f'<span class="live-status-text">{_esc(text)}</span>'
        '</span>'
    )


def _render_rig_stats(stats: dict) -> str:
    """5-cell bordered group per the build-prompt §"Header bar":
    Ripped / In review / Partial / Storage / Uptime. Storage + Uptime
    are populated by JS via /api/rig/stats (lane-3's endpoint)."""
    cells = [
        ("Ripped", str(stats.get("ripped", 0)), "rig-ripped"),
        ("In review", str(stats.get("review", 0)), "rig-review"),
        ("Partial", str(stats.get("partial", 0)), "rig-partial"),
        # Storage + Uptime are populated by the rig-stats JS poll.
        ("Storage", "—", "rig-storage"),
        ("Uptime", "—", "rig-uptime"),
    ]
    rendered = "".join(
        '<div class="stat-cell">'
        f'<span class="stat-value" data-rig-cell="{key}">{_esc(value)}</span>'
        f'<span class="stat-label">{_esc(label)}</span>'
        '</div>'
        for label, value, key in cells
    )
    return f'<div class="rig-stats">{rendered}</div>'


def _render_header_bar(
    stats: dict, links: dict, *,
    active_rip: bool = False, active_disc: str | None = None,
) -> str:
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
        '<span class="cda-brand-mark cda-brand-mark--header">cd/a</span>'
        '<span class="wordmark">cd-archivist</span>'
        '<span class="daemon-state-dot" data-daemon-state="active" '
        'aria-label="daemon active"></span>'
        f'{_render_live_status(active_rip, active_disc)}'
        '</div>'
        '<div class="header-stats">'
        f'<span class="stat">total {stats["total"]}</span>'
        f'<span class="stat">review {stats["review"]}</span>'
        f'<span class="stat">partial {stats["partial"]}</span>'
        '</div>'
        f'{_render_rig_stats(stats)}'
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
        '<div class="thumb thumb--placeholder thumb--placeholder--lg" '
        'aria-hidden="true"></div>'
        '<h3>drive status</h3>'
        '<div data-target="drive-status-body">'
        '<p class="meta">idle</p>'
        '</div>'
        '</div>'
        '<template data-drawer-template="card-detail">'
        '<div class="card-detail">'
        '<h3 data-target="detail-title"></h3>'
        '<pre data-target="detail-log"></pre>'
        '<pre class="cda-json" data-target="detail-source-json"></pre>'
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
// Sprint-7 impl-destructive-gate: arm window is 5000ms.
const CONFIRM_TIMEOUT = 5000;

// --- Destructive-action gate -------------------------------------------
// First click on a [data-destructive="true"] button arms it (label
// swaps to `confirm: <action>`, class gains .btn--confirm-armed).
// Second click within CONFIRM_TIMEOUT fires the POST. Click elsewhere
// or wait it out → revert.
let armedDestructive = null;
let armedTimer = null;

function disarmDestructive() {
  if (!armedDestructive) return;
  armedDestructive.btn.classList.remove('btn--confirm-armed');
  armedDestructive.btn.textContent = armedDestructive.originalLabel;
  if (armedTimer) { clearTimeout(armedTimer); armedTimer = null; }
  armedDestructive = null;
}

function armDestructive(btn) {
  disarmDestructive();
  const action = btn.getAttribute('data-action') || 'action';
  armedDestructive = { btn, originalLabel: btn.textContent };
  btn.classList.add('btn--confirm-armed');
  btn.textContent = `confirm: ${action}`;
  armedTimer = setTimeout(disarmDestructive, CONFIRM_TIMEOUT);
}

async function fireDestructive(btn) {
  const endpoint = btn.getAttribute('data-endpoint');
  disarmDestructive();
  if (!endpoint) return;
  try {
    await fetch(endpoint, { method: 'POST' });
  } catch (_) { /* swallow — next poll surfaces state */ }
}

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
  if (!expanded) {
    openRightDrawerForCard(card);
    loadCandidatesForCard(card);
  }
}

// Sprint-7 / impl-candidates-section-ui: fetch /api/disc/<folder>/candidates
// once per card-expand, render up to 5 rows when the response carries
// a non-empty list, hide the section otherwise. The conditional render
// guard lives here (data.candidates && data.candidates.length).
async function loadCandidatesForCard(card) {
  const section = card.querySelector('[data-section="candidates"]');
  if (!section || section.dataset.loaded === 'true') return;
  const folder = section.getAttribute('data-candidates-folder');
  if (!folder) return;
  try {
    const res = await fetch(`/api/disc/${encodeURIComponent(folder)}/candidates`);
    if (!res.ok) return;
    const data = await res.json();
    if (!(data.candidates && data.candidates.length)) {
      section.hidden = true;
      return;
    }
    renderCandidateRows(section, folder, data.candidates.slice(0, 5));
    section.hidden = false;
    section.dataset.loaded = 'true';
  } catch (_) { /* swallow — operator can re-expand to retry */ }
}

function renderCandidateRows(section, folder, candidates) {
  const target = section.querySelector('[data-target="candidate-rows"]');
  if (!target) return;
  const rows = candidates.map((c, i) => {
    const topClass = i === 0 ? ' candidate--top' : '';
    const score = (c.score == null ? '' : Math.round(c.score * 100));
    const year = c.year ? ` · ${c.year}` : '';
    const country = c.country ? ` · ${c.country}` : '';
    return (
      `<div class="candidate-row${topClass}">` +
        `<span class="score-chip">${score}</span>` +
        `<div class="candidate-meta">` +
          `<div class="candidate-meta-title">${escapeHtml(c.artist || '')} — ${escapeHtml(c.title || '')}</div>` +
          `<div class="candidate-meta-sub">${escapeHtml(c.mbid || '')}${year}${country}</div>` +
        `</div>` +
        `<button type="button" class="apply-btn btn btn--accent" ` +
          `data-mbid="${escapeAttr(c.mbid || '')}" ` +
          `data-folder="${escapeAttr(folder)}">apply</button>` +
      `</div>`
    );
  }).join('');
  target.innerHTML = rows;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>]/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
}
function escapeAttr(s) {
  return String(s).replace(/["&<>]/g, (c) => ({'"':'&quot;','&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
}

document.addEventListener('click', async (e) => {
  const apply = e.target.closest('.apply-btn[data-mbid]');
  if (apply) {
    e.preventDefault();
    e.stopPropagation();
    const folder = apply.getAttribute('data-folder');
    const mbid = apply.getAttribute('data-mbid');
    if (folder && mbid) {
      try {
        await fetch(`/api/disc/${encodeURIComponent(folder)}/accept-top-candidate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mbid }),
        });
      } catch (_) { /* swallow */ }
    }
  }
});

document.addEventListener('click', (e) => {
  // Destructive-action gate: arm on first click, fire on second.
  const destructive = e.target.closest('[data-destructive="true"]');
  if (destructive) {
    if (armedDestructive && armedDestructive.btn === destructive) {
      fireDestructive(destructive);
    } else {
      armDestructive(destructive);
    }
    return;
  }
  // Outside-click reverts any armed destructive button.
  if (armedDestructive) {
    disarmDestructive();
  }
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

// --- Transition machinery (sprint-7 impl-transitions) ------------------
// Diff each kanban poll against the previous one. Cards new this
// cycle get .card--entering (fadeIn 200ms). Cards vanished this
// cycle get .card--leaving (fadeOut 200ms) then removed from the
// DOM. Cards whose payload hash changed get .flash-moss (200ms
// var(--moss) border pulse).
const TRANSITION_MS = 200;
let lastPayloadHashes = new Map(); // folder -> shallow hash
function payloadHash(card) {
  try { return JSON.stringify(card.source_json || {}); }
  catch (_) { return ''; }
}
function diffKanban(payload) {
  const seen = new Map();
  for (const bucket of Object.values(payload.buckets || {})) {
    for (const c of bucket) {
      if (c.folder) seen.set(c.folder, payloadHash(c));
    }
  }
  // Apply .card--entering to cards new this cycle.
  for (const [folder, hash] of seen.entries()) {
    const el = document.querySelector(`[data-card-id="${folder}"]`);
    if (!el) continue;
    if (!lastPayloadHashes.has(folder)) {
      el.classList.add('card--entering');
      setTimeout(() => el.classList.remove('card--entering'), TRANSITION_MS);
    } else if (lastPayloadHashes.get(folder) !== hash) {
      el.classList.add('flash-moss');
      setTimeout(() => el.classList.remove('flash-moss'), TRANSITION_MS);
    }
  }
  // Apply .card--leaving to cards present last cycle but absent now.
  for (const folder of lastPayloadHashes.keys()) {
    if (seen.has(folder)) continue;
    const el = document.querySelector(`[data-card-id="${folder}"]`);
    if (!el) continue;
    el.classList.add('card--leaving');
    setTimeout(() => { try { el.remove(); } catch (_) {} }, TRANSITION_MS);
  }
  lastPayloadHashes = seen;
}

// --- Adaptive polling ---------------------------------------------------
function pollKanban() {
  fetch('/api/kanban')
    .then(r => r.json())
    .then(j => {
      const interval = j.active_rip ? POLL_ACTIVE : POLL_IDLE;
      setTimeout(pollKanban, interval);
      diffKanban(j);
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


# Sprint-7 / impl-css-migration-brand-mark: the legacy inline `_STYLES`
# block moved onto /static/css/cda.css per D-inline-css-whitelist. The
# `MOBILE_BREAKPOINT_PX` Python constant above is preserved for the
# adaptive-polling / JS callers that read it; the matching @media rule
# is hard-coded to 720px in cda.css.


def _stats(buckets: dict, cards_flat: list[DiscCard]) -> dict:
    return {
        "total": sum(len(v) for v in buckets.values()),
        "ripped": len(buckets.get("library", [])),
        "review": len(buckets.get("review", [])),
        "partial": sum(1 for c in cards_flat if c.partial),
    }


def render_kanban_page(music_root: Path, loop_state) -> str:
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
        '</head>'
        '<body>'
        f'{_render_header_bar(stats, links, active_rip=active_rip, active_disc=active_disc)}'
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
