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

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

_LOG_LINES_CAP = 1000
_LOG_LINES_DEFAULT = 200
_STATIC_DIR = Path(__file__).parent / "static"


@dataclass
class LoopState:
    """Mutable snapshot the state-machine writes; the service reads."""

    state: str = "IDLE"
    disc_id: str | None = None
    last_rip_status: str | None = None
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))


def _tail_log(path: Path, lines: int) -> str:
    if not path.exists():
        return ""
    n = max(0, min(lines, _LOG_LINES_CAP))
    if n == 0:
        return ""
    with path.open("r", encoding="utf-8", errors="replace") as f:
        return "".join(deque(f, maxlen=n))


def create_app(loop_state: LoopState, log_path: Path) -> FastAPI:
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
                "last_updated": loop_state.last_updated.isoformat(),
            }
        )

    @app.get("/api/log")
    def api_log(lines: int = Query(_LOG_LINES_DEFAULT, ge=0)) -> PlainTextResponse:
        return PlainTextResponse(_tail_log(log_path, lines))

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        return HTMLResponse(_PAGE_HTML)

    return app


_PAGE_HTML = """<!doctype html>
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
    .log-card { border-left-color: var(--ink-5); }
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
  </style>
</head>
<body>
  <main class="wrap">
    <p class="eyebrow">STATUS</p>
    <h1 class="page-title">cd-archivist</h1>

    <section class="card" aria-label="Current state">
      <p class="eyebrow">DRIVE</p>
      <p class="state-line" id="state">&hellip;</p>
      <div class="meta">
        <div><span class="label">disc</span><span class="value" id="disc-id">&mdash;</span></div>
        <div><span class="label">last rip</span><span class="value" id="last-rip">&mdash;</span></div>
        <div><span class="label">updated</span><span class="value" id="last-updated">&mdash;</span></div>
      </div>
    </section>

    <section class="card log-card" aria-label="Recent log lines">
      <p class="eyebrow">LOG TAIL</p>
      <pre class="log" id="log">loading&hellip;</pre>
    </section>

    <p class="footnote">
      polling <code>/api/status</code> and <code>/api/log</code> every 2 seconds.
    </p>
  </main>

  <script>
    // Vanilla JS — no framework. Polls /api/status and /api/log every 2s.
    const $ = (id) => document.getElementById(id);
    const dash = (v) => (v === null || v === undefined || v === "") ? "—" : v;

    async function pollStatus() {
      try {
        const r = await fetch("/api/status", { cache: "no-store" });
        if (!r.ok) return;
        const s = await r.json();
        $("state").textContent = dash(s.state);
        $("disc-id").textContent = dash(s.disc_id);
        $("last-rip").textContent = dash(s.last_rip_status);
        $("last-updated").textContent = dash(s.last_updated);
      } catch (e) { /* swallow — next tick retries */ }
    }

    async function pollLog() {
      try {
        const r = await fetch("/api/log?lines=200", { cache: "no-store" });
        if (!r.ok) return;
        const text = await r.text();
        $("log").textContent = text || "(empty)";
      } catch (e) { /* swallow */ }
    }

    function tick() { pollStatus(); pollLog(); }
    tick();
    setInterval(tick, 2000);
  </script>
</body>
</html>
"""
