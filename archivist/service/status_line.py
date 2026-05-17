"""Card status-line formatter (sprint-7 impl-card-anatomy, lane-2).

Maps a `DiscCard` to the one-line mono status string spec'd in the
Mash Co. build prompt. The format is dot-separated, lowercase verbs,
sentence-case nouns, mono-shorthand for time + byte values.

Examples per state:

  Capture · active   "ripping track 7 · sector 24,318 · 1 retry · 04:12 elapsed"
  Capture · damaged  "halted · 3 unrecoverable sectors · track 6"
  Review  · weak     "weak match · beets returned 0.42"
  Review  · no-match "no match · 13 tracks · no embedded tags"
  Library · stored   "stored · matched 0.97 · imported 2026-05-16 13:18"

Voice rules: sentence case, mono dot-separator, project vocabulary.
"""
from __future__ import annotations

from typing import Any

# Comma-separator for sector counts ("24,318") per build prompt examples.
def _fmt_sector(n: int | None) -> str:
    if n is None:
        return "?"
    return f"{int(n):,}"


def _fmt_elapsed(seconds: float | None) -> str:
    """Mono shorthand: `04:12` for under-an-hour, `1:23:45` otherwise."""
    if seconds is None:
        return "?"
    s = max(0, int(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


def _retry_phrase(retries: int | None) -> str | None:
    if not retries:
        return None
    return f"{retries} retry" if retries == 1 else f"{retries} retries"


def _capture_active(card: Any) -> str:
    """Per build prompt: 'ripping track 7 · sector 24,318 · 1 retry ·
    04:12 elapsed'. Pull the numbers from the card's progress dict
    (set by disc_card_builder._active_capture_card from
    LoopState.drive_status)."""
    progress = card.progress or {}
    ds = progress.get("drive_status") or {}
    track = ds.get("current_track")
    sector = ds.get("sector_current")
    retries = ds.get("retries_on_current_track")
    elapsed = ds.get("elapsed_seconds")

    parts: list[str] = []
    if track is not None:
        parts.append(f"ripping track {int(track)}")
    else:
        parts.append("ripping")
    if sector is not None:
        parts.append(f"sector {_fmt_sector(sector)}")
    retry = _retry_phrase(retries)
    if retry:
        parts.append(retry)
    if elapsed is not None:
        parts.append(f"{_fmt_elapsed(elapsed)} elapsed")
    return " · ".join(parts)


def _capture_damaged(card: Any) -> str:
    """Per build prompt: 'halted · 3 unrecoverable sectors · track 6'."""
    failed = list(card.failed_tracks or [])
    parts: list[str] = ["halted"]
    src = card.source_json or {}
    errors = (src.get("status") or {}).get("errors") or []
    # Look for a sector count in the error text; fall back to the failed
    # tracks length as a coarse proxy.
    sector_count: int | None = None
    for line in errors:
        # Naïve: pull the first integer from the first error line.
        digits = "".join(ch if ch.isdigit() else " " for ch in str(line)).split()
        if digits:
            try:
                sector_count = int(digits[0])
                break
            except ValueError:
                pass
    if sector_count is None and failed:
        sector_count = len(failed)
    if sector_count is not None:
        plural = "" if sector_count == 1 else "s"
        parts.append(f"{sector_count} unrecoverable sector{plural}")
    if failed:
        parts.append(f"track {failed[0]}")
    return " · ".join(parts)


def _review_weak(card: Any, score: float | None) -> str:
    score_s = f"{score:.2f}" if score is not None else "?"
    return f"weak match · beets returned {score_s}"


def _review_no_match(card: Any) -> str:
    """Per build prompt: 'no match · 13 tracks · no embedded tags'."""
    track_count = len(card.track_bar) or 0
    src = card.source_json or {}
    identifiers = src.get("identifiers") or {}
    has_disc_id = bool(identifiers.get("musicbrainz_disc_id"))
    detected = src.get("detected_metadata") or {}
    has_tags = bool(detected.get("album_artist") or detected.get("album"))
    parts: list[str] = ["no match", f"{track_count} tracks"]
    if not has_tags and not has_disc_id:
        parts.append("no embedded tags")
    return " · ".join(parts)


def _library_stored(card: Any) -> str:
    """Per build prompt: 'stored · matched 0.97 · imported 2026-05-16 13:18'.
    Score comes from the top_candidate sidecar; import date from the
    source.json ready_at / rip_finished_at."""
    top = card.top_candidate or {}
    score = top.get("score")
    score_s = f"{score:.2f}" if isinstance(score, (int, float)) else None
    src = card.source_json or {}
    disc = src.get("disc") or {}
    imported = disc.get("ready_at") or disc.get("rip_finished_at") or ""
    # Trim ISO timestamp to "YYYY-MM-DD HH:MM"; never raise on bad input.
    imported_short = ""
    if isinstance(imported, str) and len(imported) >= 16:
        imported_short = imported[:16].replace("T", " ")
    parts: list[str] = ["stored"]
    if score_s:
        parts.append(f"matched {score_s}")
    if imported_short:
        parts.append(f"imported {imported_short}")
    return " · ".join(parts)


def _top_candidate_score(card: Any) -> float | None:
    top = card.top_candidate or {}
    score = top.get("score")
    if isinstance(score, (int, float)):
        return float(score)
    src = card.source_json or {}
    reason = ((src.get("status") or {}).get("beets_review_reason")) or ""
    import re as _re
    m = _re.search(r"([01]?\.[0-9]+)", reason)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def _is_damaged(card: Any) -> bool:
    if getattr(card, "partial", False):
        return True
    src = card.source_json or {}
    return (src.get("status") or {}).get("rip_success") is False


def format(card: Any) -> str:  # noqa: A001 — public name matches the spec
    """Top-level dispatch. Picks the right per-state formatter."""
    bucket = getattr(card, "bucket", None)
    if bucket == "capture":
        if card.progress is not None:
            return _capture_active(card)
        if _is_damaged(card):
            return _capture_damaged(card)
        return "queued"
    if bucket == "review":
        score = _top_candidate_score(card)
        src = card.source_json or {}
        reason = ((src.get("status") or {}).get("beets_review_reason")) or ""
        if "weak" in reason.lower() or (score is not None and score < 0.85):
            return _review_weak(card, score)
        return _review_no_match(card)
    if bucket == "library":
        return _library_stored(card)
    return ""
