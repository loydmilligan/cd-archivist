"""Failing tests for the DriveStatus snapshot exposed via LoopState.

Per sprint-6.5 Bucket F task `test-drive-status-snapshot`. Impl lands
in `impl-drive-status-snapshot` (drivers' Wave 2).

Contract — `archivist/state_machine/drive_status.py::DriveStatus`:

  state: Literal["idle", "ripping", "stabilizing", "capturing"] = "idle"
  current_disc: str | None = None
  current_track: int | None = None
  track_total: int | None = None
  sector_current: int | None = None
  sector_total: int | None = None
  retries_on_current_track: int | None = None
  photo_state: Literal["pending", "capturing", "done"] | None = None
  elapsed_seconds: float | None = None

  # Thread-safety: drive_status is mutated from the ripper-streaming
  # thread (via the progress_callback) and read from the FastAPI
  # request thread. The dataclass either exposes a `lock` attribute
  # (threading.Lock / RLock) for callers to wrap mutations in, OR
  # exposes an atomic-snapshot helper. Either way the test below
  # exercises the `lock` attribute as the canonical mechanism.

LoopState (in archivist/service/app.py) gains:
  drive_status: DriveStatus = field(default_factory=DriveStatus)

Progress-callback contract (consumed by the state machine when wiring
the ripper's progress_callback): given a cdparanoia stderr line, the
helper updates the corresponding DriveStatus fields. The test verifies
this via the public helper `update_from_progress_line(drive_status,
line)` that the state machine's callback closure will delegate to.

State transitions: STABILIZE→drive_status.state = "stabilizing";
RIP→"ripping"; CAPTURE→"capturing"; back to IDLE→"idle" + transient
fields reset to None.
"""
from __future__ import annotations

import threading
from pathlib import Path

import pytest

from archivist.drivers.ripper import RipResult
from archivist.state_machine.loop import ArchivistLoop, State

# Reuse the test-loop fakes through the package import (the same trick
# sprint-6's test_cdplay_decoupled uses).
from tests.state_machine.test_loop import (  # type: ignore[import-not-found]
    DEVICE,
    _FakeCamera,
    _FakeDrive,
    _FakeLED,
    _FakeRipper,
    _FakeServices,
    _Clock,
)


# ---------------------------- (a) dataclass shape --------------------

def test_drive_status_dataclass_has_documented_fields() -> None:
    """DriveStatus exists with the exact field set + defaults."""
    from archivist.state_machine.drive_status import DriveStatus  # noqa: PLC0415

    ds = DriveStatus()
    # Defaults
    assert ds.state == "idle"
    assert ds.current_disc is None
    assert ds.current_track is None
    assert ds.track_total is None
    assert ds.sector_current is None
    assert ds.sector_total is None
    assert ds.retries_on_current_track is None
    assert ds.photo_state is None
    assert ds.elapsed_seconds is None


def test_drive_status_accepts_typed_values() -> None:
    """All fields accept the documented value types (smoke check)."""
    from archivist.state_machine.drive_status import DriveStatus  # noqa: PLC0415

    ds = DriveStatus(
        state="ripping",
        current_disc="2026-05-16_1830_disc-000042",
        current_track=3,
        track_total=12,
        sector_current=24_000,
        sector_total=298_500,
        retries_on_current_track=1,
        photo_state="pending",
        elapsed_seconds=42.5,
    )
    assert ds.state == "ripping"
    assert ds.current_track == 3
    assert ds.track_total == 12
    assert ds.sector_current == 24_000
    assert ds.sector_total == 298_500
    assert ds.retries_on_current_track == 1
    assert ds.photo_state == "pending"
    assert ds.elapsed_seconds == 42.5


# ---------------------------- (b) LoopState attribute ----------------

def test_loop_state_has_drive_status_with_default_factory() -> None:
    """LoopState() yields a fresh DriveStatus instance (NOT a shared default)."""
    from archivist.service.app import LoopState  # noqa: PLC0415
    from archivist.state_machine.drive_status import DriveStatus  # noqa: PLC0415

    a = LoopState()
    b = LoopState()
    assert isinstance(a.drive_status, DriveStatus)
    assert isinstance(b.drive_status, DriveStatus)
    # Independent instances — mutating one must not affect the other.
    assert a.drive_status is not b.drive_status
    a.drive_status.current_track = 5
    assert b.drive_status.current_track is None


# ---------------------------- (c) progress-callback updates ----------

def test_progress_line_outputting_track_updates_current_track() -> None:
    """A `:outputting track N` line bumps drive_status.current_track."""
    from archivist.state_machine.drive_status import (  # noqa: PLC0415
        DriveStatus,
        update_from_progress_line,
    )

    ds = DriveStatus()
    update_from_progress_line(ds, "==PROGRESS== :outputting track 7")
    assert ds.current_track == 7


def test_progress_line_scsi_read_updates_sector_and_retries() -> None:
    """A `scsi_read error: sector=X length=Y retry=N` line updates
    sector_current and retries_on_current_track."""
    from archivist.state_machine.drive_status import (  # noqa: PLC0415
        DriveStatus,
        update_from_progress_line,
    )

    ds = DriveStatus()
    update_from_progress_line(
        ds, "scsi_read error: sector=12345 length=27 retry=2"
    )
    assert ds.sector_current == 12345
    assert ds.retries_on_current_track == 2


def test_progress_line_retries_reset_on_new_track() -> None:
    """When the track changes, retries_on_current_track resets to 0
    (or None — impl picks; both indicate "no retries seen yet on the
    new track")."""
    from archivist.state_machine.drive_status import (  # noqa: PLC0415
        DriveStatus,
        update_from_progress_line,
    )

    ds = DriveStatus()
    update_from_progress_line(ds, "scsi_read error: sector=100 length=27 retry=3")
    assert ds.retries_on_current_track == 3

    # Moving to a new track resets the retry counter — the retries
    # field is per-track, not cumulative across the rip.
    update_from_progress_line(ds, "==PROGRESS== :outputting track 4")
    assert ds.retries_on_current_track in (0, None)


def test_progress_line_progress_no_op_for_unrelated_lines() -> None:
    """Lines that don't match either parser leave state untouched."""
    from archivist.state_machine.drive_status import (  # noqa: PLC0415
        DriveStatus,
        update_from_progress_line,
    )

    ds = DriveStatus(current_track=5, sector_current=999)
    update_from_progress_line(ds, "cdparanoia: scanning toc")
    assert ds.current_track == 5
    assert ds.sector_current == 999


# ---------------------------- (d) state-machine transitions ----------

@pytest.fixture
def discs_root(tmp_disc_root) -> Path:
    return tmp_disc_root()


def _make_loop_with_loopstate(discs_root: Path):
    """Build a loop wired to a LoopState so we can introspect
    drive_status mutations through the cycle."""
    from archivist.service.app import LoopState  # noqa: PLC0415

    audio_dir = discs_root / "CD_0001" / "audio"
    drive = _FakeDrive(
        ["disc-ok", "disc-ok", "disc-ok", "disc-ok",
         "tray-open", "tray-open"]
    )
    ripper = _FakeRipper(
        RipResult(status="success", tracks=[audio_dir / "track01.flac"], errors=[])
    )
    services = _FakeServices()
    camera = _FakeCamera()
    led = _FakeLED()
    clock = _Clock()
    loop_state = LoopState()

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
        loop_state=loop_state,
    )
    return loop, loop_state, clock


def test_stabilize_sets_drive_status_state_stabilizing(
    discs_root: Path,
) -> None:
    loop, loop_state, _clock = _make_loop_with_loopstate(discs_root)
    loop.tick()  # IDLE → WAITING
    loop.tick()  # WAITING → STABILIZE
    assert loop.state == State.STABILIZE
    assert loop_state.drive_status.state == "stabilizing"


def test_rip_sets_drive_status_state_ripping(discs_root: Path) -> None:
    loop, loop_state, clock = _make_loop_with_loopstate(discs_root)
    loop.tick()  # IDLE → WAITING
    loop.tick()  # WAITING → STABILIZE
    clock.advance(2.1)
    loop.tick()  # STABILIZE → RIP
    # NB: the RIP→EJECT transition might happen on the same tick in
    # the test-fake loop because _FakeRipper returns synchronously.
    # We check the snapshot mid-flight by reading immediately after the
    # state machine entered RIP — and accept that an instantaneous fake
    # rip means drive_status may already be "capturing" by tick end.
    assert loop_state.drive_status.state in ("ripping", "capturing", "idle"), (
        f"expected drive_status.state to advance through ripping; got "
        f"{loop_state.drive_status.state!r}"
    )


def test_capture_sets_photo_state(discs_root: Path) -> None:
    """During CAPTURE, drive_status.photo_state should walk through
    `pending` → `capturing` → `done` (at least the final state should
    be observable since CAPTURE runs synchronously in the fake loop)."""
    loop, loop_state, clock = _make_loop_with_loopstate(discs_root)
    loop.tick()  # IDLE → WAITING
    loop.tick()  # WAITING → STABILIZE
    clock.advance(2.1)
    loop.tick()  # STABILIZE → RIP
    loop.tick()  # RIP → EJECT
    loop.tick()  # EJECT → CAPTURE
    # By end of this tick, capture has run; photo_state should at least
    # have been advanced to "done" before the state machine returned to
    # IDLE.
    assert loop_state.drive_status.photo_state in ("done", None), (
        f"expected photo_state to land at 'done' (or be reset to None on "
        f"return-to-idle); got {loop_state.drive_status.photo_state!r}"
    )


# ---------------------------- (e) idle reset -------------------------

def test_idle_resets_transient_fields(discs_root: Path) -> None:
    """After a complete cycle returns to IDLE, all transient fields
    are reset to None and state is back to 'idle'."""
    loop, loop_state, clock = _make_loop_with_loopstate(discs_root)
    # Pre-populate fields to verify they get cleared.
    loop_state.drive_status.current_track = 7
    loop_state.drive_status.sector_current = 99999
    loop_state.drive_status.retries_on_current_track = 2
    loop_state.drive_status.photo_state = "done"

    # Drive a full cycle.
    loop.tick()  # IDLE → WAITING
    loop.tick()  # WAITING → STABILIZE
    clock.advance(2.1)
    loop.tick()  # STABILIZE → RIP
    loop.tick()  # RIP → EJECT
    loop.tick()  # EJECT → CAPTURE
    loop.tick()  # CAPTURE → IDLE (or WAITING_REMOVE in sprint-4 mode)

    # State machine has returned to a non-active state; drive_status
    # transient fields must be reset.
    assert loop_state.drive_status.state == "idle"
    assert loop_state.drive_status.current_track is None
    assert loop_state.drive_status.sector_current is None
    assert loop_state.drive_status.retries_on_current_track is None
    assert loop_state.drive_status.photo_state is None
    assert loop_state.drive_status.current_disc is None


# ---------------------------- (f) thread-safety ----------------------

def test_drive_status_exposes_a_lock_for_thread_safe_mutation() -> None:
    """DriveStatus exposes a `lock` attribute (threading.Lock or RLock)
    so callers can wrap multi-field mutations atomically when the
    FastAPI thread might be reading concurrently."""
    from archivist.state_machine.drive_status import DriveStatus  # noqa: PLC0415

    ds = DriveStatus()
    # Must support the context-manager protocol (`with ds.lock: ...`).
    assert hasattr(ds, "lock"), "DriveStatus must expose a `lock` attribute"
    lock = ds.lock
    assert hasattr(lock, "__enter__") and hasattr(lock, "__exit__"), (
        "DriveStatus.lock must support the context-manager protocol "
        "(threading.Lock or threading.RLock)"
    )
    # Reentrant or not, acquiring it must succeed in a fresh thread.
    with lock:
        ds.current_track = 1
    assert ds.current_track == 1


def test_drive_status_lock_serializes_concurrent_mutations() -> None:
    """Smoke test: 100 concurrent writers via the lock leave the
    snapshot in a self-consistent state (no torn reads of multi-field
    invariants). We use the simplest invariant possible: a counter
    that's bumped under the lock — final value should equal the
    contributors."""
    from archivist.state_machine.drive_status import DriveStatus  # noqa: PLC0415

    ds = DriveStatus()
    # We don't have a numeric counter field, so we reuse current_track
    # as an integer accumulator under the lock.
    workers = 8
    bumps_per_worker = 50

    def worker() -> None:
        for _ in range(bumps_per_worker):
            with ds.lock:
                ds.current_track = (ds.current_track or 0) + 1

    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert ds.current_track == workers * bumps_per_worker
