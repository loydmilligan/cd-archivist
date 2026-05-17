"""MusicBrainz client singleton with rate-limit gate + UA header.

Per `docs/design/2026-05-16-in-ui-beets-review.md` and
`D-mb-query-direct-not-beets`. Wraps the `musicbrainzngs` module so:

  - User-Agent is set once at first access (MB requires it).
  - Concurrent FastAPI requests serialise through a 1 req/sec gate
    (MB throttles aggressively at the server end).

Throttling is intentionally minimal: monotonic-clock gate (≥1.0s
between calls), no retry-with-backoff, no caching. `WebServiceError`
propagates — the route handler converts to 502.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

import musicbrainzngs

_USER_AGENT_NAME = "cd-archivist"
_USER_AGENT_VERSION = "0.1.0"
_USER_AGENT_CONTACT = "https://github.com/loydmilligan/cd-archivist"
_MIN_REQUEST_INTERVAL_SECONDS = 1.0


class MBClient:
    """Thin wrapper enforcing the MB rate limit + UA + serial access."""

    def __init__(self) -> None:
        musicbrainzngs.set_useragent(
            _USER_AGENT_NAME, _USER_AGENT_VERSION, _USER_AGENT_CONTACT,
        )
        self._lock = threading.Lock()
        self._last_call_monotonic: float | None = None

    def _wait_for_gate(self) -> None:
        if self._last_call_monotonic is None:
            return
        elapsed = time.monotonic() - self._last_call_monotonic
        if elapsed < _MIN_REQUEST_INTERVAL_SECONDS:
            time.sleep(_MIN_REQUEST_INTERVAL_SECONDS - elapsed)

    def search_releases(self, query: str, *, limit: int = 5, **kwargs: Any) -> dict:
        with self._lock:
            self._wait_for_gate()
            try:
                return musicbrainzngs.search_releases(query=query, limit=limit, **kwargs)
            finally:
                self._last_call_monotonic = time.monotonic()

    def get_release_by_id(self, mbid: str, **kwargs: Any) -> dict:
        with self._lock:
            self._wait_for_gate()
            try:
                return musicbrainzngs.get_release_by_id(mbid, **kwargs)
            finally:
                self._last_call_monotonic = time.monotonic()

    # ---- sprint-7 / impl-candidates-endpoint ------------------------

    def lookup_by_disc_id(self, disc_id: str) -> dict | None:
        """Resolve a MusicBrainz disc-id → top release candidate row."""
        with self._lock:
            self._wait_for_gate()
            try:
                payload = musicbrainzngs.get_releases_by_discid(
                    disc_id, includes=["artists", "recordings"],
                )
            finally:
                self._last_call_monotonic = time.monotonic()
        disc = (payload or {}).get("disc") or {}
        releases = disc.get("release-list") or []
        if not releases:
            return None
        return _release_to_candidate(releases[0], score=1.0)

    def search_by_fingerprint(self, folder: Path) -> list[dict]:
        """AcoustID fingerprint search — sprint-8 wires fpcalc."""
        _ = folder
        return []

    def search_by_metadata(
        self, *, artist: str | None, album: str | None,
    ) -> list[dict]:
        """Operator-hint-driven MB search by artist + album."""
        if not (artist or album):
            return []
        query_parts: list[str] = []
        if artist:
            query_parts.append(f'artist:"{artist}"')
        if album:
            query_parts.append(f'release:"{album}"')
        query = " AND ".join(query_parts)
        with self._lock:
            self._wait_for_gate()
            try:
                payload = musicbrainzngs.search_releases(
                    query=query, limit=5,
                )
            finally:
                self._last_call_monotonic = time.monotonic()
        out: list[dict] = []
        for rel in (payload or {}).get("release-list") or []:
            raw_score = rel.get("ext:score") or rel.get("score") or 0
            try:
                score = float(raw_score) / 100.0
            except (TypeError, ValueError):
                score = 0.0
            out.append(_release_to_candidate(rel, score=score))
        return out


def _release_to_candidate(rel: dict, *, score: float) -> dict:
    """Squash a musicbrainzngs release dict into the candidate shape."""
    artists = rel.get("artist-credit") or []
    artist_name = ""
    for ac in artists:
        if isinstance(ac, dict):
            name = (ac.get("artist") or {}).get("name") or ac.get("name")
            if name:
                artist_name = name
                break
    year: int | None = None
    date = rel.get("date") or ""
    if date[:4].isdigit():
        year = int(date[:4])
    track_count: int | None = None
    medium_list = rel.get("medium-list") or []
    if medium_list:
        try:
            track_count = sum(int(m.get("track-count") or 0)
                              for m in medium_list) or None
        except (TypeError, ValueError):
            track_count = None
    return {
        "mbid": rel.get("id") or "",
        "score": float(score),
        "artist": artist_name,
        "title": rel.get("title") or "",
        "year": year,
        "track_count": track_count,
        "country": rel.get("country"),
    }


_singleton: MBClient | None = None
_singleton_lock = threading.Lock()


def get_mb_client() -> MBClient:
    """Return the process-wide MBClient singleton (lazy-constructed)."""
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                _singleton = MBClient()
    return _singleton
