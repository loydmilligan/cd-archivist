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
_EJECT_SETTLE_SECONDS = 3.0
_CDPLAY = "cdplay.service"


class State(enum.Enum):
    IDLE = "IDLE"
    WAITING = "WAITING"
    STABILIZE = "STABILIZE"
    CAPTURE = "CAPTURE"
    RIP = "RIP"
    EJECT = "EJECT"
    # Sprint-3 / D-rip-failure-error: terminal state on rip failure.
    # Exits only on tray-open → IDLE.
    ERROR = "ERROR"


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
        # Sprint-3 / impl-loop-device-missing: log "device-missing" once
        # per disconnect; reset when the device comes back so the next
        # disconnect is re-logged.
        self._device_missing_logged: bool = False

    # ------------------------- public API -----------------------------

    def tick(self) -> State:
        self._heartbeat()
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
        elif self.state == State.CAPTURE:
            self._from_capture()
        elif self.state == State.ERROR:
            self._from_error()

    def _from_idle(self) -> None:
        status = self._drive()
        if status == "device-missing":
            # Rate-limited: warn once per disconnect, reset on recovery.
            if not self._device_missing_logged:
                logger.warning(
                    "CD-ROM device is missing (read_drive_status='device-missing'); "
                    "loop will stay in IDLE until it reappears"
                )
                self._device_missing_logged = True
            return
        # Any other status counts as the device being present again.
        self._device_missing_logged = False
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

        # 2s elapsed — claim the drive, then move to RIP. Capture runs
        # post-eject now (D-eject-time-capture) so the camera sees the
        # open tray instead of the closed-tray side of the rig.
        if not self._services.stop_unit(_CDPLAY):
            logger.warning("stop_unit(%s) returned False — proceeding with rip", _CDPLAY)
        self._cdplay_stopped = True

        disc_id = next_disc_id(self._discs_root)
        disc_dir = prepare_disc_folder(disc_id, self._discs_root)
        self._cycle = _Cycle(disc_id=disc_id, disc_dir=disc_dir)

        self._set_state(State.RIP, disc_id=disc_id)

    def _from_rip(self) -> None:
        """Run the rip; on failure (raise OR status=fail) park in ERROR.

        Sprint-3 / impl-rip-error-recovery: rip failures land the loop in
        a terminal ERROR state instead of propagating the exception (which
        used to stop the loop entirely). cdplay is restarted, the
        manifest records status="rip_failed", and the operator's only
        exit is to eject the disc (ERROR + tray-open → IDLE).
        """
        assert self._cycle.disc_dir is not None

        rip_record = None
        rip_error: str | None = None
        try:
            rip_record = rip_disc(self._cycle.disc_dir, self._device, ripper=self._ripper)
        except Exception as exc:
            rip_error = f"{type(exc).__name__}: {exc}"
            logger.exception("rip_disc raised; transitioning to ERROR")

        # First manifest write: rip outcome lands here. Captures stay
        # empty — they're added by the second write at end-of-CAPTURE
        # (D-eject-time-capture).
        manifest_path = self._cycle.disc_dir / "manifest.json"
        manifest = read_manifest(manifest_path)

        if rip_record is not None and rip_record.status != "fail":
            new_status = "ripped"
            rips_update = [*manifest.rips, rip_record]
            last_rip = rip_record.status
            errors_update = manifest.errors
        else:
            new_status = "rip_failed"
            rips_update = [*manifest.rips, rip_record] if rip_record is not None else manifest.rips
            last_rip = "fail"
            errors_update = [*manifest.errors] + ([rip_error] if rip_error else [])

        manifest = manifest.model_copy(
            update={
                "status": new_status,
                "rips": rips_update,
                "errors": errors_update,
            }
        )
        manifest = attach_pairing(manifest, make_pairing("single_session"))
        write_manifest(manifest_path, manifest)

        # Failure path restarts cdplay and parks in ERROR — no eject
        # (operator must manually eject the bad disc).
        if new_status == "rip_failed":
            if self._cdplay_stopped:
                self._services.start_unit(_CDPLAY)
                self._cdplay_stopped = False
            self._set_state(State.ERROR, last_rip_status=last_rip)
            return

        self._set_state(State.EJECT, last_rip_status=last_rip)

    def _from_eject(self) -> None:
        """Eject the disc, restart cdplay (paired invariant), then settle.

        Sprint-3: eject + cdplay-restart happen here; then a settle sleep
        (EJECT_SETTLE_SECONDS) covers the 2–4s the tray takes to physically
        open before CAPTURE fires next tick.
        """
        try:
            self._drive.eject(self._device)
        finally:
            if self._cdplay_stopped:
                self._services.start_unit(_CDPLAY)
                self._cdplay_stopped = False
        # Let the tray actually open before the camera fires.
        self._sleeper(_EJECT_SETTLE_SECONDS)
        self._set_state(State.CAPTURE)

    def _from_capture(self) -> None:
        """Run capture_disc against the now-open tray; write second manifest.

        Capture is best-effort: a successful rip already lives in the
        manifest from _from_rip. If capture_disc raises, log the error
        into manifest.errors and proceed to IDLE without disturbing
        the rip record.
        """
        assert self._cycle.disc_dir is not None
        captures: list[Any] = []
        capture_error: str | None = None
        try:
            captures = capture_disc(
                self._cycle.disc_dir,
                camera=self._camera,
                led=self._led,
            )
        except Exception as exc:
            capture_error = f"capture failed: {type(exc).__name__}: {exc}"
            logger.exception("capture_disc raised; preserving rip record")

        manifest_path = self._cycle.disc_dir / "manifest.json"
        manifest = read_manifest(manifest_path)
        updates: dict[str, Any] = {
            "captures": [*manifest.captures, *captures],
        }
        if capture_error is not None:
            updates["errors"] = [*manifest.errors, capture_error]
        manifest = manifest.model_copy(update=updates)
        write_manifest(manifest_path, manifest)

        self._cycle = _Cycle()
        self._stabilize_since = None
        self._set_state(State.IDLE, disc_id=None)

    def _from_error(self) -> None:
        """ERROR is terminal; only tray-open exits back to IDLE."""
        status = self._drive()
        if status == "tray-open":
            self._cycle = _Cycle()
            self._stabilize_since = None
            self._set_state(State.IDLE, disc_id=None)
        # Any other status: stay in ERROR. The operator must eject.

    # ------------------------- helpers --------------------------------

    def _heartbeat(self) -> None:
        """Advance last_tick_at on every tick (not just transitions)."""
        if self._loop_state is not None:
            self._loop_state.last_tick_at = datetime.now(UTC)

    def _set_state(self, new_state: State, **patch: Any) -> None:
        self.state = new_state
        if self._loop_state is None:
            return
        # Update the snapshot the FastAPI service reads. state_entered_at
        # advances ONLY on real transitions; last_tick_at is the heartbeat.
        now = datetime.now(UTC)
        self._loop_state.state = new_state.value
        self._loop_state.state_entered_at = now
        self._loop_state.last_tick_at = now
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
