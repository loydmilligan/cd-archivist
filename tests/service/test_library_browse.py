"""Sprint-10 / library-impl — Library (browse) panel tests.

Covers:
  - subsonic_client.search + get_newest_albums with a mocked
    requests session (happy paths + NavidromeUnavailable on
    transport/protocol failure + missing-credentials guard)
  - /api/library/browse and /api/library/browse/recent endpoints
  - Rendered panel HTML structure (search input wired to
    /api/library/browse, recent list with name + artist + created,
    Navidrome CTA href, degraded state when Navidrome is unavailable)
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import requests
from fastapi.testclient import TestClient

from archivist.service.app import LoopState, create_app
from archivist.service.clients import subsonic_client
from archivist.service.clients.subsonic_client import (
    AlbumSummary,
    NavidromeUnavailable,
    get_newest_albums,
    search,
)
from archivist.service.config import reload_config, save_config
from archivist.service.library_panels import render_panel


_CONFIG_ENV_VARS = (
    "SPOOTY_API_URL", "SPOOTY_API_TOKEN",
    "NAVIDROME_URL", "NAVIDROME_USER", "NAVIDROME_PASS",
    "MUSIC_INBOX_DIR", "MUSIC_LIBRARY_DIR", "MUSIC_ARCHIVE_DIR",
    "MUSIC_SPOOTY_DIR", "MUSIC_REVIEW_DIR",
)


@pytest.fixture(autouse=True)
def _isolated_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """Per sprint-11 / config-runtime-wiring: subsonic_client reads
    creds via `get_config()`. Tests configure via `save_config(...)`
    rather than `monkeypatch.setenv(...)`."""
    monkeypatch.setenv(
        "ARCHIVIST_CONFIG_PATH", str(tmp_path / "_test_config.json"),
    )
    for var in _CONFIG_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    reload_config()
    yield
    reload_config()


# ---------- subsonic_client.search ------------------------------------------

class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self._payload


@pytest.fixture
def navidrome_env() -> None:
    """Seed the config store with Navidrome creds (replaces the old
    monkeypatch.setenv pattern; sprint-11 / config-runtime-wiring)."""
    save_config({
        "navidrome_url": "https://nav.example/",
        "navidrome_user": "operator",
        "navidrome_pass": "hunter2",
    })


def _ok(payload_inner: dict) -> dict:
    return {"subsonic-response": {"status": "ok", **payload_inner}}


def test_search_returns_album_summaries(
    navidrome_env, monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    def _fake_get(url, params, timeout):
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = timeout
        return _FakeResponse(_ok({
            "searchResult3": {
                "album": [
                    {"id": "a1", "name": "Kid A", "artist": "Radiohead",
                     "coverArt": "ca1", "created": "2026-05-18T10:00:00Z"},
                    {"id": "a2", "name": "Amnesiac", "artist": "Radiohead",
                     "created": "2026-05-17T10:00:00Z"},
                ],
            },
        }))

    monkeypatch.setattr(subsonic_client.requests, "get", _fake_get)
    albums = search("radiohead")
    assert len(albums) == 2
    assert albums[0].id == "a1"
    assert albums[0].name == "Kid A"
    assert albums[0].cover_art_id == "ca1"
    assert albums[1].cover_art_id is None

    # Endpoint + auth + 5s timeout contract
    assert captured["url"] == "https://nav.example/rest/search3.view"
    assert captured["timeout"] == 5.0
    assert captured["params"]["query"] == "radiohead"
    assert captured["params"]["u"] == "operator"
    assert captured["params"]["f"] == "json"
    assert "t" in captured["params"] and "s" in captured["params"]


def test_search_empty_query_skips_api(
    navidrome_env, monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = []

    def _fake_get(*a, **kw):
        called.append(True)
        raise AssertionError("should not be called")

    monkeypatch.setattr(subsonic_client.requests, "get", _fake_get)
    assert search("") == []
    assert search("    ") == []
    assert called == []


def test_search_normalizes_single_album_dict(
    navidrome_env, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_get(*a, **kw):
        return _FakeResponse(_ok({
            "searchResult3": {"album": {"id": "x", "name": "Solo", "artist": "X"}},
        }))
    monkeypatch.setattr(subsonic_client.requests, "get", _fake_get)
    albums = search("solo")
    assert len(albums) == 1
    assert albums[0].id == "x"


def test_search_raises_on_connection_error(
    navidrome_env, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_get(*a, **kw):
        raise requests.ConnectionError("nav down")
    monkeypatch.setattr(subsonic_client.requests, "get", _fake_get)
    with pytest.raises(NavidromeUnavailable):
        search("anything")


def test_search_raises_on_failed_subsonic_status(
    navidrome_env, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_get(*a, **kw):
        return _FakeResponse({"subsonic-response": {
            "status": "failed",
            "error": {"code": 40, "message": "Wrong username or password."},
        }})
    monkeypatch.setattr(subsonic_client.requests, "get", _fake_get)
    with pytest.raises(NavidromeUnavailable):
        search("anything")


def test_missing_credentials_raises_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NAVIDROME_URL", raising=False)
    monkeypatch.delenv("NAVIDROME_USER", raising=False)
    monkeypatch.delenv("NAVIDROME_PASS", raising=False)
    with pytest.raises(NavidromeUnavailable):
        search("anything")


def test_get_newest_albums_returns_summaries(
    navidrome_env, monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    def _fake_get(url, params, timeout):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse(_ok({
            "albumList2": {"album": [
                {"id": "n1", "name": "New One", "artist": "A1",
                 "created": "2026-05-18T12:00:00Z"},
                {"id": "n2", "name": "New Two", "artist": "A2",
                 "created": "2026-05-17T12:00:00Z"},
            ]},
        }))

    monkeypatch.setattr(subsonic_client.requests, "get", _fake_get)
    albums = get_newest_albums(limit=2)
    assert [a.id for a in albums] == ["n1", "n2"]
    assert captured["url"] == "https://nav.example/rest/getAlbumList2.view"
    assert captured["params"]["type"] == "newest"
    assert captured["params"]["size"] == 2


# ---------- /api/library/browse* endpoints ----------------------------------

@pytest.fixture
def music_root(tmp_path: Path) -> Path:
    root = tmp_path / "music"
    for sub in ("inbox", "review", "library", "archive", "failed"):
        (root / sub).mkdir(parents=True)
    return root


@pytest.fixture
def client(music_root: Path, tmp_path: Path) -> TestClient:
    log_path = tmp_path / "archivist.log"
    log_path.write_text("")
    return TestClient(create_app(
        LoopState(), log_path,
        discs_root=music_root / "inbox",
        review_root=music_root / "review",
        library_root=music_root / "library",
        music_root=music_root,
    ))


def test_api_browse_endpoint_shape(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "archivist.service.clients.subsonic_client.search",
        lambda q, **kw: [
            AlbumSummary(id="a1", name="Kid A", artist="Radiohead",
                         cover_art_id="ca1", created="2026-05-18T10:00:00Z"),
        ],
    )
    res = client.get("/api/library/browse?q=radiohead")
    assert res.status_code == 200
    body = res.json()
    assert "albums" in body and len(body["albums"]) == 1
    assert body["albums"][0]["id"] == "a1"
    assert body["albums"][0]["name"] == "Kid A"
    assert body["albums"][0]["artist"] == "Radiohead"


def test_api_browse_503_on_navidrome_unavailable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(q, **kw):
        raise NavidromeUnavailable("nav down")
    monkeypatch.setattr(
        "archivist.service.clients.subsonic_client.search", _boom,
    )
    res = client.get("/api/library/browse?q=anything")
    assert res.status_code == 503
    body = res.json()
    assert body["albums"] == []
    assert "nav down" in body["error"]


def test_api_browse_recent_endpoint_shape(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "archivist.service.clients.subsonic_client.get_newest_albums",
        lambda **kw: [
            AlbumSummary(id=f"r{i}", name=f"Album {i}", artist="Artist",
                         cover_art_id=None, created="2026-05-18T00:00:00Z")
            for i in range(10)
        ],
    )
    res = client.get("/api/library/browse/recent")
    assert res.status_code == 200
    body = res.json()
    assert len(body["albums"]) == 10
    assert body["albums"][0]["id"] == "r0"


def test_api_browse_recent_503_on_navidrome_unavailable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(**kw):
        raise NavidromeUnavailable("nav down")
    monkeypatch.setattr(
        "archivist.service.clients.subsonic_client.get_newest_albums", _boom,
    )
    res = client.get("/api/library/browse/recent")
    assert res.status_code == 503


# ---------- panel render ----------------------------------------------------

def test_panel_renders_search_input_and_results_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NAVIDROME_URL", "https://nav.example")
    monkeypatch.setattr(
        "archivist.service.library_browse_panel.get_newest_albums",
        lambda **kw: [],
    )
    html = render_panel("library")
    assert "data-cda-browse-search" in html
    assert "data-cda-browse-results" in html
    # The debounced fetcher targets the public endpoint
    assert "/api/library/browse?q=" in html


def test_panel_renders_navidrome_cta_with_href(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NAVIDROME_URL", "https://nav.example/path")
    monkeypatch.setattr(
        "archivist.service.library_browse_panel.get_newest_albums",
        lambda **kw: [],
    )
    html = render_panel("library")
    m = re.search(
        r'<a class="cda-lib-browse-cta" href="([^"]+)" target="_blank"',
        html,
    )
    assert m is not None
    assert m.group(1) == "https://nav.example/path"
    assert "Open Navidrome" in html


def test_panel_renders_recent_list_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NAVIDROME_URL", "https://nav.example")
    monkeypatch.setattr(
        "archivist.service.library_browse_panel.get_newest_albums",
        lambda **kw: [
            AlbumSummary(id="r1", name="Recent A", artist="Artist X",
                         cover_art_id=None, created="2026-05-18T11:00:00Z"),
            AlbumSummary(id="r2", name="Recent B", artist="Artist Y",
                         cover_art_id=None, created="2026-05-17T09:00:00Z"),
        ],
    )
    html = render_panel("library")
    rows = re.findall(r'class="cda-lib-browse-recent-row"', html)
    assert len(rows) == 2
    assert "Recent A" in html
    assert "Recent B" in html
    assert "Artist X" in html
    assert "2026-05-18T11:00:00Z" in html


def test_panel_degrades_on_navidrome_unavailable_but_cta_still_works(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NAVIDROME_URL", "https://nav.example")
    def _boom(**kw):
        raise NavidromeUnavailable("not configured here")
    monkeypatch.setattr(
        "archivist.service.library_browse_panel.get_newest_albums", _boom,
    )
    html = render_panel("library")
    assert "is-unavailable" in html
    # CTA still has a real href so the operator can click through.
    assert 'href="https://nav.example"' in html


def test_panel_does_not_emit_polling_meta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Library/browse cadence is `none` — chassis_js requires both
    meta tags, so absence means no-op. The panel must not emit them."""
    monkeypatch.setenv("NAVIDROME_URL", "https://nav.example")
    monkeypatch.setattr(
        "archivist.service.library_browse_panel.get_newest_albums",
        lambda **kw: [],
    )
    html = render_panel("library")
    assert "library-poll-ms" not in html
    assert "library-poll-endpoint" not in html


def test_panel_renders_eyebrow_and_title(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NAVIDROME_URL", "https://nav.example")
    monkeypatch.setattr(
        "archivist.service.library_browse_panel.get_newest_albums",
        lambda **kw: [],
    )
    html = render_panel("library")
    assert '<span class="eyebrow">Library</span>' in html
    assert "<h1>Browse · jump to Navidrome</h1>" in html
