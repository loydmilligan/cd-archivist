"""FastAPI status surface.

Three routes:
  GET /            — single-file HTML status page, dressed in Mash Co.
  GET /api/status  — JSON snapshot of LoopState
  GET /api/log     — text/plain tail of the pipeline log (deque, cap 1000)

The HTML lives inline (`_PAGE_HTML`). Styling comes from the vendored
`archivist/service/static/tokens.css` (Mash Co. v0.1.0) mounted at
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
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from archivist.models.manifest import Manifest, read_manifest
from archivist.pipeline.review_capture import recapture_review

_RECAPTURE_BUSY_STATES = {"CAPTURE", "EJECT"}

logger = logging.getLogger(__name__)

_LOG_LINES_CAP = 1000
_LOG_LINES_DEFAULT = 200
_STATIC_DIR = Path(__file__).parent / "static"
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
    See Contract Changes in docs/coordination/sprint-3.md.
    """

    state: str = "IDLE"
    disc_id: str | None = None
    last_rip_status: str | None = None
    state_entered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_tick_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    # Sprint-3 / test-rip-progress: live cdparanoia progress label.
    rip_progress: str | None = None


def _tail_log(path: Path, lines: int) -> str:
    if not path.exists():
        return ""
    n = max(0, min(lines, _LOG_LINES_CAP))
    if n == 0:
        return ""
    with path.open("r", encoding="utf-8", errors="replace") as f:
        return "".join(deque(f, maxlen=n))


def create_app(
    loop_state: LoopState,
    log_path: Path,
    *,
    discs_root: Path | None = None,
    recapture_camera: Callable[..., Any] | None = None,
    recapture_led: Any | None = None,
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
            }
        )

    @app.get("/api/log")
    def api_log(lines: int = Query(_LOG_LINES_DEFAULT, ge=0)) -> PlainTextResponse:
        return PlainTextResponse(_tail_log(log_path, lines))

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        return HTMLResponse(_PAGE_HTML)

    # ---------------- library browser (sprint-3 / impl-library) ----------

    if discs_root is not None:
        _mount_library_routes(
            app, discs_root,
            loop_state=loop_state,
            recapture_camera=recapture_camera,
            recapture_led=recapture_led,
        )

    return app


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


def _disc_dir(discs_root: Path, disc_id: str) -> Path | None:
    if not _VALID_DISC_FOLDER_RE.match(disc_id):
        return None
    d = discs_root / disc_id
    if not d.is_dir():
        return None
    return d


def _mount_library_routes(
    app: FastAPI,
    discs_root: Path,
    *,
    loop_state: "LoopState",
    recapture_camera: Callable[..., Any] | None = None,
    recapture_led: Any | None = None,
) -> None:
    @app.get("/library", response_class=HTMLResponse)
    def library_list(status: str = "success") -> HTMLResponse:
        if status not in ("success", "failed", "all"):
            status = "success"
        return HTMLResponse(_render_library_list(discs_root, status=status))

    @app.get("/library/{disc_id}", response_class=HTMLResponse)
    def library_detail(disc_id: str) -> HTMLResponse:
        if not _VALID_DISC_FOLDER_RE.match(disc_id):
            raise HTTPException(status_code=404)
        d = _disc_dir(discs_root, disc_id)
        if d is None:
            raise HTTPException(status_code=404)
        if not (d / "manifest.json").is_file() and not (d / "source.json").is_file():
            raise HTTPException(status_code=404)
        return HTMLResponse(_render_library_detail(d))

    @app.get("/library/{disc_id}/captures/{filename}")
    def library_capture(disc_id: str, filename: str) -> FileResponse:
        d = _disc_dir(discs_root, disc_id)
        if d is None:
            raise HTTPException(status_code=404)
        target = _resolve_under(d / "captures", filename)
        if target is None:
            raise HTTPException(status_code=404)
        return FileResponse(target, media_type="image/jpeg")

    @app.get("/library/{disc_id}/audio/{filename}")
    def library_audio(disc_id: str, filename: str) -> FileResponse:
        d = _disc_dir(discs_root, disc_id)
        if d is None:
            raise HTTPException(status_code=404)
        target = _resolve_under(d / "audio", filename)
        if target is None:
            raise HTTPException(status_code=404)
        return FileResponse(target, media_type="audio/flac")

    @app.get("/library/{disc_id}/photo")
    def library_photo(disc_id: str) -> FileResponse:
        """Serve the canonical disc-photo.jpg (sprint-4 new-shape folders)."""
        d = _disc_dir(discs_root, disc_id)
        if d is None:
            raise HTTPException(status_code=404)
        target = _resolve_under(d, "disc-photo.jpg")
        if target is None:
            raise HTTPException(status_code=404)
        return FileResponse(target, media_type="image/jpeg")

    @app.get("/library/{disc_id}/review/{filename}")
    def library_review_asset(disc_id: str, filename: str) -> FileResponse:
        d = _disc_dir(discs_root, disc_id)
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
        d = _disc_dir(discs_root, disc_id)
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


def _render_library_list(discs_root: Path, *, status: str = "success") -> str:
    from archivist.service.library import read_disc_summary

    cards: list[str] = []
    if discs_root.is_dir():
        entries = sorted(
            (p for p in discs_root.iterdir() if _VALID_DISC_FOLDER_RE.match(p.name)),
            key=lambda p: p.name,
            reverse=True,
        )
        for d in entries:
            summary = read_disc_summary(d)
            if summary is None:
                continue
            if status == "success" and not summary.rip_success:
                continue
            if status == "failed" and summary.rip_success:
                continue
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
    if summary.thumbnail is not None:
        # Route the thumbnail through whichever asset-serving endpoint
        # applies. New-shape folders serve disc-photo.jpg via /library/.../
        # but legacy folders serve via /library/.../captures/.
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


def _render_library_detail(disc_dir: Path) -> str:
    manifest = read_manifest(disc_dir / "manifest.json")
    disc_id = html.escape(manifest.disc_id)
    accent = _accent_class(manifest)

    # Manifest dump.
    manifest_json = manifest.model_dump_json(indent=2)
    manifest_block = (
        '<pre class="manifest-dump">' + html.escape(manifest_json) + "</pre>"
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
  <link rel="stylesheet" href="/static/tokens.css">
  <style>
    /* Page-specific layout. Tokens come from /static/tokens.css. */
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


# Shared library-page styles. Reuses Mash Co. tokens from /static/tokens.css.
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
  <link rel="stylesheet" href="/static/tokens.css">
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
  <link rel="stylesheet" href="/static/tokens.css">
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
