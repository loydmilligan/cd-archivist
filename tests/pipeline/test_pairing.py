"""Failing tests for archivist.pipeline.pairing.

Implementation lands in Wave 2 (impl-pairing). Imports from
archivist.models.manifest also fail until impl-manifest lands.
"""
from __future__ import annotations

from datetime import datetime

from archivist.models.manifest import Manifest, PairingRecord
from archivist.pipeline.pairing import attach_pairing, make_pairing


def _empty_manifest() -> Manifest:
    return Manifest(
        schema_version="0.2",
        disc_id="CD_0001",
        media_type="audio_cd",
        created_at=datetime(2026, 5, 14, 12, 0, 0),
        status="created",
        captures=[],
        rips=[],
        pairings=[],
        metadata={},
        errors=[],
    )


def test_make_pairing_single_session_defaults() -> None:
    pairing = make_pairing("single_session")
    assert isinstance(pairing, PairingRecord)
    assert pairing.method == "single_session"
    assert pairing.confidence == "high"
    # created_at is an ISO datetime; just verify it's a datetime instance
    assert isinstance(pairing.created_at, datetime)


def test_make_pairing_respects_confidence() -> None:
    pairing = make_pairing("single_session", confidence="low")
    assert pairing.confidence == "low"


def test_attach_pairing_appends_and_returns_manifest() -> None:
    manifest = _empty_manifest()
    pairing = make_pairing("single_session")

    updated = attach_pairing(manifest, pairing)
    assert isinstance(updated, Manifest)
    assert len(updated.pairings) == 1
    assert updated.pairings[0] == pairing

    # Input not mutated — attach returns a copy (per impl-pairing contract:
    # `manifest.model_copy(update={"pairings": [*manifest.pairings, pairing]})`).
    assert manifest.pairings == []
