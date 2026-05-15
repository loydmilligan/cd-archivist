"""Atomic disc-id allocator.

Allocates the next free `CD_NNNN` identifier under a discs root, using
an exclusive lockfile so concurrent callers cannot collide.
"""
from __future__ import annotations

import fcntl
import re
from pathlib import Path

_DISC_ID_RE = re.compile(r"^CD_(\d{4})$")
_LOCKFILE_NAME = ".disc-id.lock"


def next_disc_id(discs_root: Path) -> str:
    """Reserve and return the next free disc-id under ``discs_root``.

    Holds an exclusive ``fcntl.flock`` on ``<discs_root>/.disc-id.lock`` for
    the duration of the scan + reservation, then materializes the
    reservation by creating the target directory before releasing the
    lock. Concurrent callers are serialized and receive distinct ids.
    """
    discs_root.mkdir(parents=True, exist_ok=True)
    lock_path = discs_root / _LOCKFILE_NAME

    with open(lock_path, "w") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            highest = 0
            for entry in discs_root.iterdir():
                if not entry.is_dir():
                    continue
                match = _DISC_ID_RE.match(entry.name)
                if match:
                    highest = max(highest, int(match.group(1)))
            disc_id = f"CD_{highest + 1:04d}"
            (discs_root / disc_id).mkdir(exist_ok=False)
            return disc_id
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
