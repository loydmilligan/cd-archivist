"""Disk usage client — `shutil.disk_usage()` + per-surface filesystem walks.

Sprint-10 / disk-impl. Powers `/api/library/disk` and the Disk panel.

Snapshot shape:

    DiskUsageSnapshot
      mounts: list[MountUsage]
        - mount_path: str       (e.g., "/", "/mnt/seagate")
        - mounted: bool         (False if the path doesn't exist on this host)
        - total_bytes, used_bytes, available_bytes: int
        - pct_used: float (0.0 — 100.0; 0.0 when not mounted)
        - surfaces: dict[str, int]
            keys: "inbox", "library", "archive", "spooty"
            values: bytes attributed to this mount

Surface attribution: each known surface path is walked (size-summed) and
attributed to whichever mount path is its longest prefix. Surfaces whose
host directory does not exist are attributed as 0 bytes everywhere; they
remain in the dict so renderers can show empty rows consistently.

No caching here. Cadence is owned by the panel meta tag (30s for Disk);
operators can profile-and-cache later if walks get slow.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path


# Default mount paths per build-prompt §3 (Disk panel).
_DEFAULT_MOUNTS: tuple[str, ...] = ("/", "/mnt/seagate", "/mnt/archive")

# Surface name → default host path. Env vars override at call time so
# tests can monkeypatch without re-importing.
_SURFACE_ENV: dict[str, tuple[str, str]] = {
    # name        env var              default
    "inbox":    ("MUSIC_INBOX_DIR",   "/srv/music/inbox"),
    "library":  ("MUSIC_LIBRARY_DIR", "/srv/music/library"),
    "archive":  ("MUSIC_ARCHIVE_DIR", "/mnt/archive"),
    # spooty is conventionally a subdir of the inbox; track it
    # separately so the breakdown surfaces it as its own line.
    "spooty":   ("MUSIC_SPOOTY_DIR",  ""),  # computed below
}

_SURFACE_NAMES: tuple[str, ...] = ("inbox", "library", "archive", "spooty")


class DiskClientError(Exception):
    """Raised on unrecoverable failure in the disk client. Reserved
    for future use — current implementation degrades to zero-filled
    snapshots rather than raising."""


@dataclass(frozen=True)
class MountUsage:
    mount_path: str
    mounted: bool
    total_bytes: int
    used_bytes: int
    available_bytes: int
    pct_used: float
    surfaces: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class DiskUsageSnapshot:
    mounts: list[MountUsage]


def _resolve_surface_paths() -> dict[str, Path]:
    """Resolve surface name → host Path using env vars (read at call time)."""
    paths: dict[str, Path] = {}
    for name in _SURFACE_NAMES:
        env_var, default = _SURFACE_ENV[name]
        raw = os.environ.get(env_var) or default
        if name == "spooty" and not raw:
            # Default: $MUSIC_INBOX_DIR/spooty or /srv/music/inbox/spooty.
            inbox_root = os.environ.get(_SURFACE_ENV["inbox"][0]) or _SURFACE_ENV["inbox"][1]
            raw = str(Path(inbox_root) / "spooty")
        paths[name] = Path(raw)
    return paths


def _walk_size_bytes(root: Path, *, exclude: tuple[Path, ...] = ()) -> int:
    """Sum file sizes under `root` recursively. Missing → 0. Symlinks
    are not followed. Stat errors on individual entries are skipped
    rather than raised.

    `exclude` lists subpaths whose contents should NOT be counted; this
    is how we keep inbox/spooty byte counts disjoint when spooty lives
    inside inbox on disk.
    """
    if not root.exists():
        return 0
    excluded_resolved = {str(p.resolve() if p.exists() else p) for p in exclude}
    total = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # Prune excluded subtrees in-place so os.walk doesn't descend.
        try:
            dirpath_resolved = str(Path(dirpath).resolve())
        except OSError:
            dirpath_resolved = dirpath
        if dirpath_resolved in excluded_resolved:
            dirnames[:] = []
            continue
        dirnames[:] = [
            d for d in dirnames
            if str(Path(dirpath, d)) not in excluded_resolved
            and str(Path(dirpath, d).resolve() if Path(dirpath, d).exists() else Path(dirpath, d)) not in excluded_resolved
        ]
        for name in filenames:
            try:
                total += os.stat(os.path.join(dirpath, name), follow_symlinks=False).st_size
            except OSError:
                continue
    return total


def _longest_prefix_mount(surface_path: Path, mount_paths: list[str]) -> str | None:
    """Return the mount whose path is the longest prefix of `surface_path`.

    Comparison uses resolved absolute string paths with a trailing slash
    so that `/mnt/archive` matches a surface at `/mnt/archive/library`
    but not at `/mnt/archive-other`.
    """
    surface_str = str(surface_path.resolve() if surface_path.exists() else surface_path)
    if not surface_str.endswith(os.sep):
        surface_str_cmp = surface_str + os.sep
    else:
        surface_str_cmp = surface_str
    best: str | None = None
    best_len = -1
    for m in mount_paths:
        m_cmp = m if m.endswith(os.sep) else m + os.sep
        if surface_str_cmp.startswith(m_cmp) and len(m) > best_len:
            best = m
            best_len = len(m)
    return best


def get_disk_usage(
    *,
    mounts: tuple[str, ...] | None = None,
    surfaces: dict[str, Path] | None = None,
) -> DiskUsageSnapshot:
    """Snapshot disk usage across the configured mounts + surfaces.

    Args:
      mounts: override list of mount paths (defaults to /, /mnt/seagate,
        /mnt/archive). A mount whose path doesn't exist renders with
        `mounted=False` and zero byte counts.
      surfaces: override surface name → host path (defaults read from env).

    No exceptions are raised for missing mounts or surfaces — the
    snapshot is always well-formed so the panel can render cleanly on
    dev hosts that don't have the production layout.
    """
    mount_paths = list(mounts) if mounts is not None else list(_DEFAULT_MOUNTS)
    surface_paths = surfaces if surfaces is not None else _resolve_surface_paths()

    # First pass: walk each surface once, then attribute to mounts.
    # Exclude other-surface subpaths so byte counts are disjoint when
    # one surface lives inside another on disk (spooty inside inbox).
    surface_bytes_by_mount: dict[str, dict[str, int]] = {m: {} for m in mount_paths}
    for surface_name in _SURFACE_NAMES:
        path = surface_paths.get(surface_name)
        if path is None:
            continue
        exclude = tuple(
            p for other_name, p in surface_paths.items()
            if other_name != surface_name and p != path
        )
        size = _walk_size_bytes(path, exclude=exclude)
        target_mount = _longest_prefix_mount(path, mount_paths)
        if target_mount is None:
            # Surface lives off the configured mount tree — skip.
            # (e.g., MUSIC_ARCHIVE_DIR=/tmp/whatever on a dev host)
            continue
        surface_bytes_by_mount[target_mount][surface_name] = size

    mounts_out: list[MountUsage] = []
    for mp in mount_paths:
        p = Path(mp)
        # Ensure surfaces dict has all known keys so renderers don't
        # branch on presence.
        surfaces_for_mount = {n: surface_bytes_by_mount[mp].get(n, 0) for n in _SURFACE_NAMES}
        if not p.exists():
            mounts_out.append(MountUsage(
                mount_path=mp,
                mounted=False,
                total_bytes=0,
                used_bytes=0,
                available_bytes=0,
                pct_used=0.0,
                surfaces=surfaces_for_mount,
            ))
            continue
        try:
            usage = shutil.disk_usage(mp)
        except OSError:
            mounts_out.append(MountUsage(
                mount_path=mp,
                mounted=False,
                total_bytes=0,
                used_bytes=0,
                available_bytes=0,
                pct_used=0.0,
                surfaces=surfaces_for_mount,
            ))
            continue
        pct = (usage.used / usage.total * 100.0) if usage.total > 0 else 0.0
        mounts_out.append(MountUsage(
            mount_path=mp,
            mounted=True,
            total_bytes=int(usage.total),
            used_bytes=int(usage.used),
            available_bytes=int(usage.free),
            pct_used=round(pct, 2),
            surfaces=surfaces_for_mount,
        ))

    return DiskUsageSnapshot(mounts=mounts_out)


def threshold_class(pct_used: float) -> str:
    """Map pct_used → CSS modifier class per build-prompt §3.

    < 60   → `is-pulp` (--mash-pulp; healthy)
    60-85  → `is-amber` (--amber; warning)
    > 85   → `is-ember` (--ember; critical)

    Class names are stable contract used by `library_disk_panel.py`
    and `tests/service/test_library_disk.py`.
    """
    if pct_used > 85.0:
        return "is-ember"
    if pct_used >= 60.0:
        return "is-amber"
    return "is-pulp"


def format_bytes(n: int) -> str:
    """Compact human format for the panel: 12.4 GB, 932 MB, 4 KB."""
    if n < 1024:
        return f"{n} B"
    units = ("KB", "MB", "GB", "TB", "PB")
    size = float(n)
    unit = "B"
    for u in units:
        size /= 1024.0
        unit = u
        if size < 1024.0:
            break
    if size >= 100:
        return f"{size:.0f} {unit}"
    return f"{size:.1f} {unit}"
