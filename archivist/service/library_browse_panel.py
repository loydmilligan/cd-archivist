"""Library Manager — Library (browse) panel.

Sprint-10 / library-impl. Replaces the sprint-9 placeholder for
`panel_id == "library"`. Build-prompt §3 / §7 explicitly scopes this
panel narrowly: search input + 10 most-recent imports + a prominent
"Open Navidrome ↗" CTA. Real browsing happens in Navidrome.

No polling — search is debounced client-side and fires on input;
the recent list refreshes only on full panel load. So this module
does NOT emit `library-poll-ms` / `library-poll-endpoint` meta tags
(chassis_js no-ops without them, per its contract).

Navidrome unavailable: render the empty state but keep the CTA
working (link is just an `<a href="$NAVIDROME_URL">`, independent of
the API).
"""

from __future__ import annotations

import html as _html
import os

from archivist.service.clients.subsonic_client import (
    AlbumSummary,
    NavidromeUnavailable,
    get_newest_albums,
)
from archivist.service.library_panel_inventory import PanelSpec


_SEARCH_INPUT_DEBOUNCE_MS = 300


def _render_recent_row(album: AlbumSummary) -> str:
    name = _html.escape(album.name) or "(untitled)"
    artist = _html.escape(album.artist) or "—"
    created = _html.escape(album.created or "")
    return (
        '<li class="cda-lib-browse-recent-row">'
        f'<span class="name">{name}</span>'
        f'<span class="artist">{artist}</span>'
        f'<span class="mono created">{created}</span>'
        '</li>'
    )


def _render_recent_block(albums: list[AlbumSummary]) -> str:
    if not albums:
        return (
            '<div class="cda-lib-browse-recent is-empty">'
            '<p class="meta">No recent imports to show.</p>'
            '</div>'
        )
    rows = "".join(_render_recent_row(a) for a in albums)
    return (
        '<div class="cda-lib-browse-recent">'
        '<h2 class="cda-lib-browse-recent-h">10 most-recent imports</h2>'
        f'<ul class="cda-lib-browse-recent-list">{rows}</ul>'
        '</div>'
    )


def _render_unavailable_block(reason: str) -> str:
    return (
        '<div class="cda-lib-browse-recent is-unavailable">'
        '<p class="meta">'
        'Navidrome is unavailable. The link above still opens it directly.'
        '</p>'
        f'<p class="meta cda-lib-browse-reason">{_html.escape(reason)}</p>'
        '</div>'
    )


def _render_cta(nav_url: str) -> str:
    if nav_url:
        href = _html.escape(nav_url, quote=True)
        return (
            f'<a class="cda-lib-browse-cta" href="{href}" target="_blank" rel="noopener">'
            'Open Navidrome ↗'
            '</a>'
        )
    # CTA still rendered but disabled when URL isn't configured so the
    # operator sees that the surface exists; tooltip explains the gap.
    return (
        '<span class="cda-lib-browse-cta is-disabled" '
        'title="set NAVIDROME_URL to enable">'
        'Open Navidrome ↗'
        '</span>'
    )


_SEARCH_JS = f"""
(function(){{
  const input = document.querySelector('[data-cda-browse-search]');
  if (!input) return;
  const out = document.querySelector('[data-cda-browse-results]');
  let timer = null;
  let inflight = null;
  function tick(){{
    const q = input.value.trim();
    if (!q) {{
      if (out) out.innerHTML = '';
      return;
    }}
    if (inflight) inflight.abort();
    inflight = new AbortController();
    fetch('/api/library/browse?q=' + encodeURIComponent(q), {{signal: inflight.signal}})
      .then(function(r){{ return r.json(); }})
      .then(function(body){{
        if (!out) return;
        const albums = (body && body.albums) || [];
        if (!albums.length) {{
          out.innerHTML = '<p class="meta">No matches.</p>';
          return;
        }}
        const rows = albums.map(function(a){{
          const name = (a.name || '(untitled)').replace(/[&<>]/g, function(c){{
            return c === '&' ? '&amp;' : c === '<' ? '&lt;' : '&gt;';
          }});
          const artist = (a.artist || '—').replace(/[&<>]/g, function(c){{
            return c === '&' ? '&amp;' : c === '<' ? '&lt;' : '&gt;';
          }});
          return '<li class="cda-lib-browse-result-row">'
            + '<span class="name">' + name + '</span>'
            + '<span class="artist">' + artist + '</span>'
            + '</li>';
        }}).join('');
        out.innerHTML = '<ul class="cda-lib-browse-result-list">' + rows + '</ul>';
      }})
      .catch(function(err){{
        if (err && err.name === 'AbortError') return;
        if (out) out.innerHTML = '<p class="meta">Search failed.</p>';
      }});
  }}
  input.addEventListener('input', function(){{
    if (timer) clearTimeout(timer);
    timer = setTimeout(tick, {_SEARCH_INPUT_DEBOUNCE_MS});
  }});
}})();
"""


def render(spec: PanelSpec) -> str:
    nav_url = os.environ.get("NAVIDROME_URL", "").strip()
    try:
        recent = get_newest_albums(limit=10)
        recent_block = _render_recent_block(recent)
    except NavidromeUnavailable as exc:
        recent_block = _render_unavailable_block(str(exc))

    return (
        '<section class="cda-lib-viewport">'
        '<div class="cda-lib-panel">'
        '<header class="cda-lib-panel-head">'
        '<div class="cda-lib-panel-head-left">'
        f'<span class="eyebrow">{_html.escape(spec["eyebrow"])}</span>'
        f'<h1>{_html.escape(spec["title"])}</h1>'
        f'<p class="sub">{_html.escape(spec["summary"])}</p>'
        '</div>'
        f'<div class="cda-lib-panel-head-right">{_render_cta(nav_url)}</div>'
        '</header>'
        '<div class="cda-lib-browse-search">'
        '<input type="search" data-cda-browse-search '
        'placeholder="Search Navidrome…" '
        'autocomplete="off" spellcheck="false" />'
        '<div data-cda-browse-results class="cda-lib-browse-results"></div>'
        '</div>'
        f'{recent_block}'
        '</div>'
        f'<script>{_SEARCH_JS}</script>'
        '</section>'
    )
