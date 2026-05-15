"""Parser for cdparanoia's stderr → a short human label for LoopState.

cdparanoia emits a handful of recognisable line shapes; we map those
to a compact string the UI renders as-is:

    "Ripping from sectors  6750 [00:01:30.00] (track 4 ...)"  → "track 4"
    "Progress: 47% complete (track 3 of 12)"                  → "track 3/12, 47%"
    "(== PROGRESS == [ ... | 023456 00 ==]"                   → (None or "...%" if a track is known)

Anything we don't recognise returns None — the caller leaves the
existing label alone so the UI doesn't flap.

This module is import-safe and side-effect-free.
"""
from __future__ import annotations

import re

# Match the human "Progress: NN% complete (track N of M)" line first;
# it carries both percent and track info in one shot.
_RE_FULL_PROGRESS = re.compile(
    r"Progress:\s+(?P<pct>\d{1,3})\s*%.*?\(track\s+(?P<track>\d+)\s+of\s+(?P<total>\d+)\)",
    re.IGNORECASE,
)

# Plain "track N" mention (from "Ripping from sectors ... (track 4 [00:01:30.00])"
# or "(track 7)" lines). We don't require a percent on this shape.
_RE_TRACK_ONLY = re.compile(r"\(track\s+(?P<track>\d+)\b", re.IGNORECASE)


def parse_cdparanoia_progress(line: str) -> str | None:
    """Return a short status label or None if the line is unrecognised."""
    if not line:
        return None
    line = line.strip()
    if not line:
        return None

    m = _RE_FULL_PROGRESS.search(line)
    if m:
        return f"track {m.group('track')}/{m.group('total')}, {m.group('pct')}%"

    m = _RE_TRACK_ONLY.search(line)
    if m:
        return f"track {m.group('track')}"

    return None
