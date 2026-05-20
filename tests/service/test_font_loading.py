"""Failing tests for sprint-7 Bucket A — Google Fonts loading.

Per the Mash Co. build prompt the three brand families
(Bricolage Grotesque, Inter Tight, JetBrains Mono) load from
Google Fonts. The page <head> must include the preconnect
and the family stylesheet <link>; tokens.css must import the
same families; and no system-font fallback <style> blocks
may override the brand stack.

Wave 2 impl: `impl-asset-wire-up` (lane-1).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from archivist.service.app import LoopState, create_app


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


# ---------------- (a) page emits preconnect + family stylesheet ---------


def test_head_emits_google_fonts_preconnect(client: TestClient) -> None:
    html = client.get("/rip").text
    # Preconnect to fonts.googleapis.com AND fonts.gstatic.com per
    # Google Fonts' recommended two-host preconnect.
    assert re.search(
        r'<link\s+rel=["\']preconnect["\']\s+href=["\']https://fonts\.googleapis\.com["\']',
        html,
    ), "missing preconnect for fonts.googleapis.com"
    assert re.search(
        r'<link\s+rel=["\']preconnect["\']\s+href=["\']https://fonts\.gstatic\.com["\']',
        html,
    ), "missing preconnect for fonts.gstatic.com (CORS)"


def test_head_loads_bricolage_grotesque_weights(client: TestClient) -> None:
    html = client.get("/rip").text
    # Bricolage Grotesque at weights 600 + 800.
    m = re.search(
        r'fonts\.googleapis\.com/css2\?[^"\']*family=Bricolage[+ ]Grotesque[^"\']*',
        html,
    )
    assert m is not None, "missing Bricolage Grotesque <link>"
    spec = m.group(0)
    assert "600" in spec, "Bricolage weight 600 not requested"
    assert "800" in spec, "Bricolage weight 800 not requested"


def test_head_loads_inter_tight_weights(client: TestClient) -> None:
    html = client.get("/rip").text
    m = re.search(
        r'fonts\.googleapis\.com/css2\?[^"\']*family=Inter[+ ]Tight[^"\']*',
        html,
    )
    assert m is not None, "missing Inter Tight <link>"
    spec = m.group(0)
    for w in ("400", "500", "700"):
        assert w in spec, f"Inter Tight weight {w} not requested"


def test_head_loads_jetbrains_mono_weights(client: TestClient) -> None:
    html = client.get("/rip").text
    m = re.search(
        r'fonts\.googleapis\.com/css2\?[^"\']*family=JetBrains[+ ]Mono[^"\']*',
        html,
    )
    assert m is not None, "missing JetBrains Mono <link>"
    spec = m.group(0)
    for w in ("400", "500"):
        assert w in spec, f"JetBrains Mono weight {w} not requested"


# ---------------- (b) tokens.css imports the same families --------------


def test_tokens_css_imports_brand_font_families(client: TestClient) -> None:
    css = client.get("/static/css/tokens.css").text
    # Either via @import url(...fonts.googleapis.com...) or via a
    # documented @font-face block referencing the families.
    has_import = "fonts.googleapis.com" in css
    for family in ("Bricolage Grotesque", "Inter Tight", "JetBrains Mono"):
        assert family in css, (
            f"tokens.css missing reference to {family!r} — the brand "
            "fonts must be declared in tokens.css alongside the "
            "page-level Google Fonts <link>"
        )
    assert has_import, (
        "tokens.css must @import the Google Fonts stylesheet so that "
        "the families are declared in the tokens layer, not only in "
        "page-level <head> tags"
    )


# ---------------- (c) no system-font fallback overrides -----------------


def test_no_system_font_fallback_style_override(client: TestClient) -> None:
    """A previous version of the page declared inline
    `font-family: -apple-system, BlinkMacSystemFont, ...` that would
    short-circuit Bricolage. The brand fonts win — any such inline
    override is a bug per the build prompt's anti-pattern list."""
    html = client.get("/rip").text
    forbidden_stacks = (
        "-apple-system",
        "BlinkMacSystemFont",
        "Segoe UI",
        '"system-ui", -apple-system',
    )
    for stack in forbidden_stacks:
        assert stack not in html, (
            f"system-font fallback {stack!r} appears in page HTML; the "
            "brand stack must come from tokens.css / cda.css only"
        )
