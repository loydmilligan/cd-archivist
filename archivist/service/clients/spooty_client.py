"""Spooty client — thin proxy over the spooty REST API.

Sprint-10 / downloads-impl. Per the package contract (see ``README.md``):
- one module per external surface (here: the spooty downloader's REST
  API at ``$SPOOTY_API_URL``, default ``http://192.168.6.38:3003/api``),
- typed exceptions on transport failure (``SpootyUnavailable``),
- env-var configuration read at call time so tests can monkeypatch,
- short network timeouts (5s).

The Library Manager's Downloads panel is a thin shell over this client:
it forwards operator actions (submit playlist, retry track, delete
track, retry whole playlist) verbatim and returns whatever spooty says
back. Spooty itself is the source of truth for queue state; cda just
surfaces it.

There is no auth wrapping today (sprint-10 plan §Auth — Cloudflare
Access service-token is deferred). All destructive actions are
LAN-safe until Access is configured.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import requests

from archivist.service.config import get_config


DEFAULT_API_URL = "http://192.168.6.38:3003/api"
DEFAULT_TIMEOUT_S = 5.0


class SpootyUnavailable(Exception):
    """Spooty REST API is unreachable or returned a transport error.

    Raised on connection refused, DNS failure, timeout, and any
    non-2xx response. Callers (panel + endpoints) catch this and
    degrade to an "unavailable" empty state.
    """


def _api_url() -> str:
    """Resolve the spooty base URL via the config store (call time)."""
    return (get_config().spooty_api_url or DEFAULT_API_URL).rstrip("/")


def _headers() -> dict[str, str]:
    """Optional token header — sprint-10 ships without auth on LAN."""
    token = (get_config().spooty_api_token or "").strip()
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def _request(method: str, path: str, *, json: dict | None = None) -> dict | list:
    """Issue a request against the spooty API and return parsed JSON.

    Wraps all ``requests``-level errors in ``SpootyUnavailable`` so
    callers only need one ``except`` clause. The path is appended
    to the resolved base URL; pass paths with a leading ``/``.
    """
    url = f"{_api_url()}{path}"
    try:
        resp = requests.request(
            method,
            url,
            json=json,
            headers=_headers(),
            timeout=DEFAULT_TIMEOUT_S,
        )
    except requests.RequestException as exc:
        raise SpootyUnavailable(f"spooty {method} {path} failed: {exc}") from exc
    if resp.status_code >= 400:
        raise SpootyUnavailable(
            f"spooty {method} {path} -> HTTP {resp.status_code}"
        )
    try:
        return resp.json()
    except ValueError as exc:
        raise SpootyUnavailable(
            f"spooty {method} {path} returned non-JSON body"
        ) from exc


# ---- read methods -----------------------------------------------------------


@dataclass(frozen=True)
class SpootyTrack:
    id: str
    title: str
    state: str  # "ok" | "active" | "error" | "pending"
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class SpootyPlaylist:
    id: str
    name: str
    url: str
    track_count: int = 0
    done_count: int = 0
    error_count: int = 0
    tracks: list[SpootyTrack] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "track_count": self.track_count,
            "done_count": self.done_count,
            "error_count": self.error_count,
            "tracks": [t.to_dict() for t in self.tracks],
        }


def _coerce_track(raw: dict) -> SpootyTrack:
    return SpootyTrack(
        id=str(raw.get("id") or ""),
        title=str(raw.get("title") or raw.get("name") or ""),
        state=str(raw.get("state") or "pending"),
        error=raw.get("error"),
    )


def _coerce_playlist(raw: dict) -> SpootyPlaylist:
    tracks = [_coerce_track(t) for t in (raw.get("tracks") or [])]
    return SpootyPlaylist(
        id=str(raw.get("id") or ""),
        name=str(raw.get("name") or ""),
        url=str(raw.get("url") or ""),
        track_count=int(raw.get("track_count") or len(tracks)),
        done_count=int(raw.get("done_count") or 0),
        error_count=int(raw.get("error_count") or 0),
        tracks=tracks,
    )


def list_playlists() -> list[SpootyPlaylist]:
    """Return all known playlists. Raises ``SpootyUnavailable`` on failure."""
    data = _request("GET", "/playlist")
    if isinstance(data, dict):
        data = data.get("playlists") or []
    return [_coerce_playlist(p) for p in (data or [])]


def list_tracks(playlist_id: str) -> list[SpootyTrack]:
    """Return tracks for one playlist. Raises ``SpootyUnavailable`` on failure."""
    data = _request("GET", f"/track/playlist/{playlist_id}")
    if isinstance(data, dict):
        data = data.get("tracks") or []
    return [_coerce_track(t) for t in (data or [])]


# ---- mutating methods -------------------------------------------------------
#
# Path shapes follow the spooty upstream REST contract (docs/
# LIBRARY-MANAGER-PROPOSAL.md "Spooty REST API"): singular nouns
# (`/playlist`, `/track`), retry endpoints are GETs at
# `/<resource>/retry/<id>`, and track-deletion is at `/track/<id>`.


def submit_playlist(url: str) -> dict:
    """Submit a new Spotify playlist URL to the spooty queue.

    Returns the spooty response verbatim (dict). Raises
    ``SpootyUnavailable`` on transport failure.
    """
    return dict(_request("POST", "/playlist", json={"url": url}))  # type: ignore[arg-type]


def retry_playlist(playlist_id: str) -> dict:
    return dict(_request("GET", f"/playlist/retry/{playlist_id}"))  # type: ignore[arg-type]


def retry_track(track_id: str) -> dict:
    return dict(_request("GET", f"/track/retry/{track_id}"))  # type: ignore[arg-type]


def delete_track(track_id: str) -> dict:
    return dict(_request("DELETE", f"/track/{track_id}"))  # type: ignore[arg-type]
