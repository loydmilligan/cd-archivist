"""Shared chassis JS — drawer toggles + log refresh + per-panel poll dispatch.

These behaviors are needed on every surface that renders the
header drawer buttons + the right-drawer + the bottom-drawer:
- `/rip` (kanban): wired via the full _INLINE_JS in kanban_page.py
- `/library` and `/library/{panelId}`: wired via this module

The kanban's _INLINE_JS still owns its kanban-specific bits (card
click handlers, polling, transitions). This module is the minimum
viable wire-up for the drawer buttons in the page-header so the
chassis works on surfaces that aren't the kanban.

Per-panel polling contract (sprint-10 / chassis-poll-dispatcher)
----------------------------------------------------------------
Library panel render modules (library_disk_panel.py,
library_inbox_panel.py, library_downloads_panel.py,
library_browse_panel.py) declare their desired refresh cadence by
emitting two meta tags into the rendered HTML — either inside the
page <head> or inside the panel's viewport HTML (the dispatcher
queries the whole document):

    <meta name="library-poll-ms" content="5000">
    <meta name="library-poll-endpoint" content="/api/library/inbox">

Contract:

- Both tags must be present for polling to engage. If either is
  absent (e.g., the Library/browse panel, the landing grid, or
  the `/rip` kanban surface), the dispatcher is a no-op.
- `library-poll-ms` is parsed as an integer; values <= 0 disable
  polling.
- `library-poll-endpoint` is fetched verbatim. The response is
  not consumed by the dispatcher itself — the dispatcher just
  fires the request. Per-panel modules that need to react to
  the response should listen for the `library:poll-tick` custom
  event dispatched on `document` after each fetch resolves
  (detail: `{ endpoint, response }` on success, `{ endpoint, error }`
  on failure).
- Polling pauses when the page is hidden (visibilitychange ->
  hidden) and resumes when it becomes visible again, so background
  tabs do not hammer the endpoints.
- The dispatcher does not throttle or coalesce — per-panel
  cadences (Disk 30000, Inbox 5000, Downloads 1000/5000 active/idle,
  Library none) are the responsibility of the emitting render
  module. A panel that needs active/idle cadence-switching emits
  the active value initially and updates the meta tag's `content`
  attribute at runtime; the dispatcher re-reads on each tick.

This dispatcher is independent of the existing chassis-level
drive-status polling (every 5s against `/api/drive/status`),
which remains hard-coded above.
"""

from __future__ import annotations


CHASSIS_JS = """
(function(){
  // --- Right drawer toggle ----------------------------------------------
  function setDrawerHidden(id, hidden) {
    const el = document.getElementById(id);
    if (el) el.setAttribute('aria-hidden', hidden ? 'true' : 'false');
    if (id === 'right-drawer') {
      document.body.dataset.rightDrawerOpen = hidden ? 'false' : 'true';
    }
  }
  function isRightDrawerOpen() {
    const el = document.getElementById('right-drawer');
    return el && el.getAttribute('aria-hidden') === 'false';
  }
  function closeRightDrawer() {
    setDrawerHidden('right-drawer', true);
    const driveBtn = document.querySelector('.drawer-toggle--drive');
    if (driveBtn) driveBtn.setAttribute('aria-pressed', 'false');
  }
  document.querySelectorAll('.drawer-toggle--drive').forEach(function(btn){
    btn.addEventListener('click', function(e){
      e.stopPropagation();
      if (isRightDrawerOpen()) {
        closeRightDrawer();
      } else {
        setDrawerHidden('right-drawer', false);
        btn.setAttribute('aria-pressed', 'true');
      }
    });
  });
  document.querySelectorAll('.drawer-close').forEach(function(btn){
    btn.addEventListener('click', function(e){
      e.stopPropagation();
      closeRightDrawer();
    });
  });
  document.addEventListener('click', function(e){
    if (!isRightDrawerOpen()) return;
    const inDrawer = e.target.closest && e.target.closest('#right-drawer');
    const onToggle = e.target.closest && e.target.closest('.drawer-toggle--drive');
    if (!inDrawer && !onToggle) closeRightDrawer();
  });

  // --- Bottom drawer toggle + log refresh ------------------------------
  const BOTTOM_KEY = 'cd-archivist:bottom-drawer:open';
  function applyBottomState() {
    const open = localStorage.getItem(BOTTOM_KEY) === 'true';
    setDrawerHidden('bottom-drawer', !open);
  }
  function refreshBottomDrawer() {
    const pre = document.getElementById('bottom-drawer-log');
    if (!pre) return;
    fetch(pre.getAttribute('data-endpoint'))
      .then(function(r){ return r.ok ? r.json() : { lines: [] }; })
      .then(function(j){ pre.textContent = (j.lines || []).join('\\n'); });
  }
  applyBottomState();
  document.querySelectorAll('[data-drawer-toggle="bottom"]').forEach(function(btn){
    btn.addEventListener('click', function(){
      const open = localStorage.getItem(BOTTOM_KEY) !== 'true';
      localStorage.setItem(BOTTOM_KEY, String(open));
      applyBottomState();
      if (open) refreshBottomDrawer();
    });
  });

  // --- Drive-status polling (chassis-level, every 5s) ------------------
  // Sprint-9 / library-drive-status: drive status is chassis-level
  // info (same justification as rig-stats per build-prompt §2). The
  // kanban's full _INLINE_JS already polls this via /api/kanban; on
  // library we poll independently at a slower cadence (5s) since
  // library isn't tracking per-card state.
  function refreshDriveStatus() {
    const body = document.querySelector('[data-target="drive-status-body"]');
    if (!body) return;
    fetch('/api/drive/status')
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(function(s){
        if (!s) return;
        body.textContent = JSON.stringify(s, null, 2);
      })
      .catch(function(){});
  }
  refreshDriveStatus();
  setInterval(refreshDriveStatus, 5000);

  // --- Per-panel poll dispatcher (sprint-10 / chassis-poll-dispatcher) -
  // Reads <meta name="library-poll-ms"> + <meta name="library-poll-endpoint">
  // at page load. No-op when either tag is missing. Pauses on
  // visibilitychange -> hidden, resumes on visible. Dispatches a
  // `library:poll-tick` custom event after each fetch so per-panel
  // modules can wire response handlers. See chassis_js.py docstring
  // for the full contract.
  function readPollMeta() {
    const msEl = document.querySelector('meta[name="library-poll-ms"]');
    const epEl = document.querySelector('meta[name="library-poll-endpoint"]');
    if (!msEl || !epEl) return null;
    const ms = parseInt(msEl.getAttribute('content') || '0', 10);
    const endpoint = epEl.getAttribute('content') || '';
    if (!ms || ms <= 0 || !endpoint) return null;
    return { ms: ms, endpoint: endpoint };
  }
  let pollTimer = null;
  function pollTick() {
    const meta = readPollMeta();
    if (!meta) return;
    fetch(meta.endpoint)
      .then(function(r){
        document.dispatchEvent(new CustomEvent('library:poll-tick', {
          detail: { endpoint: meta.endpoint, response: r }
        }));
      })
      .catch(function(err){
        document.dispatchEvent(new CustomEvent('library:poll-tick', {
          detail: { endpoint: meta.endpoint, error: err }
        }));
      });
  }
  function startPolling() {
    const meta = readPollMeta();
    if (!meta) return;
    if (pollTimer !== null) return;
    pollTimer = setInterval(pollTick, meta.ms);
  }
  function stopPolling() {
    if (pollTimer === null) return;
    clearInterval(pollTimer);
    pollTimer = null;
  }
  document.addEventListener('visibilitychange', function(){
    if (document.hidden) {
      stopPolling();
    } else {
      startPolling();
    }
  });
  if (readPollMeta()) {
    startPolling();
  }
})();
""".strip()
