"""Failing tests for targeted voice pass (sprint-7 Bucket G lane-3).

Targeted scope (per K1 brainstorm follow-up):
  - status-line templates           (where Bucket C lands them)
  - button labels in kanban + drawer + expanded card body
  - error states in /review explainer + drawer card-detail
  - no emoji + no smart quotes — only allowed Unicode glyphs

Allowed Unicode glyphs: ▸ ▾ ↵ ↑ ↓ ↗ ↻

Impl lands in Wave 2 (impl-voice-pass-targeted).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from archivist.service.app import LoopState, create_app

_SERVICE_DIR = Path(__file__).resolve().parents[2] / "archivist" / "service"

# Project's reserved Unicode glyphs (operator UI).
_ALLOWED_GLYPHS = {"▸", "▾", "↵", "↑", "↓", "↗", "↻", "·"}

# Emoji ranges that must not appear in shipped templates.
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]"
)
# Smart quotes / fancy punctuation that violates the voice pass.
_SMART_QUOTES = ("‘", "’", "“", "”")
# Markers that look like the wrong case treatments. SHOUTING is allowed
# only inside text-transform: uppercase eyebrows (CSS), not source.
_TITLE_CASE_BUTTON_RE = re.compile(
    r'>\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,})\s*<'
)


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


def _iter_template_sources() -> list[Path]:
    """Source files that ship operator-visible templates.

    Limited to the kanban surface + status-line + review explainer +
    expanded-card sections — those are the touch-up surfaces in the
    targeted voice pass per the sprint plan.
    """
    candidates = [
        _SERVICE_DIR / "kanban_page.py",
        _SERVICE_DIR / "review_explainer.py",
        _SERVICE_DIR / "operator_hints.py",
        _SERVICE_DIR / "damaged_disc.py",
        _SERVICE_DIR / "status_line.py",
        _SERVICE_DIR / "card_render.py",
        _SERVICE_DIR / "card_evolution.py",
    ]
    return [p for p in candidates if p.is_file()]


# ============== (a) status-line templates match build-prompt examples ===


def test_status_line_module_contains_canonical_phrases():
    """status_line.format(card) -> str is built by lane-2 in Bucket C.

    The targeted voice pass requires the canonical sentence-case
    operator phrases to be present in the module: 'ripping', 'stored',
    'weak match', 'no match', 'halted'. We assert the source carries
    them so the formatter cannot drift to title case or marketing copy.
    """
    sl = _SERVICE_DIR / "status_line.py"
    assert sl.is_file(), (
        "status_line.py is the home of the status-line formatter "
        "(lane-2 Bucket C); voice pass depends on it"
    )
    src = sl.read_text(encoding="utf-8")
    # Sentence-case operator phrases (lowercase verbs).
    for phrase in ("ripping", "stored", "halted", "weak match", "no match"):
        assert phrase in src.lower(), (
            f"status-line source missing canonical phrase {phrase!r}"
        )
    # Mono dot-separator.
    assert "·" in src, "status-line source missing the mono · separator"


def test_no_title_case_or_marketing_in_status_phrases():
    sl = _SERVICE_DIR / "status_line.py"
    if not sl.is_file():
        pytest.skip("status_line.py not yet present")
    src = sl.read_text(encoding="utf-8")
    # No anti-patterns from the build prompt's avoidance list.
    forbidden = ("Something went wrong", "Title Case", "Ripping Track",
                 "Stored Successfully", "Awaiting Beets")
    for bad in forbidden:
        assert bad not in src, f"status-line source contains {bad!r}"


# ============== (b) button labels are sentence case =====================


def test_button_labels_are_sentence_case_in_rendered_html(
    client: TestClient,
) -> None:
    html = client.get("/rip").text
    # Extract <button>…</button> text bodies.
    button_bodies = re.findall(
        r"<button[^>]*>([^<]+)</button>", html, flags=re.IGNORECASE,
    )
    offenders = []
    for body in button_bodies:
        text = body.strip()
        if not text:
            continue
        # Allow lone uppercase-acronym tokens (mbid → upper allowed) but
        # ban multi-word Title Case like "Run Beets Search".
        words = [w for w in text.split() if w]
        if len(words) < 2:
            continue
        title_case_words = sum(
            1 for w in words
            if w[:1].isupper() and w[1:].islower()
        )
        if title_case_words >= 2:
            offenders.append(text)
    assert not offenders, (
        f"button labels in title case (should be sentence case): {offenders}"
    )


def test_button_labels_have_no_all_caps_shouting_in_source():
    """Eyebrows are CSS-uppercased, not source-uppercased. Buttons
    in the kanban templates must not be SHOUTING in source."""
    sources = _iter_template_sources()
    assert sources, "no template sources found — fixture wiring broken"
    offenders: list[tuple[str, str]] = []
    button_re = re.compile(
        r"<button[^>]*>\s*([A-Z][A-Z\s·]{3,})\s*</button>",
    )
    for path in sources:
        text = path.read_text(encoding="utf-8")
        for m in button_re.finditer(text):
            label = m.group(1).strip()
            # Allow short acronyms (e.g. MBID alone) — long all-caps phrases
            # are the SHOUTING pattern the voice pass bans.
            if len(label.split()) >= 2:
                offenders.append((path.name, label))
    assert not offenders, f"SHOUTING button labels: {offenders}"


# ============== (c) error states follow specific-error pattern ==========


def test_review_explainer_uses_specific_error_pattern():
    """review_explainer.py and damaged_disc.py copy must be specific —
    e.g. 'track 4 · sector 12,044 · gave up after 8 retries' — not a
    generic 'something went wrong'."""
    targets = [
        _SERVICE_DIR / "review_explainer.py",
        _SERVICE_DIR / "damaged_disc.py",
    ]
    forbidden_generic = (
        "something went wrong",
        "an error occurred",
        "unexpected error",
        "oops",
    )
    for path in targets:
        if not path.is_file():
            continue
        src = path.read_text(encoding="utf-8").lower()
        for phrase in forbidden_generic:
            assert phrase not in src, (
                f"{path.name} carries generic error copy {phrase!r}; "
                f"use the specific-error pattern instead"
            )


# ============== (d) no emoji or smart quotes in shipped templates =======


def test_no_emoji_in_template_sources():
    offenders: list[tuple[str, str]] = []
    for path in _iter_template_sources():
        text = path.read_text(encoding="utf-8")
        # Strip any glyphs we explicitly allow before scanning for emoji.
        scrubbed = text
        for g in _ALLOWED_GLYPHS:
            scrubbed = scrubbed.replace(g, "")
        for m in _EMOJI_RE.finditer(scrubbed):
            offenders.append((path.name, m.group(0)))
    assert not offenders, f"emoji in shipped templates: {offenders}"


def test_no_smart_quotes_in_template_sources():
    offenders: list[tuple[str, str]] = []
    for path in _iter_template_sources():
        text = path.read_text(encoding="utf-8")
        for q in _SMART_QUOTES:
            if q in text:
                offenders.append((path.name, q))
    assert not offenders, f"smart quotes in shipped templates: {offenders}"


def test_no_emoji_in_rendered_kanban(client: TestClient) -> None:
    html = client.get("/rip").text
    scrubbed = html
    for g in _ALLOWED_GLYPHS:
        scrubbed = scrubbed.replace(g, "")
    found = _EMOJI_RE.findall(scrubbed)
    assert not found, f"emoji rendered in kanban HTML: {found[:5]}"
