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
    """Sprint-4: `?status=all` is required to see failed/created discs.
    Default (success) hides CD_0002 (rip_failed) and CD_0003 (created).
    """
    body = client.get("/library?status=all").text
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


# -------- /library/CD_NNNN — detail page (test-library-detail) -------


def test_library_detail_existing_disc(client: TestClient) -> None:
    resp = client.get("/library/CD_0001")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")


def test_library_detail_unknown_disc_404(client: TestClient) -> None:
    resp = client.get("/library/CD_9999")
    assert resp.status_code == 404


def test_library_detail_renders_manifest_dump(client: TestClient) -> None:
    body = client.get("/library/CD_0001").text
    assert "<pre" in body
    assert "schema_version" in body
    assert "audio_cd" in body


def test_library_detail_renders_capture_thumbnails(client: TestClient) -> None:
    body = client.get("/library/CD_0001").text
    matches = re.findall(
        r"/library/CD_0001/captures/disc_front_(?:ambient|lit)_\d{3}\.jpg", body
    )
    assert len(matches) >= 6


def test_library_detail_renders_audio_players(client: TestClient) -> None:
    body = client.get("/library/CD_0001").text
    assert body.count("<audio") >= 2
    assert "/library/CD_0001/audio/track01.flac" in body
    assert "/library/CD_0001/audio/track02.flac" in body


def test_library_detail_shows_file_sizes(client: TestClient) -> None:
    body = client.get("/library/CD_0001").text
    # Some byte-size unit must appear with the track listing.
    assert any(unit in body for unit in ("KB", "MB", "kB", "MiB", "B "))


def test_library_detail_log_tail_when_logs_present(client: TestClient) -> None:
    body = client.get("/library/CD_0001").text
    # Fixture wrote logs/rip.log; the page tails it.
    assert "ripping" in body or "ok" in body


# -------- asset serving (test-library-asset-serving) -----------------


def test_capture_endpoint_serves_jpg(client: TestClient) -> None:
    resp = client.get("/library/CD_0001/captures/disc_front_lit_001.jpg")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"
    assert resp.content.startswith(b"\xff\xd8")


def test_audio_endpoint_serves_flac(client: TestClient) -> None:
    resp = client.get("/library/CD_0001/audio/track01.flac")
    assert resp.status_code == 200
    # Accept any flac variant (audio/flac, audio/x-flac); impl-library
    # sets the media_type explicitly per task body.
    ct = resp.headers["content-type"]
    assert "flac" in ct.lower(), f"unexpected content-type: {ct!r}"
    assert resp.content.startswith(b"fLaC")


def test_traversal_attempts_return_404(
    client: TestClient, discs_root: Path, tmp_path: Path
) -> None:
    """Path-traversal must never serve files outside the disc_dir."""
    secret = tmp_path / "secret.txt"
    secret.write_text("PASSWORD=hunter2")
    paths_to_try = [
        "/library/CD_0001/captures/../../../secret.txt",
        "/library/CD_0001/captures/..%2F..%2F..%2Fsecret.txt",
        "/library/CD_0001/audio/../../secret.txt",
        "/library/CD_0001/captures//etc/passwd",
    ]
    for p in paths_to_try:
        resp = client.get(p)
        assert resp.status_code in (404, 400), f"{p!r} returned {resp.status_code}"
        assert b"PASSWORD" not in resp.content


def test_missing_asset_returns_404(client: TestClient) -> None:
    resp = client.get("/library/CD_0001/captures/does-not-exist.jpg")
    assert resp.status_code == 404
    resp = client.get("/library/CD_0001/audio/missing.flac")
    assert resp.status_code == 404


def test_unknown_disc_in_asset_path_returns_404(client: TestClient) -> None:
    resp = client.get("/library/CD_9999/captures/disc_front_lit_001.jpg")
    assert resp.status_code == 404
    resp = client.get("/library/INVALID/captures/x.jpg")
    assert resp.status_code == 404
