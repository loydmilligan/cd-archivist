"""Per-track identification lookup (sprint-7 impl-card-anatomy).

Resolves D-track-identification-source — picks **option (c)**:
re-derive identification from `source.json.detected_metadata.tracks`
(already populated by beets via the post-rip hook) gated on a
`musicbrainz_disc_id` being present.

Why (c) over (a) parse beets-import.log or (b) query the beets web
API: (c) reads what beets already wrote into source.json instead of
parsing a verbose log or adding a second runtime dependency. Trade-
off: a track is "identified" only when beets populated a title for
it — partial beets runs surface as partial identification, which is
the correct visual.

If neither disc-id nor detected_metadata.tracks is available, the
helper returns an empty set — the renderer omits the
`.track-cell--identified` outline. Sprint-8 may revisit if beets'
behavior on tagless discs shifts.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def identified_tracks(
    folder: Path | None = None, *, source_json: dict[str, Any] | None = None,
) -> set[int]:
    """Return the set of 1-indexed track numbers beets has identified
    for this disc.

    Either pass `folder` (the helper will read source.json from disk)
    or pre-load + pass `source_json` directly — the kanban card builder
    already has the parsed dict, so per-render disk reads are
    redundant in the hot path.
    """
    if source_json is None and folder is not None:
        path = folder / "source.json"
        if not path.is_file():
            return set()
        try:
            import json as _json
            source_json = _json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return set()
    if not isinstance(source_json, dict):
        return set()
    identifiers = source_json.get("identifiers") or {}
    if not identifiers.get("musicbrainz_disc_id"):
        return set()
    detected = source_json.get("detected_metadata") or {}
    out: set[int] = set()
    for t in (detected.get("tracks") or []):
        if not isinstance(t, dict):
            continue
        n = t.get("track")
        title = t.get("title")
        if isinstance(n, int) and n >= 1 and title:
            out.add(n)
    return out
