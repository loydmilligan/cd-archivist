"""Sprint-11 / settings-page-render — `/settings` page tests.

Covers:
  - Route returns 200
  - Form contains all 10 fields with the correct `type` attribute
  - Password fields show the masked placeholder when a value is
    stored, "(unset)" otherwise; never carry a `value=` attribute
  - Save button submits the form (form has the data attribute the
    inline JS hooks; the JS posts to /api/config)
  - Three sections rendered in expected order
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from archivist.service.app import LoopState, create_app
from archivist.service.config import reload_config, save_config


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


def test_settings_route_returns_200(client: TestClient) -> None:
    res = client.get("/settings")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")


def test_form_contains_ten_inputs(client: TestClient) -> None:
    """Acceptance criterion: `curl ... | grep -c "<input"` returns 10."""
    html = client.get("/settings").text
    inputs = re.findall(r"<input\b", html)
    assert len(inputs) == 10, f"expected 10 inputs, got {len(inputs)}: {inputs}"


@pytest.mark.parametrize("field_name,expected_type", [
    ("spooty_api_url",    "url"),
    ("spooty_api_token",  "password"),
    ("navidrome_url",     "url"),
    ("navidrome_user",    "text"),
    ("navidrome_pass",    "password"),
    ("music_inbox_dir",   "text"),
    ("music_library_dir", "text"),
    ("music_archive_dir", "text"),
    ("music_spooty_dir",  "text"),
    ("music_review_dir",  "text"),
])
def test_field_has_correct_type(
    client: TestClient, field_name: str, expected_type: str,
) -> None:
    html = client.get("/settings").text
    pat = (
        rf'<input type="{re.escape(expected_type)}" '
        rf'id="{re.escape(field_name)}" '
        rf'name="{re.escape(field_name)}"'
    )
    assert re.search(pat, html), (
        f"missing input type={expected_type} for field {field_name}"
    )


def test_password_placeholder_when_set(client: TestClient) -> None:
    """Password fields show the eight-bullet glyph placeholder once
    a value is stored, signalling 'something here, leave blank to keep'."""
    save_config({"navidrome_pass": "hunter2", "spooty_api_token": "tok-abc"})
    html = client.get("/settings").text
    # Both password fields carry the mask placeholder.
    nav_pass = re.search(
        r'<input type="password" id="navidrome_pass" name="navidrome_pass" '
        r'placeholder="([^"]+)"',
        html,
    )
    assert nav_pass is not None
    assert nav_pass.group(1) == "●" * 8

    spooty_tok = re.search(
        r'<input type="password" id="spooty_api_token" name="spooty_api_token" '
        r'placeholder="([^"]+)"',
        html,
    )
    assert spooty_tok is not None
    assert spooty_tok.group(1) == "●" * 8


def test_password_placeholder_when_unset(client: TestClient) -> None:
    html = client.get("/settings").text
    m = re.search(
        r'<input type="password" id="navidrome_pass" name="navidrome_pass" '
        r'placeholder="([^"]+)"',
        html,
    )
    assert m is not None
    assert m.group(1) == "(unset)"


def test_password_field_never_carries_value_attr(client: TestClient) -> None:
    """Even when a password is stored, the form must not echo it back
    as a `value=` attribute (it'd leak the secret to anyone viewing
    the page; the placeholder is the only signal of presence)."""
    save_config({"navidrome_pass": "hunter2"})
    html = client.get("/settings").text
    # Locate the navidrome_pass input.
    m = re.search(
        r'<input type="password" id="navidrome_pass" name="navidrome_pass"[^>]*/?>',
        html,
    )
    assert m is not None
    assert " value=" not in m.group(0), (
        "password field leaked stored value as value= attribute"
    )
    # And the plaintext secret is not anywhere in the page body.
    assert "hunter2" not in html


def test_url_field_shows_stored_value(client: TestClient) -> None:
    save_config({"navidrome_url": "https://nav.example"})
    html = client.get("/settings").text
    assert 'value="https://nav.example"' in html


def test_three_sections_in_order(client: TestClient) -> None:
    html = client.get("/settings").text
    spooty_idx = html.index("Spooty")
    navidrome_idx = html.index("Navidrome")
    music_idx = html.index("Music paths")
    assert spooty_idx < navidrome_idx < music_idx


def test_save_button_posts_to_api_config(client: TestClient) -> None:
    """The inline JS hooks via `data-cda-settings-form` and posts to
    `/api/config`. Verify both the form attribute is present (so the
    JS finds it) and the JS body references the API path."""
    html = client.get("/settings").text
    assert "data-cda-settings-form" in html
    assert "/api/config" in html
    # Submit button is type=submit so a no-JS fallback at least
    # triggers a browser-level form POST.
    assert re.search(
        r'<button type="submit" class="cda-settings-save">Save</button>',
        html,
    ) is not None


def test_banner_element_present(client: TestClient) -> None:
    """The save banner div exists in the markup (initially hidden)
    so the JS can address it without inserting nodes."""
    html = client.get("/settings").text
    assert "data-cda-settings-banner" in html


def test_page_loads_with_no_music_root(tmp_path: Path) -> None:
    """`/settings` must work even when no music tree is configured —
    the whole point is to configure it from scratch from the UI."""
    log_path = tmp_path / "archivist.log"
    log_path.write_text("")
    bootstrap_client = TestClient(create_app(LoopState(), log_path))
    res = bootstrap_client.get("/settings")
    assert res.status_code == 200
