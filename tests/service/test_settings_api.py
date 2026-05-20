"""Sprint-11 / settings-api-endpoints — `/api/config` GET + POST tests.

Covers:
  - GET masks secret fields (●●●●●●●● when set, null when unset),
    non-secret fields returned verbatim
  - POST happy path persists via config_store and returns the updated
    masked config
  - POST validates URL fields (must be http(s)://) — rejects with 400
  - POST validates dir fields (must be absolute) — rejects with 400
  - POST empty-string in a password field = no-change behavior
  - POST rejects unknown keys via the config_store error path (400)
  - POST returns 400 on invalid JSON / non-object body
  - POST allows null to clear a previously-saved field
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from archivist.service.app import LoopState, create_app
from archivist.service.config import (
    get_config,
    reload_config,
    save_config,
)


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg_path = tmp_path / "cd-archivist" / "config.json"
    monkeypatch.setenv("ARCHIVIST_CONFIG_PATH", str(cfg_path))
    for env_var in (
        "SPOOTY_API_URL", "SPOOTY_API_TOKEN",
        "NAVIDROME_URL", "NAVIDROME_USER", "NAVIDROME_PASS",
        "MUSIC_INBOX_DIR", "MUSIC_LIBRARY_DIR", "MUSIC_ARCHIVE_DIR",
        "MUSIC_SPOOTY_DIR", "MUSIC_REVIEW_DIR",
    ):
        monkeypatch.delenv(env_var, raising=False)
    reload_config()
    yield cfg_path
    reload_config()


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


_MASK = "●" * 8


# ---------- GET masking -----------------------------------------------------

def test_get_returns_defaults_with_secrets_null_when_unset(client: TestClient) -> None:
    res = client.get("/api/config")
    assert res.status_code == 200
    body = res.json()
    # Music dirs come back as defaults.
    assert body["music_inbox_dir"] == "/srv/music/inbox"
    assert body["music_archive_dir"] == "/mnt/archive"
    # Unset secrets are null (not the mask glyph).
    assert body["navidrome_pass"] is None
    assert body["spooty_api_token"] is None
    # Unset URLs are null.
    assert body["navidrome_url"] is None
    assert body["spooty_api_url"] is None


def test_get_masks_secret_fields_when_set(client: TestClient) -> None:
    save_config({
        "navidrome_url": "https://nav.example",
        "navidrome_user": "operator",
        "navidrome_pass": "hunter2",
        "spooty_api_token": "tok-abc",
    })
    res = client.get("/api/config")
    body = res.json()
    assert body["navidrome_url"] == "https://nav.example"   # non-secret returned verbatim
    assert body["navidrome_user"] == "operator"             # non-secret returned verbatim
    assert body["navidrome_pass"] == _MASK                  # masked
    assert body["spooty_api_token"] == _MASK                # masked


# ---------- POST happy path -------------------------------------------------

def test_post_happy_path_persists_and_returns_masked(client: TestClient) -> None:
    res = client.post("/api/config", json={
        "navidrome_url": "https://nav.example",
        "navidrome_user": "operator",
        "navidrome_pass": "hunter2",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["navidrome_url"] == "https://nav.example"
    assert body["navidrome_user"] == "operator"
    assert body["navidrome_pass"] == _MASK
    # Persisted: config_store sees it.
    cfg = get_config()
    assert cfg.navidrome_pass == "hunter2"


def test_post_supports_dir_fields(client: TestClient) -> None:
    res = client.post("/api/config", json={
        "music_inbox_dir": "/srv/new/inbox",
    })
    assert res.status_code == 200
    assert res.json()["music_inbox_dir"] == "/srv/new/inbox"


# ---------- POST validation -------------------------------------------------

def test_post_rejects_non_http_url(client: TestClient) -> None:
    res = client.post("/api/config", json={
        "navidrome_url": "ftp://nope.example",
    })
    assert res.status_code == 400
    body = res.json()
    assert "navidrome_url" in str(body)
    # Nothing persisted.
    assert get_config().navidrome_url is None


def test_post_rejects_relative_dir(client: TestClient) -> None:
    res = client.post("/api/config", json={
        "music_inbox_dir": "relative/path",
    })
    assert res.status_code == 400
    assert "music_inbox_dir" in str(res.json())


def test_post_rejects_empty_non_secret_field(client: TestClient) -> None:
    res = client.post("/api/config", json={
        "navidrome_user": "",
    })
    assert res.status_code == 400


def test_post_rejects_non_string_value(client: TestClient) -> None:
    res = client.post("/api/config", json={
        "navidrome_url": 12345,
    })
    assert res.status_code == 400


def test_post_rejects_non_object_body(client: TestClient) -> None:
    res = client.post(
        "/api/config",
        content=b'["list", "not", "object"]',
        headers={"content-type": "application/json"},
    )
    assert res.status_code == 400


def test_post_rejects_invalid_json(client: TestClient) -> None:
    res = client.post(
        "/api/config",
        content=b"{not valid json",
        headers={"content-type": "application/json"},
    )
    assert res.status_code == 400


# ---------- POST empty-pass = no-change -------------------------------------

def test_post_empty_password_does_not_overwrite_stored(client: TestClient) -> None:
    # First, save a real password.
    save_config({"navidrome_pass": "hunter2"})
    assert get_config().navidrome_pass == "hunter2"
    # POSTing empty string for the password should NOT overwrite.
    res = client.post("/api/config", json={"navidrome_pass": ""})
    assert res.status_code == 200
    assert get_config().navidrome_pass == "hunter2"


def test_post_empty_password_silent_skip_with_other_fields(
    client: TestClient,
) -> None:
    """Empty password gets dropped; other fields in the same payload
    still apply. This is the typical edit case: user fills in a URL
    but doesn't retype their password."""
    save_config({"navidrome_pass": "hunter2"})
    res = client.post("/api/config", json={
        "navidrome_url": "https://new.example",
        "navidrome_pass": "",
    })
    assert res.status_code == 200
    cfg = get_config()
    assert cfg.navidrome_url == "https://new.example"
    assert cfg.navidrome_pass == "hunter2"


def test_post_null_clears_a_field(client: TestClient) -> None:
    save_config({"navidrome_url": "https://nav.example"})
    res = client.post("/api/config", json={"navidrome_url": None})
    assert res.status_code == 200
    assert get_config().navidrome_url is None


# ---------- POST unknown keys ----------------------------------------------

def test_post_rejects_unknown_key(client: TestClient) -> None:
    res = client.post("/api/config", json={"bogus_field": "x"})
    assert res.status_code == 400
    # Detail message names the bogus key.
    detail = res.json().get("detail", "")
    assert "bogus_field" in str(detail)


def test_post_with_unknown_key_does_not_persist_known_keys(
    client: TestClient,
) -> None:
    """If even one key is unknown, the whole request is rejected —
    no partial write."""
    res = client.post("/api/config", json={
        "navidrome_url": "https://ok.example",
        "bogus_field": "x",
    })
    assert res.status_code == 400
    assert get_config().navidrome_url is None
