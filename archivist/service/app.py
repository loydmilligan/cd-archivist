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

    return app


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
