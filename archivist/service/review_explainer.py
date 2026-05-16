"""Why-in-review explainer (sprint-6 Bucket C).

Derives a single-sentence "why is this disc in the review bucket"
explanation from on-disk artifacts. Sources in priority order:

  1. source.json.status.beets_review_reason — when the post-rip
     hook chose to write a structured reason.
  2. The tail of beets-import.log inside the folder — string-match
     for weak-match score lines and AcoustID empty-match markers.
  3. Presence of identifiers.musicbrainz_disc_id — its absence is
     itself a signal (libdiscid was unavailable / disc unreadable
     by the MB algorithm).
  4. Safe fallback string — always non-empty.

Sprint-6 ships the explainer + read-only Review v1 page; in-UI
beets candidate selection is sprint-7 (Sprint-7 Candidates).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_LOG_TAIL_BYTES = 16 * 1024
_SCORE_RE = re.compile(r"score\s+([0-9]+(?:\.[0-9]+)?)\s+below\s+threshold")


def _read_source(folder: Path) -> dict:
    p = folder / "source.json"
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _read_log_tail(folder: Path) -> str:
    p = folder / "beets-import.log"
    if not p.is_file():
        return ""
    try:
        data = p.read_bytes()
    except OSError:
        return ""
    return data[-_LOG_TAIL_BYTES:].decode("utf-8", errors="replace")


def explain(folder: Path) -> str:
    source = _read_source(folder)
    status = source.get("status") or {}

    reason = status.get("beets_review_reason")
    if isinstance(reason, str) and reason.strip():
        return reason.strip()

    log = _read_log_tail(folder)
    if log:
        score_match = _SCORE_RE.search(log)
        if score_match:
            return (
                f"weak match: top score {score_match.group(1)} "
                "is below the beets threshold"
            )
        log_lower = log.lower()
        if "acoustid" in log_lower and (
            "empty" in log_lower or "no tags" in log_lower
        ):
            return (
                "AcoustID empty match against tagless flacs — "
                "MB had nothing to fingerprint"
            )

    identifiers = source.get("identifiers") or {}
    if not identifiers.get("musicbrainz_disc_id"):
        return (
            "no MusicBrainz disc-id was captured at rip time "
            "(libdiscid unavailable or disc not in MB)"
        )

    return "ready for review — no auto-match was attempted yet"
