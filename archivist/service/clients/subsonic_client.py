"""Subsonic API client — read-only browse against Navidrome.

Sprint-10 / library-impl. Powers `/api/library/browse` (search) and
`/api/library/browse/recent` (10 most-recent imports).

Auth: Subsonic API uses username + token + salt where
`token = md5(password + salt)`. We re-salt per request so transport
sniffers can't replay. `NAVIDROME_URL` is the base URL (e.g.,
`https://navidrome.mattmariani.com`); the `/rest/...` path is appended
here.

This client is read-only — search3.view + getAlbumList2.view (newest).
That's all the Library panel needs; full browsing happens in Navidrome
behind the "Open Navidrome ↗" CTA.

Failure modes:
  - `NavidromeUnavailable` on connection/HTTP errors so the panel can
    degrade to an empty state with the CTA still working.
  - Missing credentials raise `NavidromeUnavailable` immediately
    rather than send an obviously-broken request.
"""

from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass
from typing import Any

import requests


# Per-request timeout (build-prompt and clients/README contract).
_HTTP_TIMEOUT_SECONDS = 5.0

# Subsonic API version we advertise. 1.16.1 was the last common-baseline
# release before the OpenSubsonic fork; Navidrome speaks it.
_SUBSONIC_API_VERSION = "1.16.1"

# Client identifier sent on every request. Shows up in Navidrome's
# session list so the operator can recognize our traffic.
_SUBSONIC_CLIENT = "cd-archivist"


class NavidromeUnavailable(Exception):
    """Raised on transport or config failure talking to Navidrome.

    The panel catches this and renders the empty state with the
    "Open Navidrome ↗" CTA still functional.
    """


@dataclass(frozen=True)
class AlbumSummary:
    id: str
    name: str
    artist: str
    cover_art_id: str | None
    created: str | None  # ISO-8601 string per Navidrome's `created` field

    def cover_art_url(self, base_url: str) -> str | None:
        """Construct the Subsonic `getCoverArt.view` URL for this
        album's cover art. Returns None when the album has no cover
        art id (Navidrome omits the field for art-less albums)."""
        if not self.cover_art_id:
            return None
        creds = _read_credentials_or_raise()
        params = _auth_params(creds)
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{base_url.rstrip('/')}/rest/getCoverArt.view?id={self.cover_art_id}&{qs}"


def _read_credentials_or_raise() -> tuple[str, str, str]:
    """Return `(url, user, password)`. Raises NavidromeUnavailable if
    any are missing. Reads env vars at call time so tests can
    monkeypatch."""
    url = os.environ.get("NAVIDROME_URL", "").strip()
    user = os.environ.get("NAVIDROME_USER", "").strip()
    password = os.environ.get("NAVIDROME_PASS", "").strip()
    if not (url and user and password):
        raise NavidromeUnavailable(
            "NAVIDROME_URL / NAVIDROME_USER / NAVIDROME_PASS not all set"
        )
    return url, user, password


def _auth_params(creds: tuple[str, str, str]) -> dict[str, str]:
    """Build the Subsonic auth query params. Salt is fresh per call."""
    _, user, password = creds
    salt = secrets.token_hex(8)
    token = hashlib.md5((password + salt).encode("utf-8")).hexdigest()  # noqa: S324
    return {
        "u": user,
        "t": token,
        "s": salt,
        "v": _SUBSONIC_API_VERSION,
        "c": _SUBSONIC_CLIENT,
        "f": "json",
    }


def _get(endpoint: str, extra_params: dict[str, Any]) -> dict[str, Any]:
    """GET a Subsonic endpoint, returning the parsed `subsonic-response`
    dict. Raises NavidromeUnavailable on transport or protocol failure."""
    creds = _read_credentials_or_raise()
    base_url, _, _ = creds
    url = f"{base_url.rstrip('/')}/rest/{endpoint}"
    params: dict[str, Any] = dict(_auth_params(creds))
    params.update(extra_params)
    try:
        resp = requests.get(url, params=params, timeout=_HTTP_TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise NavidromeUnavailable(f"{endpoint} request failed: {exc}") from exc
    try:
        body = resp.json()
    except ValueError as exc:
        raise NavidromeUnavailable(f"{endpoint} returned non-JSON body") from exc
    sub = body.get("subsonic-response") if isinstance(body, dict) else None
    if not isinstance(sub, dict):
        raise NavidromeUnavailable(f"{endpoint} missing subsonic-response key")
    if sub.get("status") != "ok":
        err = sub.get("error", {}).get("message") if isinstance(sub.get("error"), dict) else "unknown"
        raise NavidromeUnavailable(f"{endpoint} returned status={sub.get('status')}: {err}")
    return sub


def _album_from_dict(d: dict[str, Any]) -> AlbumSummary:
    return AlbumSummary(
        id=str(d.get("id", "")),
        name=str(d.get("name") or d.get("title") or ""),
        artist=str(d.get("artist") or ""),
        cover_art_id=(str(d["coverArt"]) if d.get("coverArt") else None),
        created=(str(d["created"]) if d.get("created") else None),
    )


def search(query: str, *, limit: int = 20) -> list[AlbumSummary]:
    """Search albums by query string. Uses `search3.view`. Returns up
    to `limit` AlbumSummary rows. Empty query returns an empty list
    without hitting the API."""
    if not query.strip():
        return []
    sub = _get("search3.view", {
        "query": query,
        "albumCount": int(limit),
        "songCount": 0,
        "artistCount": 0,
    })
    result = sub.get("searchResult3") or {}
    raw_albums = result.get("album") or []
    if isinstance(raw_albums, dict):
        # Some Subsonic implementations return a single dict instead of
        # a list when there's exactly one result. Normalize.
        raw_albums = [raw_albums]
    return [_album_from_dict(a) for a in raw_albums]


def get_newest_albums(*, limit: int = 10) -> list[AlbumSummary]:
    """Return the `limit` most-recently-added albums via
    `getAlbumList2.view?type=newest`."""
    sub = _get("getAlbumList2.view", {
        "type": "newest",
        "size": int(limit),
    })
    container = sub.get("albumList2") or {}
    raw_albums = container.get("album") or []
    if isinstance(raw_albums, dict):
        raw_albums = [raw_albums]
    return [_album_from_dict(a) for a in raw_albums]
