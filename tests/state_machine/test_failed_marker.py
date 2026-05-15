"""Failing tests for failed-disc disposition (sprint-4 / D-failed-disc-disposition).

On rip failure:
  (i)   write `<working>/<folder>/FAILED` marker with failed_at + reason
  (ii)  write `source.json` with status.rip_success=False, ready=False
  (iii) move the folder `working_dir/<folder>` → `failed_dir/<folder>`
        (NOT inbox)
  (iv)  do NOT write READY
  (v)   sprint-3 invariants preserved: ERROR state still entered,
        cdplay restarts (cdplay-paired invariant)

Impl lands in Wave 2 (impl-failed-marker).
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
    def __init__(self) -> None:
        self.events: list[str] = []

    def stop_unit(self, name: str) -> bool:
        self.events.append(f"stop:{name}")
        return True

    def start_unit(self, name: str) -> bool:
        self.events.append(f"start:{name}")
        return True


class _FakeRipper:
    media_types = {"audio_cd"}

    def __init__(self, behavior: str = "raise") -> None:
        self._behavior = behavior  # "raise" or "status_fail"

    def detect(self, device: Path) -> str | None:
        return "audio_cd"

    def rip(self, device: Path, out_dir: Path) -> RipResult:
        if self._behavior == "raise":
            raise RuntimeError("cdparanoia exploded")
        # Return a fail status with no tracks.
        return RipResult(status="fail", tracks=[], errors=["bad sectors"])


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


@pytest.fixture
def dirs(tmp_path: Path) -> tuple[Path, Path, Path]:
    working = tmp_path / "music" / ".ripping"
    inbox = tmp_path / "music" / "inbox"
    failed = tmp_path / "music" / "failed"
    for d in (working, inbox, failed):
        d.mkdir(parents=True)
    return working, inbox, failed


def _build_loop(dirs, behavior: str):
    working, inbox, failed = dirs
    services = _FakeServices()
    clock = _Clock()
    loop = ArchivistLoop(
        working_dir=working,
        inbox_dir=inbox,
        failed_dir=failed,
        device=DEVICE,
        drive=_FakeDrive(["disc-ok"]),
        ripper=_FakeRipper(behavior),
        camera=_FakeCamera(),
        led=_FakeLED(),
        services=services,
        clock=clock,
        sleeper=lambda s: None,
    )
    return loop, services, clock


def _walk_to_failure(loop, clock) -> None:
    for _ in range(15):
        clock.advance(3.0)
        loop.tick()
        if loop.state == State.ERROR:
            return


# -------- (a) RIP raises → folder moves to failed_dir with markers ---


def test_rip_raises_moves_folder_to_failed_dir_with_marker(
    dirs: tuple[Path, Path, Path],
) -> None:
    working, inbox, failed = dirs
    loop, _services, clock = _build_loop(dirs, behavior="raise")
    _walk_to_failure(loop, clock)

    failed_folders = [p for p in failed.iterdir() if p.is_dir()]
    assert failed_folders, "failed folder must move to failed_dir on raise"
    f = failed_folders[0]
    assert (f / "FAILED").is_file(), "FAILED marker must be present"
    assert (f / "source.json").is_file(), "source.json must be written for ops debug"
    assert (f / "rip.log").is_file(), "rip.log must be preserved"
    assert not (f / "READY").exists(), "READY must NOT be written on failure"

    # Inbox is untouched.
    assert not any(p.is_dir() for p in inbox.iterdir())
    # Working dir empty after the move.
    assert not any(p.is_dir() for p in working.iterdir())


# -------- (b) RipResult.status='fail' → same disposition ------------


def test_rip_status_fail_moves_to_failed_dir(
    dirs: tuple[Path, Path, Path],
) -> None:
    working, inbox, failed = dirs
    loop, _services, clock = _build_loop(dirs, behavior="status_fail")
    _walk_to_failure(loop, clock)

    failed_folders = [p for p in failed.iterdir() if p.is_dir()]
    assert failed_folders
    f = failed_folders[0]
    assert (f / "FAILED").is_file()
    assert (f / "source.json").is_file()
    assert not (f / "READY").exists()


# -------- (c) inbox is untouched on failure -------------------------


def test_inbox_unchanged_on_rip_failure(
    dirs: tuple[Path, Path, Path],
) -> None:
    working, inbox, failed = dirs
    loop, _services, clock = _build_loop(dirs, behavior="raise")

    # Take a snapshot of inbox before the rip.
    inbox_snapshot = set(inbox.iterdir())
    _walk_to_failure(loop, clock)
    assert set(inbox.iterdir()) == inbox_snapshot, (
        "inbox must not be touched on rip failure"
    )


# -------- (d) ERROR state still entered (sprint-3 invariant) --------


def test_error_state_still_entered_on_failure(
    dirs: tuple[Path, Path, Path],
) -> None:
    loop, _services, clock = _build_loop(dirs, behavior="raise")
    _walk_to_failure(loop, clock)
    assert loop.state == State.ERROR


# -------- (e) cdplay restarted (cdplay-paired invariant) ------------


def test_cdplay_restarted_on_failure(
    dirs: tuple[Path, Path, Path],
) -> None:
    loop, services, clock = _build_loop(dirs, behavior="raise")
    _walk_to_failure(loop, clock)
    # Every stop must be paired with a subsequent start.
    stops = [e for e in services.events if e.startswith("stop:")]
    starts = [e for e in services.events if e.startswith("start:")]
    assert len(starts) >= len(stops), (
        "cdplay-paired invariant violated: stop without subsequent start"
    )


# -------- (f) FAILED marker carries failed_at + reason --------------


def test_failed_marker_has_reason_and_timestamp(
    dirs: tuple[Path, Path, Path],
) -> None:
    _working, _inbox, failed = dirs
    loop, _services, clock = _build_loop(dirs, behavior="raise")
    _walk_to_failure(loop, clock)

    failed_folders = [p for p in failed.iterdir() if p.is_dir()]
    assert failed_folders
    marker = failed_folders[0] / "FAILED"
    contents = marker.read_text(encoding="utf-8")
    assert "failed_at=" in contents
    assert "reason=" in contents
    # Reason should reference the failure mode somehow.
    assert "RuntimeError" in contents or "cdparanoia" in contents
