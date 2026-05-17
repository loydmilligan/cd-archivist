"""DriveStatus snapshot — live drive/rip/capture state exposed via LoopState.

Per sprint-6.5 task `impl-drive-status-snapshot` + D-drive-status-snapshot-
schema. The state machine writes to a single `DriveStatus` instance
held on `LoopState`; the FastAPI request handler reads it from a
different thread.

Thread-safety model: every mutation is wrapped in `with ds.lock:`. The
lock is a `threading.RLock` so a state-transition path that's already
holding the lock (e.g. multi-field reset) can call the smaller helpers
(`update_from_progress_line`) without deadlocking. Readers can either
grab the lock themselves for a consistent multi-field snapshot or
read one field at a time — Python attribute reads are GIL-atomic, so
field-by-field reads can briefly mix old/new values mid-transition,
which is acceptable for the polling UI we feed.

Field semantics (every field except `state` resets to `None` on
return-to-idle):

  state — coarse phase. "idle" outside an active disc cycle; advances
    through "stabilizing" → "ripping" → "capturing" within a cycle.
    EJECT is mapped to "capturing" because from the operator's view
    the drive is opening the tray for the photo step.
  current_disc — folder name (sprint-3 disc_id like "CD_0001" or
    sprint-4-style "YYYY-MM-DD_HHMM_disc-NNNNNN").
  current_track / track_total — 1-indexed; current advances as
    cdparanoia emits `:outputting track N` lines.
  sector_current / sector_total — sector currently being read. Total
    is populated when the parser sees a `:reading from sector X to Y`
    line; current advances with each scsi_read line.
  retries_on_current_track — most recent retry count for the current
    track (resets to 0 when the track changes).
  photo_state — "pending" → "capturing" → "done" during the CAPTURE
    state. `None` outside it.
  elapsed_seconds — cycle-elapsed at the moment of last update. The
    state machine bumps this on transitions; readers can compare to
    wall-clock if a finer-grained measure is needed.
"""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from typing import Literal

DriveState = Literal["idle", "ripping", "stabilizing", "capturing"]
PhotoState = Literal["pending", "capturing", "done"]

# cdparanoia stderr regexes. Same shapes _run_cdparanoia_streaming
# uses for the retry-threshold detector, but pulled here so the
# DriveStatus helper has its own self-contained parser surface — the
# state machine can update both drive_status and rip_progress from
# the same callback without coupling them.
_TRACK_RE = re.compile(r":outputting track (\d+)", re.IGNORECASE)
_SECTOR_RE = re.compile(r"sector=(\d+)", re.IGNORECASE)
_RETRY_RE = re.compile(r"retry=(\d+)", re.IGNORECASE)


@dataclass
class DriveStatus:
    state: DriveState = "idle"
    current_disc: str | None = None
    current_track: int | None = None
    track_total: int | None = None
    sector_current: int | None = None
    sector_total: int | None = None
    retries_on_current_track: int | None = None
    photo_state: PhotoState | None = None
    elapsed_seconds: float | None = None
    # Reentrant lock so multi-field mutations can call into smaller
    # helpers (each of which also takes the lock) without deadlocking.
    # Excluded from repr / eq so DriveStatus instances compare on
    # their data, not on lock identity.
    lock: threading.RLock = field(
        default_factory=threading.RLock,
        repr=False,
        compare=False,
    )


def update_from_progress_line(ds: DriveStatus, line: str) -> None:
    """Parse one cdparanoia stderr line and update `ds` in place.

    Lines that don't match either parser leave `ds` untouched.
    Multi-field updates are atomic under `ds.lock`.

    Track-change semantics: when `:outputting track N` fires for a
    different `N` than the current value, retry counter resets to 0
    — the retry count is per-track, not cumulative across the rip.
    """
    track_m = _TRACK_RE.search(line)
    if track_m is not None:
        new_track = int(track_m.group(1))
        with ds.lock:
            if ds.current_track != new_track:
                ds.retries_on_current_track = 0
            ds.current_track = new_track
        return

    sector_m = _SECTOR_RE.search(line)
    retry_m = _RETRY_RE.search(line)
    if sector_m is not None or retry_m is not None:
        with ds.lock:
            if sector_m is not None:
                ds.sector_current = int(sector_m.group(1))
            if retry_m is not None:
                ds.retries_on_current_track = int(retry_m.group(1))
