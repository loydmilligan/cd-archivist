"""Kanban disc-card builder (sprint-6 Bucket B).

Walks `music_root/{inbox,review,library,archive,failed}/` for
terminal-state cards and layers `LoopState` for the active rip per
D-card-data-source. Returns a `KanbanState` of bucketed `DiscCard`s
ready for `GET /api/kanban` to JSON-serialise.

Per-track bar emits state labels (`success`, `fail`, `in_progress`,
`pending`); the color map (`green`, `red`, `blue`, empty) lives in
the page CSS.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Literal

Bucket = Literal["capture", "beets_id", "review", "library"]
TrackState = Literal["success", "fail", "in_progress", "pending"]


class ReviewPriority(IntEnum):
    """D-default-sort-v1: Review-bucket sort priority. Lower wins.

    Ordering encodes operator urgency — partial rips are the highest-
    leverage rescue (clean tracks already on disk); weak beets matches
    need a human decision; no-match needs more work; no-id-no-tags is
    the hardest to recover and tends to be old-burned-CD failures.
    """

    PARTIAL = 0
    WEAK_MATCH = 1
    NO_MATCH = 2
    NO_ID_NO_TAGS = 3

_AUDIO_GLOB = "*.flac"
_PROGRESS_PCT_RE = re.compile(r"\((\d+)%\)")


@dataclass
class DiscCard:
    folder: str
    bucket: Bucket
    source_json: dict | None = None
    photo_path: str | None = None
    track_bar: list[str] = field(default_factory=list)
    progress: dict | None = None
    archived: bool = False
    partial: bool = False
    failed_tracks: list[int] = field(default_factory=list)
    disc_id: str | None = None
    rip_started_at: str | None = None
    rip_finished_at: str | None = None
    operator_hints: dict = field(default_factory=dict)
    review_priority: int | None = None
    top_candidate: dict | None = None
    mtime: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("mtime", None)
        return d


@dataclass
class KanbanState:
    buckets: dict[str, list[DiscCard]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "buckets": {
                name: [c.to_dict() for c in cards]
                for name, cards in self.buckets.items()
            }
        }


def track_bar_from_counts(
    *,
    total: int,
    successful: list[int],
    failed: list[int],
    in_progress: int | None,
) -> list[str]:
    """Build the per-track bar state list.

    Track numbers are 1-indexed. `failed` overrides any other state.
    """
    successful_set = set(successful)
    failed_set = set(failed)
    bar: list[str] = []
    for n in range(1, total + 1):
        if n in failed_set:
            bar.append("fail")
        elif n in successful_set:
            bar.append("success")
        elif in_progress is not None and n == in_progress:
            bar.append("in_progress")
        else:
            bar.append("pending")
    return bar


def _load_source_json(folder: Path) -> dict | None:
    p = folder / "source.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _iter_disc_folders(root: Path, *, depth: int = 1) -> list[Path]:
    """Yield disc folders directly under `root` at the given depth.

    Sprint-6.5 / impl-fix-phantom-audio: the previous os.walk-based
    implementation recursed into each disc folder's children and
    surfaced `audio/`, `captures/`, `logs/`, `review/` subdirs as
    phantom cards. We now iterate explicitly at the configured depth
    — disc-folder-internal structure is read by the card-from-folder
    code via `disc_dir / "<name>"` patterns, never by recursion.

    depth=1: review/<folder>, archive/<folder>, failed/<folder>,
             inbox/<folder>
    depth=2: library/<artist>/<album>
    """
    if not root.is_dir():
        return []
    if depth <= 1:
        return [c for c in sorted(root.iterdir()) if c.is_dir()]
    out: list[Path] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        out.extend(
            grand for grand in sorted(child.iterdir()) if grand.is_dir()
        )
    return out


def _derive_review_priority(
    source: dict | None, folder: Path,
) -> int | None:
    """D-default-sort-v1: classify a Review-bucket card.

    Priority lookup is text-based against status.beets_review_reason
    (preferred) and the tail of beets-import.log (fallback). Partial
    rips trump beets signals; missing disc-id is the lowest-priority
    fallback.
    """
    if source is None:
        return ReviewPriority.NO_ID_NO_TAGS.value

    status = source.get("status") or {}
    if status.get("partial"):
        return ReviewPriority.PARTIAL.value

    reason = (status.get("beets_review_reason") or "").lower()
    if not reason:
        log = folder / "beets-import.log"
        if log.is_file():
            try:
                reason = log.read_text(encoding="utf-8", errors="replace").lower()
            except OSError:
                reason = ""

    if "weak match" in reason or "below threshold" in reason:
        return ReviewPriority.WEAK_MATCH.value
    if "no candidates" in reason or "no match" in reason:
        return ReviewPriority.NO_MATCH.value

    identifiers = source.get("identifiers") or {}
    if not identifiers.get("musicbrainz_disc_id"):
        return ReviewPriority.NO_ID_NO_TAGS.value
    return ReviewPriority.NO_MATCH.value


def _load_top_candidate(folder: Path) -> dict | None:
    """Sprint-6.5: a `top_candidate.json` sidecar (when present)
    surfaces the best beets-side match for the collapsed-card
    "Accept top match" affordance. Optional — the kanban just
    surfaces the score when the file exists."""
    p = folder / "top_candidate.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _card_from_folder(folder: Path, *, bucket: Bucket, archived: bool) -> DiscCard:
    source = _load_source_json(folder)
    photo_path: str | None = None
    disc_id: str | None = None
    rip_started_at: str | None = None
    rip_finished_at: str | None = None
    partial = False
    failed_tracks: list[int] = []
    operator_hints: dict = {}

    if source is not None:
        identifiers = source.get("identifiers") or {}
        disc_id = identifiers.get("musicbrainz_disc_id")
        disc_block = source.get("disc") or {}
        rip_started_at = disc_block.get("rip_started_at")
        rip_finished_at = disc_block.get("rip_finished_at")
        physical = source.get("physical_disc") or {}
        photo = physical.get("photo")
        if photo:
            photo_path = photo
        status = source.get("status") or {}
        partial = bool(status.get("partial", False))
        failed_tracks = list(status.get("failed_tracks") or [])
        operator_hints = source.get("operator_hints") or {}

    # Build per-track bar from terminal state. We treat failed_tracks as
    # explicit failures and the remaining tracks (up to track_count) as
    # successful.
    total = 0
    if source is not None:
        total = int((source.get("audio") or {}).get("track_count") or 0)
    if total == 0:
        # Disc-folder layout: flacs may live directly under the folder
        # OR under an `audio/` subdir. Prefer the canonical `audio/`
        # location; fall back to root-level for legacy layouts.
        total = len(list((folder / "audio").glob(_AUDIO_GLOB)))
        if total == 0:
            total = len(list(folder.glob(_AUDIO_GLOB)))
    successful = [
        n for n in range(1, total + 1) if n not in set(failed_tracks)
    ]
    track_bar = track_bar_from_counts(
        total=total, successful=successful, failed=failed_tracks,
        in_progress=None,
    )

    try:
        mtime = folder.stat().st_mtime
    except OSError:
        mtime = 0.0

    review_priority = (
        _derive_review_priority(source, folder) if bucket == "review" else None
    )
    top_candidate = _load_top_candidate(folder) if bucket == "review" else None

    return DiscCard(
        folder=folder.name,
        bucket=bucket,
        source_json=source,
        photo_path=photo_path,
        track_bar=track_bar,
        progress=None,
        archived=archived,
        partial=partial,
        failed_tracks=failed_tracks,
        disc_id=disc_id,
        rip_started_at=rip_started_at,
        rip_finished_at=rip_finished_at,
        operator_hints=operator_hints,
        review_priority=review_priority,
        top_candidate=top_candidate,
        mtime=mtime,
    )


def _parse_progress(rip_progress: str | None) -> dict | None:
    if not rip_progress:
        return None
    m = _PROGRESS_PCT_RE.search(rip_progress)
    percent = int(m.group(1)) if m else 0
    return {"percent": percent, "current_stage": rip_progress}


_ACTIVE_RIP_STATES = {"STABILIZE", "RIP", "EJECT", "CAPTURE"}


def _active_capture_card(loop_state: Any) -> DiscCard | None:
    if loop_state is None:
        return None
    state = getattr(loop_state, "state", None)
    if state not in _ACTIVE_RIP_STATES:
        return None
    disc_id = getattr(loop_state, "disc_id", None)
    rip_progress = getattr(loop_state, "rip_progress", None)
    folder = disc_id or "active-rip"
    return DiscCard(
        folder=folder,
        bucket="capture",
        progress=_parse_progress(rip_progress),
        disc_id=disc_id,
    )


def _library_retention() -> int:
    raw = os.environ.get("KANBAN_LIBRARY_RETENTION", "20")
    try:
        n = int(raw)
    except ValueError:
        return 20
    return max(0, n)


def build_kanban_state(
    music_root: Path, loop_state: Any | None = None,
) -> KanbanState:
    review_cards = [
        _card_from_folder(f, bucket="review", archived=False)
        for f in _iter_disc_folders(music_root / "review", depth=1)
    ]
    library_cards = [
        _card_from_folder(f, bucket="library", archived=False)
        for f in _iter_disc_folders(music_root / "library", depth=2)
    ] + [
        _card_from_folder(f, bucket="library", archived=True)
        for f in _iter_disc_folders(music_root / "archive", depth=1)
    ]
    terminal_capture_cards = [
        _card_from_folder(f, bucket="capture", archived=False)
        for f in _iter_disc_folders(music_root / "failed", depth=1)
    ] + [
        _card_from_folder(f, bucket="capture", archived=False)
        for f in _iter_disc_folders(music_root / "inbox", depth=1)
    ]

    library_cards.sort(key=lambda c: c.mtime, reverse=True)
    library_cards = library_cards[: _library_retention()]
    review_cards = _sort_review(review_cards)
    capture = _sort_capture(terminal_capture_cards, loop_state)

    return KanbanState(buckets={
        "capture": capture,
        "beets_id": [],
        "review": review_cards,
        "library": library_cards,
    })


def _sort_review(cards: list[DiscCard]) -> list[DiscCard]:
    """D-default-sort-v1 (Review): by ReviewPriority ascending, then
    mtime descending."""
    return sorted(cards, key=lambda c: (
        c.review_priority if c.review_priority is not None else 99,
        -c.mtime,
    ))


def _is_damaged(card: DiscCard) -> bool:
    if card.partial:
        return True
    if card.source_json is None:
        return False
    status = card.source_json.get("status") or {}
    return status.get("rip_success") is False


def _sort_capture(
    terminal_cards: list[DiscCard], loop_state: Any | None,
) -> list[DiscCard]:
    """D-default-sort-v1 (Capture): active rip pinned at index 0, then
    damaged tier newest-first, then successful tier newest-first."""
    damaged = sorted(
        [c for c in terminal_cards if _is_damaged(c)],
        key=lambda c: c.mtime, reverse=True,
    )
    healthy = sorted(
        [c for c in terminal_cards if not _is_damaged(c)],
        key=lambda c: c.mtime, reverse=True,
    )
    out: list[DiscCard] = []
    active = _active_capture_card(loop_state)
    if active is not None:
        out.append(active)
    out.extend(damaged)
    out.extend(healthy)
    return out
