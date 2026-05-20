"""Shared chassis JS — drawer toggles + log refresh.

These behaviors are needed on every surface that renders the
header drawer buttons + the right-drawer + the bottom-drawer:
- `/rip` (kanban): wired via the full _INLINE_JS in kanban_page.py
- `/library` and `/library/{panelId}`: wired via this module

The kanban's _INLINE_JS still owns its kanban-specific bits (card
click handlers, polling, transitions). This module is the minimum
viable wire-up for the drawer buttons in the page-header so the
chassis works on surfaces that aren't the kanban.
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
})();
""".strip()
