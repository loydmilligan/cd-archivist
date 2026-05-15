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

def _install_cdparanoia_popen(monkeypatch, out_dir, *, wavs_to_make, returncode, stderr_lines=()):
    """Monkeypatch subprocess.Popen so cdparanoia 'runs' synthetically.

    Sprint-3 (impl-rip-stderr-stream) replaced subprocess.run with Popen
    for the cdparanoia call. These helper hooks reproduce the old
    sprint-1 side-effects (WAV files appearing) under the new shape.
    """
    import archivist.drivers.ripper as ripper_mod

    class _Fake:
        def __init__(self, argv, **_kw):
            self.args = argv
            self.returncode = returncode
            # Create the WAVs synchronously — real cdparanoia produces them
            # incrementally; for the unit tests the file presence at .wait()
            # is what matters.
            for n in wavs_to_make:
                (out_dir / f"track{n:02d}.wav").write_bytes(b"RIFF")
            import io
            self.stdout = io.StringIO("")
            self.stderr = iter([s + "\n" for s in stderr_lines])

        def wait(self):
            return self.returncode

    monkeypatch.setattr(ripper_mod.subprocess, "Popen", _Fake)


def _install_flac_run(monkeypatch):
    """Monkeypatch subprocess.run so flac calls succeed and create .flac sidecars."""
    import archivist.drivers.ripper as ripper_mod

    def fake_run(args, **_kwargs):
        argv = list(args) if isinstance(args, (list, tuple)) else [args]
        joined = " ".join(str(x) for x in argv)
        if "flac" in joined:
            wav = Path(argv[-1])
            wav.with_suffix(".flac").write_bytes(b"fLaC")
        return FakeCompletedProcess(args, returncode=0)

    monkeypatch.setattr(ripper_mod.subprocess, "run", fake_run)


def test_rip_success(monkeypatch, tmp_path: Path) -> None:
    """All tracks rip + encode → status='success', tracks lists FLACs, errors=[]."""
    out_dir = tmp_path / "rip"
    out_dir.mkdir()
    _install_cdparanoia_popen(monkeypatch, out_dir, wavs_to_make=(1, 2, 3), returncode=0)
    _install_flac_run(monkeypatch)

    result = CDAudioRipper().rip(DEVICE, out_dir)
    assert result.status == "success"
    assert len(result.tracks) == 3
    assert all(p.suffix == ".flac" for p in result.tracks)
    assert all(p.exists() for p in result.tracks)
    assert result.errors == []


# -------------------------- rip() partial ----------------------------

def test_rip_partial(monkeypatch, tmp_path: Path) -> None:
    """cdparanoia non-zero exit with SOME WAVs produced → status='partial'."""
    out_dir = tmp_path / "rip"
    out_dir.mkdir()
    _install_cdparanoia_popen(
        monkeypatch, out_dir,
        wavs_to_make=(1, 2),
        returncode=1,
        stderr_lines=["read error on track 3"],
    )
    _install_flac_run(monkeypatch)

    result = CDAudioRipper().rip(DEVICE, out_dir)
    assert result.status == "partial"
    assert len(result.tracks) == 2
    assert result.errors, "partial rip must surface at least one error string"


# -------------------------- rip() hard fail --------------------------

def test_rip_hard_fail(monkeypatch, tmp_path: Path) -> None:
    """cdparanoia hard-fails with no WAVs → status='fail', tracks=[]."""
    out_dir = tmp_path / "rip"
    out_dir.mkdir()
    _install_cdparanoia_popen(
        monkeypatch, out_dir,
        wavs_to_make=(),
        returncode=1,
        stderr_lines=["cdparanoia: drive not ready"],
    )

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


# -------------------- live-stream stderr (sprint-3) ------------------
# Refactor target: CDAudioRipper.rip uses subprocess.Popen with
# line-iterated stderr so callbacks see lines before the process exits.
# Tests use a fake Popen that yields stderr lines on demand (with a
# blocking sentinel between yields) to prove the callback fires in
# real time, not after the process exits.

import logging  # noqa: E402

import pytest as _pytest  # noqa: E402


class _FakePopen:
    """Minimal Popen stand-in.

    `stderr_lines` is iterated by the impl; an optional `gate` Event is
    waited on after a configurable number of lines have been emitted,
    letting tests assert mid-stream callback firing.
    """

    def __init__(
        self,
        argv: object,
        stderr_lines: list[str],
        returncode: int = 0,
        gate_after: int | None = None,
    ) -> None:
        import io
        import threading as _threading

        self.args = argv
        self.returncode = returncode
        self._lines = stderr_lines
        self._gate_after = gate_after
        self._gate = _threading.Event() if gate_after is not None else None
        self._callbacks_fired_at_gate: list[int] = []
        # Pre-build the stderr stream so impl can use either iteration
        # style. We wrap a generator in a tiny file-like for-loop helper.
        self.stderr = _GatedIter(stderr_lines, gate_after, self._gate)
        self.stdout = io.StringIO("")
        self._wait_called = False

    def wait(self) -> int:
        self._wait_called = True
        return self.returncode

    def poll(self) -> int | None:
        return self.returncode if self._wait_called else None

    def release_gate(self) -> None:
        if self._gate is not None:
            self._gate.set()


class _GatedIter:
    """Line iterator that blocks on `gate` after `gate_after` lines."""

    def __init__(self, lines: list[str], gate_after: int | None, gate) -> None:
        self._lines = list(lines)
        self._gate_after = gate_after
        self._gate = gate
        self._emitted = 0

    def __iter__(self):
        return self

    def __next__(self) -> str:
        if self._emitted >= len(self._lines):
            raise StopIteration
        if self._gate_after is not None and self._emitted == self._gate_after:
            self._gate.wait(timeout=5.0)
        line = self._lines[self._emitted]
        self._emitted += 1
        return line

    def close(self) -> None:
        pass


def test_rip_stderr_callback_invoked_per_line_in_order(
    monkeypatch: _pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Each stderr line fires the callback exactly once, in order."""
    import archivist.drivers.ripper as ripper_mod

    out_dir = tmp_path / "rip"
    out_dir.mkdir()
    # Pretend a wav landed so the ripper proceeds past the "no WAVs" guard.
    (out_dir / "track01.wav").write_bytes(b"RIFF")

    lines = ["track 1\n", "track 2\n", "track 3\n"]
    fake = _FakePopen([], lines, returncode=0)

    def fake_popen(argv, **_kwargs) -> _FakePopen:
        fake.args = argv
        return fake

    monkeypatch.setattr(ripper_mod.subprocess, "Popen", fake_popen)
    # Keep flac calls happy via subprocess.run already-patched fake.
    monkeypatch.setattr(
        ripper_mod.subprocess,
        "run",
        lambda *a, **k: type("R", (), {"returncode": 0, "stderr": "",
                                       "stdout": ""})(),
    )
    # Make the flac sidecar exist so success path completes.
    (out_dir / "track01.flac").write_bytes(b"fLaC")

    progress: list[str] = []
    CDAudioRipper().rip(DEVICE, out_dir, progress_callback=progress.append)
    assert progress == [line.rstrip("\n") for line in lines]


def test_rip_stderr_callback_fires_before_process_exit(
    monkeypatch: _pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Callback fires per-line, not buffered to exit.

    The fake Popen blocks on a gate after line 2; assert the callback
    has already seen lines 1+2 before wait() returns.
    """
    import threading as _threading
    import archivist.drivers.ripper as ripper_mod

    out_dir = tmp_path / "rip"
    out_dir.mkdir()
    (out_dir / "track01.wav").write_bytes(b"RIFF")

    lines = ["line a\n", "line b\n", "line c\n"]
    fake = _FakePopen([], lines, returncode=0, gate_after=2)

    monkeypatch.setattr(ripper_mod.subprocess, "Popen",
                        lambda argv, **k: fake)
    monkeypatch.setattr(
        ripper_mod.subprocess,
        "run",
        lambda *a, **k: type("R", (), {"returncode": 0, "stderr": "",
                                       "stdout": ""})(),
    )
    (out_dir / "track01.flac").write_bytes(b"fLaC")

    progress: list[str] = []

    # Run rip in a thread so we can observe its mid-stream state.
    done = _threading.Event()

    def runner() -> None:
        CDAudioRipper().rip(DEVICE, out_dir, progress_callback=progress.append)
        done.set()

    t = _threading.Thread(target=runner, daemon=True)
    t.start()

    # Wait for the first two callbacks to fire before the gate releases.
    deadline = 5.0
    import time as _time
    start = _time.monotonic()
    while len(progress) < 2 and _time.monotonic() - start < deadline:
        _time.sleep(0.01)

    assert len(progress) >= 2, (
        f"callback should have fired ≥2 times before exit; got {progress!r}"
    )
    fake.release_gate()
    done.wait(timeout=5.0)


def test_rip_stderr_lines_logged_at_info(
    monkeypatch: _pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: _pytest.LogCaptureFixture,
) -> None:
    """Each streamed stderr line is logged at INFO via the archivist logger."""
    import archivist.drivers.ripper as ripper_mod

    out_dir = tmp_path / "rip"
    out_dir.mkdir()
    (out_dir / "track01.wav").write_bytes(b"RIFF")

    lines = ["scanning toc\n", "ripping track 1\n"]
    fake = _FakePopen([], lines, returncode=0)
    monkeypatch.setattr(ripper_mod.subprocess, "Popen", lambda argv, **k: fake)
    monkeypatch.setattr(
        ripper_mod.subprocess,
        "run",
        lambda *a, **k: type("R", (), {"returncode": 0, "stderr": "",
                                       "stdout": ""})(),
    )
    (out_dir / "track01.flac").write_bytes(b"fLaC")

    with caplog.at_level(logging.INFO, logger="archivist.drivers.ripper"):
        CDAudioRipper().rip(DEVICE, out_dir)

    messages = " | ".join(r.message for r in caplog.records)
    assert "scanning toc" in messages
    assert "ripping track 1" in messages


def test_rip_default_callback_is_none_safe(
    monkeypatch: _pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """progress_callback=None (default) must not raise on streamed lines."""
    import archivist.drivers.ripper as ripper_mod

    out_dir = tmp_path / "rip"
    out_dir.mkdir()
    (out_dir / "track01.wav").write_bytes(b"RIFF")

    fake = _FakePopen([], ["any line\n"], returncode=0)
    monkeypatch.setattr(ripper_mod.subprocess, "Popen", lambda argv, **k: fake)
    monkeypatch.setattr(
        ripper_mod.subprocess,
        "run",
        lambda *a, **k: type("R", (), {"returncode": 0, "stderr": "",
                                       "stdout": ""})(),
    )
    (out_dir / "track01.flac").write_bytes(b"fLaC")

    # Should not raise.
    CDAudioRipper().rip(DEVICE, out_dir)
