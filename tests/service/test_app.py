"""Failing tests for archivist.service.app — FastAPI status surface.

Covers:
  GET /api/status — JSON snapshot of LoopState              (test-service-status)
  GET /api/log    — text/plain tail of pipeline log         (test-service-status)
  GET /           — single-file HTML status page dressed in (test-service-ui)
                    the Mash Co. design system

Mash Co. contract (per /home/loydmilligan/Projects/Mash Co. Design
System/README.md + SKILL.md): dark-first (`data-theme="dark"`),
sentence case for body copy (Title Case only for brand names like
`Orc Tower`; `cd-archivist` is lowercase), eyebrows are ALL CAPS but
≤2 words (3+ word ALL CAPS phrases like `INSERT A CD` are the
explicit anti-pattern), no emoji (functional Unicode glyphs
`▸ ▾ ↵ ↑ ↓ ↗ ↻` are allowed), tokens `--ink-*` + `--mash-pulp`.

Impl lands in Wave 2 (impl-service).
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
    # Sprint-3 / test-last-tick: `last_updated` was renamed to
    # `state_entered_at`; `last_tick_at` is the new heartbeat field that
    # updates every tick (not just on transitions). See Contract Changes.
    return LoopState(
        state="IDLE",
        disc_id=None,
        last_rip_status=None,
        state_entered_at=datetime(2026, 5, 14, 12, 0, 0),
        last_tick_at=datetime(2026, 5, 14, 12, 0, 0),
    )


@pytest.fixture
def log_path(tmp_path: Path) -> Path:
    p = tmp_path / "archivist.log"
    p.write_text("\n".join(f"line {i}" for i in range(1, 501)) + "\n")
    return p


# -------------------------- /api/status -------------------------------


def test_api_status_returns_loop_state_snapshot(loop_state: LoopState, log_path: Path) -> None:
    client = TestClient(create_app(loop_state, log_path))
    resp = client.get("/api/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "IDLE"
    assert body["disc_id"] is None
    assert body["last_rip_status"] is None
    # Sprint-3 / test-last-tick: snapshot exposes both timestamps as
    # ISO strings; `last_updated` has been renamed to `state_entered_at`.
    assert "state_entered_at" in body
    assert "last_tick_at" in body
    assert "last_updated" not in body


def test_api_status_round_trips_rip_progress(loop_state: LoopState, log_path: Path) -> None:
    """LoopState gains an optional rip_progress field surfaced in /api/status.

    Sprint-3 / test-rip-progress: `rip_progress: str | None = None` (default).
    """
    client = TestClient(create_app(loop_state, log_path))

    # Default: None.
    body = client.get("/api/status").json()
    assert body.get("rip_progress") is None

    # Set: the JSON reflects it.
    loop_state.rip_progress = "track 4/12, 38%"
    body = client.get("/api/status").json()
    assert body["rip_progress"] == "track 4/12, 38%"


def test_api_status_reflects_live_updates(loop_state: LoopState, log_path: Path) -> None:
    """Mutating loop_state between calls must surface — no stale caching."""
    client = TestClient(create_app(loop_state, log_path))
    assert client.get("/api/status").json()["state"] == "IDLE"

    loop_state.state = "RIP"
    loop_state.disc_id = "CD_0001"
    loop_state.last_rip_status = "success"

    body = client.get("/api/status").json()
    assert body["state"] == "RIP"
    assert body["disc_id"] == "CD_0001"
    assert body["last_rip_status"] == "success"


# -------------------------- /api/log ----------------------------------


def test_api_log_default_tails_200_lines(loop_state: LoopState, log_path: Path) -> None:
    client = TestClient(create_app(loop_state, log_path))
    resp = client.get("/api/log")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    lines = [ln for ln in resp.text.splitlines() if ln]
    assert len(lines) == 200
    assert lines[0] == "line 301"
    assert lines[-1] == "line 500"


def test_api_log_lines_param_capped_at_1000(loop_state: LoopState, log_path: Path) -> None:
    client = TestClient(create_app(loop_state, log_path))
    # Ask for far more than the cap.
    resp = client.get("/api/log", params={"lines": 100000})
    assert resp.status_code == 200
    lines = [ln for ln in resp.text.splitlines() if ln]
    # Cap is 1000; log only has 500 → all 500 returned (not 100000).
    assert len(lines) == 500


def test_api_log_missing_file_returns_empty_200(loop_state: LoopState, tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.log"
    client = TestClient(create_app(loop_state, missing))
    resp = client.get("/api/log")
    assert resp.status_code == 200
    assert resp.text == ""


# -------------------------- GET / (UI page) ---------------------------
# Test-service-ui assertions. The Mash Co. constraints are documented
# in the module docstring; the heuristics below enforce them.


# Decorative emoji ranges. Functional Unicode glyphs listed in the
# Mash Co. README (▸ ▾ ↵ ↑ ↓ ↗ ↻ — geometric shapes U+25xx, arrows
# U+21xx, miscellaneous technical U+23xx) fall OUTSIDE these ranges,
# so they pass.
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"   # main emoji blocks (symbols & pictographs, etc.)
    "\U00002600-\U000027BF"   # misc symbols & dingbats incl. ☀-➿
    "\U0001F1E6-\U0001F1FF"   # regional indicator symbols
    "]"
)


def test_root_page_returns_html(loop_state: LoopState, log_path: Path) -> None:
    client = TestClient(create_app(loop_state, log_path))
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")


def test_root_page_wires_real_endpoints_and_title(loop_state: LoopState, log_path: Path) -> None:
    """The page must reference the real endpoints — not be a stub."""
    client = TestClient(create_app(loop_state, log_path))
    body = client.get("/").text
    assert "cd-archivist" in body
    assert "/api/status" in body
    assert "/api/log" in body


def test_root_page_carries_mash_design_tokens(loop_state: LoopState, log_path: Path) -> None:
    """Tokens are wired — inline <style> or via served /static/tokens.css."""
    client = TestClient(create_app(loop_state, log_path))
    body = client.get("/").text

    # Tokens may be inline OR linked. If linked, fetch the served file
    # and search across both for the token strings.
    sources = [body]
    link_match = re.search(r'href="(/static/tokens\.css[^"]*)"', body)
    if link_match:
        resp = client.get(link_match.group(1))
        assert resp.status_code == 200, "linked tokens.css must be served"
        sources.append(resp.text)

    combined = "\n".join(sources)
    assert "--ink-" in combined, "missing --ink-* design tokens"
    assert "--mash-pulp" in combined, "missing --mash-pulp design token"


def test_root_page_is_dark_first(loop_state: LoopState, log_path: Path) -> None:
    """The page declares dark theme on <html> per Mash Co. dark-first rule."""
    client = TestClient(create_app(loop_state, log_path))
    body = client.get("/").text
    assert 'data-theme="dark"' in body


def test_root_page_no_emoji(loop_state: LoopState, log_path: Path) -> None:
    """No decorative emoji per Mash Co. voice rules.

    Functional Unicode glyphs from the README allowlist
    (▸ ▾ ↵ ↑ ↓ ↗ ↻) are outside the checked ranges and pass.
    """
    client = TestClient(create_app(loop_state, log_path))
    body = client.get("/").text
    matches = _EMOJI_RE.findall(body)
    assert matches == [], f"unexpected emoji in body: {matches!r}"


def test_root_page_no_three_word_caps_body_copy(loop_state: LoopState, log_path: Path) -> None:
    """Eyebrows are ≤2 words ALL CAPS; body copy is sentence case.

    Per Mash Co. README:
      'Eyebrows go SCREAMING UPPER with letter-spacing: 0.08em, but
      they're short labels — ≤2 words — not headlines.'

    The task body calls out `INSERT A CD` and `WAITING FOR DISC` as
    the explicit anti-pattern — both 3-word all-caps phrases used as
    sentence labels. This test flags any 3-or-more-word all-caps run
    in visible text. Single-word and 2-word ALLCAPS runs are
    permissible eyebrows (e.g. `IDLE`, `WHAT NEXT`).
    """
    client = TestClient(create_app(loop_state, log_path))
    body = client.get("/").text

    # Strip <script>, <style>, and all tags so we look at visible text only.
    stripped = re.sub(r"<script\b[^>]*>.*?</script>", " ", body, flags=re.S | re.I)
    stripped = re.sub(r"<style\b[^>]*>.*?</style>", " ", stripped, flags=re.S | re.I)
    visible = re.sub(r"<[^>]+>", " ", stripped)

    # 3+ consecutive ALL-CAPS words = offender (eyebrows are ≤2 words).
    offenders = re.findall(
        r"\b[A-Z]{2,}(?:\s+[A-Z]{2,}){2,}\b",
        visible,
    )
    assert offenders == [], (
        f"3+-word ALL CAPS body copy is not an eyebrow — sentence case "
        f"required. Offenders: {offenders!r}"
    )


# -------- liveness rendering (sprint-3 / test-status-ui-liveness) ----


def test_root_page_renders_both_timestamps(loop_state: LoopState, log_path: Path) -> None:
    """Page JS references both state_entered_at and last_tick_at.

    The HTML doesn't have to format them server-side — the JS computes
    "entered Xm ago" / "last tick Ns ago" client-side. We assert that
    both field names appear in the page (in the polling JS) so the
    wiring is real.
    """
    client = TestClient(create_app(loop_state, log_path))
    body = client.get("/").text
    assert "state_entered_at" in body
    assert "last_tick_at" in body


def test_root_page_log_follow_toggle(loop_state: LoopState, log_path: Path) -> None:
    """Log tail has a data-follow attribute and a toggle button.

    Auto-scroll follow defaults to "on"; clicking the chip toggles it.
    """
    client = TestClient(create_app(loop_state, log_path))
    body = client.get("/").text
    # The <pre> declares the follow state.
    assert 'data-follow="on"' in body
    # A toggle control exists.
    assert 'id="log-follow-toggle"' in body
    # JS contains the scroll-to-bottom line gated on follow.
    assert "scrollTop" in body and "scrollHeight" in body
