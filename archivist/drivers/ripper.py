"""Audio-CD ripper: cdparanoia → flac, wrapped behind a Ripper Protocol.

Per sprint-1 task impl-ripper. The pluggable Ripper interface lets
sprint-2 add DataDiscRipper / DVDVideoRipper without touching this
module's call sites.

Sprint-3 (impl-rip-stderr-stream) refactors the cdparanoia call from
`subprocess.run(..., capture_output=True)` to `subprocess.Popen` with
line-iterated stderr so callers see progress lines as they arrive
(not buffered until exit). Motivation: the 2026-05-14 real-rig rip
exited 0, produced no WAVs, and surfaced zero diagnostic context
because everything was buffered.
"""
from __future__ import annotations

import fcntl
import logging
import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

_logger = logging.getLogger(__name__)

# include/uapi/linux/cdrom.h
CDROM_DISC_STATUS = 0x5327
CDS_AUDIO = 100

RipStatus = Literal["success", "partial", "fail"]


@dataclass
class RipResult:
    status: RipStatus
    tracks: list[Path]
    errors: list[str] = field(default_factory=list)


class Ripper(Protocol):
    media_types: set[str]

    def detect(self, device: Path) -> str | None: ...

    def rip(self, device: Path, out_dir: Path) -> RipResult: ...


class CDAudioRipper:
    """Rips audio CDs to FLAC via cdparanoia + flac."""

    media_types: set[str] = {"audio_cd"}

    def detect(self, device: Path) -> str | None:
        fd = os.open(device, os.O_RDONLY | os.O_NONBLOCK)
        try:
            code = fcntl.ioctl(fd, CDROM_DISC_STATUS)
        finally:
            os.close(fd)
        return "audio_cd" if code == CDS_AUDIO else None

    def rip(
        self,
        device: Path,
        out_dir: Path,
        *,
        progress_callback: Callable[[str], None] | None = None,
    ) -> RipResult:
        out_dir.mkdir(parents=True, exist_ok=True)
        errors: list[str] = []

        # Trailing slash is load-bearing: cdparanoia -B treats the final
        # arg as a filename PREFIX unless it looks like a directory path.
        # Without the slash, "/.../audio" → tracks land at "/.../audio*",
        # one level up. With it, tracks land inside the directory.
        # Surfaced 2026-05-14, real CM4 rip CD_0004 — files landed at
        # CD_0004/track*.audio instead of CD_0004/audio/track*.cdda.wav.
        cdp_argv = ["cdparanoia", "-B", "-d", str(device), "--", "1-", f"{out_dir}/"]
        returncode, stderr_lines = _run_cdparanoia_streaming(cdp_argv, progress_callback)
        if returncode != 0 and stderr_lines:
            errors.append("\n".join(stderr_lines).strip())

        wavs = sorted(out_dir.glob("track*.wav"))
        if not wavs:
            if not errors:
                errors.append(f"cdparanoia exit {returncode} produced no WAVs")
            return RipResult(status="fail", tracks=[], errors=errors)

        tracks: list[Path] = []
        for wav in wavs:
            enc = subprocess.run(
                ["flac", "--best", str(wav)],
                capture_output=True,
                text=True,
            )
            flac_path = wav.with_suffix(".flac")
            if enc.returncode == 0 and flac_path.exists():
                tracks.append(flac_path)
            else:
                msg = enc.stderr.strip() or f"flac exit {enc.returncode} for {wav.name}"
                errors.append(msg)

        if returncode == 0 and len(tracks) == len(wavs) and not errors:
            return RipResult(status="success", tracks=tracks, errors=[])
        return RipResult(status="partial", tracks=tracks, errors=errors)


def _run_cdparanoia_streaming(
    argv: list[str],
    progress_callback: Callable[[str], None] | None,
) -> tuple[int, list[str]]:
    """Spawn cdparanoia via Popen and iterate stderr line-by-line.

    For each line: (a) log at INFO so live progress AND failures land
    in `/api/log` and the journal; (b) invoke `progress_callback` if
    supplied so the state machine can update `loop_state.rip_progress`
    live. Returns `(returncode, captured_stderr_lines)` so non-zero
    exits still surface diagnostic context to the caller.

    bufsize=1 + text=True gives line-buffered text I/O — required for
    the "callback fires before exit" semantics that the 2026-05-14
    silent failure surfaced as critical.
    """
    captured: list[str] = []
    proc = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,
        text=True,
    )
    try:
        if proc.stderr is not None:
            for raw_line in proc.stderr:
                line = raw_line.rstrip("\n")
                captured.append(line)
                _logger.info("%s", line)
                if progress_callback is not None:
                    try:
                        progress_callback(line)
                    except Exception:  # noqa: BLE001
                        _logger.exception("rip progress_callback raised; continuing")
    finally:
        returncode = proc.wait()
    return returncode, captured
