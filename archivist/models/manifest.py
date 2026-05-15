"""Manifest schema v0.2 + atomic read/write.

Per docs/design/high-level-design.md §"Manifest sketch" and sprint-1
task `impl-manifest`. Pydantic v2 with `extra="forbid"`; writes go
through a `.tmp` sibling + `os.replace` for atomicity.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

SCHEMA_VERSION: Literal["0.2"] = "0.2"


class CaptureRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capture_id: str
    lighting: str
    image_paths: list[str]


class RipRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["success", "partial", "fail"]
    tracks: list[str]
    errors: list[str] = []


class PairingRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: Literal["single_session"]
    confidence: Literal["high", "medium", "low"] = "high"
    created_at: datetime


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["0.2"]
    disc_id: str
    media_type: Literal["audio_cd"]
    created_at: datetime
    status: str
    captures: list[CaptureRecord] = []
    rips: list[RipRecord] = []
    pairings: list[PairingRecord] = []
    metadata: dict[str, Any] = {}
    errors: list[str] = []


def read_manifest(path: Path) -> Manifest:
    """Load a Manifest from disk.

    Raises ValueError when the on-disk `schema_version` is not `"0.2"`,
    or when Pydantic rejects the payload (e.g. unknown fields).
    """
    raw = path.read_text(encoding="utf-8")
    payload = json.loads(raw)
    version = payload.get("schema_version") if isinstance(payload, dict) else None
    if version != SCHEMA_VERSION:
        raise ValueError(
            f"manifest schema_version mismatch: expected {SCHEMA_VERSION!r}, "
            f"got {version!r} at {path}"
        )
    return Manifest.model_validate(payload)


def write_manifest(path: Path, manifest: Manifest) -> None:
    """Atomically write a Manifest to disk.

    Serializes via `model_dump_json(indent=2)` plus a trailing newline,
    writes to `<path>.tmp`, then `os.replace`s into place.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    payload = manifest.model_dump_json(indent=2) + "\n"
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)
