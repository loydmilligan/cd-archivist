"""Failing tests for the `?status=` filter on GET /library (sprint-4).

Per D-library-legacy-adapter + Wave 1 Bucket B:

  - Query param `status` ∈ {success, failed, all}, default `success`
  - Chip group rendered at top of grid (3 pill chips)
  - Active chip uses `--accent` background; inactive `--surface-2`
  - Chips are same-page anchor links — no JS needed for the filter
  - Filter reads `source.status.rip_success` for new-shape folders
    and falls back to legacy manifest `status=='ripped' and
    rips[0].status=='success'` for legacy CD_NNNN folders

Impl lands in Wave 2 (impl-library-filter).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from archivist.models.manifest import Manifest, RipRecord, write_manifest
from archivist.service.app import LoopState, create_app


def _legacy(disc_id: str, *, success: bool) -> Manifest:
    return Manifest(
        schema_version="0.2",
        disc_id=disc_id,
        media_type="audio_cd",
        created_at=datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc),
        status="ripped" if success else "rip_failed",
        captures=[],
        rips=[RipRecord(
            status="success" if success else "fail",
            tracks=["audio/track01.flac"] if success else [],
            errors=[],
        )],
        pairings=[],
        metadata={},
        errors=[],
    )


def _source(folder_name: str, *, success: bool) -> dict:
    return {
        "schema_version": 1,
        "ripper": {"name": "x", "version": "0", "host": "h"},
        "disc": {
            "folder_name": folder_name,
            "disc_counter": 1,
            "inserted_at": "2026-05-15T18:28:03-07:00",
            "rip_started_at": "2026-05-15T18:28:11-07:00",
            "rip_finished_at": "2026-05-15T18:34:44-07:00",
            "ejected_at": "2026-05-15T18:35:02-07:00",
            "ready_at": "2026-05-15T18:35:18-07:00",
            "timezone": "America/Los_Angeles",
        },
        "drive": {"device": "/dev/sr0", "model": "X", "serial": None, "read_offset": None},
        "audio": {
            "format": "flac", "sample_rate_hz": 44100, "bits_per_sample": 16,
            "channels": 2, "track_count": 1, "total_duration_seconds": 60,
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
            "rip_success": success, "photo_success": success,
            "ready": success, "warnings": [],
            "errors": [] if success else ["bad sectors"],
        },
    }


@pytest.fixture
def mixed_inbox(tmp_path: Path) -> Path:
    root = tmp_path / "inbox"
    root.mkdir()

    # New-shape success
    a = root / "2026-05-15_1432_disc-000001"
    a.mkdir()
    (a / "source.json").write_text(json.dumps(_source(a.name, success=True)))

    # New-shape failure
    b = root / "2026-05-15_1500_disc-000002"
    b.mkdir()
    (b / "source.json").write_text(json.dumps(_source(b.name, success=False)))

    # Legacy success
    c = root / "CD_0001"
    c.mkdir()
    write_manifest(c / "manifest.json", _legacy("CD_0001", success=True))

    # Legacy failure
    d = root / "CD_0002"
    d.mkdir()
    write_manifest(d / "manifest.json", _legacy("CD_0002", success=False))

    return root


@pytest.fixture
def client(mixed_inbox: Path, tmp_path: Path) -> TestClient:
    log = tmp_path / "archivist.log"
    log.write_text("")
    return TestClient(create_app(LoopState(), log, discs_root=mixed_inbox))


# -------- (a) default = success -------------------------------------


def test_default_shows_only_success(client: TestClient) -> None:
    body = client.get("/library").text
    assert "2026-05-15_1432_disc-000001" in body
    assert "CD_0001" in body
    # Failed discs hidden by default.
    assert "2026-05-15_1500_disc-000002" not in body
    assert "CD_0002" not in body


# -------- (b) ?status=failed ----------------------------------------


def test_status_failed_shows_only_failures(client: TestClient) -> None:
    body = client.get("/library?status=failed").text
    assert "2026-05-15_1500_disc-000002" in body
    assert "CD_0002" in body
    assert "2026-05-15_1432_disc-000001" not in body
    assert "CD_0001" not in body


# -------- (c) ?status=all -------------------------------------------


def test_status_all_shows_everything(client: TestClient) -> None:
    body = client.get("/library?status=all").text
    for name in (
        "2026-05-15_1432_disc-000001",
        "2026-05-15_1500_disc-000002",
        "CD_0001",
        "CD_0002",
    ):
        assert name in body


# -------- (d) chip group rendered with 3 pills ----------------------


def test_chip_group_rendered(client: TestClient) -> None:
    body = client.get("/library").text
    # All three chip labels appear.
    assert "success" in body
    assert "failed" in body
    assert "all" in body
    # Active chip on the default `success` view uses --accent.
    assert "--accent" in body


# -------- (e) chips are anchor links --------------------------------


def test_chips_are_anchor_links(client: TestClient) -> None:
    body = client.get("/library").text
    assert 'href="/library?status=success"' in body
    assert 'href="/library?status=failed"' in body
    assert 'href="/library?status=all"' in body


# -------- (f) filter reads source.status for new; manifest for legacy


def test_filter_uses_adapter_for_both_shapes(client: TestClient) -> None:
    """Mixed inbox: success filter pulls from BOTH manifest.json and
    source.json successes; failed filter pulls from BOTH failures."""
    success_body = client.get("/library?status=success").text
    failed_body = client.get("/library?status=failed").text

    # Each filter sees one new-shape + one legacy.
    assert "2026-05-15_1432_disc-000001" in success_body
    assert "CD_0001" in success_body
    assert "2026-05-15_1500_disc-000002" in failed_body
    assert "CD_0002" in failed_body
