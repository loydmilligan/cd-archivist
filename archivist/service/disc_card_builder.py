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
from pathlib import Path
from typing import Any, Literal

Bucket = Literal["capture", "beets_id", "review", "library"]
TrackState = Literal["success", "fail", "in_progress", "pending"]

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


def _iter_disc_folders(root: Path) -> list[Path]:
    """Yield disc folders under `root`. A disc folder contains a
    source.json OR at least one .flac file. Walks recursively so the
    library layout `<root>/<artist>/<album>/` is found."""
    if not root.is_dir():
        return []
    found: list[Path] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        if "source.json" in filenames or any(
            f.endswith(".flac") for f in filenames
        ):
            found.append(Path(dirpath))
    return found


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
    review_root = music_root / "review"
    library_root = music_root / "library"
    archive_root = music_root / "archive"

    review_cards = [
        _card_from_folder(f, bucket="review", archived=False)
        for f in _iter_disc_folders(review_root)
    ]
    library_cards = [
        _card_from_folder(f, bucket="library", archived=False)
        for f in _iter_disc_folders(library_root)
    ] + [
        _card_from_folder(f, bucket="library", archived=True)
        for f in _iter_disc_folders(archive_root)
    ]

    library_cards.sort(key=lambda c: c.mtime, reverse=True)
    review_cards.sort(key=lambda c: c.mtime, reverse=True)
    library_cards = library_cards[: _library_retention()]

    capture: list[DiscCard] = []
    active = _active_capture_card(loop_state)
    if active is not None:
        capture.append(active)

    return KanbanState(buckets={
        "capture": capture,
        "beets_id": [],
        "review": review_cards,
        "library": library_cards,
    })
