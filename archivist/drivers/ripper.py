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
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

_logger = logging.getLogger(__name__)

# include/uapi/linux/cdrom.h
CDROM_DISC_STATUS = 0x5327
CDS_AUDIO = 100

# Sprint-6 / D-failfast-threshold. Defaults locked at the impl boundary;
# operator can override via env. Rationale in the Decision Log entry.
DEFAULT_RIP_RETRY_THRESHOLD = 3
_RETRY_THRESHOLD_ENV = "ARCHIVIST_RIP_RETRY_THRESHOLD"

# cdparanoia emits lines like:
#   "scsi_read error: sector=12345 length=27 retry=3"
# We track the count per-sector so an `r=1` on four different sectors
# doesn't trip a threshold-3 abort.
_RETRY_RE = re.compile(r"sector=(\d+).*retry=(\d+)", re.IGNORECASE)

# ATAPI sense code for Target hardware fault. Drive is reporting an
# unrecoverable hardware error — no point in retrying.
_HARDWARE_FAULT_MARKER = "ASC=3e"

RipStatus = Literal["success", "partial", "fail"]


@dataclass
class RipResult:
    status: RipStatus
    tracks: list[Path]
    errors: list[str] = field(default_factory=list)
    # Sprint-6 / impl-partial-output-preserve additions. All default to
    # safe values so existing happy-path callers don't break.
    partial: bool = False
    successful_tracks: list[int] = field(default_factory=list)
    failed_track: int | None = None


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
        retry_threshold: int | None = None,
    ) -> RipResult:
        out_dir.mkdir(parents=True, exist_ok=True)
        errors: list[str] = []

        threshold = _resolve_retry_threshold(retry_threshold)

        # Trailing slash is load-bearing: cdparanoia -B treats the final
        # arg as a filename PREFIX unless it looks like a directory path.
        # Without the slash, "/.../audio" → tracks land at "/.../audio*",
        # one level up. With it, tracks land inside the directory.
        # Surfaced 2026-05-14, real CM4 rip CD_0004 — files landed at
        # CD_0004/track*.audio instead of CD_0004/audio/track*.cdda.wav.
        cdp_argv = ["cdparanoia", "-B", "-d", str(device), "--", "1-", f"{out_dir}/"]
        returncode, stderr_lines, aborted, failed_track = _run_cdparanoia_streaming(
            cdp_argv, progress_callback, threshold,
        )
        if returncode != 0 and stderr_lines:
            errors.append("\n".join(stderr_lines).strip())

        wavs = sorted(out_dir.glob("track*.wav"))
        if not wavs:
            if not errors:
                errors.append(f"cdparanoia exit {returncode} produced no WAVs")
            return RipResult(
                status="fail", tracks=[], errors=errors,
                partial=False, successful_tracks=[],
                failed_track=failed_track if aborted else None,
            )

        tracks: list[Path] = []
        successful_track_nums: list[int] = []
        for wav in wavs:
            enc = subprocess.run(
                ["flac", "--best", str(wav)],
                capture_output=True,
                text=True,
            )
            flac_path = wav.with_suffix(".flac")
            if enc.returncode == 0 and flac_path.exists():
                tracks.append(flac_path)
                successful_track_nums.append(_track_number_from_wav(wav))
            else:
                msg = enc.stderr.strip() or f"flac exit {enc.returncode} for {wav.name}"
                errors.append(msg)

        if aborted:
            # Fail-fast fired mid-rip. Tracks 1..N-1 survived; track N is
            # the one that broke (the next track number after the last
            # successful one, if not already known from the scsi parser).
            inferred_failed = failed_track
            if inferred_failed is None and successful_track_nums:
                inferred_failed = max(successful_track_nums) + 1
            return RipResult(
                status="partial", tracks=tracks, errors=errors,
                partial=True,
                successful_tracks=successful_track_nums,
                failed_track=inferred_failed,
            )

        if returncode == 0 and len(tracks) == len(wavs) and not errors:
            return RipResult(
                status="success", tracks=tracks, errors=[],
                partial=False,
                successful_tracks=successful_track_nums,
                failed_track=None,
            )
        return RipResult(
            status="partial", tracks=tracks, errors=errors,
            partial=False,  # cdparanoia natural-exit partial: not a fail-fast abort
            successful_tracks=successful_track_nums,
            failed_track=None,
        )


def _resolve_retry_threshold(explicit: int | None) -> int:
    """`retry_threshold=...` kwarg wins; else `ARCHIVIST_RIP_RETRY_THRESHOLD`
    env var; else `DEFAULT_RIP_RETRY_THRESHOLD`."""
    if explicit is not None:
        return explicit
    raw = os.environ.get(_RETRY_THRESHOLD_ENV)
    if raw:
        try:
            return int(raw)
        except ValueError:
            _logger.warning(
                "%s=%r not an int; falling back to default %d",
                _RETRY_THRESHOLD_ENV, raw, DEFAULT_RIP_RETRY_THRESHOLD,
            )
    return DEFAULT_RIP_RETRY_THRESHOLD


def _track_number_from_wav(wav: Path) -> int:
    """Extract the integer N from a `trackNN.wav` filename."""
    stem = wav.stem  # e.g. "track03"
    m = re.search(r"(\d+)", stem)
    return int(m.group(1)) if m else 0


def _run_cdparanoia_streaming(
    argv: list[str],
    progress_callback: Callable[[str], None] | None,
    retry_threshold: int,
) -> tuple[int, list[str], bool, int | None]:
    """Spawn cdparanoia via Popen and iterate stderr line-by-line.

    For each line: (a) log at INFO so live progress AND failures land
    in `/api/log` and the journal; (b) invoke `progress_callback` if
    supplied so the state machine can update `loop_state.rip_progress`
    live; (c) parse for retry counts and sense codes — when any single
    sector accumulates retries past `retry_threshold` OR a Target
    hardware fault sense code (ASC=3e) appears, SIGTERM cdparanoia so
    a damaged disc doesn't grind for 25 min on unreadable sectors.

    Returns `(returncode, captured_stderr_lines, aborted, failed_track)`.
    `aborted` is True iff we sent SIGTERM. `failed_track` is parsed from
    the most recent `:outputting track N` progress line at the moment
    we aborted (None if no such line was seen — e.g. ASC=3e before the
    first track started).

    bufsize=1 + text=True gives line-buffered text I/O — required for
    both the "callback fires before exit" semantics (sprint-3) and the
    real-time threshold detection here.
    """
    captured: list[str] = []
    # Per-sector retry counters. cdparanoia retries on the same sector
    # before giving up, so the count rises monotonically until it
    # either succeeds or the drive gives up.
    sector_retries: dict[int, int] = {}
    aborted = False
    current_track: int | None = None
    track_re = re.compile(r":outputting track (\d+)", re.IGNORECASE)

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

                # Track which track number we're working on so a fail-fast
                # abort can report the failed track.
                tm = track_re.search(line)
                if tm:
                    current_track = int(tm.group(1))

                # Fail-fast: ASC=3e Target hardware fault → immediate abort.
                if _HARDWARE_FAULT_MARKER in line:
                    _logger.warning(
                        "fail-fast: %s detected — aborting cdparanoia (track %s)",
                        _HARDWARE_FAULT_MARKER, current_track,
                    )
                    proc.terminate()
                    aborted = True
                    break

                # Fail-fast: per-sector retry threshold.
                rm = _RETRY_RE.search(line)
                if rm:
                    sector = int(rm.group(1))
                    retry = int(rm.group(2))
                    # The cdparanoia retry counter starts at 1 and
                    # increments per attempt on the same sector. We
                    # keep the max we've seen — same sector can produce
                    # multiple lines as retries climb.
                    prev = sector_retries.get(sector, 0)
                    if retry > prev:
                        sector_retries[sector] = retry
                    if sector_retries[sector] >= retry_threshold:
                        _logger.warning(
                            "fail-fast: sector=%d hit retry=%d (threshold=%d) — "
                            "aborting cdparanoia (track %s)",
                            sector, sector_retries[sector], retry_threshold,
                            current_track,
                        )
                        proc.terminate()
                        aborted = True
                        break
    finally:
        returncode = proc.wait()

    return returncode, captured, aborted, current_track


def partial_rerip(
    device: Path, *, track_indices: list[int], out_dir: Path | None = None,
) -> RipResult:
    """Sprint-6 / Bucket C cross-lane stub.

    Re-rips a subset of tracks via `cdparanoia -B <range>`. Drivers'
    `impl-partial-output-preserve` replaces this stub with the real
    implementation; the symbol exists here today so the service-side
    `rerip-tracks` endpoint can mock-patch it under test.
    """
    raise NotImplementedError(
        "partial_rerip lands with drivers' impl-partial-output-preserve"
    )
