"""Failing tests for archivist.pipeline.folder.prepare_disc_folder.

Implementation lands in Wave 2 (impl-folder). Until then these tests
fail at import — they also import from archivist.models.manifest which
the drivers agent lands as impl-manifest.
"""
from __future__ import annotations

import json
from pathlib import Path

from archivist.models.manifest import read_manifest
from archivist.pipeline.folder import prepare_disc_folder


def test_returns_disc_dir(tmp_disc_root) -> None:
    root: Path = tmp_disc_root()
    out = prepare_disc_folder("CD_0001", root)
    assert out == root / "CD_0001"
    assert out.is_dir()


def test_creates_canonical_subdirs(tmp_disc_root) -> None:
    root: Path = tmp_disc_root()
    out = prepare_disc_folder("CD_0042", root)
    for sub in ("captures", "audio", "logs", "review"):
        assert (out / sub).is_dir(), f"missing subdir: {sub}"


def test_writes_initial_manifest(tmp_disc_root) -> None:
    root: Path = tmp_disc_root()
    out = prepare_disc_folder("CD_0007", root)
    manifest_path = out / "manifest.json"
    assert manifest_path.is_file()

    manifest = read_manifest(manifest_path)
    assert manifest.schema_version == "0.2"
    assert manifest.disc_id == "CD_0007"
    assert manifest.media_type == "audio_cd"
    assert manifest.status == "created"
    assert manifest.captures == []
    assert manifest.rips == []
    assert manifest.pairings == []
    assert manifest.errors == []
    assert manifest.created_at is not None


def test_idempotent_does_not_overwrite(tmp_disc_root) -> None:
    """Calling twice must not raise and must not clobber a populated manifest.

    Existence of manifest.json is the idempotency guard.
    """
    root: Path = tmp_disc_root()
    out = prepare_disc_folder("CD_0001", root)
    manifest_path = out / "manifest.json"

    # Mutate the manifest in-place to simulate downstream pipeline progress.
    raw = json.loads(manifest_path.read_text())
    raw["status"] = "ripped"
    raw["errors"] = ["something happened"]
    manifest_path.write_text(json.dumps(raw, indent=2) + "\n")

    out2 = prepare_disc_folder("CD_0001", root)
    assert out2 == out

    after = json.loads(manifest_path.read_text())
    assert after["status"] == "ripped"
    assert after["errors"] == ["something happened"]
