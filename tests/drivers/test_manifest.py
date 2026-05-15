"""Failing tests for archivist.models.manifest.

Per sprint-1 Wave 1 (test-manifest). Impl lands in Wave 2 (impl-manifest).

Schema per docs/design/high-level-design.md §"Manifest sketch":
    schema_version: Literal["0.2"]
    disc_id: str
    media_type: Literal["audio_cd"]
    created_at: datetime
    status: str
    captures: list[CaptureRecord]
    rips: list[RipRecord]
    pairings: list[PairingRecord]
    metadata: dict
    errors: list[str]
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from archivist.models.manifest import Manifest, read_manifest, write_manifest


def _sample_manifest() -> Manifest:
    return Manifest(
        schema_version="0.2",
        disc_id="CD_0001",
        media_type="audio_cd",
        created_at=datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc),
        status="created",
        captures=[],
        rips=[],
        pairings=[],
        metadata={},
        errors=[],
    )


# ---------------------------- round-trip -----------------------------

def test_round_trip(tmp_path: Path) -> None:
    """write_manifest then read_manifest returns an equal object."""
    path = tmp_path / "manifest.json"
    original = _sample_manifest()
    write_manifest(path, original)
    loaded = read_manifest(path)
    assert loaded == original


# ---------------------------- idempotent -----------------------------

def test_idempotent_write_byte_identical(tmp_path: Path) -> None:
    """Writing the same manifest twice produces byte-identical files."""
    path_a = tmp_path / "a.json"
    path_b = tmp_path / "b.json"
    m = _sample_manifest()

    write_manifest(path_a, m)
    write_manifest(path_b, m)

    assert path_a.read_bytes() == path_b.read_bytes()


# ---------------------------- atomic write ---------------------------

def test_atomic_write_cleans_up_tmp_sibling(tmp_path: Path) -> None:
    """write_manifest uses tmp-file + os.replace; no .tmp sibling remains."""
    path = tmp_path / "manifest.json"
    write_manifest(path, _sample_manifest())

    assert path.exists()
    # No leftover staging file.
    leftovers = [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == [], f"expected no .tmp sibling, found {leftovers}"


# ---------------------- schema_version mismatch ----------------------

def test_schema_version_mismatch_raises(tmp_path: Path) -> None:
    """read_manifest raises ValueError when schema_version != '0.2'."""
    path = tmp_path / "manifest.json"
    payload = {
        "schema_version": "0.1",
        "disc_id": "CD_0001",
        "media_type": "audio_cd",
        "created_at": "2026-05-14T12:00:00+00:00",
        "status": "created",
        "captures": [],
        "rips": [],
        "pairings": [],
        "metadata": {},
        "errors": [],
    }
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError):
        read_manifest(path)


# ---------------------- extra='forbid' invariant ---------------------

def test_extra_fields_rejected(tmp_path: Path) -> None:
    """Pydantic extra='forbid' rejects unknown top-level fields on parse."""
    path = tmp_path / "manifest.json"
    payload = {
        "schema_version": "0.2",
        "disc_id": "CD_0001",
        "media_type": "audio_cd",
        "created_at": "2026-05-14T12:00:00+00:00",
        "status": "created",
        "captures": [],
        "rips": [],
        "pairings": [],
        "metadata": {},
        "errors": [],
        "rogue_field": "should be rejected",
    }
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(Exception) as excinfo:
        read_manifest(path)
    # Pydantic raises ValidationError (subclass of ValueError).
    assert "rogue_field" in str(excinfo.value) or "extra" in str(excinfo.value).lower()
