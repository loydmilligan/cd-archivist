"""Failing tests for the new `WAITING_REMOVE` state (sprint-4 / D-waiting-remove-state).

After EJECT phase completes, the loop transitions to `WAITING_REMOVE`
(NOT directly to WAITING/IDLE) and stays there until the drive
reports `tray-open` OR `no-disc` — i.e. until the operator has
physically removed the disc.

This prevents the dogfood-rig CD_0019/0020/... auto-re-rip cascade
where a failed eject (CDROMEJECT ioctl no-op) left the drive
reporting `disc-ok`, which the loop misread as a fresh disc and
re-ripped.

Impl lands in Wave 2 (impl-waiting-remove-state).
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
        if len(self._statuses) == 1:
            return self._statuses[0]
        return self._statuses.pop(0)

    def set_status(self, status: str) -> None:
        self._statuses = [status]

    def eject(self, device: Path) -> bool:
        return True


class _FakeServices:
    def stop_unit(self, name: str) -> bool: return True
    def start_unit(self, name: str) -> bool: return True


class _FakeRipper:
    media_types = {"audio_cd"}
    def __init__(self, working_dir: Path) -> None:
        self._working_dir = working_dir
    def detect(self, device): return "audio_cd"
    def rip(self, device, out_dir):
        out_dir.mkdir(parents=True, exist_ok=True)
        flac = out_dir / "track01.flac"
        flac.write_bytes(b"fLaC")
        (out_dir.parent / "rip.log").write_text("ok\n")
        return RipResult(status="success", tracks=[flac], errors=[])


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


def _make_loop(dirs, statuses):
    working, inbox, failed = dirs
    drive = _FakeDrive(statuses)
    clock = _Clock()
    loop = ArchivistLoop(
        working_dir=working,
        inbox_dir=inbox,
        failed_dir=failed,
        device=DEVICE,
        drive=drive,
        ripper=_FakeRipper(working),
        camera=_FakeCamera(),
        led=_FakeLED(),
        services=_FakeServices(),
        clock=clock,
        sleeper=lambda s: None,
    )
    return loop, drive, clock


def _run_until(loop, clock, target: State, *, max_ticks: int = 30) -> bool:
    for _ in range(max_ticks):
        clock.advance(3.0)
        loop.tick()
        if loop.state == target:
            return True
    return False


# -------- (a) post-EJECT → WAITING_REMOVE ---------------------------


def test_post_eject_lands_in_waiting_remove(dirs) -> None:
    loop, drive, clock = _make_loop(dirs, ["disc-ok"])
    reached = _run_until(loop, clock, State.WAITING_REMOVE)
    assert reached, f"never reached WAITING_REMOVE; ended in {loop.state}"


# -------- (b) WAITING_REMOVE + disc-ok = no advance, no re-rip ------


def test_waiting_remove_does_not_advance_on_disc_ok(dirs) -> None:
    loop, drive, clock = _make_loop(dirs, ["disc-ok"])
    assert _run_until(loop, clock, State.WAITING_REMOVE)

    # Drive still reports disc-ok (the failed-eject scenario).
    inbox_before = sorted(p.name for p in (dirs[1]).iterdir())
    for _ in range(8):
        clock.advance(3.0)
        loop.tick()
        assert loop.state == State.WAITING_REMOVE, (
            f"WAITING_REMOVE must not advance while disc still present; "
            f"saw {loop.state}"
        )
    # No new disc folders appeared in inbox during the hold.
    inbox_after = sorted(p.name for p in (dirs[1]).iterdir())
    assert inbox_after == inbox_before, "WAITING_REMOVE must NOT start a new rip cycle"


# -------- (c) tray-open → IDLE/WAITING ------------------------------


def test_waiting_remove_advances_on_tray_open(dirs) -> None:
    loop, drive, clock = _make_loop(dirs, ["disc-ok"])
    assert _run_until(loop, clock, State.WAITING_REMOVE)

    drive.set_status("tray-open")
    clock.advance(1.0)
    loop.tick()
    assert loop.state in (State.IDLE, State.WAITING), (
        f"tray-open must release WAITING_REMOVE → IDLE/WAITING; got {loop.state}"
    )


# -------- (d) no-disc → IDLE/WAITING --------------------------------


def test_waiting_remove_advances_on_no_disc(dirs) -> None:
    loop, drive, clock = _make_loop(dirs, ["disc-ok"])
    assert _run_until(loop, clock, State.WAITING_REMOVE)

    drive.set_status("no-disc")
    clock.advance(1.0)
    loop.tick()
    assert loop.state in (State.IDLE, State.WAITING), (
        f"no-disc must release WAITING_REMOVE → IDLE/WAITING; got {loop.state}"
    )


# -------- (e) /api/status serializes WAITING_REMOVE -----------------


def test_loop_state_value_for_waiting_remove() -> None:
    """The enum's `.value` must be a stable string the FastAPI surface
    can render. Sprint-4 status JSON includes this string verbatim."""
    assert hasattr(State, "WAITING_REMOVE")
    val = State.WAITING_REMOVE.value
    assert isinstance(val, str)
    assert "wait" in val.lower() and "remove" in val.lower()
