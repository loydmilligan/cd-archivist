"""Failing tests for archivist.drivers.ripper — Ripper Protocol + CDAudioRipper.

Per sprint-1 Wave 1 (test-ripper). Impl lands in Wave 2 (impl-ripper).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from archivist.drivers.ripper import CDAudioRipper, RipResult, Ripper
from tests.conftest import FakeCompletedProcess

CDS_AUDIO = 100  # include/uapi/linux/cdrom.h
CDS_DATA_1 = 101
DEVICE = Path("/dev/sr0")


# -------------------------- Protocol shape ---------------------------

def test_cdaudio_ripper_satisfies_protocol() -> None:
    """CDAudioRipper must satisfy the Ripper Protocol — media_types, detect, rip."""
    ripper: Ripper = CDAudioRipper()
    assert "audio_cd" in ripper.media_types
    # Signatures exist (callable, take the documented args).
    assert callable(ripper.detect)
    assert callable(ripper.rip)


def test_rip_result_dataclass_fields() -> None:
    """RipResult must expose status, tracks, errors per the design."""
    r = RipResult(status="success", tracks=[Path("a.flac")], errors=[])
    assert r.status == "success"
    assert r.tracks == [Path("a.flac")]
    assert r.errors == []


# -------------------------- detect() ---------------------------------

def test_detect_audio_cd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """When ioctl reports CDS_AUDIO, detect returns 'audio_cd'."""
    import archivist.drivers.ripper as ripper_mod

    monkeypatch.setattr(ripper_mod.fcntl, "ioctl", lambda *a, **k: CDS_AUDIO)
    device = tmp_path / "sr0"
    device.write_bytes(b"")
    assert CDAudioRipper().detect(device) == "audio_cd"


def test_detect_non_audio_returns_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import archivist.drivers.ripper as ripper_mod

    monkeypatch.setattr(ripper_mod.fcntl, "ioctl", lambda *a, **k: CDS_DATA_1)
    device = tmp_path / "sr0"
    device.write_bytes(b"")
    assert CDAudioRipper().detect(device) is None


# -------------------------- rip() happy path -------------------------

def test_rip_success(fake_subprocess, tmp_path: Path) -> None:
    """All tracks rip + encode → status='success', tracks lists FLACs, errors=[]."""
    out_dir = tmp_path / "rip"
    out_dir.mkdir()

    # Simulate cdparanoia: produce 3 WAV stubs, exit 0. Then 3 successful flac
    # calls each produce the corresponding .flac and exit 0.
    def fake_run(args, **kwargs):
        fake_subprocess.calls.append(_record(args, kwargs))
        argv = list(args) if isinstance(args, (list, tuple)) else [args]
        joined = " ".join(str(x) for x in argv)
        if "cdparanoia" in joined:
            for i in (1, 2, 3):
                (out_dir / f"track{i:02d}.wav").write_bytes(b"RIFF")
            return FakeCompletedProcess(args, returncode=0)
        if "flac" in joined:
            # Last arg points at the .wav; produce sibling .flac.
            wav = Path(argv[-1])
            wav.with_suffix(".flac").write_bytes(b"fLaC")
            return FakeCompletedProcess(args, returncode=0)
        return FakeCompletedProcess(args, returncode=0)

    fake_subprocess.run = fake_run  # type: ignore[assignment]
    import subprocess as _sp
    _sp.run = fake_run  # type: ignore[assignment]

    result = CDAudioRipper().rip(DEVICE, out_dir)
    assert result.status == "success"
    assert len(result.tracks) == 3
    assert all(p.suffix == ".flac" for p in result.tracks)
    assert all(p.exists() for p in result.tracks)
    assert result.errors == []


# -------------------------- rip() partial ----------------------------

def test_rip_partial(fake_subprocess, tmp_path: Path) -> None:
    """cdparanoia non-zero exit with SOME WAVs produced → status='partial'."""
    out_dir = tmp_path / "rip"
    out_dir.mkdir()

    def fake_run(args, **kwargs):
        fake_subprocess.calls.append(_record(args, kwargs))
        argv = list(args) if isinstance(args, (list, tuple)) else [args]
        joined = " ".join(str(x) for x in argv)
        if "cdparanoia" in joined:
            # Only tracks 1 + 2 made it; track 3 failed mid-rip.
            (out_dir / "track01.wav").write_bytes(b"RIFF")
            (out_dir / "track02.wav").write_bytes(b"RIFF")
            return FakeCompletedProcess(
                args, returncode=1, stderr="read error on track 3"
            )
        if "flac" in joined:
            wav = Path(argv[-1])
            wav.with_suffix(".flac").write_bytes(b"fLaC")
            return FakeCompletedProcess(args, returncode=0)
        return FakeCompletedProcess(args, returncode=0)

    import subprocess as _sp
    _sp.run = fake_run  # type: ignore[assignment]

    result = CDAudioRipper().rip(DEVICE, out_dir)
    assert result.status == "partial"
    assert len(result.tracks) == 2
    assert result.errors, "partial rip must surface at least one error string"


# -------------------------- rip() hard fail --------------------------

def test_rip_hard_fail(fake_subprocess, tmp_path: Path) -> None:
    """cdparanoia hard-fails with no WAVs → status='fail', tracks=[]."""
    out_dir = tmp_path / "rip"
    out_dir.mkdir()
    fake_subprocess.set_result(returncode=1, stderr="cdparanoia: drive not ready")

    result = CDAudioRipper().rip(DEVICE, out_dir)
    assert result.status == "fail"
    assert result.tracks == []
    assert result.errors


# -------------------------- helpers ----------------------------------

class _Rec:
    __slots__ = ("args", "kwargs")
    def __init__(self, args, kwargs) -> None:
        self.args = args
        self.kwargs = kwargs


def _record(args, kwargs) -> _Rec:
    return _Rec(args, kwargs)
