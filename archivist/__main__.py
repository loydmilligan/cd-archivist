"""CLI entrypoint — boots the FastAPI service and the state-machine loop.

Run as `python -m archivist`. Defaults match the bare-metal CM4 rig
documented in docs/operations/cm4-setup.md; override via env vars.

Container-readiness (forward-compat — sprint-3 may pick Docker, may
stay bare-metal): config comes from env vars only, logging goes to
both stderr and the configured log file (line-buffered so `docker
logs` would work), and SIGTERM cleanly stops both the uvicorn server
and the state-machine loop.
"""
from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path
from types import FrameType
from typing import Any

import uvicorn

from archivist.drivers import systemctl
from archivist.drivers.camera import capture_frame_with_recovery
from archivist.drivers.drive import eject, read_drive_status
from archivist.drivers.led import LEDPanel
from archivist.drivers.ripper import CDAudioRipper
from archivist.drivers.usb_discovery import discover_camera_usb_path
from archivist.service.app import LoopState, create_app
from archivist.state_machine.loop import ArchivistLoop

logger = logging.getLogger("archivist")

# Defaults are documented in cm4-setup.md.
_DEFAULT_DEVICE = "/dev/sr0"
_DEFAULT_DISCS_ROOT = "/srv/cd-archivist/discs"  # legacy (pre-sprint-4)
_DEFAULT_LOG_PATH = "/srv/cd-archivist/logs/archivist.log"
_DEFAULT_PORT = 8228  # D-port-8228
_DEFAULT_LED_BASE = "http://192.168.5.186"
_DEFAULT_VIDEO_DEVICE = "/dev/video0"

# Sprint-4 / D-music-pipeline-paths: env-driven inbox/working/failed.
_DEFAULT_MUSIC_INBOX = "~/music-pipeline/inbox"
_DEFAULT_MUSIC_WORKING = "~/music-pipeline/.ripping"
_DEFAULT_MUSIC_FAILED = "~/music-pipeline/failed"


def _resolve_music_paths() -> tuple[Path, Path, Path]:
    """Resolve `MUSIC_{INBOX,WORKING,FAILED}_DIR` per D-music-pipeline-paths.

    Legacy `ARCHIVIST_DISCS_ROOT` is honoured as an alias for the inbox
    when neither the new env vars nor the legacy default suffice; logs a
    deprecation warning so operators see the migration path.
    """
    legacy_root = os.environ.get("ARCHIVIST_DISCS_ROOT")
    inbox_env = os.environ.get("MUSIC_INBOX_DIR")
    working_env = os.environ.get("MUSIC_WORKING_DIR")
    failed_env = os.environ.get("MUSIC_FAILED_DIR")

    if legacy_root and not inbox_env:
        logger.warning(
            "ARCHIVIST_DISCS_ROOT is deprecated; please set MUSIC_INBOX_DIR "
            "(and optionally MUSIC_WORKING_DIR / MUSIC_FAILED_DIR). "
            "Aliasing to MUSIC_INBOX_DIR=%s for this run.",
            legacy_root,
        )
        inbox_env = legacy_root

    inbox = Path(os.path.expanduser(inbox_env or _DEFAULT_MUSIC_INBOX))
    working = Path(os.path.expanduser(working_env or _DEFAULT_MUSIC_WORKING))
    failed = Path(os.path.expanduser(failed_env or _DEFAULT_MUSIC_FAILED))
    return inbox, working, failed


class _DriveAdapter:
    """Bundle `read_drive_status` + `eject` into the object the loop wants."""

    def __init__(self, device: Path) -> None:
        self._device = device

    def __call__(self) -> str:
        return read_drive_status(self._device)

    def eject(self, device: Path) -> bool:
        return eject(device)


def _configure_logging(log_path: Path) -> None:
    """Attach stderr + optional file logging; degrade gracefully.

    Sprint-3 / test-log-fallback: if `log_path.parent` cannot be
    created (e.g. running on a laptop dev shell against the default
    `/srv/cd-archivist/logs/`), or if the FileHandler cannot be
    constructed, log a clear warning naming the path + the
    ARCHIVIST_LOG_PATH env var, fall back to stderr-only, and never
    raise. The FastAPI surface must come up regardless.
    """
    file_handler_error: Exception | None = None
    file_handler: logging.Handler | None = None

    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        file_handler_error = exc
    else:
        try:
            file_handler = logging.FileHandler(log_path, encoding="utf-8")
        except OSError as exc:
            file_handler_error = exc

    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s — %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(fmt)
    root.addHandler(stream)

    if file_handler is not None:
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)

    # Quiet uvicorn's access log down a notch — the loop is the heartbeat.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    if file_handler_error is not None:
        logger.warning(
            "log file unwritable at %s (%s); falling back to stderr-only. "
            "Override with ARCHIVIST_LOG_PATH.",
            log_path,
            file_handler_error,
        )


def _build_camera(discover: Any) -> Any:
    """Curry capture_frame_with_recovery with the discovery callable."""

    def camera(device: Path, out_path: Path, *, frames: int = 15) -> Path | None:
        return capture_frame_with_recovery(
            device,
            out_path,
            frames=frames,
            discover_usb_path=discover,
        )

    return camera


class _Services:
    """Adapt the systemctl module to the .stop_unit/.start_unit interface."""

    def stop_unit(self, name: str) -> bool:
        return systemctl.stop_unit(name)

    def start_unit(self, name: str) -> bool:
        return systemctl.start_unit(name)


def _start_uvicorn(app: Any, port: int) -> tuple[uvicorn.Server, threading.Thread]:
    config = uvicorn.Config(
        app,
        host="0.0.0.0",  # noqa: S104 — intentional: the rig is on a trusted LAN
        port=port,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(config)
    # Prevent uvicorn from installing its own signal handlers; we own them.
    server.install_signal_handlers = lambda: None  # type: ignore[method-assign]

    thread = threading.Thread(target=server.run, name="uvicorn", daemon=True)
    thread.start()
    return server, thread


def main() -> int:
    device = Path(os.environ.get("ARCHIVIST_DEVICE", _DEFAULT_DEVICE))
    log_path = Path(os.environ.get("ARCHIVIST_LOG_PATH", _DEFAULT_LOG_PATH))
    port = int(os.environ.get("ARCHIVIST_PORT", str(_DEFAULT_PORT)))
    led_base = os.environ.get("ARCHIVIST_LED_BASE", _DEFAULT_LED_BASE)
    video_device = Path(os.environ.get("ARCHIVIST_VIDEO_DEVICE", _DEFAULT_VIDEO_DEVICE))

    _configure_logging(log_path)
    inbox_dir, working_dir, failed_dir = _resolve_music_paths()
    for d in (inbox_dir, working_dir, failed_dir):
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.error("cannot create music-pipeline dir %s: %s", d, exc)
            raise

    initial_mode = os.environ.get("ARCHIVIST_MODE", "auto")
    if initial_mode not in ("auto", "manual"):
        logger.warning("ARCHIVIST_MODE=%r invalid; falling back to auto", initial_mode)
        initial_mode = "auto"

    # Sprint-4 / D-process-ready-trigger: post-rip hook command. Defaults
    # to the dogfood path; empty string disables.
    process_ready_hook = os.environ.get(
        "ARCHIVIST_PROCESS_READY_HOOK",
        "/srv/cd-music-stack/bin/process-ready-auto",
    )

    logger.info(
        "starting archivist — device=%s inbox=%s working=%s failed=%s mode=%s port=%d",
        device, inbox_dir, working_dir, failed_dir, initial_mode, port,
    )

    # Camera USB autodiscover — primary; ARCHIVIST_CAMERA_USB_PATH is the fallback
    # (consumed inside discover_camera_usb_path per D-camera-autodiscover).
    usb_path = discover_camera_usb_path()
    if usb_path:
        logger.info("camera usb bus path: %s", usb_path)
    else:
        logger.warning(
            "camera USB path not resolved — captures will be skipped if ffmpeg cannot open %s",
            video_device,
        )

    loop_state = LoopState(mode=initial_mode, process_ready_hook=process_ready_hook)
    camera = _build_camera(discover_camera_usb_path)
    led = LEDPanel(led_base)

    loop = ArchivistLoop(
        working_dir=working_dir,
        inbox_dir=inbox_dir,
        failed_dir=failed_dir,
        device=device,
        drive=_DriveAdapter(device),
        ripper=CDAudioRipper(),
        camera=camera,
        led=led,
        services=_Services(),
        clock=time.monotonic,
        sleeper=time.sleep,
        loop_state=loop_state,
    )

    # /library reads from the inbox (where READY-marked folders live) plus
    # any legacy disc roots from ARCHIVIST_LEGACY_DISCS_ROOTS (colon-separated
    # paths, like $PATH). Sprint-1-3 wrote to ~/cd-archivist-data/discs/ —
    # those folders aren't in the new inbox but should still surface in /library.
    legacy_raw = os.environ.get("ARCHIVIST_LEGACY_DISCS_ROOTS", "")
    legacy_roots = tuple(
        Path(os.path.expanduser(p.strip()))
        for p in legacy_raw.split(":")
        if p.strip()
    )
    if legacy_roots:
        logger.info("library legacy roots: %s", [str(p) for p in legacy_roots])
    music_root_env = os.environ.get("MUSIC_ROOT")
    music_root = Path(music_root_env) if music_root_env else inbox_dir.parent
    app = create_app(
        loop_state, log_path,
        discs_root=inbox_dir,
        legacy_discs_roots=legacy_roots,
        recapture_camera=camera,
        recapture_led=led,
        loop=loop,
        music_root=music_root,
    )
    server, server_thread = _start_uvicorn(app, port)

    shutdown = threading.Event()

    def _sigterm(_signum: int, _frame: FrameType | None) -> None:
        logger.info("received signal; shutting down")
        shutdown.set()
        server.should_exit = True

    signal.signal(signal.SIGTERM, _sigterm)
    signal.signal(signal.SIGINT, _sigterm)

    poll_interval = 2.0
    try:
        while not shutdown.is_set():
            try:
                loop.tick()
            except Exception:
                logger.exception("tick raised; continuing")
            shutdown.wait(timeout=poll_interval)
    finally:
        server.should_exit = True
        server_thread.join(timeout=5.0)
        logger.info("archivist stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
