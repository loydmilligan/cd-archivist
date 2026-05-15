"""New disc folder naming: `YYYY-MM-DD_HHMM_disc-NNNNNN`.

Per D-folder-naming-migration. Pure name allocator (no mkdir) — the
working_dir-handoff path does the directory creation. Counter scans
the inbox for the highest existing `disc-(\d{6})` and increments;
legacy `CD_NNNN/` folders are ignored.

A collision guard bumps the counter if the computed name already
exists on disk (clock jump / test fixture).
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

_FOLDER_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})_(\d{4})_disc-(\d{6})$")


def next_disc_folder_name(
    inbox_root: Path,
    *,
    now: datetime | None = None,
) -> str:
    """Return the next disc folder name to use under ``inbox_root``.

    Pure — does NOT create the directory. The caller mkdir()s it
    inside the working_dir-handoff path.

    When ``now`` is None, falls back to ``datetime.now()`` (local time).
    """
    if now is None:
        now = datetime.now()

    highest = 0
    if inbox_root.is_dir():
        for entry in inbox_root.iterdir():
            if not entry.is_dir():
                continue
            m = _FOLDER_RE.match(entry.name)
            if m:
                highest = max(highest, int(m.group(5)))

    counter = highest + 1
    while True:
        candidate = f"{now.strftime('%Y-%m-%d_%H%M')}_disc-{counter:06d}"
        if not (inbox_root / candidate).exists():
            return candidate
        counter += 1
