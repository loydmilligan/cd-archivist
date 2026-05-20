"""Library Manager — panel inventory (single source of truth).

Sprint-9: ported verbatim from the JSX reference at
docs/reference/mashco-design-system/cd-archivist-library/reference/cda-library.jsx
(`LIB_PANELS`). All three lane-2 modules (sidebar, landing grid,
panels) read from this dict so per-panel copy / glyph / sub-line
updates land in one place.
"""

from __future__ import annotations

from typing import TypedDict


class PanelSpec(TypedDict):
    id: str
    glyph: str
    name: str
    sub: str
    count: str | None
    title: str
    eyebrow: str
    summary: str


PRIMARY: tuple[PanelSpec, ...] = (
    PanelSpec(
        id="downloads",
        glyph="↓",
        name="Downloads",
        sub="spooty queue",
        count="1",
        title="Spotify → YouTube",
        eyebrow="Downloads · spooty queue",
        summary=(
            "Albums and playlists queued for spooty to download from "
            "YouTube using the Spotify track list as the spec. One row "
            "per playlist; per-track sub-state."
        ),
    ),
    PanelSpec(
        id="inbox",
        glyph="▣",
        name="Inbox",
        sub="cd rips · downloads",
        count="3",
        title="Albums waiting to import",
        eyebrow="Inbox queue",
        summary=(
            "/srv/music/inbox/ + /srv/music/inbox/spooty/. One row per "
            "album folder. READY-marked folders are eligible for beets "
            "auto-import."
        ),
    ),
    PanelSpec(
        id="disk",
        glyph="◧",
        name="Disk",
        sub="usage",
        count=None,
        title="Where the bytes live",
        eyebrow="Disk usage",
        summary=(
            "Per-mount and per-surface breakdown. /, /mnt/seagate (the "
            "new 1 TB), /mnt/archive. Inbox vs library vs archive vs "
            "spooty."
        ),
    ),
    PanelSpec(
        id="library",
        glyph="♪",
        name="Library",
        sub="browse + jump",
        count=None,
        title="Browse · jump to Navidrome",
        eyebrow="Library",
        summary=(
            "Read-only Subsonic API into Navidrome. Search + 10 "
            "most-recent imports + one big jump-out CTA. Real browsing "
            "happens in Navidrome."
        ),
    ),
)


GHOSTS: tuple[PanelSpec, ...] = (
    PanelSpec(
        id="review",
        glyph="?",
        name="Review",
        sub="soon",
        count=None,
        title="Beets couldn't auto-apply",
        eyebrow="Review queue · v2",
        summary="Walks /srv/music/review/. Surfaces what beets couldn't match.",
    ),
    PanelSpec(
        id="recent",
        glyph="≡",
        name="Recent imports",
        sub="soon",
        count=None,
        title="Tail of beets-import.log",
        eyebrow="Recent imports · v2",
        summary=(
            "Reads /srv/music/logs/beets-import.log + beets sqlite. "
            "Live tail of what just landed."
        ),
    ),
    PanelSpec(
        id="cron",
        glyph="⏱",
        name="Cron / scheduler",
        sub="soon",
        count=None,
        title="Spooty cron health",
        eyebrow="Cron / scheduler · v2",
        summary=(
            "Next-run + last-run + errors for the spooty cron and any "
            "other scheduled jobs."
        ),
    ),
)


BY_ID: dict[str, PanelSpec] = {p["id"]: p for p in (*PRIMARY, *GHOSTS)}
