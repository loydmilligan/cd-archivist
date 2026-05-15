"""Failing tests for the read-only library browser (sprint-3).

GET /library          — Mash Co. card grid of all discs under discs_root
GET /library/CD_NNNN  — single-disc detail page
GET /library/CD_NNNN/captures/<filename>  — jpg serving
GET /library/CD_NNNN/audio/<filename>     — flac serving

Mash Co. invariants (per /home/loydmilligan/Projects/Mash Co. Design
System/{SKILL,README}.md): dark-first, sentence case, no emoji, eyebrows
≤2 words, card has full 1px border + 3px semantic-color left-border
accent for rip status (--moss success, --amber partial/created,
--ember failed).

Impl lands in Wave 2 (impl-library).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from archivist.models.manifest import Manifest, RipRecord, write_manifest
from archivist.service.app import LoopState, create_app


# Decorative emoji ranges — same regex as test_app.py.
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "]"
)


def _make_manifest(
    disc_id: str,
    *,
    status: str = "ripped",
    rip_status: str | None = "success",
    tracks: list[str] | None = None,
    created_at: datetime | None = None,
) -> Manifest:
    rips: list[RipRecord] = []
    if rip_status is not None:
        rips = [RipRecord(
            status=rip_status,  # type: ignore[arg-type]
            tracks=tracks or ["audio/track01.flac"],
            errors=[],
        )]
    return Manifest(
        schema_version="0.2",
        disc_id=disc_id,
        media_type="audio_cd",
        created_at=created_at or datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc),
        status=status,
        captures=[],
        rips=rips,
        pairings=[],
        metadata={},
        errors=[],
    )


@pytest.fixture
def discs_root(tmp_path: Path) -> Path:
    """A populated discs_root with three CD_NNNN folders of varying status."""
    root = tmp_path / "discs"
    # CD_0001 — fully ripped, success
    d1 = root / "CD_0001"
    (d1 / "captures").mkdir(parents=True)
    (d1 / "audio").mkdir(parents=True)
    (d1 / "logs").mkdir(parents=True)
    (d1 / "captures" / "disc_front_ambient_001.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    (d1 / "captures" / "disc_front_ambient_002.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    (d1 / "captures" / "disc_front_ambient_003.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    (d1 / "captures" / "disc_front_lit_001.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    (d1 / "captures" / "disc_front_lit_002.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    (d1 / "captures" / "disc_front_lit_003.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    (d1 / "audio" / "track01.flac").write_bytes(b"fLaC" + b"\x00" * 1024)
    (d1 / "audio" / "track02.flac").write_bytes(b"fLaC" + b"\x00" * 2048)
    (d1 / "logs" / "rip.log").write_text("ripping...\nok\n")
    write_manifest(
        d1 / "manifest.json",
        _make_manifest("CD_0001", status="ripped", rip_status="success",
                       tracks=["audio/track01.flac", "audio/track02.flac"]),
    )

    # CD_0002 — rip failed
    d2 = root / "CD_0002"
    (d2 / "captures").mkdir(parents=True)
    (d2 / "audio").mkdir(parents=True)
    write_manifest(
        d2 / "manifest.json",
        _make_manifest("CD_0002", status="rip_failed", rip_status="fail",
                       tracks=[]),
    )

    # CD_0003 — created, never ripped
    d3 = root / "CD_0003"
    (d3 / "captures").mkdir(parents=True)
    (d3 / "audio").mkdir(parents=True)
    write_manifest(
        d3 / "manifest.json",
        _make_manifest("CD_0003", status="created", rip_status=None),
    )

    return root


@pytest.fixture
def client(discs_root: Path, tmp_path: Path) -> TestClient:
    loop_state = LoopState()
    log_path = tmp_path / "archivist.log"
    log_path.write_text("startup line\n")
    return TestClient(create_app(loop_state, log_path, discs_root=discs_root))


# -------- /library — list page ---------------------------------------


def test_library_list_returns_html(client: TestClient) -> None:
    resp = client.get("/library")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")


def test_library_list_contains_all_disc_ids(client: TestClient) -> None:
    body = client.get("/library").text
    assert "CD_0001" in body
    assert "CD_0002" in body
    assert "CD_0003" in body


def test_library_list_thumbnail_points_to_capture(client: TestClient) -> None:
    """First lit capture is the thumbnail for the ripped disc."""
    body = client.get("/library").text
    # Either lit_001 (preferred) or ambient_001 (fallback) — both acceptable.
    assert (
        "/library/CD_0001/captures/disc_front_lit_001.jpg" in body
        or "/library/CD_0001/captures/disc_front_ambient_001.jpg" in body
    )


def test_library_list_card_accent_color_by_status(client: TestClient) -> None:
    """Card accent class reflects rip status per Mash Co. semantic colors."""
    body = client.get("/library").text
    # CD_0001 ripped/success → moss; CD_0002 rip_failed → ember;
    # CD_0003 created → amber.
    assert "card--moss" in body
    assert "card--ember" in body
    assert "card--amber" in body


def test_library_list_shows_track_count(client: TestClient) -> None:
    """Per-card metadata shows track count from manifest.rips[0].tracks."""
    body = client.get("/library").text
    # CD_0001 has 2 tracks — the number must appear somewhere near CD_0001.
    # Heuristic: scan a window of characters after the CD_0001 reference.
    idx = body.find("CD_0001")
    assert idx >= 0
    window = body[idx : idx + 2000]
    assert "2" in window  # track count


def test_library_list_mash_invariants(client: TestClient) -> None:
    body = client.get("/library").text
    assert 'data-theme="dark"' in body
    assert _EMOJI_RE.findall(body) == []
    # 3+ word ALL CAPS check.
    stripped = re.sub(r"<script\b[^>]*>.*?</script>", " ", body, flags=re.S | re.I)
    stripped = re.sub(r"<style\b[^>]*>.*?</style>", " ", stripped, flags=re.S | re.I)
    visible = re.sub(r"<[^>]+>", " ", stripped)
    offenders = re.findall(r"\b[A-Z]{2,}(?:\s+[A-Z]{2,}){2,}\b", visible)
    assert offenders == [], f"3+-word caps in /library: {offenders!r}"


# Detail-page and asset-serving cases land in the next two commits
# (test-library-detail and test-library-asset-serving).
