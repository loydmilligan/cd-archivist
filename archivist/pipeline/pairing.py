"""Capture/rip pairing records.

Sprint-1 ships the ``single_session`` method only — a record that says
"this disc had exactly one capture session and one rip session, paired
trivially." Future detached-capture workflows will add other methods
(`timestamp_window`, etc.) without changing the call site here.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from archivist.models.manifest import Manifest, PairingRecord


def make_pairing(
    method: Literal["single_session"],
    confidence: Literal["high", "medium", "low"] = "high",
) -> PairingRecord:
    return PairingRecord(
        method=method,
        confidence=confidence,
        created_at=datetime.now(UTC),
    )


def attach_pairing(manifest: Manifest, pairing: PairingRecord) -> Manifest:
    """Return a copy of ``manifest`` with ``pairing`` appended.

    Does not mutate the input manifest — uses ``model_copy`` so callers
    can keep the original around for diff/log purposes.
    """
    return manifest.model_copy(
        update={"pairings": [*manifest.pairings, pairing]}
    )
