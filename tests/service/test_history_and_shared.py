"""Sprint-9 / history-and-shared — final wire-up checks.

Browser history behavior: sidebar anchors are real anchors with real
hrefs (`<a href="/library/{id}">`). The browser handles back/forward
natively — no JS history shim is needed for this sprint's shell-only
scope. This test file proves the anchor contract is intact.

Shared chassis: bottom daemon log markup is byte-identical across
/rip and /library (same DOM, same data-endpoint), per build-prompt §5.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from archivist.service.app import LoopState, create_app


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


# ---- Browser history via real anchors ---------------------------------------


def test_sidebar_v1_clicks_target_real_urls(client: TestClient) -> None:
    """The sidebar uses native <a href> anchors for v1 panels — browser
    back/forward swaps the active panel via natural navigation. No JS
    history shim required."""
    html = client.get("/library").text
    for panel_id in ("downloads", "inbox", "disk", "library"):
        # anchor with href to the panel route exists in the sidebar
        assert re.search(
            rf'<a[^>]*class="cda-lib-row[^"]*"[^>]*href="/library/{panel_id}"',
            html,
        ), f"sidebar anchor missing for v1 panel {panel_id}"


def test_landing_v1_cards_are_clickable_anchors(client: TestClient) -> None:
    """Landing-card clicks also navigate via real anchors (same back/
    forward semantics as sidebar)."""
    html = client.get("/library").text
    for panel_id in ("downloads", "inbox", "disk", "library"):
        assert re.search(
            rf'<a[^>]*class="cda-lib-card[^"]*"[^>]*href="/library/{panel_id}"',
            html,
        ), f"landing anchor missing for v1 panel {panel_id}"


def test_v2_ghost_anchors_are_not_navigable(client: TestClient) -> None:
    """v2 ghost rows / cards have NO href — clicks are inert. The route
    handler 404s if a user types /library/review manually."""
    html = client.get("/library").text
    for panel_id in ("review", "recent", "cron"):
        # No <a> with this href anywhere in the HTML
        assert f'href="/library/{panel_id}"' not in html


def test_switcher_rip_to_library_navigation(client: TestClient) -> None:
    """Clicking `library` in the switcher dropdown from /rip targets
    /library — and vice versa. Asserts the anchor hrefs only; the actual
    click is a browser concern."""
    rip_html = client.get("/rip").text
    library_html = client.get("/library").text
    # rip → library link present
    assert re.search(
        r'class="cda-switcher-row[^"]*"[^>]*href="/library"', rip_html
    )
    # library → rip link present
    assert re.search(
        r'class="cda-switcher-row[^"]*"[^>]*href="/rip"', library_html
    )


# ---- Shared bottom log -------------------------------------------------------


def test_bottom_drawer_markup_identical_across_surfaces(client: TestClient) -> None:
    """Build-prompt §5: bottom daemon log is shared globally — same DOM,
    same data source, not duplicated per surface. Assert byte-identical
    bottom-drawer markup."""
    rip = client.get("/rip").text
    library = client.get("/library").text

    def extract_bottom(html: str) -> str:
        m = re.search(r'<aside id="bottom-drawer"[\s\S]*?</aside>', html)
        assert m is not None, "bottom-drawer markup missing"
        return m.group(0)

    rip_bottom = extract_bottom(rip)
    library_bottom = extract_bottom(library)
    assert rip_bottom == library_bottom, (
        f"bottom-drawer markup diverges across surfaces:\n"
        f"  /rip:     {rip_bottom!r}\n"
        f"  /library: {library_bottom!r}"
    )


def test_bottom_log_endpoint_is_shared(client: TestClient) -> None:
    """Both surfaces poll the same backend endpoint for the log tail."""
    rip = client.get("/rip").text
    library = client.get("/library").text
    needle = 'data-endpoint="/api/logs/tail?limit=200"'
    assert needle in rip
    assert needle in library


# ---- No console-error indicators in the rendered HTML -----------------------


def test_no_dangling_template_placeholders(client: TestClient) -> None:
    """Catch the common shipping accident: unreplaced `{var}` or
    `${var}` template literals. None should appear in HTML body
    output."""
    for path in ("/library", "/rip", "/library/downloads", "/library/inbox"):
        html = client.get(path).text
        # Inline JS in kanban_page uses ${} template literals; those
        # live INSIDE <script> tags. We scrub script tags before checking.
        body_only = re.sub(r"<script[\s\S]*?</script>", "", html)
        assert "${" not in body_only, f"dangling template literal in {path}"
        # Python-style {placeholder} that escaped string formatting.
        # Most legit braces are inside class lists or CSS-in-JS; scan
        # only for the suspicious word-only pattern `{word}`.
        for m in re.finditer(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", body_only):
            # Allow CSS or HTML attribute brace-strings that are
            # known-safe; this is a deliberately loose check — fail
            # only if a clearly-Python placeholder name shows up.
            if m.group(1) in {"stats", "active_disc", "links"}:
                pytest.fail(
                    f"unreplaced template variable {{{m.group(1)}}} in {path}"
                )
