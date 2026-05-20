"""Inbox client — filesystem walk of ``$MUSIC_INBOX_DIR``.

Sprint-10 / inbox-impl. Per the package contract (see ``README.md``):
- one module per external surface (here: the inbox tree on disk),
- typed return values (``InboxFolder`` dataclass; no bare dicts),
- typed exceptions on failure (``InboxUnavailable``),
- env-var configuration read at call time so tests can monkeypatch.

The inbox is the source-of-truth queue between rip-side (cd_rip) /
spooty-side (spooty) producers and the beets importer. This client
enumerates pending folders so the Library Manager's Inbox panel can
surface them to the operator + drive ad-hoc imports via the
``import_now`` entry point.

Layout convention:

    $MUSIC_INBOX_DIR/
      <cd-rip-folder>/            <- source="cd_rip"
        READY                     <- optional READY marker
      spooty/
        <spooty-folder>/          <- source="spooty"

Anything under ``$MUSIC_INBOX_DIR`` that is a directory and is NOT the
``spooty`` subdir is treated as a cd_rip folder. Anything under
``$MUSIC_INBOX_DIR/spooty/`` is a spooty folder.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from archivist.service.config import get_config


DEFAULT_INBOX_DIR = "/srv/music/inbox"


class InboxUnavailable(Exception):
    """Inbox root does not exist or is not readable."""


@dataclass(frozen=True)
class InboxFolder:
    name: str
    path: str
    source: Literal["cd_rip", "spooty"]
    file_count: int
    size_bytes: int
    last_modified: str  # ISO 8601 UTC
    ready_marker_present: bool

    def to_dict(self) -> dict:
        return asdict(self)


def _inbox_root() -> Path:
    """Resolve the inbox root via the config store (call time)."""
    return Path(get_config().music_inbox_dir or DEFAULT_INBOX_DIR)


def _spooty_root() -> Path:
    """Resolve the spooty sub-root via the config store (call time).

    The historical layout is `<inbox>/spooty/`; ``music_spooty_dir``
    defaults to that, but the config store lets the operator point
    it elsewhere on disk.
    """
    cfg = get_config()
    if cfg.music_spooty_dir:
        return Path(cfg.music_spooty_dir)
    return _inbox_root() / "spooty"


def _walk_folder(folder: Path, source: Literal["cd_rip", "spooty"]) -> InboxFolder:
    file_count = 0
    size_bytes = 0
    latest_mtime = folder.stat().st_mtime
    ready = False
    # rglob is fine for the inbox — these are leaf folders with a handful
    # of files each, not deep trees. We swallow per-file stat errors so a
    # disappearing tmpfile doesn't poison the whole listing.
    for entry in folder.rglob("*"):
        try:
            if entry.is_file():
                file_count += 1
                st = entry.stat()
                size_bytes += st.st_size
                if st.st_mtime > latest_mtime:
                    latest_mtime = st.st_mtime
                if entry.name == "READY" and entry.parent == folder:
                    ready = True
        except OSError:
            continue
    return InboxFolder(
        name=folder.name,
        path=str(folder),
        source=source,
        file_count=file_count,
        size_bytes=size_bytes,
        last_modified=datetime.fromtimestamp(latest_mtime, tz=UTC)
        .isoformat(timespec="seconds"),
        ready_marker_present=ready,
    )


def list_inbox_folders() -> list[InboxFolder]:
    """Enumerate pending folders under ``$MUSIC_INBOX_DIR``.

    Top-level subdirs (except ``spooty/``) → ``source="cd_rip"``.
    Subdirs of ``$MUSIC_INBOX_DIR/spooty/`` → ``source="spooty"``.

    Returns folders sorted by ``last_modified`` descending (newest
    first) so the operator sees the most-recent arrivals at the top.

    Raises ``InboxUnavailable`` when the root is missing or unreadable.
    """
    root = _inbox_root()
    if not root.exists() or not root.is_dir():
        raise InboxUnavailable(f"inbox root not found: {root}")

    folders: list[InboxFolder] = []
    try:
        entries = sorted(root.iterdir())
    except PermissionError as exc:
        raise InboxUnavailable(f"inbox root unreadable: {root}") from exc

    spooty_root = _spooty_root()
    # When spooty_root sits directly under the inbox (the default
    # layout), skip it from the cd_rip enumeration so we don't double-
    # count or mislabel its contents.
    try:
        spooty_in_inbox = spooty_root.resolve().parent == root.resolve()
    except OSError:
        spooty_in_inbox = spooty_root.parent == root

    for entry in entries:
        if not entry.is_dir():
            continue
        if spooty_in_inbox and entry.name == spooty_root.name:
            continue
        folders.append(_walk_folder(entry, source="cd_rip"))

    if spooty_root.is_dir():
        try:
            spooty_entries = sorted(spooty_root.iterdir())
        except PermissionError:
            spooty_entries = []
        for entry in spooty_entries:
            if entry.is_dir():
                folders.append(_walk_folder(entry, source="spooty"))

    folders.sort(key=lambda f: f.last_modified, reverse=True)
    return folders


def _import_command(folder: InboxFolder) -> list[str]:
    """Return the argv to invoke for this folder's import path.

    cd_rip folders use the beets ``process-ready-auto`` wrapper; spooty
    folders use ``spooty-import.sh``. Operators can override either
    binary via env vars (``CDA_PROCESS_READY_BIN`` /
    ``CDA_SPOOTY_IMPORT_BIN``) so the dev-box can wire smoke binaries.
    """
    if folder.source == "spooty":
        bin_cmd = os.environ.get("CDA_SPOOTY_IMPORT_BIN", "spooty-import.sh")
    else:
        bin_cmd = os.environ.get("CDA_PROCESS_READY_BIN", "bin/process-ready-auto")
    return [*shlex.split(bin_cmd), folder.path]


def import_now(folder_name: str) -> dict:
    """Kick off the importer for ``folder_name`` (fire-and-forget).

    Looks the folder up in the current inbox listing (so we know its
    source + canonical absolute path), spawns the matching importer
    binary via ``subprocess.Popen``, and returns immediately. The
    importer is a long-running process; the panel UI displays the
    returned ``message`` to confirm the operator action landed and
    polls the inbox listing for the folder to disappear once the
    importer consumes it.

    Returns ``{"status": "started" | "failed", "message": str}``.
    Never raises — transport failures degrade to ``status="failed"``.
    """
    try:
        listing = list_inbox_folders()
    except InboxUnavailable as exc:
        return {"status": "failed", "message": f"inbox unavailable: {exc}"}

    match = next((f for f in listing if f.name == folder_name), None)
    if match is None:
        return {
            "status": "failed",
            "message": f"folder not found in inbox: {folder_name}",
        }

    argv = _import_command(match)
    try:
        subprocess.Popen(  # noqa: S603 — argv form, shell=False
            argv,
            shell=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except FileNotFoundError:
        return {
            "status": "failed",
            "message": f"importer binary not found: {argv[0]}",
        }
    except PermissionError:
        return {
            "status": "failed",
            "message": f"importer not executable: {argv[0]}",
        }
    except OSError as exc:
        return {
            "status": "failed",
            "message": f"importer spawn failed: {exc}",
        }
    return {
        "status": "started",
        "message": f"importer started for {match.name} ({match.source})",
    }
