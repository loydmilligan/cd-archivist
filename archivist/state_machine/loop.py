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
import os
import socket
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from archivist.models.manifest import read_manifest, write_manifest
from archivist.models.source import write_source_json
from archivist.pipeline.capture import capture_disc, copy_canonical_photo
from archivist.pipeline.disc_id import next_disc_id
from archivist.pipeline.folder import prepare_disc_folder
from archivist.pipeline.folder_name import next_disc_folder_name
from archivist.pipeline.pairing import attach_pairing, make_pairing
from archivist.pipeline.post_rip_hook import run_process_ready_hook
from archivist.pipeline.rip import cleanup_wavs, rip_disc
from archivist.pipeline.rip_progress import parse_cdparanoia_progress
from archivist.pipeline.source_json import build_source_json

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
    # Sprint-4 / D-waiting-remove-state: post-EJECT gate on physical removal.
    WAITING_REMOVE = "WAITING_REMOVE"


@dataclass
class _Timestamps:
    inserted_at: datetime | None = None
    rip_started_at: datetime | None = None
    rip_finished_at: datetime | None = None
    ejected_at: datetime | None = None
    photo_captured_at: datetime | None = None


@dataclass
class _CaptureResult:
    photo_path: Path | None = None
    photo_device: str | None = None
    error: str | None = None


@dataclass
class _DriveInfo:
    device: str = "/dev/sr0"
    model: str | None = None
    serial: str | None = None
    read_offset: int | None = None


@dataclass
class _Cycle:
    """Per-cycle scratch state — cleared on every EJECT→IDLE."""

    disc_id: str | None = None
    disc_dir: Path | None = None
    captures: list[Any] | None = None
    # Sprint-4: timestamps + capture result tracked for source.json build.
    timestamps: _Timestamps = field(default_factory=_Timestamps)
    capture_result: _CaptureResult = field(default_factory=_CaptureResult)
    rip_error: str | None = None
    rip_record: Any = None
    # Sprint-5 / D-disc-id-libdiscid: captured once at rip start
    # (before tray-open) and threaded through into source.json.
    disc_id_mb: str | None = None


class ArchivistLoop:
    """Poll-driven state machine. Construct once, call tick() forever."""

    def __init__(
        self,
        *,
        device: Path,
        drive: Any,              # callable returning DriveStatus, plus .eject(device)
        ripper: Any,
        camera: Callable[..., Path | None],
        led: Any,
        services: Any,           # .stop_unit(name), .start_unit(name)
        # Path config — either pass legacy single-root `discs_root` (sprint-3
        # tests) OR the sprint-4 triple `working_dir`/`inbox_dir`/`failed_dir`
        # (new flow per D-music-pipeline-paths + working-dir-handoff).
        discs_root: Path | None = None,
        working_dir: Path | None = None,
        inbox_dir: Path | None = None,
        failed_dir: Path | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
        loop_state: Any | None = None,
    ) -> None:
        # Dual-mode path config: sprint-3 (single root) vs sprint-4 (triple).
        if working_dir is not None and inbox_dir is not None:
            self._working_dir = working_dir
            self._inbox_dir = inbox_dir
            self._failed_dir = failed_dir or (inbox_dir.parent / "failed")
            self._sprint4_mode = True
            # Convenience alias so legacy code paths can still reach a
            # single root if needed.
            self._discs_root = working_dir
        elif discs_root is not None:
            self._discs_root = discs_root
            self._working_dir = discs_root
            self._inbox_dir = discs_root
            self._failed_dir = discs_root
            self._sprint4_mode = False
        else:
            raise TypeError(
                "ArchivistLoop requires either `discs_root` (legacy) or the "
                "`working_dir`+`inbox_dir` pair (sprint-4)."
            )

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
        # Sprint-4 / manual-mode: queued advance trigger consumed at tick().
        self._pending_trigger: str | None = None

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

    # ----- sprint-4: manual-mode public trigger API -------------------

    # Trigger → state in which the trigger is meaningful. Anything else
    # is a no-op (the HTTP layer surfaces 409; the state-machine just
    # ignores).
    _TRIGGER_STATES: dict[str, "State"] = {}  # populated below via class init

    def advance(self, trigger: str) -> None:
        """Operator-driven trigger.

        Triggers: "rip" | "eject" | "capture" | "reset".

        `reset` is the always-allowed escape hatch — runs immediately.
        Other triggers run synchronously when the current state matches
        the trigger's gate, and are no-ops otherwise.
        """
        if trigger == "reset":
            self._do_reset()
            return
        expected = ArchivistLoop._TRIGGER_STATES.get(trigger)
        if expected is None or self.state != expected:
            return  # no-op
        self._pending_trigger = trigger
        try:
            self._advance()
        except Exception:
            if self._cdplay_stopped:
                try:
                    self._services.start_unit(_CDPLAY)
                finally:
                    self._cdplay_stopped = False
            raise

    def _do_reset(self) -> None:
        if self._cdplay_stopped:
            try:
                self._services.start_unit(_CDPLAY)
            finally:
                self._cdplay_stopped = False
        self._cycle = _Cycle()
        self._stabilize_since = None
        self._pending_trigger = None
        self._set_state(State.IDLE, disc_id=None)

    def _is_manual(self) -> bool:
        return getattr(self._loop_state, "mode", "auto") == "manual"

    def _consume_trigger(self, name: str) -> bool:
        if self._pending_trigger == name:
            self._pending_trigger = None
            return True
        return False

    # ------------------------------------------------------------------

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
        elif self.state == State.WAITING_REMOVE:
            self._from_waiting_remove()

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

        if self._is_manual():
            # In manual mode, hold here until advance("rip") fires.
            if not self._consume_trigger("rip"):
                return
        else:
            elapsed = self._clock() - self._stabilize_since
            if elapsed < _STABILIZE_SECONDS:
                return

        # Claim the drive, then move to RIP. Capture runs post-eject now
        # (D-eject-time-capture).
        if not self._services.stop_unit(_CDPLAY):
            logger.warning("stop_unit(%s) returned False — proceeding with rip", _CDPLAY)
        self._cdplay_stopped = True

        if self._sprint4_mode:
            folder_name = next_disc_folder_name(self._inbox_dir)
            disc_dir = self._working_dir / folder_name
            disc_dir.mkdir(parents=True, exist_ok=False)
            for sub in ("captures", "audio", "logs", "review"):
                (disc_dir / sub).mkdir(parents=True, exist_ok=True)
            ts = _Timestamps(inserted_at=datetime.now().astimezone())
            # Sprint-5: read MusicBrainz disc-id once at rip start (while
            # the disc is still in the drive). Lazy-imported so the loop
            # works even when libdiscid + the drivers helper aren't
            # installed (e.g. dev machines without the apt package).
            mb_disc_id = _read_mb_disc_id(self._device)
            self._cycle = _Cycle(
                disc_id=folder_name, disc_dir=disc_dir, timestamps=ts,
                disc_id_mb=mb_disc_id,
            )
            self._set_state(State.RIP, disc_id=folder_name)
            return

        disc_id = next_disc_id(self._discs_root)
        disc_dir = prepare_disc_folder(disc_id, self._discs_root)
        self._cycle = _Cycle(disc_id=disc_id, disc_dir=disc_dir)
        self._set_state(State.RIP, disc_id=disc_id)

    def _from_rip(self) -> None:
        """Run the rip; on failure (raise OR status=fail) park in ERROR.

        Sprint-3 / impl-rip-error-recovery preserved. Sprint-4 / impl-
        working-dir-handoff + impl-failed-marker fork: when the loop is
        configured with the new path triple, the failure path writes
        FAILED + source.json + rip.log under working_dir then moves the
        folder to failed_dir; otherwise the legacy manifest.json write
        runs.
        """
        assert self._cycle.disc_dir is not None

        # If the rip has already run this cycle, we're holding in RIP
        # waiting for advance("eject") (manual mode only).
        if self._cycle.rip_record is not None and self._cycle.rip_error is None:
            if self._is_manual() and not self._consume_trigger("eject"):
                return
            last_rip = self._cycle.rip_record.status
            self._set_state(State.EJECT, last_rip_status=last_rip)
            return

        rip_record = None
        rip_error: str | None = None

        def _on_progress(line: str) -> None:
            label = parse_cdparanoia_progress(line)
            if label is not None and self._loop_state is not None:
                self._loop_state.rip_progress = label

        self._cycle.timestamps.rip_started_at = datetime.now().astimezone()
        try:
            rip_record = rip_disc(
                self._cycle.disc_dir,
                self._device,
                ripper=self._ripper,
                progress_callback=_on_progress,
            )
        except Exception as exc:
            rip_error = f"{type(exc).__name__}: {exc}"
            logger.exception("rip_disc raised; transitioning to ERROR")
        finally:
            if self._loop_state is not None:
                self._loop_state.rip_progress = None
            self._cycle.timestamps.rip_finished_at = datetime.now().astimezone()

        self._cycle.rip_record = rip_record
        self._cycle.rip_error = rip_error

        if self._sprint4_mode:
            self._from_rip_sprint4(rip_record, rip_error)
            return

        # Legacy path (sprint-3) — manifest.json.
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

        if new_status == "rip_failed":
            if self._cdplay_stopped:
                self._services.start_unit(_CDPLAY)
                self._cdplay_stopped = False
            self._set_state(State.ERROR, last_rip_status=last_rip)
            return

        self._set_state(State.EJECT, last_rip_status=last_rip)

    def _from_rip_sprint4(self, rip_record: Any, rip_error: str | None) -> None:
        """Sprint-4 RIP path: writes per-disc rip.log; routes success/fail."""
        assert self._cycle.disc_dir is not None
        disc_dir = self._cycle.disc_dir

        # Append to the per-disc rip.log (cdparanoia stderr already routed
        # to it via the progress callback in production; in tests, the
        # FakeRipper writes a minimal rip.log alongside the audio).
        rip_log = disc_dir / "rip.log"
        if not rip_log.exists():
            rip_log.write_text(
                f"[{datetime.now().astimezone().isoformat()}] "
                f"rip completed status={getattr(rip_record, 'status', 'unknown')}\n",
                encoding="utf-8",
            )

        failed = (rip_record is None) or (rip_record.status == "fail")
        last_rip = "fail" if failed else rip_record.status

        if failed:
            # Write FAILED marker, source.json (failure shape), then move
            # folder to failed_dir.
            self._write_failed_marker(disc_dir, rip_error)
            self._write_source_json_for_cycle(disc_dir)
            try:
                target = self._failed_dir / disc_dir.name
                self._failed_dir.mkdir(parents=True, exist_ok=True)
                os.replace(disc_dir, target)
            except OSError:
                logger.exception("failed→failed_dir move failed; folder left in working_dir")

            if self._cdplay_stopped:
                self._services.start_unit(_CDPLAY)
                self._cdplay_stopped = False
            self._set_state(State.ERROR, last_rip_status=last_rip)
            return

        # Sprint-5 / impl-wav-cleanup-fix: clean up source WAVs as soon
        # as the rip succeeds — BEFORE the EJECT/CAPTURE handoff so the
        # inbox-stuck importer never sees them. Sprint-4's cleanup helper
        # was correct but never called from the state machine; STP rip
        # leaked WAVs because of this missing call site.
        try:
            keep = _env_truthy(os.environ.get("ARCHIVIST_KEEP_WAVS", ""))
            audio_dir = disc_dir / "audio"
            if audio_dir.is_dir():
                cleanup_wavs(audio_dir, keep=keep)
        except (OSError, FileNotFoundError):
            logger.exception("cleanup_wavs raised; continuing")

        # Manual mode: hold in RIP unless advance("eject") is pending
        # (operator's stated intent: "rip then advance to eject").
        if self._is_manual() and not self._consume_trigger("eject"):
            return
        self._set_state(State.EJECT, last_rip_status=last_rip)

    def _write_failed_marker(self, disc_dir: Path, rip_error: str | None) -> None:
        reason = rip_error or "rip status: fail"
        marker = disc_dir / "FAILED"
        marker.write_text(
            f"failed_at={datetime.now().astimezone().isoformat()}\n"
            f"reason={reason}\n",
            encoding="utf-8",
        )

    def _write_source_json_for_cycle(self, disc_dir: Path) -> None:
        ts = self._cycle.timestamps
        # Default any missing timestamps to now so the model validates.
        now = datetime.now().astimezone()
        ts.inserted_at = ts.inserted_at or now
        ts.rip_started_at = ts.rip_started_at or now
        ts.rip_finished_at = ts.rip_finished_at or now
        ts.ejected_at = ts.ejected_at or now
        try:
            source = build_source_json(
                disc_dir,
                ripper_name="cd-archivist",
                ripper_version="0.1.0",
                hostname=socket.gethostname(),
                drive_info=_DriveInfo(device=str(self._device)),
                rip_record=self._cycle.rip_record,
                capture_result=self._cycle.capture_result,
                ready_at=now,
                timestamps=ts,
                mb_disc_id=self._cycle.disc_id_mb,
            )
            write_source_json(disc_dir / "source.json", source)
        except Exception:
            logger.exception("build/write source.json failed; continuing")

    def _from_eject(self) -> None:
        """Eject the disc, restart cdplay (paired invariant), then settle.

        Sprint-3: eject + cdplay-restart happen here; then a settle sleep
        (EJECT_SETTLE_SECONDS) covers the 2–4s the tray takes to physically
        open before CAPTURE fires next tick.
        """
        if self._cycle.timestamps.ejected_at is None:
            try:
                self._drive.eject(self._device)
            finally:
                if self._cdplay_stopped:
                    self._services.start_unit(_CDPLAY)
                    self._cdplay_stopped = False
            self._cycle.timestamps.ejected_at = datetime.now().astimezone()
            self._sleeper(_EJECT_SETTLE_SECONDS)

        # Manual mode: advance to CAPTURE only when "capture" trigger fires.
        if self._is_manual() and not self._consume_trigger("capture"):
            return
        self._set_state(State.CAPTURE)

    def _from_capture(self) -> None:
        """Run capture_disc against the now-open tray.

        Sprint-3: writes the second manifest. Sprint-4 mode also picks
        the canonical disc-photo, writes source.json, runs the
        working_dir → inbox handoff, writes READY, and transitions to
        WAITING_REMOVE (NOT IDLE — per D-waiting-remove-state).
        """
        if self._is_manual() and not self._consume_trigger("capture"):
            return

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

        if self._sprint4_mode:
            self._from_capture_sprint4(captures, capture_error)
            return

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

    def _from_capture_sprint4(
        self, captures: list[Any], capture_error: str | None,
    ) -> None:
        assert self._cycle.disc_dir is not None
        disc_dir = self._cycle.disc_dir

        # Pick canonical disc-photo (best-effort).
        photo_path: Path | None = None
        try:
            photo_path = copy_canonical_photo(disc_dir)
        except Exception as exc:
            capture_error = capture_error or f"copy_canonical_photo: {exc}"
            logger.exception("copy_canonical_photo raised")

        self._cycle.capture_result = _CaptureResult(
            photo_path=photo_path,
            photo_device=str(self._device) if photo_path else None,
            error=capture_error,
        )
        if photo_path is not None:
            self._cycle.timestamps.photo_captured_at = datetime.now().astimezone()

        ready_at = datetime.now().astimezone()
        # Write source.json BEFORE the handoff so the inbox folder is
        # contract-complete the moment it appears.
        self._write_source_json_for_cycle(disc_dir)

        # Atomic working → inbox handoff.
        target = self._inbox_dir / disc_dir.name
        try:
            self._inbox_dir.mkdir(parents=True, exist_ok=True)
            os.replace(disc_dir, target)
        except OSError as exc:
            logger.exception("working→inbox move failed; parking in ERROR")
            self._set_state(State.ERROR)
            return

        # Only after the move do we write READY — the inbox is now
        # observable to the importer. Use a .tmp + os.replace so the
        # marker is atomic from the importer's perspective too.
        ready_tmp = target / "READY.tmp"
        ready_marker = target / "READY"
        ready_tmp.write_text(
            f"ready_at={ready_at.isoformat()}\nschema_version=1\n",
            encoding="utf-8",
        )
        os.replace(ready_tmp, ready_marker)

        # Fire-and-forget post-rip hook (D-process-ready-trigger).
        # Helper swallows missing-executable / permission errors so the
        # importer's absence never poisons the state machine.
        hook_cmd = getattr(self._loop_state, "process_ready_hook", "") if self._loop_state else ""
        run_process_ready_hook(hook_cmd)

        self._cycle = _Cycle()
        self._stabilize_since = None
        self._set_state(State.WAITING_REMOVE, disc_id=None)

    def _from_waiting_remove(self) -> None:
        """Gate re-rip on physical disc removal (D-waiting-remove-state)."""
        status = self._drive()
        if status in ("tray-open", "no-disc"):
            self._set_state(State.WAITING if status == "tray-open" else State.IDLE)
        # disc-ok or anything else: stay put. The operator must remove
        # the disc (or hit POST /api/control/reset).

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


ArchivistLoop._TRIGGER_STATES = {
    "rip": State.STABILIZE,
    "eject": State.RIP,
    "capture": State.EJECT,
}


def _env_truthy(value: str) -> bool:
    """Standard env-var truthiness: '1', 'true', 'yes' (case-insensitive)."""
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _read_mb_disc_id(device: Path) -> str | None:
    """Best-effort wrapper around `archivist.drivers.disc_id.read_disc_id`.

    Lazy-import so the absence of the drivers helper (e.g. dev machines
    without libdiscid installed) doesn't break the loop. Any exception
    returns None and logs at debug — D-disc-id-libdiscid commits the
    library to "best-effort, never blocks the rip".
    """
    try:
        from archivist.drivers.disc_id import read_disc_id
    except ImportError:
        return None
    try:
        return read_disc_id(device)
    except Exception:
        logger.debug("read_disc_id raised; treating as None", exc_info=True)
        return None


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
