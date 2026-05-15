"""Failing tests for archivist.pipeline.rip.rip_disc.

Wraps the `Ripper` Protocol (archivist.drivers.ripper.Ripper): calls
`ripper.rip(device, disc_dir / "audio")`, translates the `RipResult`
into a `RipRecord` with tracks stored as POSIX-relative paths under
`audio/`.

Impl lands in Wave 2 (impl-rip).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from archivist.drivers.ripper import RipResult
from archivist.models.manifest import RipRecord
from archivist.pipeline.rip import rip_disc

DEVICE = Path("/dev/sr0")


class _FakeRipper:
    media_types = {"audio_cd"}

    def __init__(self, result: RipResult) -> None:
        self._result = result
        self.rip_calls: list[tuple[Path, Path]] = []

    def detect(self, device: Path) -> str | None:
        return "audio_cd"

    def rip(self, device: Path, out_dir: Path) -> RipResult:
        self.rip_calls.append((device, out_dir))
        return self._result


@pytest.fixture
def disc_dir(tmp_disc_root) -> Path:
    root = tmp_disc_root()
    d = root / "CD_0001"
    (d / "audio").mkdir(parents=True)
    return d


def test_rip_disc_success(disc_dir: Path) -> None:
    tracks = [disc_dir / "audio" / f"track{i:02d}.flac" for i in (1, 2, 3)]
    for t in tracks:
        t.write_bytes(b"fLaC")
    ripper = _FakeRipper(RipResult(status="success", tracks=tracks, errors=[]))

    record = rip_disc(disc_dir, DEVICE, ripper=ripper)

    assert isinstance(record, RipRecord)
    assert record.status == "success"
    assert record.tracks == [
        "audio/track01.flac",
        "audio/track02.flac",
        "audio/track03.flac",
    ]
    assert record.errors == []
    assert ripper.rip_calls == [(DEVICE, disc_dir / "audio")]


def test_rip_disc_partial(disc_dir: Path) -> None:
    tracks = [disc_dir / "audio" / "track01.flac"]
    tracks[0].write_bytes(b"fLaC")
    ripper = _FakeRipper(
        RipResult(status="partial", tracks=tracks, errors=["read error on track 2"])
    )

    record = rip_disc(disc_dir, DEVICE, ripper=ripper)
    assert record.status == "partial"
    assert record.tracks == ["audio/track01.flac"]
    assert record.errors == ["read error on track 2"]


def test_rip_disc_fail(disc_dir: Path) -> None:
    ripper = _FakeRipper(
        RipResult(status="fail", tracks=[], errors=["cdparanoia exit 1"])
    )

    record = rip_disc(disc_dir, DEVICE, ripper=ripper)
    assert record.status == "fail"
    assert record.tracks == []
    assert record.errors == ["cdparanoia exit 1"]


def test_rip_disc_tracks_are_posix_relative(tmp_path: Path) -> None:
    """Tracks must be POSIX-relative under `audio/`, never absolute."""
    # Use a deeply nested disc_dir to prove relative-path logic isn't
    # naively string-stripping.
    nested = tmp_path / "weird" / "place" / "discs" / "CD_0042"
    (nested / "audio").mkdir(parents=True)
    tracks = [nested / "audio" / "track01.flac"]
    tracks[0].write_bytes(b"fLaC")
    ripper = _FakeRipper(RipResult(status="success", tracks=tracks, errors=[]))

    record = rip_disc(nested, DEVICE, ripper=ripper)
    assert record.tracks == ["audio/track01.flac"]
    assert not record.tracks[0].startswith("/")
