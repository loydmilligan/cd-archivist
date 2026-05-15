"""The archivist state machine — heart of sprint-2.

Glues the sprint-1 driver primitives + pipeline functions into a
poll-driven cycle:

    IDLE → WAITING → STABILIZE → CAPTURE → RIP → EJECT → IDLE

`tick()` advances at most one state per call. Capture and rip each
run synchronously within their transition tick (CAPTURE folds into
STABILIZE→RIP; the captures get attached when RIP→EJECT writes the
final manifest).

Invariants the impl preserves:
  - cdplay.service stop/start are paired via try/finally — even an
    exception inside RIP triggers the restart before it re-raises.
    cdplay must never be left stopped.
  - LED is restored (delegated to `capture_disc`'s own finally).
  - `prepare_disc_folder` is idempotent and runs exactly once per
    cycle.
  - `next_disc_id` reserves the id by mkdir-ing inside its lockfile
    so concurrent loops on the same root cannot collide.
"""
from __future__ import annotations

import enum
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from archivist.models.manifest import read_manifest, write_manifest
from archivist.pipeline.capture import capture_disc
from archivist.pipeline.disc_id import next_disc_id
from archivist.pipeline.folder import prepare_disc_folder
from archivist.pipeline.pairing import attach_pairing, make_pairing
from archivist.pipeline.rip import rip_disc

logger = logging.getLogger(__name__)

_STABILIZE_SECONDS = 2.0
_CDPLAY = "cdplay.service"


class State(enum.Enum):
    IDLE = "IDLE"
    WAITING = "WAITING"
    STABILIZE = "STABILIZE"
    CAPTURE = "CAPTURE"
    RIP = "RIP"
    EJECT = "EJECT"


@dataclass
class _Cycle:
    """Per-cycle scratch state — cleared on every EJECT→IDLE."""

    disc_id: str | None = None
    disc_dir: Path | None = None
    captures: list[Any] | None = None


class ArchivistLoop:
    """Poll-driven state machine. Construct once, call tick() forever."""

    def __init__(
        self,
        *,
        discs_root: Path,
        device: Path,
        drive: Any,              # callable returning DriveStatus, plus .eject(device)
        ripper: Any,
        camera: Callable[..., Path | None],
        led: Any,
        services: Any,           # .stop_unit(name), .start_unit(name)
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
        loop_state: Any | None = None,
    ) -> None:
        self._discs_root = discs_root
        self._device = device
        self._drive = drive
        self._ripper = ripper
        self._camera = camera
        self._led = led
        self._services = services
        self._clock = clock
        self._sleeper = sleeper
        self._loop_state = loop_state

        self.state: State = State.IDLE
        self._stabilize_since: float | None = None
        self._cdplay_stopped: bool = False
        self._cycle = _Cycle()

    # ------------------------- public API -----------------------------

    def tick(self) -> State:
        try:
            self._advance()
        except Exception:
            # Crash recovery: if we stopped cdplay but haven't restarted
            # it, do so now before the exception escapes. The player must
            # never be left stopped.
            if self._cdplay_stopped:
                try:
                    self._services.start_unit(_CDPLAY)
                finally:
                    self._cdplay_stopped = False
            raise
        return self.state

    # ------------------------- transitions ----------------------------

    def _advance(self) -> None:
        if self.state == State.IDLE:
            self._from_idle()
        elif self.state == State.WAITING:
            self._from_waiting()
        elif self.state == State.STABILIZE:
            self._from_stabilize()
        elif self.state == State.RIP:
            self._from_rip()
        elif self.state == State.EJECT:
            self._from_eject()
        # CAPTURE is folded into the STABILIZE→RIP tick; it never sits
        # as a stable state between ticks.

    def _from_idle(self) -> None:
        status = self._drive()
        if status in ("tray-open", "disc-ok"):
            self._set_state(State.WAITING)

    def _from_waiting(self) -> None:
        status = self._drive()
        if status == "disc-ok":
            self._stabilize_since = self._clock()
            self._set_state(State.STABILIZE)
        elif status == "no-disc":
            self._set_state(State.IDLE)
        # tray-open: stay in WAITING

    def _from_stabilize(self) -> None:
        assert self._stabilize_since is not None
        elapsed = self._clock() - self._stabilize_since
        if elapsed < _STABILIZE_SECONDS:
            return

        # 2s elapsed — claim the drive, do the capture, then move to RIP.
        if not self._services.stop_unit(_CDPLAY):
            logger.warning("stop_unit(%s) returned False — proceeding with rip", _CDPLAY)
        self._cdplay_stopped = True

        disc_id = next_disc_id(self._discs_root)
        disc_dir = prepare_disc_folder(disc_id, self._discs_root)
        self._cycle = _Cycle(disc_id=disc_id, disc_dir=disc_dir)

        # CAPTURE runs synchronously here. LED dance + camera bursts.
        self._cycle.captures = capture_disc(
            disc_dir,
            camera=self._camera,
            led=self._led,
        )

        self._set_state(State.RIP, disc_id=disc_id)

    def _from_rip(self) -> None:
        assert self._cycle.disc_dir is not None
        assert self._cycle.captures is not None

        rip_record = rip_disc(self._cycle.disc_dir, self._device, ripper=self._ripper)
        pairing = make_pairing("single_session")

        manifest_path = self._cycle.disc_dir / "manifest.json"
        manifest = read_manifest(manifest_path)
        manifest = manifest.model_copy(
            update={
                "status": "ripped",
                "captures": [*manifest.captures, *self._cycle.captures],
                "rips": [*manifest.rips, rip_record],
            }
        )
        manifest = attach_pairing(manifest, pairing)
        write_manifest(manifest_path, manifest)

        self._set_state(State.EJECT, last_rip_status=rip_record.status)

    def _from_eject(self) -> None:
        try:
            self._drive.eject(self._device)
        finally:
            if self._cdplay_stopped:
                self._services.start_unit(_CDPLAY)
                self._cdplay_stopped = False
        self._cycle = _Cycle()
        self._stabilize_since = None
        self._set_state(State.IDLE, disc_id=None)

    # ------------------------- helpers --------------------------------

    def _set_state(self, new_state: State, **patch: Any) -> None:
        self.state = new_state
        if self._loop_state is None:
            return
        # Update the snapshot the FastAPI service reads.
        self._loop_state.state = new_state.value
        self._loop_state.last_updated = datetime.now(UTC)
        for k, v in patch.items():
            if hasattr(self._loop_state, k):
                setattr(self._loop_state, k, v)


def run(loop: ArchivistLoop, *, poll_interval: float = 2.0) -> None:
    """Top-level driver — `while True: tick(); sleep(poll_interval)`.

    Suitable for being launched from `archivist/__main__.py`. Exits
    cleanly on KeyboardInterrupt; the entrypoint owns SIGTERM handling.
    """
    while True:
        try:
            loop.tick()
        except KeyboardInterrupt:
            raise
        except Exception:
            # Log and continue — the loop is the heartbeat; one bad disc
            # shouldn't stop the rig.
            logger.exception("tick raised; continuing after delay")
        loop._sleeper(poll_interval)  # noqa: SLF001 — module-internal driver
