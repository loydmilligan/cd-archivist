"""Failing tests for the working-dir → inbox atomic handoff (sprint-4).

Per the env-driven path config (D-music-pipeline-paths) and the
handoff doc §"Use a Temporary Working Folder":

  - STABILIZE creates the disc folder under `working_dir` (NOT inbox)
  - RIP writes audio + rip.log there
  - after CAPTURE + source.json + disc-photo.jpg, the loop
    `os.replace`s `working_dir / folder` → `inbox_dir / folder` and
    only then writes `READY` (atomic-from-importer's perspective)
  - inbox never contains a partial folder lacking READY
  - if the move fails (OSError), state → ERROR; working-dir folder
    stays intact for operator triage

Impl lands in Wave 2 (impl-working-dir-handoff). The loop constructor
gains `working_dir: Path` and `inbox_dir: Path` (replacing the legacy
`discs_root` single-root parameter — see Contract Changes
2026-05-15 §env-driven path config).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from archivist.drivers.ripper import RipResult
from archivist.state_machine.loop import ArchivistLoop, State

DEVICE = Path("/dev/sr0")


# -------------------------- fakes -------------------------------------


class _FakeDrive:
    def __init__(self, statuses: list[str]) -> None:
        self._statuses = list(statuses)
        self.eject_calls: list[Path] = []

    def __call__(self) -> str:
        return self._statuses[0] if len(self._statuses) == 1 else self._statuses.pop(0)

    def eject(self, device: Path) -> bool:
        self.eject_calls.append(device)
        return True


class _FakeServices:
    def stop_unit(self, name: str) -> bool:
        return True

    def start_unit(self, name: str) -> bool:
        return True


class _FakeRipper:
    media_types = {"audio_cd"}

    def __init__(self, result: RipResult | None = None) -> None:
        self._template = result

    def detect(self, device: Path) -> str | None:
        return "audio_cd"

    def rip(self, device: Path, out_dir: Path) -> RipResult:
        out_dir.mkdir(parents=True, exist_ok=True)
        flac = out_dir / "track01.flac"
        flac.write_bytes(b"fLaC")
        (out_dir.parent / "rip.log").write_text("rip start\nrip end\n")
        return RipResult(status="success", tracks=[flac], errors=[])


class _FakeCamera:
    def __call__(self, device: Path, out_path: Path, *, frames: int = 15) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"\xff\xd8\xff\xd9")
        return out_path


class _FakeLED:
    def power_on(self) -> bool: return True
    def power_off(self) -> bool: return True
    def status(self) -> str: return "unknown"


@dataclass
class _Clock:
    now: float = 0.0
    def __call__(self) -> float: return self.now
    def advance(self, dt: float) -> None: self.now += dt


def _build_loop(
    working_dir: Path, inbox_dir: Path,
    *, statuses: list[str], rip_result: RipResult | None = None,
    failed_dir: Path | None = None,
):
    drive = _FakeDrive(statuses)
    ripper = _FakeRipper(rip_result)
    clock = _Clock()
    loop = ArchivistLoop(
        working_dir=working_dir,
        inbox_dir=inbox_dir,
        failed_dir=failed_dir or (inbox_dir.parent / "failed"),
        device=DEVICE,
        drive=drive,
        ripper=ripper,
        camera=_FakeCamera(),
        led=_FakeLED(),
        services=_FakeServices(),
        clock=clock,
        sleeper=lambda s: None,
    )
    return loop, drive, ripper, clock


@pytest.fixture
def music_pipeline_dirs(tmp_path: Path) -> tuple[Path, Path, Path]:
    working = tmp_path / "music" / ".ripping"
    inbox = tmp_path / "music" / "inbox"
    failed = tmp_path / "music" / "failed"
    for d in (working, inbox, failed):
        d.mkdir(parents=True)
    return working, inbox, failed


def _run_full_cycle(loop, clock) -> None:
    """Run enough ticks to walk IDLE → ... → READY."""
    for _ in range(20):
        clock.advance(3.0)  # past _STABILIZE_SECONDS and any settles
        loop.tick()
        if loop.state == State.IDLE and any(
            (loop._inbox_dir).iterdir()  # type: ignore[attr-defined]
        ):
            break


# -------- (a) STABILIZE creates folder under working_dir -------------


def test_stabilize_creates_folder_in_working_not_inbox(
    music_pipeline_dirs: tuple[Path, Path, Path],
) -> None:
    working, inbox, failed = music_pipeline_dirs
    loop, _drive, _ripper, clock = _build_loop(
        working, inbox,
        statuses=["disc-ok"],
        failed_dir=failed,
    )
    # Walk IDLE → WAITING → STABILIZE (post-2s) and stop.
    loop.tick()  # IDLE → WAITING
    loop.tick()  # WAITING → STABILIZE
    clock.advance(3.0)
    loop.tick()  # STABILIZE → RIP, folder created in working

    working_entries = [p for p in working.iterdir() if p.is_dir()]
    inbox_entries = [p for p in inbox.iterdir() if p.is_dir()]
    assert working_entries, "STABILIZE should create a folder under working_dir"
    assert not inbox_entries, "inbox must be empty until atomic handoff"


# -------- (b) RIP writes audio + rip.log under working_dir ----------


def test_rip_writes_audio_and_log_in_working(
    music_pipeline_dirs: tuple[Path, Path, Path],
) -> None:
    working, inbox, failed = music_pipeline_dirs
    loop, _drive, _ripper, clock = _build_loop(
        working, inbox, statuses=["disc-ok"], failed_dir=failed,
    )
    for _ in range(5):
        clock.advance(3.0)
        loop.tick()
        if loop.state in (State.EJECT, State.CAPTURE):
            break

    working_folders = [p for p in working.iterdir() if p.is_dir()]
    assert working_folders
    f = working_folders[0]
    flacs = list(f.rglob("*.flac"))
    logs = list(f.rglob("rip.log"))
    assert flacs, "FLACs must land under working_dir"
    assert logs, "rip.log must land under working_dir"
    # And NOT under inbox.
    assert not list(inbox.rglob("*.flac"))


# -------- (c) handoff happens before READY --------------------------


def test_handoff_into_inbox_then_ready_marker(
    music_pipeline_dirs: tuple[Path, Path, Path],
) -> None:
    working, inbox, failed = music_pipeline_dirs
    loop, _drive, _ripper, clock = _build_loop(
        working, inbox, statuses=["disc-ok"], failed_dir=failed,
    )
    _run_full_cycle(loop, clock)

    inbox_folders = [p for p in inbox.iterdir() if p.is_dir()]
    assert inbox_folders, "folder must arrive in inbox after full cycle"
    f = inbox_folders[0]
    assert (f / "READY").is_file(), "READY marker must exist post-handoff"
    # Working dir is empty (move, not copy).
    leftover = [p for p in working.iterdir() if p.is_dir()]
    assert not leftover, "working_dir folder must be removed by the move"


# -------- (d) inbox never has a partial folder without READY --------


def test_inbox_never_has_partial_folder_without_ready(
    music_pipeline_dirs: tuple[Path, Path, Path],
) -> None:
    working, inbox, failed = music_pipeline_dirs
    loop, _drive, _ripper, clock = _build_loop(
        working, inbox, statuses=["disc-ok"], failed_dir=failed,
    )

    # Run tick by tick; on every tick, any folder in inbox must have READY.
    for _ in range(20):
        for child in inbox.iterdir():
            if child.is_dir():
                assert (child / "READY").is_file(), (
                    f"{child.name}: inbox folder seen WITHOUT READY"
                )
        clock.advance(3.0)
        loop.tick()
        if loop.state == State.IDLE and list(inbox.iterdir()):
            break


# -------- (e) move failure → ERROR; working folder preserved --------


def test_working_to_inbox_move_failure_lands_in_error(
    music_pipeline_dirs: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    working, inbox, failed = music_pipeline_dirs
    loop, _drive, _ripper, clock = _build_loop(
        working, inbox, statuses=["disc-ok"], failed_dir=failed,
    )

    # Sabotage the move by replacing os.replace inside the state machine
    # module to raise OSError when the source path lives under working_dir.
    import archivist.state_machine.loop as loop_mod
    real_replace = loop_mod.os.replace  # type: ignore[attr-defined]

    def boom(src, dst):  # type: ignore[no-untyped-def]
        if str(working) in str(src):
            raise OSError("simulated move failure")
        return real_replace(src, dst)

    monkeypatch.setattr(loop_mod.os, "replace", boom)

    for _ in range(25):
        clock.advance(3.0)
        loop.tick()
        if loop.state == State.ERROR:
            break

    assert loop.state == State.ERROR, (
        "move failure must transition to ERROR for operator triage"
    )
    # Working-dir folder is left intact (no auto-cleanup on failure).
    assert any(p.is_dir() for p in working.iterdir()), (
        "working_dir folder must be preserved on move failure"
    )
    # And inbox stays empty.
    assert not any(p.is_dir() for p in inbox.iterdir())
