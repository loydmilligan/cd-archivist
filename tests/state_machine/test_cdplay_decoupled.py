"""Failing tests confirming the state machine no longer invokes
systemctl on `cdplay.service`.

Per sprint-6 Bucket D task `test-cdplay-removed`. Impl lands in
`impl-cdplay-decouple` per `D-cdplay-decouple-not-install`.

Background: every rip on the production CM4 fires
`systemctl stop cdplay.service` (which exits 5 because the unit
doesn't exist) and the paired start in the eject path. The state
machine's cdplay-coexistence wiring (sprint-2 era) is dead weight —
no playback feature exists. Resolution: strip the cdplay calls.
The `systemctl` driver wrapper itself stays for future units.

Contract: a full rip cycle (IDLE → WAITING → STABILIZE → RIP →
EJECT → CAPTURE → IDLE) issues ZERO `cdplay.service` invocations
on the services adapter. The eject driver still fires.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from archivist.drivers.ripper import RipResult
from archivist.state_machine.loop import ArchivistLoop, State
from tests.state_machine.test_loop import (  # type: ignore[import-not-found]
    DEVICE,
    _FakeCamera,
    _FakeDrive,
    _FakeLED,
    _FakeRipper,
    _FakeServices,
    _Clock,
)


@pytest.fixture
def discs_root(tmp_disc_root) -> Path:
    return tmp_disc_root()


def _make_loop_for_cdplay_test(discs_root: Path):
    """Mirror of test_loop._make_loop but returns the services + drive
    so we can introspect both in the assertion."""
    audio_dir = discs_root / "CD_0001" / "audio"
    drive = _FakeDrive(
        # Full happy-path cycle ending with tray-open at eject.
        ["disc-ok", "disc-ok", "disc-ok", "disc-ok",
         "tray-open", "tray-open"]
    )
    ripper = _FakeRipper(
        RipResult(
            status="success",
            tracks=[audio_dir / "track01.flac"],
            errors=[],
        )
    )
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
    return loop, drive, services, clock


def _drive_full_cycle(loop: ArchivistLoop, clock: _Clock) -> None:
    """IDLE → WAITING → STABILIZE → RIP → EJECT → CAPTURE → IDLE."""
    loop.tick()  # IDLE -> WAITING
    loop.tick()  # WAITING -> STABILIZE
    clock.advance(2.1)  # past STABILIZE_SECONDS
    loop.tick()  # STABILIZE -> RIP
    loop.tick()  # RIP -> EJECT
    loop.tick()  # EJECT -> CAPTURE
    loop.tick()  # CAPTURE -> IDLE


# ---------------------- services not called with cdplay -------------

def test_full_rip_cycle_makes_no_cdplay_service_calls(
    discs_root: Path,
) -> None:
    """No service event mentions cdplay.service after a full rip cycle.

    The legacy stop/start pair fired on every rip on production with
    exit-5 warnings; D-cdplay-decouple-not-install removes them.
    """
    loop, _drive, services, clock = _make_loop_for_cdplay_test(discs_root)
    _drive_full_cycle(loop, clock)

    cdplay_events = [e for e in services.events if "cdplay.service" in e]
    assert cdplay_events == [], (
        f"expected zero cdplay.service service-events; got {cdplay_events!r}\n"
        f"full events: {services.events!r}"
    )


def test_full_rip_cycle_makes_no_services_calls_at_all(
    discs_root: Path,
) -> None:
    """No service calls of any kind during a normal rip — there are no
    other systemd units the state machine touches today.

    If future units land (sprint-7+), this test gets relaxed to allow
    those specific names; for now, services.events must be empty.
    """
    loop, _drive, services, clock = _make_loop_for_cdplay_test(discs_root)
    _drive_full_cycle(loop, clock)

    assert services.events == [], (
        f"unexpected service events during rip: {services.events!r}"
    )


# ---------------------- eject still fires ---------------------------

def test_eject_still_fires_via_driver(discs_root: Path) -> None:
    """The eject driver is the only post-rip path now — must still fire."""
    loop, drive, _services, clock = _make_loop_for_cdplay_test(discs_root)
    _drive_full_cycle(loop, clock)

    assert drive.eject_calls == [DEVICE], (
        f"expected one eject() invocation on {DEVICE}; got "
        f"{drive.eject_calls!r}"
    )


# ---------------------- loop reaches IDLE without cdplay ------------

def test_loop_reaches_idle_after_cycle_without_cdplay(
    discs_root: Path,
) -> None:
    """Full cycle still terminates cleanly at IDLE post-decouple.

    Smoke check that the cdplay-decouple impl doesn't accidentally
    break the eject→capture→idle sequencing.
    """
    loop, _drive, _services, clock = _make_loop_for_cdplay_test(discs_root)
    _drive_full_cycle(loop, clock)

    assert loop.state == State.IDLE
