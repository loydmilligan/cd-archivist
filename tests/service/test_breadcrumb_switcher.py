"""Sprint-9 / breadcrumb-switcher — surface picker tests.

Sprint-11 / settings-link-in-switcher: extended with a `settings` row
and a telemetry hint sourced from
`archivist.service.config.get_config_summary()`.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from archivist.service.app import LoopState, create_app
from archivist.service.config import reload_config, save_config
from archivist.service.library_switcher import render_switcher


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
    """Point the config store at a per-test JSON file + clear the
    cache + scrub config env vars. The switcher's settings-row
    telemetry reads from `get_config_summary()`, which depends on
    the config store."""
    monkeypatch.setenv(
        "ARCHIVIST_CONFIG_PATH", str(tmp_path / "_test_config.json"),
    )
    for var in _CONFIG_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    reload_config()
    yield
    reload_config()


@pytest.fixture
def loop_state() -> LoopState:
    return LoopState(
        state="IDLE",
        disc_id=None,
        last_rip_status=None,
        state_entered_at=datetime(2026, 5, 19, 12, 0, 0),
        last_tick_at=datetime(2026, 5, 19, 12, 0, 0),
    )


@pytest.fixture
def client(loop_state, tmp_path: Path) -> TestClient:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    review = tmp_path / "review"
    review.mkdir()
    app = create_app(
        loop_state=loop_state,
        log_path=tmp_path / "pipeline.log",
        music_root=inbox,
        review_root=review,
        discs_root=inbox,
    )
    return TestClient(app)


# ---- render_switcher unit tests ----------------------------------------------


def test_switcher_carries_brand_mark_and_separator() -> None:
    html = render_switcher(active="rip")
    assert 'cda-brand-mark cda-brand-mark--header' in html
    assert 'cda-switcher-sep' in html


def test_switcher_button_label_matches_active_surface() -> None:
    rip_html = render_switcher(active="rip")
    lib_html = render_switcher(active="library")
    set_html = render_switcher(active="settings")
    # button text contains the active label
    rip_btn = re.search(r'class="cda-switcher-btn"[^>]*>([^<]+)<', rip_html)
    lib_btn = re.search(r'class="cda-switcher-btn"[^>]*>([^<]+)<', lib_html)
    set_btn = re.search(r'class="cda-switcher-btn"[^>]*>([^<]+)<', set_html)
    assert rip_btn and "rip" in rip_btn.group(1)
    assert lib_btn and "library" in lib_btn.group(1)
    assert set_btn and "settings" in set_btn.group(1)


def test_switcher_marks_active_row_with_is_on() -> None:
    html = render_switcher(active="rip")
    # exactly one is-on row
    matches = re.findall(r'class="cda-switcher-row\s+is-on"', html)
    assert len(matches) == 1
    # and that row is the rip row
    assert re.search(
        r'class="cda-switcher-row\s+is-on"[^>]*data-surface="rip"', html
    )


def test_switcher_rows_link_to_surface_roots() -> None:
    html = render_switcher(active="library")
    assert 'href="/rip"' in html
    assert 'href="/library"' in html
    # Sprint-11: settings row links to /settings.
    assert 'href="/settings"' in html


def test_switcher_dropdown_has_three_rows_in_order() -> None:
    """Sprint-11 / settings-link-in-switcher: dropdown carries rip,
    library, settings in that order. Pinning the order pins build-
    prompt §2's row sequencing so a future refactor can't silently
    swap them."""
    html = render_switcher(active="rip")
    rows = re.findall(r'data-surface="([^"]+)"', html)
    assert rows == ["rip", "library", "settings"]


def test_switcher_marks_settings_row_is_on_when_active() -> None:
    html = render_switcher(active="settings")
    assert re.search(
        r'class="cda-switcher-row\s+is-on"[^>]*data-surface="settings"',
        html,
    )


def test_switcher_telemetry_renders_in_meta_spans() -> None:
    html = render_switcher(
        active="rip", rip_telemetry="4 ripping · 2 review",
        library_telemetry="3 inbox · 1 download",
        settings_telemetry="2 knobs · saved 3m ago",
    )
    assert '<span class="meta">4 ripping · 2 review</span>' in html
    assert '<span class="meta">3 inbox · 1 download</span>' in html
    assert '<span class="meta">2 knobs · saved 3m ago</span>' in html


def test_switcher_settings_telemetry_defaults_to_config_summary() -> None:
    """When the caller omits `settings_telemetry`, the switcher
    looks the summary up via `get_config_summary()`. Format is
    `N knobs · saved T ago` per the sprint-11 plan."""
    save_config({"spooty_api_url": "http://x", "navidrome_url": "http://y"})
    html = render_switcher(active="settings")
    # 2 explicit non-default knobs, file just got written → "just now".
    assert re.search(
        r'<span class="meta">2 knobs · saved (just now|0m ago)</span>',
        html,
    )


def test_switcher_settings_telemetry_says_never_when_no_config_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No file present → `saved never`. (The autouse fixture points
    `ARCHIVIST_CONFIG_PATH` at a fresh tmp file that does not yet
    exist on this code path because we haven't called `save_config`.)"""
    monkeypatch.setenv(
        "ARCHIVIST_CONFIG_PATH", str(tmp_path / "nope" / "config.json"),
    )
    reload_config()
    html = render_switcher(active="settings")
    assert "saved never" in html


def test_switcher_settings_telemetry_explicit_empty_string_overrides_default() -> None:
    """Pass `settings_telemetry=""` to suppress the auto-lookup
    entirely (e.g., if a caller wants a quiet header)."""
    html = render_switcher(active="settings", settings_telemetry="")
    assert '<span class="meta"></span>' in html


def test_switcher_dropdown_starts_collapsed() -> None:
    html = render_switcher(active="rip")
    # The popover must carry the `hidden` attribute on initial render
    # (the inline JS removes it when the button is clicked).
    assert re.search(r'id="surface-switcher-pop"[^>]*hidden', html)
    # button aria-expanded is false
    assert 'aria-expanded="false"' in html


def test_switcher_rejects_unknown_active_surface() -> None:
    with pytest.raises(ValueError):
        render_switcher(active="nonsense")


def test_switcher_present_on_settings_with_settings_active(
    client: TestClient,
) -> None:
    """Sprint-11 integration: /settings carries the switcher with the
    settings row in `is-on` state."""
    html = client.get("/settings").text
    assert "data-surface-switcher" in html
    assert re.search(
        r'class="cda-switcher-row\s+is-on"[^>]*data-surface="settings"',
        html,
    )


# ---- get_config_summary unit tests (the helper lane-2 added) ----------------


def test_get_config_summary_counts_non_default_knobs() -> None:
    from archivist.service.config import get_config_summary
    # No file yet → 0 knobs, never saved.
    assert get_config_summary() == {"knobs": 0, "saved": "never"}
    save_config({"spooty_api_url": "http://x"})
    summary = get_config_summary()
    assert summary["knobs"] == 1
    assert summary["saved"] in ("just now", "0m ago")


def test_get_config_summary_returns_never_when_file_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from archivist.service.config import get_config_summary
    monkeypatch.setenv(
        "ARCHIVIST_CONFIG_PATH", str(tmp_path / "no_such_dir" / "config.json"),
    )
    reload_config()
    summary = get_config_summary()
    assert summary["knobs"] == 0
    assert summary["saved"] == "never"


# ---- integration: switcher renders on both /rip and /library ----------------


def test_switcher_present_on_rip_with_rip_active(client: TestClient) -> None:
    html = client.get("/rip").text
    assert 'data-surface-switcher' in html
    # rip row marked is-on
    assert re.search(
        r'class="cda-switcher-row\s+is-on"[^>]*data-surface="rip"', html
    )


def test_switcher_present_on_library_with_library_active(client: TestClient) -> None:
    html = client.get("/library").text
    assert 'data-surface-switcher' in html
    assert re.search(
        r'class="cda-switcher-row\s+is-on"[^>]*data-surface="library"', html
    )


def test_switcher_js_injected_on_both_surfaces(client: TestClient) -> None:
    # Inline JS that wires the dropdown toggle. Same string both sides.
    needle = "data-surface-switcher"  # JS queries this attr
    rip_html = client.get("/rip").text
    lib_html = client.get("/library").text
    # The JS body contains the IIFE for the toggle handler.
    assert "data-switcher-toggle" in rip_html
    assert "data-switcher-toggle" in lib_html
    # The CSS-selector hook appears in both pages (one in the switcher
    # DOM, one in the IIFE).
    assert rip_html.count(needle) >= 2
    assert lib_html.count(needle) >= 2


def test_legacy_inline_brand_mark_replaced_by_switcher(client: TestClient) -> None:
    # The old bare brand-mark span (without switcher wrapper) must NOT
    # appear on /rip — the switcher's brand mark is the new canonical.
    # We check by counting cda-brand-mark--header occurrences: exactly
    # one (inside the switcher), not two (legacy + new).
    html = client.get("/rip").text
    assert html.count('cda-brand-mark cda-brand-mark--header') == 1
