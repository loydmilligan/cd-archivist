"""Sprint-10 / downloads-impl — Downloads (Spooty) panel tests.

Covers:
  - `spooty_client` happy paths (list_playlists, list_tracks, submit,
    retry_track/playlist, delete_track) with a mocked requests layer.
  - `SpootyUnavailable` raised on connection error, timeout, non-2xx
    response, and non-JSON body.
  - `/api/library/downloads/*` endpoints (each one — list, tracks,
    submit, retry_track, retry_playlist, delete_track) including 503
    on SpootyUnavailable.
  - `library_downloads_panel.render` HTML structure (poll meta tags,
    stats header, submit form, playlist rows, per-track pip strip
    with state classes, retry/delete buttons, empty + unavailable
    degradations).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
from fastapi.testclient import TestClient

from archivist.service.app import LoopState, create_app
from archivist.service.clients import spooty_client
from archivist.service.clients.spooty_client import (
    SpootyPlaylist,
    SpootyTrack,
    SpootyUnavailable,
    delete_track,
    list_playlists,
    list_tracks,
    retry_playlist,
    retry_track,
    submit_playlist,
)
from archivist.service.library_downloads_panel import (
    POLL_ENDPOINT,
    POLL_MS_ACTIVE,
    POLL_MS_IDLE,
    render,
)
from archivist.service.library_panel_inventory import BY_ID


# ---- fixtures ---------------------------------------------------------------


@pytest.fixture(autouse=True)
def _spooty_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPOOTY_API_URL", "http://test-spooty:3003/api")
    monkeypatch.delenv("SPOOTY_API_TOKEN", raising=False)


def _resp(status_code: int = 200, json_body=None, raise_text: str | None = None):
    """Build a fake requests.Response."""
    r = MagicMock(spec=requests.Response)
    r.status_code = status_code
    if raise_text is not None:
        r.json.side_effect = ValueError(raise_text)
    else:
        r.json.return_value = json_body if json_body is not None else {}
    return r


@pytest.fixture
def loop_state() -> LoopState:
    return LoopState(
        state="IDLE",
        disc_id=None,
        last_rip_status=None,
        state_entered_at=datetime(2026, 5, 20, 12, 0, 0),
        last_tick_at=datetime(2026, 5, 20, 12, 0, 0),
    )


@pytest.fixture
def client(loop_state: LoopState, tmp_path: Path) -> TestClient:
    music_root = tmp_path / "music"
    music_root.mkdir()
    review = tmp_path / "review"
    review.mkdir()
    app = create_app(
        loop_state=loop_state,
        log_path=tmp_path / "pipeline.log",
        music_root=music_root,
        review_root=review,
        discs_root=music_root,
    )
    return TestClient(app)


# ---- spooty_client.list_playlists -------------------------------------------


def test_list_playlists_happy_path() -> None:
    payload = [
        {
            "id": "p1", "name": "Mix A", "url": "https://s/p1",
            "track_count": 2, "done_count": 1, "error_count": 0,
            "tracks": [
                {"id": "t1", "title": "Song 1", "state": "ok"},
                {"id": "t2", "title": "Song 2", "state": "active"},
            ],
        },
    ]
    with patch.object(requests, "request", return_value=_resp(200, payload)) as mock_req:
        playlists = list_playlists()
    assert len(playlists) == 1
    assert playlists[0].id == "p1"
    assert playlists[0].name == "Mix A"
    assert len(playlists[0].tracks) == 2
    assert playlists[0].tracks[0].state == "ok"
    args, kwargs = mock_req.call_args
    assert args[0] == "GET"
    assert args[1].endswith("/api/playlists")
    assert kwargs["timeout"] == 5.0


def test_list_playlists_accepts_envelope_shape() -> None:
    payload = {"playlists": [{"id": "p1", "name": "X", "url": "u"}]}
    with patch.object(requests, "request", return_value=_resp(200, payload)):
        playlists = list_playlists()
    assert len(playlists) == 1
    assert playlists[0].id == "p1"


def test_list_playlists_raises_on_connection_error() -> None:
    with patch.object(
        requests, "request", side_effect=requests.ConnectionError("refused"),
    ):
        with pytest.raises(SpootyUnavailable):
            list_playlists()


def test_list_playlists_raises_on_timeout() -> None:
    with patch.object(requests, "request", side_effect=requests.Timeout("slow")):
        with pytest.raises(SpootyUnavailable):
            list_playlists()


def test_list_playlists_raises_on_http_error() -> None:
    with patch.object(requests, "request", return_value=_resp(503)):
        with pytest.raises(SpootyUnavailable):
            list_playlists()


def test_list_playlists_raises_on_non_json_body() -> None:
    with patch.object(
        requests, "request",
        return_value=_resp(200, raise_text="not json"),
    ):
        with pytest.raises(SpootyUnavailable):
            list_playlists()


# ---- spooty_client.list_tracks ----------------------------------------------


def test_list_tracks_happy_path() -> None:
    payload = [
        {"id": "t1", "title": "S1", "state": "ok"},
        {"id": "t2", "title": "S2", "state": "error", "error": "yt 410"},
    ]
    with patch.object(requests, "request", return_value=_resp(200, payload)) as mock_req:
        tracks = list_tracks("p1")
    assert len(tracks) == 2
    assert tracks[1].error == "yt 410"
    args, _ = mock_req.call_args
    assert args[0] == "GET"
    assert args[1].endswith("/api/playlists/p1/tracks")


# ---- spooty_client mutating methods -----------------------------------------


def test_submit_playlist_posts_url() -> None:
    with patch.object(requests, "request", return_value=_resp(200, {"id": "new"})) as mock_req:
        result = submit_playlist("https://open.spotify.com/playlist/x")
    assert result == {"id": "new"}
    args, kwargs = mock_req.call_args
    assert args[0] == "POST"
    assert args[1].endswith("/api/playlists")
    assert kwargs["json"] == {"url": "https://open.spotify.com/playlist/x"}


def test_retry_playlist_posts_to_correct_path() -> None:
    with patch.object(requests, "request", return_value=_resp(200, {"ok": True})) as mock_req:
        retry_playlist("p1")
    args, _ = mock_req.call_args
    assert args[0] == "POST"
    assert args[1].endswith("/api/playlists/p1/retry")


def test_retry_track_posts_to_correct_path() -> None:
    with patch.object(requests, "request", return_value=_resp(200, {"ok": True})) as mock_req:
        retry_track("t1")
    args, _ = mock_req.call_args
    assert args[0] == "POST"
    assert args[1].endswith("/api/tracks/t1/retry")


def test_delete_track_uses_delete_method() -> None:
    with patch.object(requests, "request", return_value=_resp(200, {"ok": True})) as mock_req:
        delete_track("t1")
    args, _ = mock_req.call_args
    assert args[0] == "DELETE"
    assert args[1].endswith("/api/tracks/t1")


def test_token_header_included_when_env_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPOOTY_API_TOKEN", "secret")
    with patch.object(requests, "request", return_value=_resp(200, [])) as mock_req:
        list_playlists()
    _, kwargs = mock_req.call_args
    assert kwargs["headers"] == {"Authorization": "Bearer secret"}


# ---- /api/library/downloads endpoints ---------------------------------------


def test_api_downloads_returns_playlists(client: TestClient) -> None:
    payload = [{"id": "p1", "name": "X", "url": "u", "tracks": []}]
    with patch.object(requests, "request", return_value=_resp(200, payload)):
        resp = client.get("/api/library/downloads")
    assert resp.status_code == 200
    assert resp.json()["playlists"][0]["id"] == "p1"


def test_api_downloads_503_when_spooty_unavailable(client: TestClient) -> None:
    with patch.object(
        requests, "request", side_effect=requests.ConnectionError("refused"),
    ):
        resp = client.get("/api/library/downloads")
    assert resp.status_code == 503
    body = resp.json()
    assert body["playlists"] == []
    assert "error" in body


def test_api_downloads_tracks_endpoint(client: TestClient) -> None:
    payload = [{"id": "t1", "title": "S1", "state": "ok"}]
    with patch.object(requests, "request", return_value=_resp(200, payload)):
        resp = client.get("/api/library/downloads/playlists/p1/tracks")
    assert resp.status_code == 200
    assert resp.json()["tracks"][0]["id"] == "t1"


def test_api_downloads_submit_playlist(client: TestClient) -> None:
    with patch.object(requests, "request", return_value=_resp(200, {"id": "new"})) as mock_req:
        resp = client.post(
            "/api/library/downloads/playlists",
            json={"url": "https://open.spotify.com/playlist/x"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"id": "new"}
    _, kwargs = mock_req.call_args
    assert kwargs["json"] == {"url": "https://open.spotify.com/playlist/x"}


def test_api_downloads_submit_400_on_missing_url(client: TestClient) -> None:
    resp = client.post("/api/library/downloads/playlists", json={})
    assert resp.status_code == 400


def test_api_downloads_submit_503_on_spooty_down(client: TestClient) -> None:
    with patch.object(
        requests, "request", side_effect=requests.ConnectionError("refused"),
    ):
        resp = client.post(
            "/api/library/downloads/playlists",
            json={"url": "https://x"},
        )
    assert resp.status_code == 503


def test_api_downloads_retry_playlist(client: TestClient) -> None:
    with patch.object(requests, "request", return_value=_resp(200, {"ok": True})) as mock_req:
        resp = client.post("/api/library/downloads/playlists/p1/retry")
    assert resp.status_code == 200
    args, _ = mock_req.call_args
    assert args[1].endswith("/api/playlists/p1/retry")


def test_api_downloads_retry_track(client: TestClient) -> None:
    with patch.object(requests, "request", return_value=_resp(200, {"ok": True})) as mock_req:
        resp = client.post("/api/library/downloads/tracks/t1/retry")
    assert resp.status_code == 200
    args, _ = mock_req.call_args
    assert args[1].endswith("/api/tracks/t1/retry")


def test_api_downloads_delete_track(client: TestClient) -> None:
    with patch.object(requests, "request", return_value=_resp(200, {"ok": True})) as mock_req:
        resp = client.delete("/api/library/downloads/tracks/t1")
    assert resp.status_code == 200
    args, _ = mock_req.call_args
    assert args[0] == "DELETE"
    assert args[1].endswith("/api/tracks/t1")


# ---- library_downloads_panel.render -----------------------------------------


def _patched_request(playlists_payload):
    return patch.object(
        requests, "request", return_value=_resp(200, playlists_payload),
    )


def test_render_includes_poll_meta_tags_idle() -> None:
    with _patched_request([]):
        html_out = render(BY_ID["downloads"])
    # Empty → idle cadence.
    assert (
        f'<meta name="library-poll-ms" content="{POLL_MS_IDLE}">'
        in html_out
    )
    assert (
        f'<meta name="library-poll-endpoint" content="{POLL_ENDPOINT}">'
        in html_out
    )


def test_render_uses_active_cadence_when_track_running() -> None:
    payload = [
        {
            "id": "p1", "name": "X", "url": "u",
            "tracks": [{"id": "t1", "title": "S", "state": "active"}],
        },
    ]
    with _patched_request(payload):
        html_out = render(BY_ID["downloads"])
    assert (
        f'<meta name="library-poll-ms" content="{POLL_MS_ACTIVE}">'
        in html_out
    )


def test_render_emits_stats_header() -> None:
    payload = [
        {
            "id": "p1", "name": "X", "url": "u",
            "track_count": 3, "done_count": 1, "error_count": 1,
            "tracks": [
                {"id": "t1", "title": "S1", "state": "ok"},
                {"id": "t2", "title": "S2", "state": "error"},
                {"id": "t3", "title": "S3", "state": "pending"},
            ],
        },
    ]
    with _patched_request(payload):
        html_out = render(BY_ID["downloads"])
    assert "cda-dl-stats" in html_out
    assert "playlists" in html_out
    assert "tracks" in html_out
    assert "done" in html_out
    assert "errors" in html_out


def test_render_emits_submit_form() -> None:
    with _patched_request([]):
        html_out = render(BY_ID["downloads"])
    assert "cda-dl-submit" in html_out
    assert 'type="url"' in html_out
    assert 'name="url"' in html_out


def test_render_emits_per_track_pip_strip_with_state_classes() -> None:
    payload = [
        {
            "id": "p1", "name": "X", "url": "u",
            "tracks": [
                {"id": "t1", "title": "S1", "state": "ok"},
                {"id": "t2", "title": "S2", "state": "active"},
                {"id": "t3", "title": "S3", "state": "error"},
                {"id": "t4", "title": "S4", "state": "pending"},
            ],
        },
    ]
    with _patched_request(payload):
        html_out = render(BY_ID["downloads"])
    assert "pip--ok" in html_out
    assert "pip--active" in html_out
    assert "pip--error" in html_out
    assert "pip--pending" in html_out
    assert "cda-dl-pipstrip" in html_out


def test_render_emits_retry_and_delete_buttons() -> None:
    payload = [
        {
            "id": "p1", "name": "X", "url": "u",
            "tracks": [{"id": "t1", "title": "S1", "state": "error"}],
        },
    ]
    with _patched_request(payload):
        html_out = render(BY_ID["downloads"])
    assert "cda-dl-track-retry" in html_out
    assert "cda-dl-track-delete" in html_out
    assert "cda-dl-playlist-retry" in html_out
    assert 'data-track-id="t1"' in html_out
    assert 'data-playlist-id="p1"' in html_out


def test_render_panel_title_from_spec() -> None:
    with _patched_request([]):
        html_out = render(BY_ID["downloads"])
    assert BY_ID["downloads"]["title"] in html_out


def test_render_degrades_when_spooty_unavailable() -> None:
    with patch.object(
        requests, "request", side_effect=requests.ConnectionError("refused"),
    ):
        html_out = render(BY_ID["downloads"])
    # Still emits the panel shell + meta tags + submit form.
    assert "library-poll-ms" in html_out
    assert "spooty unavailable" in html_out
    assert "cda-dl-submit" in html_out


def test_render_empty_state_when_no_playlists() -> None:
    with _patched_request([]):
        html_out = render(BY_ID["downloads"])
    assert "no playlists queued" in html_out


def test_render_pluggable_into_library_panels_dispatcher() -> None:
    from archivist.service.library_panels import render_panel
    with _patched_request([]):
        html_out = render_panel("downloads")
    assert "cda-dl-stats" in html_out


# ---- dataclass JSON-safety --------------------------------------------------


def test_spooty_playlist_to_dict_round_trips() -> None:
    import json
    p = SpootyPlaylist(
        id="p", name="n", url="u", track_count=1,
        tracks=[SpootyTrack(id="t", title="ti", state="ok")],
    )
    json.dumps(p.to_dict())  # must not raise


# ---- module-level imports used (defensive) ----------------------------------


def test_default_timeout_and_url_constants() -> None:
    assert spooty_client.DEFAULT_TIMEOUT_S == 5.0
    assert spooty_client.DEFAULT_API_URL.startswith("http")
