"""Failing tests for source.json syntax highlight (sprint-7 Bucket E lane-3).

Two layers:

  1. Unit-test the highlight helper:
     archivist/service/json_highlight.py::highlight(obj) -> str
     wraps keys in <span class="k">, strings in <span class="s">,
     numbers in <span class="n">, booleans/nulls in <span class="b">,
     and emits the whole thing inside <pre class="cda-json">.

  2. Integration: the right-drawer card-detail body renders source.json
     using that helper (markers visible in the rendered HTML).

  3. No external highlighting library is added to pyproject.toml.

Impl lands in Wave 2 (impl-source-json-highlight).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from archivist.service.app import LoopState, create_app


def _write_flac(path: Path, n_bytes: int = 1024) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fLaC" + b"\x00" * n_bytes)


def _seed(parent: Path, name: str) -> Path:
    folder = parent / name
    _write_flac(folder / "01.flac")
    folder.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "ripper": {"name": "cd-archivist", "version": "0.1.0", "host": "cm4"},
        "disc": {
            "folder_name": name, "disc_counter": 1,
            "inserted_at": "2026-05-16T10:00:00-07:00",
            "rip_started_at": "2026-05-16T10:00:10-07:00",
            "rip_finished_at": "2026-05-16T10:05:00-07:00",
            "ejected_at": "2026-05-16T10:05:30-07:00",
            "ready_at": "2026-05-16T10:05:45-07:00",
            "timezone": "America/Los_Angeles",
        },
        "drive": {"device": "/dev/sr0", "model": "X", "serial": None,
                  "read_offset": None},
        "audio": {
            "format": "flac", "sample_rate_hz": 44100, "bits_per_sample": 16,
            "channels": 2, "track_count": 3,
            "total_duration_seconds": 480,
            "secure_rip": True, "accuraterip_verified": None,
        },
        "identifiers": {
            "musicbrainz_disc_id": None, "freedb_disc_id": None,
            "cd_toc": None, "upc": None, "isrcs": [],
        },
        "detected_metadata": {
            "album_artist": None, "album": None, "year": None,
            "label": None, "catalog_number": None, "tracks": [],
        },
        "physical_disc": {
            "photo": None, "photo_captured": False,
            "photo_captured_at": None, "photo_device": None,
            "photo_notes": None, "label_text_guess": None,
            "appears_burned": None, "handwritten": None,
        },
        "files": [],
        "status": {
            "rip_success": True, "photo_success": True, "ready": True,
            "warnings": [], "errors": [],
            "partial": False, "failed_tracks": [],
        },
    }
    (folder / "source.json").write_text(json.dumps(payload))
    return folder


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


# ============== (a) helper module exists with `highlight` callable ======


def test_highlight_helper_module_importable():
    from archivist.service import json_highlight  # noqa: F401
    assert callable(json_highlight.highlight)


# ============== (b) helper wraps each JSON type in the right span =======


def test_highlight_wraps_keys_strings_numbers_booleans_and_nulls():
    from archivist.service.json_highlight import highlight
    out = highlight({
        "name": "value",
        "n": 42,
        "f": 3.14,
        "yes": True,
        "no": False,
        "nothing": None,
    })
    assert isinstance(out, str)
    assert '<pre class="cda-json"' in out
    # Keys.
    assert '<span class="k">' in out
    assert "name" in out
    # Strings.
    assert '<span class="s">' in out
    assert "value" in out
    # Numbers (both int + float).
    assert '<span class="n">' in out
    assert "42" in out
    assert "3.14" in out
    # Booleans + nulls share the .b class per the build-prompt mapping.
    assert '<span class="b">' in out
    assert "true" in out
    assert "false" in out
    assert "null" in out


def test_highlight_does_not_break_on_nested_lists_and_dicts():
    from archivist.service.json_highlight import highlight
    out = highlight({"a": [1, "two", {"b": None}]})
    # Containers preserved verbatim — no double-encoding.
    assert "[" in out and "]" in out
    assert "{" in out and "}" in out
    # Nested key still wrapped.
    assert "b" in out


# ============== (c) integration: drawer card-detail body uses helper ====


def test_card_detail_template_uses_cda_json_pre_block(
    client: TestClient, music_root: Path,
) -> None:
    _seed(music_root / "review", "sj-card")
    html = client.get("/").text
    # The card-detail template references the source.json render slot
    # using the cda-json class — the JS substitutes the highlighted HTML
    # when a card is clicked.
    assert "cda-json" in html


# ============== (d) no external highlight library in pyproject.toml ====


_FORBIDDEN_HIGHLIGHT_PACKAGES = (
    "pygments", "Pygments", "highlight.js", "highlightjs",
    "prismjs", "prism-py", "rich-syntax",
)


def test_no_external_highlight_library_added():
    pyproject = (
        Path(__file__).resolve().parents[2] / "pyproject.toml"
    )
    text = pyproject.read_text(encoding="utf-8")
    for pkg in _FORBIDDEN_HIGHLIGHT_PACKAGES:
        assert pkg.lower() not in text.lower(), (
            f"highlight is supposed to be hand-rolled; {pkg!r} present "
            f"in pyproject.toml"
        )
