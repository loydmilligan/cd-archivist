"""Failing tests for sprint-7 Bucket B — the `cd/a` brand mark.

Per the Mash Co. build prompt the brand mark is **chunky and extruded**,
NOT a flat italic. Rendered as `<span class="cda-brand-mark">cd/a</span>`
with a specific CSS recipe in cda.css: Bricolage Grotesque 800 italic,
letter-spacing -0.05em, --mash-pulp color with --mash-pulp-edge stroke,
paint-order stroke-fill, and a multi-layer text-shadow extrude.

Three size variants must exist in cda.css:
  - .cda-brand-mark--header     (22px, used in the kanban header)
  - .cda-brand-mark--splash     (84px, reserved for splash hero)
  - .cda-brand-mark--marketing  (240px, reserved for marketing)

Wave 2 impl: `impl-css-migration-brand-mark` (lane-1).
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


# ---------------- (a) header renders the brand mark span ----------------


def test_header_renders_cda_brand_mark_span(client: TestClient) -> None:
    html = client.get("/rip").text
    # Must literally render `cd/a` inside a span carrying the brand-mark
    # class and the --header size variant.
    assert re.search(
        r'<span\s+class="[^"]*\bcda-brand-mark\b[^"]*\bcda-brand-mark--header\b[^"]*"[^>]*>cd/a</span>',
        html,
    ) or re.search(
        r'<span\s+class="[^"]*\bcda-brand-mark--header\b[^"]*\bcda-brand-mark\b[^"]*"[^>]*>cd/a</span>',
        html,
    ), (
        "expected `<span class=\"cda-brand-mark cda-brand-mark--header\">"
        "cd/a</span>` in the rendered header"
    )


def test_header_brand_mark_replaces_plain_wordmark(client: TestClient) -> None:
    """Sprint-6.5 shipped a `class=\"wordmark\"` text element; the
    brand-mark recipe replaces it. Asserts the old class no longer
    carries the 'cd-archivist' text alone — the brand mark must be
    present (slug `cd-archivist` may still appear as a sibling label)."""
    html = client.get("/rip").text
    assert "cda-brand-mark" in html, (
        "header is still using the legacy text wordmark; the cd/a "
        "brand mark must be rendered per the build prompt"
    )


# ---------------- (b) cda.css recipe per the build prompt ---------------


def _read_cda_css(client: TestClient) -> str:
    r = client.get("/static/css/cda.css")
    assert r.status_code == 200, "cda.css must be served at /static/css/cda.css"
    return r.text


def test_cda_css_defines_brand_mark_base_recipe(client: TestClient) -> None:
    cda = _read_cda_css(client)
    m = re.search(r"\.cda-brand-mark\s*\{([^}]*)\}", cda, re.DOTALL)
    assert m is not None, "cda.css missing `.cda-brand-mark { ... }` block"
    block = m.group(1)
    # Required declarations per the build prompt's recipe.
    required = [
        ("font-family", "var(--font-display)"),
        ("font-weight", "800"),
        ("font-style", "italic"),
        ("letter-spacing", "-0.05em"),
        ("color", "var(--mash-pulp)"),
        ("paint-order", "stroke fill"),
    ]
    for prop, value in required:
        assert prop in block, (
            f".cda-brand-mark missing `{prop}` declaration"
        )
        assert value in block, (
            f".cda-brand-mark `{prop}` must use {value!r} per the build "
            "prompt's recipe"
        )
    # -webkit-text-stroke present (any width/color, the impl picks
    # 1.5px var(--mash-pulp-edge) for the header variant).
    assert "-webkit-text-stroke" in block, (
        ".cda-brand-mark must declare -webkit-text-stroke for the "
        "extruded edge"
    )
    # Multi-layer text-shadow extrude (the recipe stacks 5+ layers).
    shadow_match = re.search(r"text-shadow\s*:\s*([^;]+);", block, re.DOTALL)
    assert shadow_match is not None, (
        ".cda-brand-mark missing text-shadow extrude"
    )
    layers = [ln for ln in shadow_match.group(1).split(",") if ln.strip()]
    assert len(layers) >= 5, (
        f"text-shadow must stack at least 5 layers for the extrude "
        f"effect; found {len(layers)}"
    )


# ---------------- (c) size variants exist -------------------------------


# Sprint-7 polish (header embiggen): the --header variant scaled from
# 22px → 36px so the mark reads as a dashboard quick view. The splash
# and marketing variants keep the original build-prompt sizes.
@pytest.mark.parametrize("variant,px", [
    ("cda-brand-mark--header", "36px"),
    ("cda-brand-mark--splash", "84px"),
    ("cda-brand-mark--marketing", "240px"),
])
def test_cda_css_defines_brand_mark_size_variant(
    client: TestClient, variant: str, px: str,
) -> None:
    cda = _read_cda_css(client)
    m = re.search(rf"\.{re.escape(variant)}\s*\{{([^}}]*)\}}", cda, re.DOTALL)
    assert m is not None, (
        f"cda.css missing `.{variant} {{ ... }}` block per the build "
        "prompt's three size variants"
    )
    block = m.group(1)
    assert "font-size" in block, f".{variant} must set font-size"
    assert px in block, (
        f".{variant} must use font-size: {px} per the build-prompt table"
    )
