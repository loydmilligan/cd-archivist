"""Failing tests for manual-mode state-machine gating (sprint-4 / D-manual-mode).

In manual mode (`LoopState.mode == "manual"`), the loop still polls
drive status but does NOT auto-advance through STABILIZE/RIP/EJECT/
CAPTURE. Transitions fire only when an explicit `advance(trigger)`
call is made.

  - `advance("rip")`     STABILIZE → RIP
  - `advance("eject")`   RIP → EJECT  (after rip completes)
  - `advance("capture")` EJECT → CAPTURE
  - `advance("reset")`   any state → IDLE, clearing the in-flight cycle

In auto mode (default), transitions fire as today (sprint-3 regression
check).

Impl lands in Wave 2 (impl-manual-mode).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from archivist.drivers.ripper import RipResult
from archivist.state_machine.loop import ArchivistLoop, State
from archivist.service.app import LoopState

DEVICE = Path("/dev/sr0")


class _FakeDrive:
    def __init__(self, statuses: list[str]) -> None:
        self._statuses = list(statuses)

    def __call__(self) -> str:
        return self._statuses[0] if len(self._statuses) == 1 else self._statuses.pop(0)

    def eject(self, device: Path) -> bool: return True


class _FakeServices:
    def stop_unit(self, name: str) -> bool: return True
    def start_unit(self, name: str) -> bool: return True


class _FakeRipper:
    media_types = {"audio_cd"}
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


def _make_loop(dirs, *, mode: str, statuses: list[str]):
    working, inbox, failed = dirs
    clock = _Clock()
    loop_state = LoopState(mode=mode)
    loop = ArchivistLoop(
        working_dir=working,
        inbox_dir=inbox,
        failed_dir=failed,
        device=DEVICE,
        drive=_FakeDrive(statuses),
        ripper=_FakeRipper(),
        camera=_FakeCamera(),
        led=_FakeLED(),
        services=_FakeServices(),
        clock=clock,
        sleeper=lambda s: None,
        loop_state=loop_state,
    )
    return loop, clock, loop_state


# -------- (a) manual mode: STABILIZE doesn't auto-advance to RIP ----


def test_manual_holds_at_stabilize_without_trigger(dirs) -> None:
    loop, clock, _state = _make_loop(dirs, mode="manual", statuses=["disc-ok"])

    # Walk: IDLE → WAITING → STABILIZE
    loop.tick(); loop.tick()
    assert loop.state == State.STABILIZE

    # Advance time well past STABILIZE_SECONDS; loop should NOT auto-jump
    # to RIP in manual mode.
    for _ in range(5):
        clock.advance(5.0)
        loop.tick()
        assert loop.state == State.STABILIZE, (
            f"manual mode must NOT auto-advance STABILIZE→RIP; saw {loop.state}"
        )


# -------- (b) advance("rip") fires the rip --------------------------


def test_advance_rip_transitions_to_rip(dirs) -> None:
    loop, clock, _state = _make_loop(dirs, mode="manual", statuses=["disc-ok"])
    loop.tick(); loop.tick()
    assert loop.state == State.STABILIZE

    loop.advance("rip")
    # Either RIP-then-EJECT (rip runs synchronously inside the transition)
    # or RIP and then waits for advance("eject"). Both are acceptable —
    # the test asserts the rip moved past STABILIZE.
    assert loop.state != State.STABILIZE


# -------- (c) advance("eject"), advance("capture") drive subsequent phases


def test_advance_eject_and_capture_progress_through_phases(dirs) -> None:
    loop, clock, _state = _make_loop(dirs, mode="manual", statuses=["disc-ok"])
    loop.tick(); loop.tick()  # → STABILIZE
    loop.advance("rip")
    # The rip happens synchronously. After advance("rip"), state is
    # either RIP (waiting for eject trigger) or further along.
    # Manual mode holds before each phase, so we should be able to
    # advance("eject") and advance("capture") next.
    if loop.state == State.RIP:
        loop.advance("eject")
    if loop.state == State.EJECT:
        loop.advance("capture")
    assert loop.state in (State.CAPTURE, State.WAITING_REMOVE, State.IDLE), (
        f"advance sequence didn't progress past EJECT; saw {loop.state}"
    )


# -------- (d) auto mode: regression — no manual trigger needed ------


def test_auto_mode_still_auto_advances(dirs) -> None:
    loop, clock, _state = _make_loop(dirs, mode="auto", statuses=["disc-ok"])

    # Walk through ticks; auto mode must reach WAITING_REMOVE or IDLE
    # within a reasonable number of ticks WITHOUT any advance() calls.
    for _ in range(15):
        clock.advance(3.0)
        loop.tick()
        if loop.state in (State.WAITING_REMOVE, State.IDLE):
            return
    pytest.fail(f"auto mode did not progress; ended in {loop.state}")


# -------- (e) advance() with non-matching trigger is a no-op --------


def test_advance_wrong_trigger_is_noop(dirs) -> None:
    loop, clock, _state = _make_loop(dirs, mode="manual", statuses=["disc-ok"])
    # In IDLE, advance("eject") makes no sense — no-op at state-machine level.
    starting = loop.state
    loop.advance("eject")
    assert loop.state == starting, "wrong-state advance must be a no-op"


# -------- (f) advance("reset") returns to IDLE, clearing _cycle -----


def test_advance_reset_returns_to_idle(dirs) -> None:
    loop, clock, _state = _make_loop(dirs, mode="manual", statuses=["disc-ok"])
    loop.tick(); loop.tick()  # → STABILIZE
    assert loop.state == State.STABILIZE

    loop.advance("reset")
    assert loop.state == State.IDLE
    # In-flight cycle cleared (cycle.disc_dir back to None).
    assert getattr(loop, "_cycle", None) is None or loop._cycle.disc_dir is None


def test_reset_works_in_auto_mode_too(dirs) -> None:
    """`reset` is the operator escape hatch — always allowed."""
    loop, clock, _state = _make_loop(dirs, mode="auto", statuses=["disc-ok"])
    loop.tick(); loop.tick()  # advance somewhere
    loop.advance("reset")
    assert loop.state == State.IDLE
