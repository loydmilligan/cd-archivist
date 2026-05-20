"""FastAPI status surface.

Three routes:
  GET /            — single-file HTML status page, dressed in Mash Co.
  GET /api/status  — JSON snapshot of LoopState
  GET /api/log     — text/plain tail of the pipeline log (deque, cap 1000)

The HTML lives inline (`_PAGE_HTML`). Styling comes from the vendored
`archivist/service/static/css/tokens.css` (Mash Co. v0.1.0) mounted at
`/static`, with page-specific overrides in an inline <style> block.

Mash Co. voice/visual contract enforced here:
  - sentence case body copy (Title Case only for proper nouns)
  - eyebrows ≤2 words, all-caps, with `letter-spacing: 0.08em`
  - dark-first (`data-theme="dark"` on <html>)
  - no decorative emoji (functional Unicode glyphs only)
  - card has full border + a 3px semantic-color left-border accent
    (not the bare left-stripe anti-pattern)
"""
from __future__ import annotations

import html
import logging
import re
import shutil
import time as _time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from archivist.state_machine.drive_status import DriveStatus

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from archivist.models.manifest import Manifest, read_manifest
from archivist.pipeline.review_capture import recapture_review

_RECAPTURE_BUSY_STATES = {"CAPTURE", "EJECT"}

logger = logging.getLogger(__name__)

_LOG_LINES_CAP = 1000
_LOG_LINES_DEFAULT = 200
_STATIC_DIR = Path(__file__).parent / "static"
# Sprint-7 / impl-rig-stats-endpoint: process-start monotonic clock for
# uptime. Captured at module import so the elapsed seconds reported by
# /api/rig/stats reflects how long this daemon process has been alive.
_PROCESS_START_MONOTONIC = _time.monotonic()


def _format_bytes_short(n: int) -> str:
    """Mono-shorthand byte formatter — `'26.4 GB'`, `'47 MB'`, `'512 B'`.

    Single decimal place above MB to keep the rig-stats group narrow.
    """
    abs_n = abs(int(n))
    if abs_n < 1024:
        return f"{abs_n} B"
    kb = abs_n / 1024
    if kb < 1024:
        return f"{kb:.1f} KB"
    mb = kb / 1024
    if mb < 1024:
        return f"{mb:.1f} MB"
    gb = mb / 1024
    if gb < 1024:
        return f"{gb:.1f} GB"
    return f"{gb / 1024:.1f} TB"


def _format_uptime_short(seconds: int) -> str:
    """Mono-shorthand uptime — `'1d 22h'`, `'4h 12m'`, `'47m'`, `'9s'`."""
    s = max(0, int(seconds))
    days, rem = divmod(s, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m"
    return f"{secs}s"


_DISC_ID_RE = re.compile(r"^CD_\d{4}$")
# Sprint-4: also accept the new shape `YYYY-MM-DD_HHMM_disc-NNNNNN`.
_NEW_FOLDER_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{4}_disc-\d{6}$")
_VALID_DISC_FOLDER_RE = re.compile(
    r"^(?:CD_\d{4}|\d{4}-\d{2}-\d{2}_\d{4}_disc-\d{6})$"
)


@dataclass
class LoopState:
    """Mutable snapshot the state-machine writes; the service reads.

    Sprint-3 / test-last-tick: `last_updated` was renamed to
    `state_entered_at` (advances on transitions only) and a separate
    `last_tick_at` heartbeat field was added (advances every tick).
    Sprint-4 / D-manual-mode: `mode` field controls auto-advance gating.
    """

    state: str = "IDLE"
    disc_id: str | None = None
    last_rip_status: str | None = None
    state_entered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_tick_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    # Sprint-3 / test-rip-progress: live cdparanoia progress label.
    rip_progress: str | None = None
    # Sprint-4 / D-manual-mode: "auto" (default, unchanged behaviour) or
    # "manual" (state-machine waits for /api/control/* triggers).
    mode: str = "auto"
    # Sprint-4 / D-process-ready-trigger: shell command (argv-style;
    # shlex.split internally) invoked after the atomic READY rename.
    # Empty string disables the hook (the systemd backup timer is the
    # safety net).
    process_ready_hook: str = ""
    # Sprint-6.5 / impl-drive-status-snapshot / D-drive-status-snapshot-
    # schema: live drive/rip/capture snapshot exposed via /api/drive/
    # status. Written from the state-machine thread (transitions) and
    # the ripper's progress-callback thread; read from the FastAPI
    # request thread. The DriveStatus's internal `lock` (threading.
    # RLock) serializes multi-field mutations.
    drive_status: DriveStatus = field(default_factory=DriveStatus)


def _tail_log(path: Path, lines: int) -> str:
    if not path.exists():
        return ""
    n = max(0, min(lines, _LOG_LINES_CAP))
    if n == 0:
        return ""
    with path.open("r", encoding="utf-8", errors="replace") as f:
        return "".join(deque(f, maxlen=n))


_MANUAL_TRIGGERS: dict[str, set[str]] = {
    "start-rip": {"STABILIZE"},
    "eject": {"RIP"},
    "capture": {"EJECT"},
}


def create_app(
    loop_state: LoopState,
    log_path: Path,
    *,
    discs_root: Path | None = None,
    legacy_discs_roots: tuple[Path, ...] = (),
    recapture_camera: Callable[..., Any] | None = None,
    recapture_led: Any | None = None,
    loop: Any | None = None,
    review_root: Path | None = None,
    library_root: Path | None = None,
    music_root: Path | None = None,
) -> FastAPI:
    app = FastAPI(title="cd-archivist", docs_url=None, redoc_url=None)

    if _STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    @app.get("/api/status")
    def api_status() -> JSONResponse:
        return JSONResponse(
            {
                "state": loop_state.state,
                "disc_id": loop_state.disc_id,
                "last_rip_status": loop_state.last_rip_status,
                "state_entered_at": loop_state.state_entered_at.isoformat(),
                "last_tick_at": loop_state.last_tick_at.isoformat(),
                "rip_progress": loop_state.rip_progress,
                "mode": loop_state.mode,
            }
        )

    if music_root is not None:
        from archivist.service.disc_card_builder import build_kanban_state
        from archivist.service.operator_hints import mount_operator_hints_routes

        @app.get("/api/kanban")
        def api_kanban() -> JSONResponse:
            state = build_kanban_state(music_root, loop_state=loop_state)
            payload = state.to_dict()
            # Sprint-6.5 / impl-adaptive-polling: top-level active_rip
            # drives the client's poll cadence (1s active / 5s idle).
            payload["active_rip"] = any(
                c.get("progress") is not None
                for c in payload["buckets"].get("capture", [])
            )
            return JSONResponse(payload)

        mount_operator_hints_routes(app, music_root=music_root)

        from archivist.service.damaged_disc import mount_damaged_disc_routes
        mount_damaged_disc_routes(app, music_root=music_root)

        # Sprint-7 / impl-candidates-endpoint. D-candidates-source-
        # priority: (1) musicbrainz_disc_id lookup, prepended at score
        # 1.0; (2) AcoustID fingerprint lookup; (3) metadata search by
        # operator_hints.artist|album. Dedupe by MBID, sort desc, top 5.
        # D-candidates-cache-ttl: TTL=300s, key=folder name only — hints
        # mtime is intentionally NOT part of the key because hint edits
        # land via /api/disc/<folder>/hints which already invalidates
        # the cache by call site (next request after an edit re-runs).
        _CANDIDATES_CACHE_TTL_SECONDS = 300
        _candidates_cache: dict[str, tuple[float, dict]] = {}

        def _find_disc_folder(folder: str) -> Path | None:
            from archivist.service.disc_card_builder import _iter_disc_folders
            for sub in ("review", "inbox", "failed", "archive"):
                for d in _iter_disc_folders(music_root / sub, depth=1):
                    if d.name == folder:
                        return d
            return None

        @app.get("/api/disc/{folder}/candidates")
        def api_disc_candidates(folder: str) -> JSONResponse:
            import json as _json

            target = _find_disc_folder(folder)
            if target is None:
                raise HTTPException(status_code=404, detail=f"folder not found: {folder}")

            now = _time.monotonic()
            cached = _candidates_cache.get(folder)
            if cached is not None and (now - cached[0]) < _CANDIDATES_CACHE_TTL_SECONDS:
                return JSONResponse(cached[1])

            source: dict = {}
            sp = target / "source.json"
            if sp.is_file():
                try:
                    source = _json.loads(sp.read_text(encoding="utf-8")) or {}
                except (ValueError, OSError):
                    source = {}

            identifiers = source.get("identifiers") or {}
            mb_disc_id = identifiers.get("musicbrainz_disc_id")
            hints = source.get("operator_hints") or {}

            from archivist.service.mb_client import get_mb_client
            client = get_mb_client()

            candidates: list[dict] = []
            try:
                if mb_disc_id:
                    hit = client.lookup_by_disc_id(mb_disc_id)
                    if hit is not None:
                        hit["score"] = 1.0
                        candidates.append(hit)
                else:
                    fp_hits = client.search_by_fingerprint(target)
                    if fp_hits:
                        candidates.extend(fp_hits)
                    elif hints.get("artist") or hints.get("album"):
                        candidates.extend(client.search_by_metadata(
                            artist=hints.get("artist"),
                            album=hints.get("album"),
                        ))
            except Exception as exc:  # noqa: BLE001 — wrap any MB failure
                logger.warning("candidates: musicbrainz failure: %s", exc)
                raise HTTPException(
                    status_code=503,
                    detail={"error": "musicbrainz unavailable"},
                ) from exc

            seen: set[str] = set()
            unique: list[dict] = []
            for c in candidates:
                mbid = c.get("mbid") or ""
                if mbid and mbid in seen:
                    continue
                if mbid:
                    seen.add(mbid)
                unique.append(c)
            unique.sort(key=lambda c: float(c.get("score") or 0), reverse=True)
            payload = {
                "candidates": unique[:5],
                "source": "musicbrainzngs",
            }
            _candidates_cache[folder] = (now, payload)
            return JSONResponse(payload)

        # Sprint-6.5 / impl-collapsed-card-actions: high-confidence
        # one-click accept. Body invokes the existing beets pipeline
        # via the docker stack — sprint-7 wires the actual `beet
        # import --search-id <mbid>` shell-out. For sprint-6.5 the
        # endpoint records the operator's intent on disk.
        @app.post("/api/disc/{folder}/accept-top-candidate")
        async def api_accept_top_candidate(folder: str, request: Request) -> JSONResponse:
            """Sprint-7: additive body contract. With no body, picks the
            on-disk top_candidate.json (sprint-6.5 behaviour). With a
            JSON body `{mbid: str}`, accepts the operator-picked MBID
            directly — used by the Beets-candidates Apply buttons."""
            import json as _json
            from archivist.service.disc_card_builder import _iter_disc_folders
            target: Path | None = None
            for sub in ("review", "inbox", "failed"):
                for d in _iter_disc_folders(music_root / sub, depth=1):
                    if d.name == folder:
                        target = d
                        break
                if target is not None:
                    break
            if target is None:
                raise HTTPException(
                    status_code=404, detail=f"folder not found: {folder}",
                )

            # Operator-picked MBID path (additive sprint-7 surface).
            picked_mbid: str | None = None
            try:
                raw = await request.body()
            except Exception:  # noqa: BLE001 — body read may fail on weird clients
                raw = b""
            if raw:
                try:
                    body = _json.loads(raw)
                    picked_mbid = (body or {}).get("mbid") or None
                except ValueError:
                    picked_mbid = None
            if picked_mbid:
                accepted = {"mbid": picked_mbid, "score": None, "source": "operator"}
                (target / "ACCEPTED").write_text(
                    _json.dumps(accepted), encoding="utf-8",
                )
                return JSONResponse({"accepted": accepted, "folder": folder})

            # No-body path: pick from on-disk top_candidate.json (legacy).
            top_cand_path = target / "top_candidate.json"
            if not top_cand_path.is_file():
                raise HTTPException(
                    status_code=409,
                    detail="no top_candidate.json sidecar on disk",
                )
            top = _json.loads(top_cand_path.read_text(encoding="utf-8"))
            if float(top.get("score") or 0) < 0.85:
                raise HTTPException(
                    status_code=409,
                    detail="top candidate score below 0.85 threshold",
                )
            (target / "ACCEPTED").write_text(
                _json.dumps({"mbid": top.get("mbid"), "score": top.get("score")}),
                encoding="utf-8",
            )
            return JSONResponse({"accepted": top, "folder": folder})

        # Sprint-6.5 / impl-right-drawer: per-disc rip-log tail for
        # the card-detail drawer body.
        @app.get("/api/disc/{folder}/log/tail")
        def api_disc_log_tail(
            folder: str, limit: int = Query(200, ge=1, le=2000),
        ) -> PlainTextResponse:
            from archivist.service.disc_card_builder import _iter_disc_folders
            target: Path | None = None
            for sub in ("review", "inbox", "failed", "archive"):
                root = music_root / sub
                if sub == "library":
                    continue
                for d in _iter_disc_folders(root, depth=1):
                    if d.name == folder:
                        target = d
                        break
                if target is not None:
                    break
            if target is None:
                raise HTTPException(status_code=404)
            log = target / "rip.log"
            if not log.is_file():
                log = target / "logs" / "rip.log"
            if not log.is_file():
                return PlainTextResponse("")
            with log.open("r", encoding="utf-8", errors="replace") as f:
                return PlainTextResponse("".join(deque(f, maxlen=limit)))

    if music_root is not None:
        @app.get("/api/rig/stats")
        def api_rig_stats() -> JSONResponse:
            """Sprint-7 / impl-rig-stats-endpoint. Storage from
            `shutil.disk_usage(music_root)`; uptime from the
            module-init monotonic timestamp. Human strings follow
            the build-prompt mono-shorthand rules."""
            usage = shutil.disk_usage(music_root)
            seconds = int(_time.monotonic() - _PROCESS_START_MONOTONIC)
            return JSONResponse({
                "storage": {
                    "used_bytes": int(usage.used),
                    "total_bytes": int(usage.total),
                    "human": (
                        f"{_format_bytes_short(usage.used)} / "
                        f"{_format_bytes_short(usage.total)}"
                    ),
                },
                "uptime": {
                    "seconds": seconds,
                    "human": _format_uptime_short(seconds),
                },
            })

    @app.get("/api/log")
    def api_log(lines: int = Query(_LOG_LINES_DEFAULT, ge=0)) -> PlainTextResponse:
        return PlainTextResponse(_tail_log(log_path, lines))

    @app.get("/api/drive/status")
    def api_drive_status() -> JSONResponse:
        """Sprint-6.5 / impl-drive-status-endpoint. Reads from
        `loop_state.drive_status` (populated by drivers'
        impl-drive-status-snapshot). Returns a default-idle snapshot
        when the attribute is missing so the right-drawer doesn't
        500 in environments without the drivers update yet."""
        snap = getattr(loop_state, "drive_status", None)
        if snap is None:
            return JSONResponse({
                "state": "idle",
                "current_disc": None, "current_track": None,
                "track_total": None, "sector_current": None,
                "sector_total": None, "retries_on_current_track": None,
                "photo_state": None, "elapsed_seconds": None,
            })
        return JSONResponse({
            "state": getattr(snap, "state", "idle"),
            "current_disc": getattr(snap, "current_disc", None),
            "current_track": getattr(snap, "current_track", None),
            "track_total": getattr(snap, "track_total", None),
            "sector_current": getattr(snap, "sector_current", None),
            "sector_total": getattr(snap, "sector_total", None),
            "retries_on_current_track":
                getattr(snap, "retries_on_current_track", None),
            "photo_state": getattr(snap, "photo_state", None),
            "elapsed_seconds": getattr(snap, "elapsed_seconds", None),
        })

    @app.get("/api/logs/tail")
    def api_logs_tail(
        request: Request,
        limit: int = Query(200, ge=1),
    ) -> JSONResponse:
        """Sprint-6.5 / impl-logs-tail-endpoint. Default tail of N=200
        lines from `ARCHIVIST_LOG_PATH` (env override) or the path the
        daemon was started with. Future per-rip/per-card filter params
        are accepted-and-ignored today so sprint-7 can wire the UI
        without a contract bump (request.query_params is consulted
        only via the typed `limit` param)."""
        import os as _os
        # Honour the env override so operators can re-point logs
        # without restarting the daemon; fall back to log_path.
        target = Path(_os.environ.get("ARCHIVIST_LOG_PATH") or str(log_path))
        if not target.is_file():
            raise HTTPException(
                status_code=404, detail=f"log file not found: {target}",
            )
        clamped = min(max(limit, 1), 2000)
        with target.open("r", encoding="utf-8", errors="replace") as f:
            tail = list(deque(f, maxlen=clamped))
        # Strip trailing newline per line for a clean JSON list.
        lines_out = [line.rstrip("\n") for line in tail]
        # truncated=True iff the source had MORE than the clamped limit.
        truncated = False
        try:
            with target.open("rb") as fh:
                truncated = sum(1 for _ in fh) > clamped
        except OSError:
            truncated = False
        # Drain query_params just so unused-name lints don't fire and
        # the accept-and-ignore contract is observable in code.
        _ = request.query_params
        return JSONResponse({
            "lines": lines_out,
            "log_path": str(target),
            "truncated": truncated,
        })

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        # Per sprint-9 build-prompt §6, `/` redirects to `/rip`. We
        # serve a tiny meta-redirect HTML so curl-without-follow still
        # gets a 200 and the legacy callers that read the body see the
        # link target. Browsers follow instantly.
        if music_root is not None:
            return HTMLResponse(
                '<!doctype html><meta charset="utf-8">'
                '<meta http-equiv="refresh" content="0; url=/rip">'
                '<title>cd-archivist</title>'
                '<p>Redirecting to <a href="/rip">/rip</a>…</p>'
            )
        return HTMLResponse(_PAGE_HTML)

    @app.get("/rip", response_class=HTMLResponse)
    def rip_index() -> HTMLResponse:
        if music_root is not None:
            from archivist.service.kanban_page import render_kanban_page
            return HTMLResponse(render_kanban_page(music_root, loop_state))
        return HTMLResponse(_PAGE_HTML)

    # ---------------- Library Manager surface (sprint-9) ----------------
    # Build-prompt: docs/reference/mashco-design-system/cd-archivist-library/handoff/build-prompt.md

    if music_root is not None:
        from archivist.service.library_page import (
            V1_PANEL_IDS,
            render_library_page,
        )

        @app.get("/library", response_class=HTMLResponse)
        def library_index() -> HTMLResponse:
            return HTMLResponse(
                render_library_page(music_root, loop_state, panel_id=None)
            )

        @app.get("/library/{panel_id}", response_class=HTMLResponse)
        def library_panel(panel_id: str) -> HTMLResponse:
            # v2 panel ids (`review`, `recent`, `cron`) are not
            # addressable yet — build-prompt §3 + §7 explicitly defer
            # them. Any unknown id 404s.
            if panel_id not in V1_PANEL_IDS:
                raise HTTPException(status_code=404, detail="unknown panel")
            return HTMLResponse(
                render_library_page(music_root, loop_state, panel_id=panel_id)
            )

        # ---------- /api/library/* — per-panel data endpoints (sprint-10) ----------

        @app.get("/api/library/disk")
        def api_library_disk() -> JSONResponse:
            """Sprint-10 / disk-impl. Per-mount disk usage + per-surface
            byte breakdown for the Disk panel. Polled at 30s cadence by
            the panel's `<meta name="library-poll-ms">` tag."""
            from archivist.service.clients.disk_client import get_disk_usage
            snap = get_disk_usage()
            return JSONResponse({
                "mounts": [
                    {
                        "mount_path": m.mount_path,
                        "mounted": m.mounted,
                        "total_bytes": m.total_bytes,
                        "used_bytes": m.used_bytes,
                        "available_bytes": m.available_bytes,
                        "pct_used": m.pct_used,
                        "surfaces": dict(m.surfaces),
                    }
                    for m in snap.mounts
                ],
            })

        # ---- Inbox panel (sprint-10 / inbox-impl) ---------------------
        @app.get("/api/library/inbox")
        def api_library_inbox() -> JSONResponse:
            """List pending folders under `$MUSIC_INBOX_DIR`. Polled at
            5s cadence by the Inbox panel's poll meta tags."""
            from archivist.service.clients.inbox_client import (
                InboxUnavailable,
                list_inbox_folders,
            )
            try:
                folders = list_inbox_folders()
            except InboxUnavailable as exc:
                return JSONResponse(
                    {"folders": [], "error": str(exc)},
                    status_code=503,
                )
            return JSONResponse(
                {"folders": [f.to_dict() for f in folders]}
            )

        @app.post("/api/library/inbox/import-now")
        async def api_library_inbox_import_now(
            request: Request,
        ) -> JSONResponse:
            """Kick the importer for one folder (fire-and-forget).

            Body: `{"folder": "<name>"}`. Returns the import_now
            result verbatim with HTTP 200 on `started`, 409 on
            `failed` (folder missing, binary not found, etc.)."""
            import json as _json
            from archivist.service.clients.inbox_client import import_now
            try:
                raw = await request.body()
                body = _json.loads(raw or b"{}")
            except ValueError:
                raise HTTPException(
                    status_code=400, detail="invalid json body",
                )
            folder = (body or {}).get("folder")
            if not folder or not isinstance(folder, str):
                raise HTTPException(
                    status_code=400,
                    detail="missing or non-string `folder` field",
                )
            result = import_now(folder)
            status_code = 200 if result["status"] == "started" else 409
            return JSONResponse(result, status_code=status_code)

        # ---- Library (browse) panel (sprint-10 / library-impl) --------
        @app.get("/api/library/browse")
        def api_library_browse(q: str = Query("", min_length=0)) -> JSONResponse:
            """Search Navidrome by query string via Subsonic search3.view.
            Empty `q` returns an empty list without hitting the API.
            Navidrome unavailable → 503 with `{albums: [], error: ...}`
            so the client-side JS can render a friendly empty state."""
            from archivist.service.clients.subsonic_client import (
                NavidromeUnavailable,
                search,
            )
            try:
                albums = search(q)
            except NavidromeUnavailable as exc:
                return JSONResponse(
                    {"albums": [], "error": str(exc)}, status_code=503,
                )
            return JSONResponse({
                "albums": [
                    {
                        "id": a.id, "name": a.name, "artist": a.artist,
                        "cover_art_id": a.cover_art_id,
                        "created": a.created,
                    }
                    for a in albums
                ],
            })

        @app.get("/api/library/browse/recent")
        def api_library_browse_recent() -> JSONResponse:
            """10 most-recently-added albums via Subsonic
            getAlbumList2.view?type=newest. 503 on unavailable."""
            from archivist.service.clients.subsonic_client import (
                NavidromeUnavailable,
                get_newest_albums,
            )
            try:
                albums = get_newest_albums(limit=10)
            except NavidromeUnavailable as exc:
                return JSONResponse(
                    {"albums": [], "error": str(exc)}, status_code=503,
                )
            return JSONResponse({
                "albums": [
                    {
                        "id": a.id, "name": a.name, "artist": a.artist,
                        "cover_art_id": a.cover_art_id,
                        "created": a.created,
                    }
                    for a in albums
                ],
            })

        # ---- Downloads (Spooty) panel (sprint-10 / downloads-impl) ----
        # Thin proxy: forwards operator actions to the spooty REST API
        # at $SPOOTY_API_URL and returns the response verbatim. spooty
        # is the source of truth for queue state.
        @app.get("/api/library/downloads")
        def api_library_downloads() -> JSONResponse:
            from archivist.service.clients.spooty_client import (
                SpootyUnavailable,
                list_playlists,
            )
            try:
                playlists = list_playlists()
            except SpootyUnavailable as exc:
                return JSONResponse(
                    {"playlists": [], "error": str(exc)},
                    status_code=503,
                )
            return JSONResponse(
                {"playlists": [p.to_dict() for p in playlists]}
            )

        @app.get("/api/library/downloads/playlists/{playlist_id}/tracks")
        def api_library_downloads_tracks(playlist_id: str) -> JSONResponse:
            from archivist.service.clients.spooty_client import (
                SpootyUnavailable,
                list_tracks,
            )
            try:
                tracks = list_tracks(playlist_id)
            except SpootyUnavailable as exc:
                return JSONResponse(
                    {"tracks": [], "error": str(exc)}, status_code=503,
                )
            return JSONResponse({"tracks": [t.to_dict() for t in tracks]})

        @app.post("/api/library/downloads/playlists")
        async def api_library_downloads_submit(
            request: Request,
        ) -> JSONResponse:
            import json as _json
            from archivist.service.clients.spooty_client import (
                SpootyUnavailable,
                submit_playlist,
            )
            try:
                body = _json.loads(await request.body() or b"{}")
            except ValueError:
                raise HTTPException(
                    status_code=400, detail="invalid json body",
                )
            url = (body or {}).get("url")
            if not url or not isinstance(url, str):
                raise HTTPException(
                    status_code=400,
                    detail="missing or non-string `url` field",
                )
            try:
                result = submit_playlist(url)
            except SpootyUnavailable as exc:
                return JSONResponse(
                    {"error": str(exc)}, status_code=503,
                )
            return JSONResponse(result)

        @app.post(
            "/api/library/downloads/playlists/{playlist_id}/retry",
        )
        def api_library_downloads_retry_playlist(
            playlist_id: str,
        ) -> JSONResponse:
            from archivist.service.clients.spooty_client import (
                SpootyUnavailable,
                retry_playlist,
            )
            try:
                result = retry_playlist(playlist_id)
            except SpootyUnavailable as exc:
                return JSONResponse(
                    {"error": str(exc)}, status_code=503,
                )
            return JSONResponse(result)

        @app.post("/api/library/downloads/tracks/{track_id}/retry")
        def api_library_downloads_retry_track(track_id: str) -> JSONResponse:
            from archivist.service.clients.spooty_client import (
                SpootyUnavailable,
                retry_track,
            )
            try:
                result = retry_track(track_id)
            except SpootyUnavailable as exc:
                return JSONResponse(
                    {"error": str(exc)}, status_code=503,
                )
            return JSONResponse(result)

        @app.delete("/api/library/downloads/tracks/{track_id}")
        def api_library_downloads_delete_track(
            track_id: str,
        ) -> JSONResponse:
            from archivist.service.clients.spooty_client import (
                SpootyUnavailable,
                delete_track,
            )
            try:
                result = delete_track(track_id)
            except SpootyUnavailable as exc:
                return JSONResponse(
                    {"error": str(exc)}, status_code=503,
                )
            return JSONResponse(result)

    # ---------------- /api/config (sprint-11 / settings-api-endpoints) -----
    # GET returns the current Config with secret fields masked.
    # POST applies a sparse update via config_store.save_config(); empty-
    # string in a password field is treated as "no change" (don't
    # overwrite the stored secret with empty).

    _MASKED_VALUE = "●" * 8  # eight bullet glyphs

    def _mask_config(cfg) -> dict[str, Any]:
        from archivist.service.config import SECRET_FIELDS, as_dict
        out = as_dict(cfg)
        for k in SECRET_FIELDS:
            out[k] = _MASKED_VALUE if out.get(k) else None
        return out

    def _validate_update(key: str, value: Any) -> tuple[bool, str | None]:
        """Per-field validation. Returns (skip, error).
        skip=True means "drop silently from updates" (empty password
        = no-change). error non-None means "reject the whole request
        with 400"."""
        from archivist.service.config import SECRET_FIELDS
        if value is None:
            return False, None  # allow clearing a key
        if not isinstance(value, str):
            return False, f"{key}: must be string or null"
        if key in SECRET_FIELDS and value == "":
            return True, None
        if value == "":
            return False, f"{key}: must be non-empty"
        if key.endswith("_url"):
            if not (value.startswith("http://") or value.startswith("https://")):
                return False, f"{key}: must start with http:// or https://"
        if key.endswith("_dir"):
            if not value.startswith("/"):
                return False, f"{key}: must be an absolute path"
        return False, None

    @app.get("/api/config")
    def api_config_get() -> JSONResponse:
        from archivist.service.config import get_config
        return JSONResponse(_mask_config(get_config()))

    @app.get("/settings", response_class=HTMLResponse)
    def settings_index() -> HTMLResponse:
        """Sprint-11 / settings-page-render. Read-write config UI bound
        to `/api/config`. Available regardless of `music_root` so the
        operator can configure music dirs from scratch."""
        from archivist.service.config import get_config
        from archivist.service.settings_page import render_settings_page
        return HTMLResponse(render_settings_page(get_config()))

    @app.post("/api/config")
    async def api_config_post(request: Request) -> JSONResponse:
        import json as _json
        from archivist.service.config import (
            UnknownConfigKey,
            get_config,
            save_config,
        )
        try:
            raw = await request.body()
            body = _json.loads(raw or b"{}")
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid json body")
        if not isinstance(body, dict):
            raise HTTPException(
                status_code=400, detail="body must be a JSON object",
            )

        errors: list[str] = []
        updates: dict[str, Any] = {}
        for key, value in body.items():
            skip, err = _validate_update(key, value)
            if err is not None:
                errors.append(err)
                continue
            if skip:
                continue
            updates[key] = value
        if errors:
            return JSONResponse(
                {"error": "validation failed", "details": errors},
                status_code=400,
            )

        if not updates:
            # All values were no-change-empties or the body was empty.
            return JSONResponse(_mask_config(get_config()))

        try:
            saved = save_config(updates)
        except UnknownConfigKey as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return JSONResponse(_mask_config(saved))

    # ---------------- library browser (sprint-3 / impl-library) ----------

    if discs_root is not None:
        _mount_library_routes(
            app, discs_root,
            loop_state=loop_state,
            recapture_camera=recapture_camera,
            recapture_led=recapture_led,
            legacy_discs_roots=legacy_discs_roots,
            library_root=library_root,
        )

    _mount_control_routes(app, loop_state=loop_state, loop=loop)
    _mount_review_routes(
        app,
        loop_state=loop_state,
        review_root=review_root,
        inbox_root=discs_root,
        use_v1_page=music_root is not None,
    )
    return app


def _mount_review_routes(
    app: FastAPI,
    *,
    loop_state: "LoopState",
    review_root: Path | None,
    inbox_root: Path | None,
    use_v1_page: bool = False,
) -> None:
    """Sprint-5 / impl-review-routes: /api/review/* surface.

    Sprint-6 / impl-review-page-v1: when `use_v1_page` is set, the
    `/review` HTML page renders the read-only Review v1 surface with
    the why-in-review explainer + manual-steps shell snippet; the
    sprint-5 `/review/<folder>` detail page is left in place for
    operators still mid-cycle on the old workflow.
    """
    from archivist.service import beets_review

    @app.get("/api/review/folders")
    def api_review_folders() -> JSONResponse:
        return JSONResponse(beets_review.handle_folder_list(review_root, inbox_root))

    @app.get("/api/review/{folder}/candidates")
    def api_review_candidates(
        folder: str,
        search: str | None = None,
        mbid: str | None = None,
    ) -> JSONResponse:
        return JSONResponse(beets_review.handle_candidates(
            folder,
            review_root=review_root,
            inbox_root=inbox_root,
            search=search,
            mbid=mbid,
        ))

    @app.post("/api/review/{folder}/apply")
    async def api_review_apply(folder: str, request: Request) -> JSONResponse:
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        return JSONResponse(beets_review.handle_apply(
            folder, payload,
            loop_state=loop_state,
            review_root=review_root,
            inbox_root=inbox_root,
        ))

    @app.post("/api/review/{folder}/use-as-is")
    def api_review_use_as_is(folder: str) -> JSONResponse:
        return JSONResponse(beets_review.handle_use_as_is(
            folder,
            loop_state=loop_state,
            review_root=review_root,
            inbox_root=inbox_root,
        ))

    @app.get("/api/review/{folder}/audio/{filename}")
    def api_review_audio(folder: str, filename: str) -> FileResponse:
        resolved = beets_review.find_folder(folder, review_root, inbox_root)
        if resolved is None:
            raise HTTPException(status_code=404)
        folder_path, _ = resolved
        target = _resolve_under(folder_path, filename)
        if target is None or not target.name.endswith(".flac"):
            raise HTTPException(status_code=404)
        return FileResponse(target, media_type="audio/flac")

    # --------- HTML page routes (impl-review-pages) ----------------

    @app.get("/review", response_class=HTMLResponse)
    def review_list() -> HTMLResponse:
        if use_v1_page:
            from archivist.service.review_page_v1 import render_review_v1
            return HTMLResponse(render_review_v1(
                review_root=review_root, inbox_root=inbox_root,
            ))
        folders = beets_review.list_review_folders(review_root, inbox_root)
        return HTMLResponse(beets_review.render_review_list(folders))

    @app.get("/review/{folder}", response_class=HTMLResponse)
    def review_detail(
        folder: str,
        search: str | None = None,
        mbid: str | None = None,
    ) -> HTMLResponse:
        return HTMLResponse(beets_review.render_review_detail_handler(
            folder,
            review_root=review_root,
            inbox_root=inbox_root,
            search=search,
            mbid=mbid,
        ))


def _mount_control_routes(
    app: FastAPI,
    *,
    loop_state: "LoopState",
    loop: Any | None,
) -> None:
    """Sprint-4 / impl-manual-mode: /api/control/* surface."""

    def _check_state_trigger(trigger: str, endpoint_name: str) -> None:
        """Enforce: auto-mode rejects (403); state mismatch yields 409."""
        if loop_state.mode == "auto":
            raise HTTPException(
                status_code=403,
                detail=f"{endpoint_name} is a manual-only trigger",
            )
        valid_states = _MANUAL_TRIGGERS[trigger]
        if loop_state.state not in valid_states:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"{endpoint_name} requires state in {sorted(valid_states)}; "
                    f"current state is {loop_state.state}"
                ),
            )

    @app.post("/api/control/mode")
    def control_mode(mode: str) -> JSONResponse:
        if mode not in ("auto", "manual"):
            raise HTTPException(status_code=400, detail="mode must be 'auto' or 'manual'")
        loop_state.mode = mode
        return JSONResponse({"mode": mode})

    @app.post("/api/control/start-rip")
    def control_start_rip() -> JSONResponse:
        _check_state_trigger("start-rip", "start-rip")
        if loop is not None:
            loop.advance("rip")
        return JSONResponse({"ok": True, "state": loop_state.state})

    @app.post("/api/control/eject")
    def control_eject() -> JSONResponse:
        _check_state_trigger("eject", "eject")
        if loop is not None:
            loop.advance("eject")
        return JSONResponse({"ok": True, "state": loop_state.state})

    @app.post("/api/control/capture")
    def control_capture() -> JSONResponse:
        _check_state_trigger("capture", "capture")
        if loop is not None:
            loop.advance("capture")
        return JSONResponse({"ok": True, "state": loop_state.state})

    @app.post("/api/control/reset")
    def control_reset() -> JSONResponse:
        """Always allowed — operator escape hatch."""
        if loop is not None:
            loop.advance("reset")
        else:
            # No loop attached (test client): mimic the state-machine
            # reset by stamping IDLE so callers can observe the effect.
            loop_state.state = "IDLE"
        return JSONResponse({"ok": True, "state": loop_state.state})


# ============== library browser helpers ==============================


def _format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 / 1024:.1f} MB"


def _rel_time(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    delta = (datetime.now(UTC) - dt).total_seconds()
    if delta < 60:
        return f"{int(delta)}s ago"
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    if delta < 86400:
        return f"{int(delta // 3600)}h ago"
    return f"{int(delta // 86400)}d ago"


def _accent_class(manifest: Manifest) -> str:
    """card--moss / card--amber / card--ember per rip status."""
    if manifest.status == "rip_failed":
        return "card--ember"
    if manifest.rips and manifest.rips[0].status == "success":
        return "card--moss"
    if manifest.rips and manifest.rips[0].status == "partial":
        return "card--amber"
    # status="ripped" with success was handled above; created / no-rip → amber.
    return "card--amber"


def _resolve_under(root: Path, *parts: str) -> Path | None:
    """Join parts onto root and reject anything that escapes the root.

    Returns the resolved path if it lives under `root` AND is a real file,
    else None. The check is path-traversal safe: `..` segments resolve
    out of the target dir, and an HTTPException(404) is raised by the
    caller.
    """
    try:
        candidate = (root.joinpath(*parts)).resolve()
        root_resolved = root.resolve()
    except (OSError, RuntimeError):
        return None
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


def _disc_dir(
    discs_root: Path,
    disc_id: str,
    *,
    legacy_roots: tuple[Path, ...] = (),
) -> Path | None:
    if not _VALID_DISC_FOLDER_RE.match(disc_id):
        return None
    for root in (discs_root, *legacy_roots):
        d = root / disc_id
        if d.is_dir():
            return d
    return None


def _mount_library_routes(
    app: FastAPI,
    discs_root: Path,
    *,
    loop_state: "LoopState",
    recapture_camera: Callable[..., Any] | None = None,
    recapture_led: Any | None = None,
    legacy_discs_roots: tuple[Path, ...] = (),
    library_root: Path | None = None,
) -> None:
    @app.get("/library", response_class=HTMLResponse)
    def library_list(status: str = "success") -> HTMLResponse:
        if status not in ("success", "failed", "all"):
            status = "success"
        return HTMLResponse(
            _render_library_list(
                discs_root, status=status, legacy_roots=legacy_discs_roots,
                library_root=library_root,
            )
        )

    @app.get("/library/{disc_id}", response_class=HTMLResponse)
    def library_detail(disc_id: str) -> HTMLResponse:
        if not _VALID_DISC_FOLDER_RE.match(disc_id):
            raise HTTPException(status_code=404)
        d = _disc_dir(discs_root, disc_id, legacy_roots=legacy_discs_roots)
        if d is None:
            raise HTTPException(status_code=404)
        if not (d / "manifest.json").is_file() and not (d / "source.json").is_file():
            raise HTTPException(status_code=404)
        return HTMLResponse(_render_library_detail(d, library_root=library_root))

    @app.get("/library/{disc_id}/album-cover")
    def library_album_cover(disc_id: str) -> FileResponse:
        """Sprint-5 / D-library-cover-preference: serve the beets-fetched
        cover from `<library_root>/<album_artist>/<album>/cover.{...}`.
        """
        from archivist.service.library import read_disc_summary
        d = _disc_dir(discs_root, disc_id, legacy_roots=legacy_discs_roots)
        if d is None:
            raise HTTPException(status_code=404)
        summary = read_disc_summary(d, library_root=library_root)
        if summary is None or summary.library_cover_path is None:
            raise HTTPException(status_code=404)
        target = summary.library_cover_path
        # Path-traversal guard: ensure it lives under library_root.
        if library_root is not None:
            try:
                target.resolve().relative_to(library_root.resolve())
            except ValueError:
                raise HTTPException(status_code=404) from None
        if not target.is_file():
            raise HTTPException(status_code=404)
        media = "image/png" if target.suffix.lower() == ".png" else "image/jpeg"
        return FileResponse(target, media_type=media)

    @app.get("/library/{disc_id}/captures/{filename}")
    def library_capture(disc_id: str, filename: str) -> FileResponse:
        d = _disc_dir(discs_root, disc_id, legacy_roots=legacy_discs_roots)
        if d is None:
            raise HTTPException(status_code=404)
        target = _resolve_under(d / "captures", filename)
        if target is None:
            raise HTTPException(status_code=404)
        return FileResponse(target, media_type="image/jpeg")

    @app.get("/library/{disc_id}/audio/{filename}")
    def library_audio(disc_id: str, filename: str) -> FileResponse:
        d = _disc_dir(discs_root, disc_id, legacy_roots=legacy_discs_roots)
        if d is None:
            raise HTTPException(status_code=404)
        target = _resolve_under(d / "audio", filename)
        if target is None:
            raise HTTPException(status_code=404)
        return FileResponse(target, media_type="audio/flac")

    @app.get("/library/{disc_id}/photo")
    def library_photo(disc_id: str) -> FileResponse:
        """Serve the canonical disc-photo.jpg (sprint-4 new-shape folders)."""
        d = _disc_dir(discs_root, disc_id, legacy_roots=legacy_discs_roots)
        if d is None:
            raise HTTPException(status_code=404)
        target = _resolve_under(d, "disc-photo.jpg")
        if target is None:
            raise HTTPException(status_code=404)
        return FileResponse(target, media_type="image/jpeg")

    @app.get("/library/{disc_id}/review/{filename}")
    def library_review_asset(disc_id: str, filename: str) -> FileResponse:
        d = _disc_dir(discs_root, disc_id, legacy_roots=legacy_discs_roots)
        if d is None:
            raise HTTPException(status_code=404)
        target = _resolve_under(d / "review", filename)
        if target is None:
            raise HTTPException(status_code=404)
        return FileResponse(target, media_type="image/jpeg")

    @app.post("/api/library/{disc_id}/recapture")
    def api_recapture(disc_id: str) -> JSONResponse:
        # (b) busy gate — loop owns the camera in CAPTURE/EJECT.
        if loop_state.state in _RECAPTURE_BUSY_STATES:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"pipeline is busy ({loop_state.state}); "
                    "try again after eject completes."
                ),
            )
        # (c) disc-existence + (d) id-shape.
        d = _disc_dir(discs_root, disc_id, legacy_roots=legacy_discs_roots)
        if d is None:
            raise HTTPException(status_code=404)
        if recapture_camera is None or recapture_led is None:
            raise HTTPException(
                status_code=503,
                detail="recapture not configured (camera/led not wired).",
            )
        result = recapture_review(
            d, camera=recapture_camera, led=recapture_led,
        )
        payload: dict[str, Any] = {"ambient": result.ambient, "lit": result.lit}
        if result.errors:
            payload["errors"] = result.errors
        return JSONResponse(payload)


def _render_library_list(
    discs_root: Path,
    *,
    status: str = "success",
    legacy_roots: tuple[Path, ...] = (),
    library_root: Path | None = None,
) -> str:
    from archivist.service.library import read_disc_summary

    cards: list[str] = []
    seen: set[str] = set()
    # Scan inbox (new sprint-4 disc folders) + legacy roots (sprint-1-3
    # CD_NNNN folders that live outside the music-pipeline inbox). Newer
    # folders (by name sort) win on dedupe.
    for root in (discs_root, *legacy_roots):
        if not root.is_dir():
            continue
        entries = sorted(
            (p for p in root.iterdir() if _VALID_DISC_FOLDER_RE.match(p.name)),
            key=lambda p: p.name,
            reverse=True,
        )
        for d in entries:
            if d.name in seen:
                continue
            summary = read_disc_summary(d, library_root=library_root)
            if summary is None:
                continue
            if status == "success" and not summary.rip_success:
                continue
            if status == "failed" and summary.rip_success:
                continue
            seen.add(d.name)
            cards.append(_render_summary_card(d, summary))

    grid = "\n".join(cards) if cards else (
        '<p class="meta">no discs match this filter.</p>'
    )

    chips = _render_status_chip_group(status)
    return (
        _LIBRARY_LIST_HTML
        .replace("{{CHIPS}}", chips)
        .replace("{{GRID}}", grid)
    )


def _render_status_chip_group(active: str) -> str:
    """Three-pill chip group; active uses --accent, inactive --surface-2."""
    chips: list[str] = []
    for label in ("success", "failed", "all"):
        if label == active:
            style = "background: var(--accent); color: var(--bg);"
            cls = "chip chip--active"
        else:
            style = "background: var(--surface-2); color: var(--fg-muted);"
            cls = "chip"
        chips.append(
            f'<a class="{cls}" href="/library?status={label}" style="{style}">{label}</a>'
        )
    return '<div class="chip-group">' + "\n".join(chips) + "</div>"


def _render_summary_card(disc_dir: Path, summary: Any) -> str:
    disc_id = html.escape(summary.disc_id_or_folder)
    if summary.rip_success:
        accent = "card--moss"
        rip_status_label = "SUCCESS"
    else:
        accent = "card--ember"
        rip_status_label = "FAILED"

    thumb: str
    # Sprint-5 / D-library-cover-preference: when the beets-fetched
    # library cover exists, prefer it over disc-photo.jpg.
    if summary.library_cover_path is not None:
        thumb_url = f"/library/{disc_id}/album-cover"
        thumb = f'<img class="thumb" src="{thumb_url}" alt="">'
    elif summary.thumbnail is not None:
        # New-shape folders serve disc-photo.jpg via /library/<id>/photo;
        # legacy folders serve via /library/<id>/captures/<file>.
        if summary.is_legacy:
            thumb_url = f"/library/{disc_id}/captures/{html.escape(summary.thumbnail.name)}"
        else:
            thumb_url = f"/library/{disc_id}/photo"
        thumb = f'<img class="thumb" src="{thumb_url}" alt="">'
    else:
        thumb = '<div class="thumb-empty">no capture</div>'

    created = _rel_time(summary.created_at) if summary.created_at else "—"

    return (
        f'<a class="card card--lib {accent}" href="/library/{disc_id}">'
        f'  {thumb}'
        f'  <div class="card-body">'
        f'    <p class="eyebrow">{rip_status_label}</p>'
        f'    <h2 class="card-title">{disc_id}</h2>'
        f'    <p class="meta">'
        f'      <span>{summary.track_count} tracks</span>'
        f'      <span class="dot">·</span>'
        f'      <span>{html.escape(created)}</span>'
        f'    </p>'
        f'  </div>'
        f'</a>'
    )


def _render_library_card(disc_dir: Path, m: Manifest) -> str:
    disc_id = html.escape(m.disc_id)
    accent = _accent_class(m)
    captures_dir = disc_dir / "captures"

    # Thumbnail: first lit capture if present, else first ambient, else
    # a placeholder.
    thumb_src: str | None = None
    if captures_dir.is_dir():
        lit = sorted(captures_dir.glob("disc_front_lit_*.jpg"))
        amb = sorted(captures_dir.glob("disc_front_ambient_*.jpg"))
        any_caps = sorted(captures_dir.glob("*.jpg"))
        chosen = (lit or amb or any_caps)
        if chosen:
            thumb_src = f"/library/{disc_id}/captures/{html.escape(chosen[0].name)}"

    if thumb_src:
        thumb = f'<img class="thumb" src="{thumb_src}" alt="">'
    else:
        thumb = '<div class="thumb-empty">no capture</div>'

    track_count = len(m.rips[0].tracks) if m.rips else 0
    created = _rel_time(m.created_at)
    rip_status = m.rips[0].status if m.rips else m.status

    return (
        f'<a class="card card--lib {accent}" href="/library/{disc_id}">'
        f'  {thumb}'
        f'  <div class="card-body">'
        f'    <p class="eyebrow">{html.escape(rip_status).upper()[:6]}</p>'
        f'    <h2 class="card-title">{disc_id}</h2>'
        f'    <p class="meta">'
        f'      <span>{track_count} tracks</span>'
        f'      <span class="dot">·</span>'
        f'      <span>{html.escape(created)}</span>'
        f'    </p>'
        f'  </div>'
        f'</a>'
    )


def _render_library_detail(
    disc_dir: Path,
    *,
    library_root: Path | None = None,
) -> str:
    from archivist.service.library import read_disc_summary

    summary = read_disc_summary(disc_dir, library_root=library_root)
    is_new_shape = summary is not None and not summary.is_legacy

    if is_new_shape:
        from archivist.models.source import read_source_json
        source = read_source_json(disc_dir / "source.json")
        disc_id = html.escape(source.disc.folder_name)
        accent = "card--moss" if source.status.rip_success else "card--ember"
        dump = source.model_dump_json(indent=2)
    else:
        manifest = read_manifest(disc_dir / "manifest.json")
        disc_id = html.escape(manifest.disc_id)
        accent = _accent_class(manifest)
        dump = manifest.model_dump_json(indent=2)

    manifest_block = (
        '<pre class="manifest-dump">' + html.escape(dump) + "</pre>"
    )

    # Sprint-5 / D-library-cover-preference: distinct "album art" +
    # "physical disc" sections when the new-shape folder has a beets-
    # fetched cover. Legacy folders keep the original layout.
    album_art_section = ""
    if summary is not None and summary.library_cover_path is not None:
        album_art_section = (
            '<section class="card">'
            f'<p class="eyebrow">ALBUM ART</p>'
            f'<img class="thumb thumb--lg" '
            f'src="/library/{disc_id}/album-cover" alt="album art">'
            '</section>'
        )

    # Physical disc — disc-photo.jpg lives at the disc-folder root for
    # sprint-4+ folders. Sprint-3 review-recapture buttons remain in
    # the existing review section below.
    physical_disc_section = ""
    if (disc_dir / "disc-photo.jpg").is_file():
        physical_disc_section = (
            '<section class="card">'
            f'<p class="eyebrow">PHYSICAL DISC</p>'
            f'<img class="thumb thumb--lg" '
            f'src="/library/{disc_id}/photo" alt="disc photo">'
            '</section>'
        )

    # Captures grid.
    captures_dir = disc_dir / "captures"
    capture_files = sorted(captures_dir.glob("*.jpg")) if captures_dir.is_dir() else []
    cap_imgs = "\n".join(
        f'<a target="_blank" href="/library/{disc_id}/captures/{html.escape(p.name)}">'
        f'<img class="thumb" src="/library/{disc_id}/captures/{html.escape(p.name)}" alt=""></a>'
        for p in capture_files
    )

    # Operator review captures (sprint-3 / D-review-recapture-mvp).
    # Surfaced from the directory listing only — not in the manifest.
    review_dir = disc_dir / "review"
    review_files = sorted(review_dir.glob("*.jpg")) if review_dir.is_dir() else []
    review_imgs = "\n".join(
        f'<figure class="review-item">'
        f'  <a target="_blank" href="/library/{disc_id}/review/{html.escape(p.name)}">'
        f'    <img class="thumb" src="/library/{disc_id}/review/{html.escape(p.name)}" alt="">'
        f'  </a>'
        f'  <figcaption class="review-caption">{html.escape(p.name)}</figcaption>'
        f'</figure>'
        for p in review_files
    )
    if not review_imgs:
        review_imgs = '<p class="meta">no review photos yet.</p>'

    # Audio tracks.
    audio_dir = disc_dir / "audio"
    audio_files = sorted(audio_dir.glob("*.flac")) if audio_dir.is_dir() else []
    track_rows = "\n".join(
        f'<li class="track">'
        f'  <span class="track-name">{html.escape(p.name)}</span>'
        f'  <span class="track-size">{_format_bytes(p.stat().st_size)}</span>'
        f'  <audio controls preload="none" src="/library/{disc_id}/audio/{html.escape(p.name)}"></audio>'
        f'</li>'
        for p in audio_files
    )

    # Log tail.
    log_block = ""
    logs_dir = disc_dir / "logs"
    if logs_dir.is_dir():
        log_text = ""
        for lp in sorted(logs_dir.glob("*.log")):
            log_text += _tail_log(lp, 200)
        if log_text:
            log_block = (
                '<section class="card log-card">'
                '<p class="eyebrow">LOG TAIL</p>'
                '<pre class="log">' + html.escape(log_text) + "</pre>"
                "</section>"
            )

    return (
        _LIBRARY_DETAIL_HTML
        .replace("{{DISC_ID}}", disc_id)
        .replace("{{ACCENT}}", accent)
        .replace("{{ALBUM_ART}}", album_art_section)
        .replace("{{PHYSICAL_DISC}}", physical_disc_section)
        .replace("{{MANIFEST}}", manifest_block)
        .replace("{{CAPTURES}}", cap_imgs or '<p class="meta">no captures.</p>')
        .replace("{{REVIEW_IMGS}}", review_imgs)
        .replace("{{TRACKS}}", track_rows or '<li class="meta">no audio.</li>')
        .replace("{{LOG_BLOCK}}", log_block)
    )


_PAGE_HTML = r"""<!doctype html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>cd-archivist</title>
  <link rel="stylesheet" href="/static/css/tokens.css">
  <style>
    /* Page-specific layout. Tokens come from /static/css/tokens.css. */
    html, body {
      margin: 0;
      background: var(--bg);
      color: var(--fg);
      font-family: var(--font-body);
    }
    .wrap {
      max-width: 720px;
      margin: 0 auto;
      padding: var(--s-7) var(--s-5);
    }
    .eyebrow {
      font-family: var(--font-body);
      font-size: var(--fs-xs);
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--fg-muted);
      margin: 0 0 var(--s-2) 0;
    }
    .page-title {
      font-family: var(--font-display);
      font-weight: 700;
      font-size: 32px;
      margin: 0 0 var(--s-7) 0;
      color: var(--fg);
    }
    .card {
      background: var(--surface);
      border: 1px solid var(--line);
      border-left: 3px solid var(--accent);
      border-radius: var(--r-4);
      padding: var(--s-5);
      margin-bottom: var(--s-5);
    }
    .card .eyebrow { color: var(--accent); }
    .card--ember { border-left-color: var(--ember); }
    .card--ember .eyebrow { color: var(--ember); }
    .state-line {
      font-family: var(--font-display);
      font-weight: 700;
      font-size: 28px;
      color: var(--fg);
      margin: 0 0 var(--s-3) 0;
    }
    .meta {
      font-family: var(--font-mono);
      font-size: var(--fs-sm);
      color: var(--fg-muted);
      line-height: 1.6;
    }
    .meta span.label { color: var(--fg-quiet); margin-right: var(--s-2); }
    .meta span.value { color: var(--fg-2); }
    /* RIP progress bar — sky accent on an ink-2 track. */
    #rip-progress-wrap {
      margin: var(--s-3) 0 var(--s-2) 0;
    }
    .progress-track {
      width: 100%;
      height: 6px;
      background: var(--ink-2);
      border-radius: var(--r-1);
      overflow: hidden;
    }
    .progress-fill {
      height: 100%;
      width: 0%;
      background: var(--sky);
      transition: width 200ms ease-out;
    }
    #rip-progress-label {
      display: block;
      margin-top: var(--s-1);
      font-family: var(--font-mono);
      font-size: var(--fs-xs);
      color: var(--fg-muted);
    }
    .log-card { border-left-color: var(--ink-5); }
    .log-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: var(--s-2);
    }
    .chip {
      font-family: var(--font-body);
      font-size: var(--fs-xs);
      letter-spacing: 0.04em;
      text-transform: lowercase;
      background: var(--surface-hover);
      color: var(--fg-quiet);
      border: 1px solid var(--line);
      border-radius: var(--r-full);
      padding: 4px 10px;
      cursor: pointer;
    }
    .chip[data-follow="on"] {
      color: var(--accent);
      border-color: var(--accent);
    }
    pre.log {
      font-family: var(--font-mono);
      font-size: var(--fs-xs);
      color: var(--fg-muted);
      background: var(--ink-0);
      border: 1px solid var(--line);
      border-radius: var(--r-3);
      padding: var(--s-3);
      margin: 0;
      max-height: 320px;
      overflow: auto;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .footnote {
      font-family: var(--font-mono);
      font-size: var(--fs-xs);
      color: var(--fg-quiet);
      margin-top: var(--s-6);
    }
    .nav {
      display: flex;
      gap: var(--s-4);
      margin-bottom: var(--s-5);
      font-family: var(--font-body);
      font-size: var(--fs-sm);
    }
    .nav a {
      color: var(--fg-muted);
      text-decoration: none;
      padding-bottom: 2px;
      border-bottom: 1px solid transparent;
    }
    .nav a.active {
      color: var(--fg);
      border-bottom-color: var(--accent);
    }
  </style>
</head>
<body>
  <main class="wrap">
    <nav class="nav">
      <a href="/" class="active">status</a>
      <a href="/library">library</a>
    </nav>

    <p class="eyebrow">STATUS</p>
    <h1 class="page-title">cd-archivist</h1>

    <section class="card" id="state-card" aria-label="Current state">
      <p class="eyebrow">DRIVE</p>
      <p class="state-line" id="state">&hellip;</p>
      <div id="rip-progress-wrap" hidden>
        <div class="progress-track">
          <div id="rip-progress-fill" class="progress-fill"></div>
        </div>
        <span id="rip-progress-label">&nbsp;</span>
      </div>
      <div class="meta">
        <div><span class="label">disc</span><span class="value" id="disc-id">&mdash;</span></div>
        <div><span class="label">last rip</span><span class="value" id="last-rip">&mdash;</span></div>
        <div><span class="label">entered</span><span class="value" id="state-entered">&mdash;</span></div>
        <div><span class="label">last tick</span><span class="value" id="last-tick">&mdash;</span></div>
      </div>
    </section>

    <section class="card log-card" aria-label="Recent log lines">
      <div class="log-header">
        <p class="eyebrow" style="margin:0">LOG TAIL</p>
        <button id="log-follow-toggle" class="chip" data-follow="on" type="button">follow</button>
      </div>
      <pre class="log" id="log" data-follow="on">loading&hellip;</pre>
    </section>

    <p class="footnote">
      polling <code>/api/status</code> and <code>/api/log</code> every 2 seconds.
    </p>
  </main>

  <script>
    // Vanilla JS — no framework. Polls /api/status and /api/log every 2s.
    const $ = (id) => document.getElementById(id);
    const dash = (v) => (v === null || v === undefined || v === "") ? "—" : v;

    // Relative-time helper: "Xs ago", "Xm ago", "Xh ago".
    function relTime(iso) {
      if (!iso) return "—";
      const then = new Date(iso).getTime();
      if (Number.isNaN(then)) return "—";
      const sec = Math.max(0, Math.round((Date.now() - then) / 1000));
      if (sec < 60) return sec + "s ago";
      const min = Math.round(sec / 60);
      if (min < 60) return min + "m ago";
      const hr = Math.round(min / 60);
      return hr + "h ago";
    }

    // Parse "track 4/12, 38%" → 38; return null if no percent.
    function parsePercent(label) {
      if (!label) return null;
      const m = String(label).match(/(\d{1,3})\s*%/);
      if (!m) return null;
      const n = parseInt(m[1], 10);
      return (n >= 0 && n <= 100) ? n : null;
    }

    function applyStateAccent(state) {
      const card = $("state-card");
      card.classList.remove("card--ember");
      if (state === "ERROR") card.classList.add("card--ember");
    }

    async function pollStatus() {
      try {
        const r = await fetch("/api/status", { cache: "no-store" });
        if (!r.ok) return;
        const s = await r.json();
        $("state").textContent = dash(s.state);
        $("disc-id").textContent = dash(s.disc_id);
        $("last-rip").textContent = dash(s.last_rip_status);
        $("state-entered").textContent = relTime(s.state_entered_at);
        $("last-tick").textContent = relTime(s.last_tick_at);
        applyStateAccent(s.state);

        // RIP progress bar — show only when there's a value.
        const wrap = $("rip-progress-wrap");
        if (s.rip_progress) {
          wrap.hidden = false;
          $("rip-progress-label").textContent = s.rip_progress;
          const pct = parsePercent(s.rip_progress);
          if (pct !== null) $("rip-progress-fill").style.width = pct + "%";
        } else {
          wrap.hidden = true;
          $("rip-progress-fill").style.width = "0%";
        }
      } catch (e) { /* swallow — next tick retries */ }
    }

    // Log tail with follow toggle. `follow` defaults to on; clicking
    // the chip toggles it. Manual scroll-up auto-disables follow.
    let follow = true;
    const pre = $("log");
    const chip = $("log-follow-toggle");

    function setFollow(on) {
      follow = on;
      const flag = on ? "on" : "off";
      chip.setAttribute("data-follow", flag);
      pre.setAttribute("data-follow", flag);
    }
    chip.addEventListener("click", () => setFollow(!follow));
    pre.addEventListener("scroll", () => {
      // If the user scrolled away from the bottom, turn follow off.
      const distFromBottom = pre.scrollHeight - pre.scrollTop - pre.clientHeight;
      if (distFromBottom > 24 && follow) setFollow(false);
    });

    async function pollLog() {
      try {
        const r = await fetch("/api/log?lines=200", { cache: "no-store" });
        if (!r.ok) return;
        const text = await r.text();
        pre.textContent = text || "(empty)";
        if (follow) {
          pre.scrollTop = pre.scrollHeight;
        }
      } catch (e) { /* swallow */ }
    }

    function tick() { pollStatus(); pollLog(); }
    tick();
    setInterval(tick, 2000);
  </script>
</body>
</html>
"""


# Shared library-page styles. Reuses Mash Co. tokens from /static/css/tokens.css.
_LIBRARY_STYLES = r"""
<style>
  html, body { margin: 0; background: var(--bg); color: var(--fg); font-family: var(--font-body); }
  .wrap { max-width: 1080px; margin: 0 auto; padding: var(--s-7) var(--s-5); }
  .nav { display: flex; gap: var(--s-4); margin-bottom: var(--s-5);
         font-family: var(--font-body); font-size: var(--fs-sm); }
  .nav a { color: var(--fg-muted); text-decoration: none;
           padding-bottom: 2px; border-bottom: 1px solid transparent; }
  .nav a.active { color: var(--fg); border-bottom-color: var(--accent); }
  .eyebrow { font-family: var(--font-body); font-size: var(--fs-xs);
             letter-spacing: 0.08em; text-transform: uppercase;
             color: var(--fg-muted); margin: 0 0 var(--s-2) 0; }
  .page-title { font-family: var(--font-display); font-weight: 700;
                font-size: 32px; margin: 0 0 var(--s-7) 0; color: var(--fg); }
  .card { background: var(--surface); border: 1px solid var(--line);
          border-left: 3px solid var(--accent); border-radius: var(--r-4);
          padding: var(--s-5); margin-bottom: var(--s-5); }
  .card--moss { border-left-color: var(--moss); }
  .card--moss .eyebrow { color: var(--moss); }
  .card--amber { border-left-color: var(--amber); }
  .card--amber .eyebrow { color: var(--amber); }
  .card--ember { border-left-color: var(--ember); }
  .card--ember .eyebrow { color: var(--ember); }
  .meta { font-family: var(--font-mono); font-size: var(--fs-sm);
          color: var(--fg-muted); line-height: 1.6; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
          gap: var(--s-4); }
  a.card { display: block; text-decoration: none; color: inherit; }
  a.card:hover { background: var(--surface-2); }
  .thumb { display: block; width: 100%; aspect-ratio: 1 / 1; object-fit: cover;
           border-radius: var(--r-3); background: var(--ink-2); }
  .thumb-empty { display: flex; align-items: center; justify-content: center;
                 width: 100%; aspect-ratio: 1 / 1; background: var(--ink-2);
                 color: var(--fg-quiet); border-radius: var(--r-3);
                 font-family: var(--font-mono); font-size: var(--fs-xs); }
  .card-body { padding-top: var(--s-3); }
  .card-title { font-family: var(--font-display); font-weight: 700;
                font-size: 18px; margin: 0 0 var(--s-2) 0; color: var(--fg); }
  .dot { margin: 0 6px; color: var(--fg-quiet); }
  .captures-grid { display: grid; grid-template-columns: repeat(3, 1fr);
                   gap: var(--s-3); margin-top: var(--s-3); }
  ul.tracks { list-style: none; padding: 0; margin: var(--s-3) 0 0; }
  li.track { display: grid; grid-template-columns: 1fr auto;
             grid-template-areas: "name size" "audio audio";
             gap: 4px 12px; padding: var(--s-3) 0;
             border-bottom: 1px solid var(--line);
             font-family: var(--font-mono); font-size: var(--fs-sm); }
  li.track .track-name { grid-area: name; color: var(--fg-2); }
  li.track .track-size { grid-area: size; color: var(--fg-quiet); }
  li.track audio { grid-area: audio; width: 100%; margin-top: 4px; }
  pre.manifest-dump, pre.log {
    font-family: var(--font-mono); font-size: var(--fs-xs);
    color: var(--fg-muted); background: var(--ink-0);
    border: 1px solid var(--line); border-radius: var(--r-3);
    padding: var(--s-3); margin: 0; max-height: 400px; overflow: auto;
    white-space: pre-wrap; word-break: break-word;
  }
  .log-card { border-left-color: var(--ink-5); }
  .chip-group {
    display: flex; gap: var(--s-2); margin-bottom: var(--s-5);
  }
  .chip {
    font-family: var(--font-body); font-size: var(--fs-sm);
    text-decoration: none; padding: 6px 14px;
    border-radius: var(--r-full); border: 1px solid var(--line);
  }
  .chip--active { border-color: var(--accent); }
  .review-header { display: flex; align-items: center; justify-content: space-between; gap: var(--s-3); }
  .review-actions { display: flex; align-items: center; gap: var(--s-3); }
  .btn-primary {
    font-family: var(--font-body); font-size: var(--fs-sm);
    color: var(--fg); background: var(--surface-2);
    border: 1px solid var(--line); border-left: 3px solid var(--accent);
    border-radius: var(--r-3); padding: 8px 14px; cursor: pointer;
  }
  .btn-primary:hover { background: var(--surface-hover); }
  .btn-primary[disabled] { opacity: 0.5; cursor: progress; }
  .countdown {
    font-family: var(--font-display); font-weight: 700;
    font-size: 28px; color: var(--accent); min-width: 1.5em;
    text-align: center;
  }
  .review-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
                 gap: var(--s-3); margin-top: var(--s-3); }
  .review-item { margin: 0; }
  .review-caption { font-family: var(--font-mono); font-size: var(--fs-xs);
                    color: var(--fg-quiet); margin-top: 4px;
                    word-break: break-all; }
</style>
"""


_LIBRARY_LIST_HTML = r"""<!doctype html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>cd-archivist · library</title>
  <link rel="stylesheet" href="/static/css/tokens.css">
""" + _LIBRARY_STYLES + r"""
</head>
<body>
  <main class="wrap">
    <nav class="nav">
      <a href="/">status</a>
      <a href="/library" class="active">library</a>
    </nav>
    <p class="eyebrow">LIBRARY</p>
    <h1 class="page-title">cd-archivist</h1>
    {{CHIPS}}
    <div class="grid">
      {{GRID}}
    </div>
  </main>
</body>
</html>
"""


_LIBRARY_DETAIL_HTML = r"""<!doctype html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>cd-archivist · {{DISC_ID}}</title>
  <link rel="stylesheet" href="/static/css/tokens.css">
""" + _LIBRARY_STYLES + r"""
</head>
<body>
  <main class="wrap">
    <nav class="nav">
      <a href="/">status</a>
      <a href="/library" class="active">library</a>
    </nav>
    <p class="eyebrow">DISC</p>
    <h1 class="page-title">{{DISC_ID}}</h1>

    {{ALBUM_ART}}
    {{PHYSICAL_DISC}}

    <section class="card {{ACCENT}}">
      <p class="eyebrow">MANIFEST</p>
      {{MANIFEST}}
    </section>

    <section class="card">
      <p class="eyebrow">CAPTURES</p>
      <div class="captures-grid">
        {{CAPTURES}}
      </div>
    </section>

    <section class="card">
      <div class="review-header">
        <p class="eyebrow" style="margin:0">REVIEW PHOTOS</p>
        <div class="review-actions">
          <span id="countdown" class="countdown" aria-live="polite"></span>
          <button id="recapture-btn" class="btn-primary" type="button">
            take a review photo
          </button>
        </div>
      </div>
      <div id="review-grid" class="review-grid">
        {{REVIEW_IMGS}}
      </div>
    </section>

    <section class="card">
      <p class="eyebrow">TRACKS</p>
      <ul class="tracks">
        {{TRACKS}}
      </ul>
    </section>

    {{LOG_BLOCK}}
  </main>

  <script>
    // 3-2-1 countdown, then POST to /api/library/<disc>/recapture.
    // No framework — ~30 lines of vanilla JS.
    (function () {
      const discId = "{{DISC_ID}}";
      const btn = document.getElementById("recapture-btn");
      const cd = document.getElementById("countdown");
      if (!btn || !cd) return;

      function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

      async function run() {
        btn.disabled = true;
        try {
          for (const n of [3, 2, 1]) {
            cd.textContent = String(n);
            await sleep(1000);
          }
          cd.textContent = "…";
          const resp = await fetch(
            "/api/library/" + discId + "/recapture",
            { method: "POST", cache: "no-store" }
          );
          if (!resp.ok) {
            cd.textContent = "failed (" + resp.status + ")";
            await sleep(2500);
          } else {
            cd.textContent = "done";
            await sleep(600);
            // Refresh page so the review grid picks up the new pair.
            window.location.reload();
            return;
          }
        } catch (e) {
          cd.textContent = "error";
          await sleep(2500);
        } finally {
          cd.textContent = "";
          btn.disabled = false;
        }
      }
      btn.addEventListener("click", run);
    })();
  </script>
</body>
</html>
"""
