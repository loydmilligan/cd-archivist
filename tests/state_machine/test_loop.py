"""Failing tests for archivist.state_machine.loop.ArchivistLoop.

The heart of sprint-2: glues the sprint-1 driver primitives + pipeline
functions into a state machine. Driven by `tick()` — one transition
per call based on the current drive status.

States: IDLE | WAITING | STABILIZE | CAPTURE | RIP | EJECT.

Impl lands in Wave 2 (impl-state-machine).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from archivist.drivers.ripper import RipResult
from archivist.models.manifest import CaptureRecord, RipRecord, read_manifest
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
    def __init__(self, *, fail: bool = False) -> None:
        self.events: list[str] = []
        self._fail = fail

    def stop_unit(self, name: str) -> bool:
        self.events.append(f"stop:{name}")
        return not self._fail

    def start_unit(self, name: str) -> bool:
        self.events.append(f"start:{name}")
        return True


class _FakeRipper:
    media_types = {"audio_cd"}

    def __init__(self, result: RipResult | Exception) -> None:
        self._result = result
        self.rip_calls: list[tuple[Path, Path]] = []

    def detect(self, device: Path) -> str | None:
        return "audio_cd"

    def rip(self, device: Path, out_dir: Path) -> RipResult:
        self.rip_calls.append((device, out_dir))
        if isinstance(self._result, Exception):
            raise self._result
        # Materialize whatever tracks the canned result claims.
        out_dir.mkdir(parents=True, exist_ok=True)
        for t in self._result.tracks:
            t.parent.mkdir(parents=True, exist_ok=True)
            t.write_bytes(b"fLaC")
        return self._result


class _FakeCamera:
    """Records calls; writes a 1-byte stub at out_path."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, device: Path, out_path: Path, *, frames: int = 15) -> Path:
        self.calls += 1
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"\xff\xd8\xff\xd9")
        return out_path


class _FakeLED:
    def __init__(self) -> None:
        self.events: list[str] = []

    def power_on(self) -> bool:
        self.events.append("on")
        return True

    def power_off(self) -> bool:
        self.events.append("off")
        return True

    def status(self) -> str:
        return "unknown"


@dataclass
class _Clock:
    """Test clock — caller advances `now` between ticks."""

    now: float = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, dt: float) -> None:
        self.now += dt


def _make_loop(
    *,
    statuses: list[str],
    discs_root: Path,
    rip_result: RipResult | Exception | None = None,
) -> tuple[ArchivistLoop, _FakeDrive, _FakeRipper, _FakeServices, _FakeCamera, _FakeLED, _Clock]:
    drive = _FakeDrive(statuses)
    audio_dir = discs_root / "CD_0001" / "audio"
    if rip_result is None:
        rip_result = RipResult(
            status="success",
            tracks=[audio_dir / "track01.flac"],
            errors=[],
        )
    ripper = _FakeRipper(rip_result)
    services = _FakeServices()
    camera = _FakeCamera()
    led = _FakeLED()
    clock = _Clock()
    loop = ArchivistLoop(
        discs_root=discs_root,
        device=DEVICE,
        drive=drive,
        ripper=ripper,
        camera=camera,
        led=led,
        services=services,
        clock=clock,
        sleeper=lambda _s: None,
    )
    return loop, drive, ripper, services, camera, led, clock


@pytest.fixture
def discs_root(tmp_disc_root) -> Path:
    return tmp_disc_root()


# ---------------- last_tick_at heartbeat (sprint-3 / test-last-tick) ----


def test_loop_state_has_both_timestamp_fields() -> None:
    """LoopState gains last_tick_at and renames last_updated→state_entered_at."""
    from archivist.service.app import LoopState

    s = LoopState()
    # Defaults — both populated.
    assert s.state_entered_at is not None
    assert s.last_tick_at is not None
    # The old name is gone.
    assert not hasattr(s, "last_updated")


def test_tick_updates_last_tick_at_without_transition(discs_root: Path) -> None:
    """A tick that does NOT transition state still bumps last_tick_at.

    Heartbeat semantics: last_tick_at is "loop is alive"; state_entered_at
    is "current state began at".
    """
    from archivist.service.app import LoopState

    loop_state = LoopState()
    loop, *_, clock = _make_loop(
        statuses=["tray-open", "tray-open", "tray-open"], discs_root=discs_root
    )
    loop._loop_state = loop_state  # inject

    before = loop_state.last_tick_at
    clock.advance(0.05)
    loop.tick()  # IDLE -> WAITING (transition)
    after_transition = loop_state.last_tick_at
    entered_after_transition = loop_state.state_entered_at
    assert after_transition > before
    assert entered_after_transition >= before

    # Now stay in WAITING (tray-open keeps WAITING).
    clock.advance(0.05)
    loop.tick()  # WAITING (no transition)
    assert loop_state.last_tick_at > after_transition, (
        "last_tick_at must advance even when the state did not change"
    )
    assert loop_state.state_entered_at == entered_after_transition, (
        "state_entered_at must NOT advance when the state did not change"
    )


def test_transition_updates_both_timestamps(discs_root: Path) -> None:
    from archivist.service.app import LoopState

    loop_state = LoopState()
    loop, *_, clock = _make_loop(statuses=["tray-open"], discs_root=discs_root)
    loop._loop_state = loop_state

    entered_before = loop_state.state_entered_at
    tick_before = loop_state.last_tick_at
    clock.advance(0.1)
    loop.tick()  # IDLE → WAITING
    assert loop_state.state_entered_at > entered_before
    assert loop_state.last_tick_at > tick_before


# -------------------------- transitions -------------------------------


def test_idle_tray_open_to_waiting(discs_root: Path) -> None:
    loop, *_ = _make_loop(statuses=["tray-open"], discs_root=discs_root)
    assert loop.state == State.IDLE
    loop.tick()
    assert loop.state == State.WAITING


def test_waiting_disc_ok_to_stabilize_sets_timer(discs_root: Path) -> None:
    loop, drive, _, _, _, _, clock = _make_loop(
        statuses=["tray-open", "disc-ok"], discs_root=discs_root
    )
    loop.tick()  # IDLE -> WAITING
    assert loop.state == State.WAITING
    clock.advance(0.1)
    loop.tick()  # WAITING -> STABILIZE
    assert loop.state == State.STABILIZE
    # Subsequent tick before 2s elapsed should NOT advance to CAPTURE.
    clock.advance(0.5)
    loop.tick()
    assert loop.state == State.STABILIZE


def test_stabilize_past_2s_advances_to_rip(discs_root: Path) -> None:
    """STABILIZE past 2s → CAPTURE (stop cdplay, run capture_disc) → RIP."""
    loop, _, _, services, camera, led, clock = _make_loop(
        statuses=["disc-ok"], discs_root=discs_root
    )
    # Drive straight from WAITING via internal forcing — first tick from IDLE
    # with status disc-ok should go to WAITING; then to STABILIZE.
    loop.tick()  # IDLE -> WAITING
    loop.tick()  # WAITING -> STABILIZE (timer set)
    assert loop.state == State.STABILIZE
    clock.advance(2.1)
    loop.tick()  # STABILIZE -> CAPTURE -> RIP (CAPTURE is a synchronous burst)
    assert loop.state == State.RIP
    assert "stop:cdplay.service" in services.events
    # capture_disc fired LED dance off→on→off and camera was called.
    assert led.events == ["off", "on", "off"]
    assert camera.calls == 6  # 3 ambient + 3 lit


def test_rip_writes_manifest_and_advances_to_eject(discs_root: Path) -> None:
    loop, _, ripper, _, _, _, clock = _make_loop(
        statuses=["disc-ok"], discs_root=discs_root
    )
    loop.tick()  # IDLE -> WAITING
    loop.tick()  # WAITING -> STABILIZE
    clock.advance(2.1)
    loop.tick()  # STABILIZE -> CAPTURE -> RIP
    loop.tick()  # RIP -> EJECT
    assert loop.state == State.EJECT
    assert len(ripper.rip_calls) == 1

    # Manifest reflects reality.
    manifest_path = discs_root / "CD_0001" / "manifest.json"
    assert manifest_path.exists()
    manifest = read_manifest(manifest_path)
    assert manifest.status == "ripped"
    assert len(manifest.captures) == 2   # ambient + lit
    assert all(isinstance(c, CaptureRecord) for c in manifest.captures)
    assert len(manifest.rips) == 1
    assert isinstance(manifest.rips[0], RipRecord)
    assert len(manifest.pairings) == 1


def test_eject_calls_drive_and_restarts_cdplay(discs_root: Path) -> None:
    loop, drive, _, services, _, _, clock = _make_loop(
        statuses=["disc-ok", "disc-ok", "disc-ok", "disc-ok", "tray-open"],
        discs_root=discs_root,
    )
    loop.tick()  # IDLE -> WAITING
    loop.tick()  # WAITING -> STABILIZE
    clock.advance(2.1)
    loop.tick()  # STABILIZE -> RIP
    loop.tick()  # RIP -> EJECT
    loop.tick()  # EJECT -> IDLE
    assert loop.state == State.IDLE
    assert drive.eject_calls == [DEVICE]
    # Start/stop are paired — both must appear, in order.
    assert services.events.index("stop:cdplay.service") < services.events.index(
        "start:cdplay.service"
    )


def test_rip_exception_still_restarts_cdplay(discs_root: Path) -> None:
    """Sprint-3 / test-rip-error-recovery: rip_disc raising transitions to
    ERROR, restarts cdplay, and surfaces the failure in the manifest.

    Crash recovery invariant: cdplay must never be left stopped. The
    exception is caught by the loop and the rig parks in ERROR until
    the operator ejects.
    """
    loop, _, _, services, _, _, clock = _make_loop(
        statuses=["disc-ok"],
        discs_root=discs_root,
        rip_result=RuntimeError("cdparanoia exploded"),
    )
    loop.tick()  # IDLE -> WAITING
    loop.tick()  # WAITING -> STABILIZE
    clock.advance(2.1)
    loop.tick()  # STABILIZE -> RIP
    loop.tick()  # RIP raises internally → caught → ERROR

    assert loop.state == State.ERROR
    assert "stop:cdplay.service" in services.events
    assert "start:cdplay.service" in services.events
    assert services.events.index("stop:cdplay.service") < services.events.index(
        "start:cdplay.service"
    )

    # Manifest reflects the failure.
    manifest = read_manifest(discs_root / "CD_0001" / "manifest.json")
    assert manifest.status == "rip_failed"


# --------------- ERROR state recovery (sprint-3 / test-rip-error-recovery) -


def test_rip_status_fail_transitions_to_error(discs_root: Path) -> None:
    """rip_disc returning RipResult(status='fail') → ERROR (same as raising)."""
    fail_result = RipResult(status="fail", tracks=[], errors=["read errors"])
    loop, _, _, services, _, _, clock = _make_loop(
        statuses=["disc-ok"], discs_root=discs_root, rip_result=fail_result
    )
    loop.tick()  # IDLE -> WAITING
    loop.tick()  # WAITING -> STABILIZE
    clock.advance(2.1)
    loop.tick()  # STABILIZE -> RIP
    loop.tick()  # RIP -> ERROR (status=fail short-circuit)

    assert loop.state == State.ERROR
    assert "start:cdplay.service" in services.events
    manifest = read_manifest(discs_root / "CD_0001" / "manifest.json")
    assert manifest.status == "rip_failed"


def test_error_state_tray_open_returns_to_idle(discs_root: Path) -> None:
    """From ERROR, tray-open is the only exit — cleanup and back to IDLE."""
    loop, drive, _, _, _, _, clock = _make_loop(
        statuses=["disc-ok", "disc-ok", "disc-ok", "tray-open"],
        discs_root=discs_root,
        rip_result=RuntimeError("boom"),
    )
    loop.tick()  # IDLE -> WAITING
    loop.tick()  # WAITING -> STABILIZE
    clock.advance(2.1)
    loop.tick()  # STABILIZE -> RIP
    loop.tick()  # RIP -> ERROR  (consumes one of the disc-ok statuses)
    # ERROR state should ignore drive() calls except for the tray-open exit.
    loop.tick()  # ERROR + tray-open → IDLE
    assert loop.state == State.IDLE


def test_error_state_holds_on_other_statuses(discs_root: Path) -> None:
    """ERROR + disc-ok / no-disc / drive-not-ready → stay in ERROR."""
    loop, *_, clock = _make_loop(
        statuses=["disc-ok"],  # constant — always disc-ok
        discs_root=discs_root,
        rip_result=RuntimeError("boom"),
    )
    loop.tick()  # IDLE -> WAITING
    loop.tick()  # WAITING -> STABILIZE
    clock.advance(2.1)
    loop.tick()  # STABILIZE -> RIP
    loop.tick()  # RIP -> ERROR
    assert loop.state == State.ERROR
    # Repeated ticks with disc-ok must NOT advance — operator must eject.
    for _ in range(3):
        loop.tick()
        assert loop.state == State.ERROR


def test_full_cycle_creates_disc_folder_exactly_once(discs_root: Path) -> None:
    """prepare_disc_folder must be called once per cycle, not per tick."""
    loop, *_, clock = _make_loop(
        statuses=["disc-ok", "disc-ok", "disc-ok", "disc-ok", "tray-open"],
        discs_root=discs_root,
    )
    loop.tick()  # IDLE -> WAITING
    loop.tick()  # WAITING -> STABILIZE
    clock.advance(2.1)
    loop.tick()  # STABILIZE -> RIP
    loop.tick()  # RIP -> EJECT
    loop.tick()  # EJECT -> IDLE

    # Exactly one CD_NNNN folder was created.
    cd_dirs = sorted(p.name for p in discs_root.iterdir() if p.name.startswith("CD_"))
    assert cd_dirs == ["CD_0001"]
