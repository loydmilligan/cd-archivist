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
