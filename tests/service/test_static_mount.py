"""Failing tests for sprint-7 Bucket A — FastAPI static asset wire-up.

The Mash Co. design system handoff vendors token CSS, component CSS,
favicon family, manifest, and apple-touch into the cd-archivist repo.
Sprint-7 mounts these at /static/css/ and /static/img/brand/ and emits
the full favicon family + PWA manifest + theme-color meta in the
kanban page <head>.

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


# ---------------- (a) /static/css/tokens.css resolves --------------------


def test_static_tokens_css_served_at_css_subdir(client: TestClient) -> None:
    r = client.get("/static/css/tokens.css")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/css")


# ---------------- (b) /static/css/cda.css resolves -----------------------


def test_static_cda_css_served(client: TestClient) -> None:
    r = client.get("/static/css/cda.css")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/css")


# ---------------- (c) favicon PNG resolves -------------------------------


def test_static_favicon_png_served(client: TestClient) -> None:
    r = client.get("/static/img/brand/cd-a-favicon-32x32.png")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"


# ---------------- (d) PWA manifest resolves ------------------------------


def test_static_pwa_manifest_served(client: TestClient) -> None:
    r = client.get("/static/manifest.webmanifest")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/manifest+json")


# ---------------- (e) head emits favicon family + manifest + theme-color


def test_head_emits_favicon_family_manifest_theme_color(
    client: TestClient,
) -> None:
    html = client.get("/rip").text
    # Per build prompt's snippet: 32, 64, 256 PNG favicons + apple-touch
    # + manifest + theme-color meta.
    assert 'href="/static/img/brand/cd-a-favicon-32x32.png"' in html
    assert 'href="/static/img/brand/cd-a-favicon-64x64.png"' in html
    assert 'href="/static/img/brand/cd-a-favicon-256x256.png"' in html
    assert 'rel="apple-touch-icon"' in html
    assert 'href="/static/img/brand/cd-a-apple-touch-180.png"' in html
    assert 'href="/static/manifest.webmanifest"' in html
    assert re.search(
        r'<meta\s+name=["\']theme-color["\']\s+content=["\']#07090c["\']',
        html,
    ), "missing <meta name='theme-color' content='#07090c'>"


# ---------------- (f) tokens.css loads BEFORE cda.css --------------------


def test_tokens_css_loads_before_cda_css(client: TestClient) -> None:
    html = client.get("/rip").text
    tokens_pos = html.find("/static/css/tokens.css")
    cda_pos = html.find("/static/css/cda.css")
    assert tokens_pos != -1, "tokens.css link not in <head>"
    assert cda_pos != -1, "cda.css link not in <head>"
    assert tokens_pos < cda_pos, (
        "tokens.css must load BEFORE cda.css so cda.css "
        "can consume the design-token variables"
    )
