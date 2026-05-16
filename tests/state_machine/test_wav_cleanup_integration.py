"""Failing regression for the sprint-4 wav-cleanup bug (sprint-5 / Bucket C).

STP rip leaked .wav siblings into `/srv/music/library`. Sprint-4's
`cleanup_wavs` helper is correct in isolation; this regression
exercises the state-machine call path:

  (a) full rip cycle → after _from_rip + _from_capture, working-dir
      folder contains ONLY .flac files (no .wav siblings).
  (b) ARCHIVIST_KEEP_WAVS=1 → both .wav and .flac present in the
      working-dir folder (env-override path preserved).
  (c) cleanup runs BEFORE the working→inbox handoff in _from_capture
      so the music-pipeline importer never sees the WAVs.

Root cause identified in `D-wav-cleanup-real-fix` (see Decision Log).

Impl: impl-wav-cleanup-fix.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from archivist.drivers.ripper import RipResult
from archivist.state_machine.loop import ArchivistLoop, State

DEVICE = Path("/dev/sr0")


class _FakeDrive:
    def __init__(self, statuses: list[str]) -> None:
        self._statuses = list(statuses)

    def __call__(self) -> str:
        return self._statuses[0] if len(self._statuses) == 1 else self._statuses.pop(0)

    def eject(self, device: Path) -> bool:
        return True


class _FakeServices:
    def stop_unit(self, name: str) -> bool: return True
    def start_unit(self, name: str) -> bool: return True


class _FakeRipperWithWavs:
    """Materializes BOTH .wav and .flac per track — reproduces real cdparanoia+flac."""
    media_types = {"audio_cd"}

    def detect(self, device: Path) -> str | None:
        return "audio_cd"

    def rip(self, device: Path, out_dir: Path) -> RipResult:
        out_dir.mkdir(parents=True, exist_ok=True)
        flacs: list[Path] = []
        for n in (1, 2):
            wav = out_dir / f"track{n:02d}.cdda.wav"
            flac = out_dir / f"track{n:02d}.cdda.flac"
            wav.write_bytes(b"RIFFwav data")
            flac.write_bytes(b"fLaC data")
            flacs.append(flac)
        (out_dir.parent / "rip.log").write_text("rip ok\n")
        return RipResult(status="success", tracks=flacs, errors=[])


class _FakeCamera:
    def __call__(self, device, out_path, *, frames=15):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"\xff\xd8\xff\xd9")
        return out_path


class _FakeLED:
    def power_on(self): return True
    def power_off(self): return True
    def status(self): return "unknown"


@dataclass
class _Clock:
    now: float = 0.0
    def __call__(self): return self.now
    def advance(self, dt): self.now += dt


@pytest.fixture
def dirs(tmp_path: Path) -> tuple[Path, Path, Path]:
    working = tmp_path / "w"
    inbox = tmp_path / "in"
    failed = tmp_path / "f"
    for d in (working, inbox, failed):
        d.mkdir()
    return working, inbox, failed


def _build_loop(dirs):
    working, inbox, failed = dirs
    clock = _Clock()
    loop = ArchivistLoop(
        working_dir=working, inbox_dir=inbox, failed_dir=failed,
        device=DEVICE,
        drive=_FakeDrive(["disc-ok"]),
        ripper=_FakeRipperWithWavs(),
        camera=_FakeCamera(),
        led=_FakeLED(),
        services=_FakeServices(),
        clock=clock,
        sleeper=lambda s: None,
    )
    return loop, clock


def _run_to_idle(loop, clock, max_ticks: int = 30) -> None:
    for _ in range(max_ticks):
        clock.advance(3.0)
        loop.tick()
        if loop.state in (State.WAITING_REMOVE, State.IDLE):
            return


# -------- (a) cleanup deletes WAVs by default -----------------------


def test_default_cycle_inbox_has_no_wavs(dirs) -> None:
    working, inbox, failed = dirs
    loop, clock = _build_loop(dirs)
    _run_to_idle(loop, clock)

    # Folder landed in inbox.
    inbox_folders = [p for p in inbox.iterdir() if p.is_dir()]
    assert inbox_folders, f"folder must arrive in inbox; saw {list(inbox.iterdir())}"
    folder = inbox_folders[0]

    wavs = list(folder.rglob("*.wav"))
    flacs = list(folder.rglob("*.flac"))
    assert flacs, "FLACs must be present"
    assert wavs == [], f"WAVs must be cleaned up before handoff; saw {wavs}"


# -------- (b) ARCHIVIST_KEEP_WAVS=1 preserves WAVs ------------------


def test_keep_wavs_env_preserves_both(
    dirs, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARCHIVIST_KEEP_WAVS", "1")
    loop, clock = _build_loop(dirs)
    _run_to_idle(loop, clock)

    _, inbox, _ = dirs
    inbox_folders = [p for p in inbox.iterdir() if p.is_dir()]
    assert inbox_folders
    folder = inbox_folders[0]
    wavs = sorted(p.name for p in folder.rglob("*.wav"))
    flacs = sorted(p.name for p in folder.rglob("*.flac"))
    assert wavs, "ARCHIVIST_KEEP_WAVS=1 must preserve WAVs"
    assert flacs, "FLACs always preserved"


# -------- (c) cleanup runs BEFORE working→inbox handoff -------------


def test_cleanup_runs_before_handoff(dirs) -> None:
    """Inbox never holds a .wav file at ANY point during the cycle."""
    working, inbox, failed = dirs
    loop, clock = _build_loop(dirs)

    for _ in range(30):
        clock.advance(3.0)
        loop.tick()
        # On every tick, inbox folders (if any) must be wav-free.
        for child in inbox.iterdir():
            if child.is_dir():
                stray = list(child.rglob("*.wav"))
                assert stray == [], (
                    f"inbox folder {child.name} held WAV(s) at some tick: {stray}"
                )
        if loop.state in (State.WAITING_REMOVE, State.IDLE):
            break
