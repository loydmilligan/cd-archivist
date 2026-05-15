"""Parser for cdparanoia's stderr → a short human label for LoopState.

Sprint-4 / impl-rip-progress-real-format: rewritten against the real
cdparanoia III 10.2 stderr shape captured in
`tests/pipeline/fixtures/cdparanoia_stderr_real.txt`. Recognised
line shapes:

  - "Ripping from sector       0 (track  1 [00:00:00.00])"
      → "track 1"
  - "outputting to track03.cdda.wav"
      → "track 3"  (updates module-instance track context for bar lines)
  - " (== PROGRESS == [..............| NNNNNN NN ] == :^D * ==)"
      → "track N, P%"  (P derived from bar fill ratio)
  - "Progress: 47% complete (track 3 of 12)"  (man-page synthetic)
      → "track 3/12, 47%"

`parse_cdparanoia_progress` is stateless at the call-site level —
the bar-percent derivation uses regex on the bar itself, so each
line stands alone. Track context is parsed from the same line
(via the "outputting to" or "Ripping from sector ... (track N)"
recognisers) and emitted in the label.
"""
from __future__ import annotations

import re

# (a) Man-page synthetic — kept for back-compat with sprint-3 tests.
_RE_FULL_PROGRESS = re.compile(
    r"Progress:\s+(?P<pct>\d{1,3})\s*%.*?\(track\s+(?P<track>\d+)\s+of\s+(?P<total>\d+)\)",
    re.IGNORECASE,
)

# (b) "outputting to track03.cdda.wav" — clear track boundary.
_RE_OUTPUTTING = re.compile(
    r"outputting\s+to\s+track(?P<track>\d{1,3})\.cdda\.wav", re.IGNORECASE,
)

# (c) "Ripping from sector       0 (track  1 [..])"
_RE_RIPPING_FROM = re.compile(
    r"Ripping\s+from\s+sector.*?\(track\s+(?P<track>\d{1,3})", re.IGNORECASE,
)

# (d) Bar line:  (== PROGRESS == [content| 132432 04 ] == :^D ...)
# Capture the bar content between '[' and '|' (used to estimate %).
_RE_BAR = re.compile(
    r"\(==\s*PROGRESS\s*==\s*\[(?P<bar>[^|]*)\|", re.IGNORECASE,
)

# (e) Standalone "(track 7)" mention — last-resort.
_RE_TRACK_PAREN = re.compile(r"\(track\s+(?P<track>\d{1,3})\b", re.IGNORECASE)


def _bar_percent(bar: str) -> int | None:
    """Estimate percent from the fill of the bar segment.

    The bar is a fixed-width column; cdparanoia paints `+` for verified,
    `.` for re-read attempts, ` ` for unread. We treat any non-space
    char as "covered" and report the coverage ratio.
    """
    if not bar:
        return None
    width = len(bar)
    if width == 0:
        return None
    filled = sum(1 for ch in bar if not ch.isspace())
    pct = round(filled / width * 100)
    if pct < 0 or pct > 100:
        return None
    return pct


# Module-level context: cdparanoia emits a "outputting to trackNN" header
# once per track and then floods stderr with bar lines that don't repeat
# the track number. The parser keeps a small bit of state so bar updates
# can be reported with their owning track.
_last_track: int | None = None


def reset_progress_context() -> None:
    """Clear the cached track context. Call between rips to avoid bleed."""
    global _last_track
    _last_track = None


def parse_cdparanoia_progress(line: str) -> str | None:
    """Return a short status label or None if the line is unrecognised."""
    global _last_track
    if not line:
        return None
    line = line.strip()
    if not line:
        return None

    m = _RE_FULL_PROGRESS.search(line)
    if m:
        _last_track = int(m.group("track"))
        return f"track {m.group('track')}/{m.group('total')}, {m.group('pct')}%"

    m = _RE_OUTPUTTING.search(line)
    if m:
        n = int(m.group("track"))
        _last_track = n
        return f"track {n}"

    m = _RE_RIPPING_FROM.search(line)
    if m:
        n = int(m.group("track"))
        _last_track = n
        return f"track {n}"

    m_bar = _RE_BAR.search(line)
    if m_bar:
        pct = _bar_percent(m_bar.group("bar"))
        m_track = _RE_TRACK_PAREN.search(line)
        track = int(m_track.group("track")) if m_track else _last_track
        if pct is not None and track is not None:
            return f"track {track}, {pct}%"
        if track is not None:
            return f"track {track}"
        return None

    m = _RE_TRACK_PAREN.search(line)
    if m:
        n = int(m.group("track"))
        _last_track = n
        return f"track {n}"

    return None
