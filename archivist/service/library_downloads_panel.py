"""Downloads (Spooty) panel — `/library/downloads` viewport.

Sprint-10 / downloads-impl. Renders the spooty download queue: one row
per playlist, a per-track pip strip (green=ok, pulp=active, ember=error,
empty=pending), submit-playlist form, per-track retry/delete buttons,
retry-whole-playlist button, and a stats header
(Playlists · Tracks · Done · Errors).

Polling cadence per sprint-10 plan: 1000ms during active rip activity,
5000ms idle. The render module emits the active cadence initially; the
client-side `library:poll-tick` listener (per-panel JS — out of scope
of this module) can mutate the meta `content` to switch to idle when
``any active tracks == 0``.

When spooty is unavailable the panel degrades to an empty state with
the submit form still present (the operator may want to queue a
playlist even when the worker is offline; spooty's retry-on-restart
will pick it up). The empty state still emits poll meta tags so the
panel transparently re-renders once spooty comes back online.
"""

from __future__ import annotations

import html
import os
from typing import Iterable

from archivist.service.clients.spooty_client import (
    SpootyPlaylist,
    SpootyTrack,
    SpootyUnavailable,
    list_playlists,
)
from archivist.service.library_panel_inventory import PanelSpec


POLL_MS_ACTIVE = 1000
POLL_MS_IDLE = 5000
POLL_ENDPOINT = "/api/library/downloads"


_PIP_CLASSES = {
    "ok": "pip pip--ok",
    "done": "pip pip--ok",
    "active": "pip pip--active",
    "running": "pip pip--active",
    "error": "pip pip--error",
    "failed": "pip pip--error",
    "pending": "pip pip--pending",
}


def _pip_class(state: str) -> str:
    return _PIP_CLASSES.get(state.lower(), "pip pip--pending")


def _track_pip(track: SpootyTrack) -> str:
    cls = _pip_class(track.state)
    title = html.escape(track.title or track.id)
    if track.error:
        title = f"{title} — {html.escape(track.error)}"
    return (
        f'<span class="{cls}" data-track-id="{html.escape(track.id)}" '
        f'data-state="{html.escape(track.state)}" '
        f'title="{title}"></span>'
    )


def _track_actions(track: SpootyTrack) -> str:
    return (
        '<div class="cda-dl-track-actions">'
        '<button type="button" '
        'class="btn btn--small cda-dl-track-retry" '
        f'data-track-id="{html.escape(track.id)}">retry</button>'
        '<button type="button" '
        'class="btn btn--small btn--danger cda-dl-track-delete" '
        f'data-track-id="{html.escape(track.id)}">delete</button>'
        "</div>"
    )


def _track_row(track: SpootyTrack) -> str:
    title = html.escape(track.title or track.id)
    err = (
        f'<span class="cda-dl-track-error">'
        f"{html.escape(track.error or '')}</span>"
        if track.error
        else ""
    )
    return (
        '<li class="cda-dl-track" '
        f'data-track-id="{html.escape(track.id)}" '
        f'data-state="{html.escape(track.state)}">'
        f"{_track_pip(track)}"
        f'<span class="cda-dl-track-title">{title}</span>'
        f'<span class="cda-dl-track-state mono">{html.escape(track.state)}</span>'
        f"{err}"
        f"{_track_actions(track)}"
        "</li>"
    )


def _playlist_row(playlist: SpootyPlaylist) -> str:
    pips = "".join(_track_pip(t) for t in playlist.tracks)
    track_rows = "".join(_track_row(t) for t in playlist.tracks)
    return (
        '<section class="cda-dl-playlist" '
        f'data-playlist-id="{html.escape(playlist.id)}">'
        '<header class="cda-dl-playlist-head">'
        '<div class="cda-dl-playlist-head-left">'
        f'<h2 class="cda-dl-playlist-name">{html.escape(playlist.name or playlist.id)}</h2>'
        f'<span class="meta cda-dl-playlist-counts">'
        f"{playlist.done_count} / {playlist.track_count} done"
        + (
            f' · <span class="cda-dl-error-count">{playlist.error_count} errors</span>'
            if playlist.error_count
            else ""
        )
        + "</span>"
        "</div>"
        '<div class="cda-dl-playlist-head-right">'
        '<button type="button" '
        'class="btn btn--small cda-dl-playlist-retry" '
        f'data-playlist-id="{html.escape(playlist.id)}">retry playlist</button>'
        "</div>"
        "</header>"
        f'<div class="cda-dl-pipstrip" aria-label="track states">{pips}</div>'
        f'<ul class="cda-dl-tracks">{track_rows}</ul>'
        "</section>"
    )


def _playlists(playlists: Iterable[SpootyPlaylist]) -> str:
    return "".join(_playlist_row(p) for p in playlists)


def _stats_header(playlists: list[SpootyPlaylist]) -> str:
    pl_count = len(playlists)
    track_count = sum(p.track_count for p in playlists)
    done_count = sum(p.done_count for p in playlists)
    error_count = sum(p.error_count for p in playlists)
    return (
        '<div class="cda-dl-stats">'
        f'<span class="cda-dl-stat"><span class="num">{pl_count}</span> '
        '<span class="label">playlists</span></span>'
        f'<span class="cda-dl-stat"><span class="num">{track_count}</span> '
        '<span class="label">tracks</span></span>'
        f'<span class="cda-dl-stat"><span class="num">{done_count}</span> '
        '<span class="label">done</span></span>'
        f'<span class="cda-dl-stat cda-dl-stat--errors">'
        f'<span class="num">{error_count}</span> '
        '<span class="label">errors</span></span>'
        "</div>"
    )


def _submit_form() -> str:
    return (
        '<form class="cda-dl-submit" '
        'data-action="/api/library/downloads/playlists" method="post">'
        '<label class="cda-dl-submit-label" for="cda-dl-submit-url">'
        "Spotify playlist URL"
        "</label>"
        '<div class="cda-dl-submit-row">'
        '<input type="url" id="cda-dl-submit-url" name="url" '
        'placeholder="https://open.spotify.com/playlist/..." required>'
        '<button type="submit" class="btn cda-dl-submit-btn">submit</button>'
        "</div>"
        "</form>"
    )


def _is_active(playlists: list[SpootyPlaylist]) -> bool:
    for p in playlists:
        for t in p.tracks:
            if t.state.lower() in {"active", "running"}:
                return True
    return False


def render(spec: PanelSpec) -> str:
    """Render the Downloads panel viewport.

    Pulls the live playlist listing from spooty (or an empty list on
    SpootyUnavailable), renders the stats header + submit form +
    playlist rows, and emits the polling meta tags so the chassis
    dispatcher refreshes us at 1s active / 5s idle.
    """
    unavailable = False
    error_message = ""
    try:
        playlists = list_playlists()
    except SpootyUnavailable as exc:
        playlists = []
        unavailable = True
        error_message = str(exc)

    poll_ms = POLL_MS_ACTIVE if _is_active(playlists) else POLL_MS_IDLE

    if unavailable:
        body_html = (
            '<div class="cda-lib-panel-empty">'
            '<div class="cda-lib-panel-empty-foot">'
            '<span class="tag">spooty unavailable</span>'
            f"<span>{html.escape(error_message)}</span>"
            "</div>"
            "</div>"
        )
    elif not playlists:
        body_html = (
            '<div class="cda-lib-panel-empty">'
            '<div class="cda-lib-panel-empty-foot">'
            '<span class="tag">empty</span>'
            "<span>no playlists queued — submit one above.</span>"
            "</div>"
            "</div>"
        )
    else:
        body_html = (
            f'<div class="cda-dl-playlists">{_playlists(playlists)}</div>'
        )

    api_url_link = html.escape(
        os.environ.get("SPOOTY_API_URL", "http://192.168.6.38:3003/api")
    )

    return (
        '<section class="cda-lib-viewport" data-panel="downloads">'
        f'<meta name="library-poll-ms" content="{poll_ms}">'
        f'<meta name="library-poll-endpoint" content="{POLL_ENDPOINT}">'
        '<div class="cda-lib-panel">'
        '<header class="cda-lib-panel-head">'
        '<div class="cda-lib-panel-head-left">'
        f'<span class="eyebrow">{html.escape(spec["eyebrow"])}</span>'
        f'<h1>{html.escape(spec["title"])}</h1>'
        f'<p class="sub">{html.escape(spec["summary"])}</p>'
        "</div>"
        '<div class="cda-lib-panel-head-right">'
        f'<span class="meta mono">{api_url_link}</span>'
        "</div>"
        "</header>"
        f"{_stats_header(playlists)}"
        f"{_submit_form()}"
        f'<div class="cda-dl-body">{body_html}</div>'
        "</div>"
        "</section>"
    )
