---
project: cd-archivist
sprint: sprint-9
created: 2026-05-19T00:00:00.000Z
updated: 2026-05-19T00:00:00.000Z
status: active
---

# cd-archivist — coordination doc (sprint-9)

> Strict template per Session O2=B / seed §12 Phase 8. The dashboard
> reads this as the canonical substrate (seed §3.7); orc emits
> `coord-doc-stale` cards when drift is detected (§3.8 / O7=A).
>
> Section headings are load-bearing — keep them as-is so the parser can
> find them. Section bodies are markdown-flexible.

## Plan Source

- Type: inline
- Path: this document (`## Active Sprint Plan` section)
- Active unit: sprint-9
- Upstream design handoff:
  `docs/reference/mascho-design-handoff-cda-library/library-manager-handoff/handoff/build-prompt.md`
- Upstream proposal: `docs/LIBRARY-MANAGER-PROPOSAL.md`
- Upstream design brief: `docs/design/2026-05-18-library-manager-design-brief.md`

## Sprint Goals

Add the Library Manager shell alongside the rip kanban

Shell, sidebar, landing grid, panel placeholders — per-panel UX deferred to follow-up briefs.

## Active Initiatives

- _None — sprint-9 plan below is the substrate._

## Active Sprint Plan

<!-- Inline plan parsed by orc-tower's InlineArtifactSource. Task syntax
     per the strict template comment. Replace the body, not accumulate. -->

- [x] {agent: lane-1, id: vendor-assets} Move the handoff into its canonical locations and track the untracked design briefs. Copy `docs/reference/mascho-design-handoff-cda-library/library-manager-handoff/handoff/reference/cda-library-styles.css` to `archivist/service/static/css/library.css` (the file must load AFTER `cda.css` once wired). Relocate the rest of the handoff tree to `docs/reference/mashco-design-system/cd-archivist-library/` (build-prompt §1; note the path correction from `mascho` → `mashco`). Add the untracked `docs/LIBRARY-MANAGER-PROPOSAL.md` and `docs/design/2026-05-18-library-manager-design-brief.md` to git. No template or route edits in this task.
  - **Acceptance:** `archivist/service/static/css/library.css` exists and is byte-identical to the handoff's `cda-library-styles.css`. The handoff lives at `docs/reference/mashco-design-system/cd-archivist-library/` (the old `mascho-design-handoff-cda-library/` path is gone). `git ls-files docs/LIBRARY-MANAGER-PROPOSAL.md docs/design/2026-05-18-library-manager-design-brief.md` returns both paths.

- [x] {agent: lane-1, id: shell-route} Add the `/library` FastAPI route and a new `archivist/service/library_page.py` renderer that emits the shell — the existing chassis-level header (breadcrumb switcher slot, rig stats group, nav buttons; rig-stats stay byte-identical to `/rip` per build-prompt §2), a `<aside>` sidebar placeholder (220px), a viewport region, a right-drawer slot (340px sticky) rendering the idle state ("Select an item to see details."), and a bottom-log mount-point that reuses the same DOM id `/rip` uses. Also: `/` redirects to `/rip` (existing behavior preserved); `/library` returns 200; `/library/{panelId}` routing is wired but the panel body is owned by `panel-placeholder`.
  - **Acceptance:** `curl -s http://localhost:8228/library | grep -c 'cda-rig-stat'` returns the same count as `curl -s http://localhost:8228/rip | grep -c 'cda-rig-stat'` (rig stats identical). HTML contains `<aside class="cda-lib-sidebar">`, the right-drawer idle copy verbatim, and the existing bottom-log element id. `/rip` still renders unchanged. `tests/service/test_library_shell.py` covers route registration + the shared rig-stats group + drawer idle copy. Run the pipeline test suite green before close.

- [x] {agent: lane-1, depends: vendor-assets,shell-route, id: load-library-css} Wire `library.css` into the shell template. Inside `library_page.py`'s `<head>`, add `<link rel="stylesheet" href="/static/css/library.css">` immediately after the existing `cda.css` link. Verify load order in DevTools (cda.css → library.css; library tokens never override mash co. tokens because they don't redefine any).
  - **Acceptance:** `curl -s http://localhost:8228/library` shows `library.css` link tag immediately after `cda.css`; opening `/library` in a browser side-by-side with `reference/Cd Archivist - Library Manager.html` shows matching colors/type on the shell chrome. No console 404s on the static mount.

- [ ] {agent: lane-1, depends: shell-route, id: breadcrumb-switcher} Replace the static `cd/a` brand mark on both `/rip` and `/library` with the brand-lockup breadcrumb switcher per build-prompt §2. Recipe: `[cd/a] · rip ▾` (or `library ▾`). Clicking opens a dropdown listing both surfaces with a one-line telemetry hint each — `4 ripping · 2 review` style for `/rip`, `3 inbox · 1 download` style for `/library`. Pull rip telemetry from the existing kanban state source; library telemetry is allowed to be a static placeholder for this sprint (per-panel briefs will replace). Active surface row carries a moss check.
  - **Acceptance:** `tests/service/test_breadcrumb_switcher.py` asserts the dropdown DOM structure (two surface rows + telemetry-hint span + active-check marker), tests both surface routes render the switcher, and asserts navigation: clicking `library` from `/rip` issues a GET to `/library` (route + nav assertion). Visual smoke against the reference HTML's third artboard (dropdown-open in isolation).

- [ ] {agent: lane-2, depends: shell-route, id: sidebar-panels} Render the 7-panel grouped sidebar inside `archivist/service/library_sidebar.py` (new module; called from `library_page.py`). Four v1 primaries are anchor links (`downloads`, `inbox`, `disk`, `library`); three v2 ghosts (`review`, `recent`, `cron`) render at 42% opacity, non-interactive (`aria-disabled="true"`, `cursor: not-allowed`), each with a `soon` chip. Group labels: `QUEUES`, `HEALTH`, `BROWSE`, `COMING · v2` — per build-prompt §2/§3.
  - **Acceptance:** `tests/service/test_library_sidebar.py` asserts: four `<a>` entries for v1 panels (each with the documented sub-line); three `aria-disabled` entries for v2 with `soon` chips; group labels render in order; the active panel's sidebar entry carries a distinguishing class when on `/library/{panelId}`. Visual smoke against the reference HTML's second artboard.

- [ ] {agent: lane-2, depends: shell-route, id: landing-grid} Render the landing card grid at `/library` (no panel selected) inside `archivist/service/library_landing.py` (new module). Four v1 cards (downloads, inbox, disk, library) each with eyebrow + title + sub + a small preview shape per build-prompt §2 landing-state: per-track pip strip for Downloads, album rows with READY pip for Inbox, three horizontal usage bars for Disk, recent-imports list for Library. Three v2 ghost cards beneath, 42% opacity, non-clickable. Card clicks navigate to `/library/{panelId}`.
  - **Acceptance:** `curl -s http://localhost:8228/library` HTML contains 4 v1 card blocks + 3 v2 ghost card blocks; each v1 card's preview-shape selector matches the build-prompt's named hint (e.g. `.cda-lib-card-preview--pip-strip` for Downloads). `tests/service/test_library_landing.py` covers each card's structure and the v2-ghost opacity class. Visual smoke against the reference HTML's first artboard.

- [ ] {agent: lane-2, depends: shell-route, id: panel-placeholder} Implement the `/library/{panelId}` route body for the four v1 panels inside `archivist/service/library_panels.py` (new module). Each panel renders the build-prompt §4 pattern: panel header (eyebrow + h1 + sub + optional right-aligned stat cells matching the rig-stats group style) + an honest dashed-border placeholder card with 3 ghost rows and a `tag: in design` + "UX is intentionally undecided in this pass…" foot. Per-panel header copy comes from the build-prompt §3 panel inventory table. v2 panel ids (`review`, `recent`, `cron`) return 404 — they are not addressable yet.
  - **Acceptance:** `curl -s -o /dev/null -w '%{http_code}' http://localhost:8228/library/downloads` (and `/inbox`, `/disk`, `/library`) all return `200`. `curl ... /library/review` returns `404`. `tests/service/test_library_panels.py` covers per-panel header copy (eyebrow/h1/sub) + the placeholder card structure + the v2-id 404 behavior.

- [ ] {agent: lane-1, depends: breadcrumb-switcher,sidebar-panels,landing-grid,panel-placeholder,load-library-css, id: history-and-shared} Final wire-up. (a) Sidebar clicks update the URL to `/library/{panelId}` and browser back/forward swap the active panel — either via `history.pushState` + a panel-only fetch/swap, OR by ensuring full server reloads are fast enough that the operator can't tell (document the choice in the commit message). (b) Confirm the bottom daemon log is the same DOM element id across `/rip` and `/library`, mounted at app-level beneath both main regions — not duplicated per surface. Final visual diff against the reference HTML's three artboards (landing, panel-selected, dropdown-open).
  - **Acceptance:** `tests/service/test_shared_bottom_log.py` asserts the bottom-log element id is identical when rendered from `/rip` vs `/library`. Browser back/forward between sidebar selections: no console errors, no full re-render of the shell chrome (or full reload <100ms — the chosen approach is documented in the commit body). All three reference-HTML artboards have a matching live route. `tests/service/test_library_*` and `tests/service/test_breadcrumb_switcher.py` all green; full pipeline test suite passes.

## Agent Roster

| Agent | Pane | Lane | Owns |
|---|---|---|---|
| lane-1 | (TBD at launch) | shell + routing | `archivist/service/library_page.py` (new), `archivist/service/app.py` (new `/library` + `/library/{panelId}` routes, `/` redirect), `archivist/service/static/css/library.css` (vendored — read-only after vendor-assets), the brand-lockup switcher fragment in `archivist/service/kanban_page.py` + `archivist/service/library_page.py`, `tests/service/test_library_shell.py`, `tests/service/test_breadcrumb_switcher.py`, `tests/service/test_shared_bottom_log.py`, `docs/reference/mashco-design-system/cd-archivist-library/` (relocation), `docs/LIBRARY-MANAGER-PROPOSAL.md`, `docs/design/2026-05-18-library-manager-design-brief.md` |
| lane-2 | (TBD at launch) | panel UX | `archivist/service/library_sidebar.py` (new), `archivist/service/library_landing.py` (new), `archivist/service/library_panels.py` (new), `tests/service/test_library_sidebar.py`, `tests/service/test_library_landing.py`, `tests/service/test_library_panels.py` |

**Cross-lane coordination:**
- `archivist/service/library_page.py` is owned by lane-1 (shell scaffold). lane-2's three new modules are called *from* `library_page.py`; lane-2 does not edit it directly. Wire-up happens lane-1-side after lane-2's modules land their public render functions.
- `archivist/service/app.py` is touched by lane-1 only this sprint (route registration). lane-2 stays out of routing.
- `archivist/service/kanban_page.py` is touched by lane-1 only (breadcrumb switcher fragment).
- The bottom daemon log mount is **not duplicated** — lane-1 confirms the existing element id is shared and used as-is on `/library`.

## Decision Log

_No decisions yet._

## Ratification Log

_No ratifications yet._

## Contract Changes

_No contract changes yet._

## Blockers

- _None._

## Activity Log

<!-- Per-agent updates land here, newest first. Format:

     ### {{date}} — {{agent}} — {{summary}}
     - what changed
     - why
     - links: PRs, audit entries

     Drift detection (O6) compares this section's most recent timestamp
     against git history; if commits land on owns paths without a
     matching entry, orc emits a coord-doc-stale card proposing an
     entry for the agent that committed. -->

### 2026-05-19 — orc (lane-1) — shell-route landed (9 new tests, 635/635 green)

- New module `archivist/service/library_page.py` with `render_library_page(music_root, loop_state, *, panel_id=None)` and `V1_PANEL_IDS = ("downloads", "inbox", "disk", "library")`. Reuses kanban's `_render_header_bar` + `_render_bottom_drawer` + `_stats`; ships its own `_render_library_right_drawer` rendering the build-prompt §5 idle copy ("Select an item to see details.") with the same DOM id (`right-drawer`) so chassis JS still targets one element.
- Lane-2's three modules (`library_sidebar`, `library_landing`, `library_panels`) are lazy-imported with stub fallbacks — this shell lands without them and lane-2's work plugs in by replacing the stub render path.
- Routing in `archivist/service/app.py`: `/` now serves a meta-refresh redirect to `/rip` (per build-prompt §6); `/rip` is the new mount point for the kanban (was `/`); `/library` renders the landing surface; `/library/{panel_id}` renders the panel surface for v1 ids and 404s for v2 ids (`review`, `recent`, `cron`).
- Cross-test sweep: 18 existing `tests/service/test_*.py` files had `client.get("/")` assertions for kanban content — flipped to `client.get("/rip")`. None of those tests required `/` specifically; they were asserting kanban markup at the old mount point. `test_app.py` (no-music-root fallback) kept `/` since `_PAGE_HTML` still serves there when `music_root is None`.
- New tests: `tests/service/test_library_shell.py` (9 cases) — root redirect, `/rip` serves kanban, `/library` landing 200, four v1 panels 200, three v2 panels 404, drawer idle copy verbatim, shared `right-drawer` element id, shared `bottom-drawer` + `bottom-drawer-log` element ids, rig-stats labels identical across surfaces.
- Verified: `pytest tests/` → 635/635 green (404/404 service tests).

### 2026-05-19 — orc (lane-1) — vendor-assets landed

- Copied `docs/reference/mascho-design-handoff-cda-library/library-manager-handoff/reference/cda-library-styles.css` → `archivist/service/static/css/library.css` (byte-identical vendor; wire-up deferred to `load-library-css`).
- Relocated the handoff tree: `docs/reference/mascho-design-handoff-cda-library/library-manager-handoff/` → `docs/reference/mashco-design-system/cd-archivist-library/`. The old `mascho-` typo path is gone; the new path is sibling to the existing `docs/reference/mashco-design-system/cd-archivist/` (sprint-7 handoff).
- Tracked the two previously-untracked design briefs: `docs/LIBRARY-MANAGER-PROPOSAL.md` + `docs/design/2026-05-18-library-manager-design-brief.md`.
- No template or route edits in this commit — vendor-only.
- Working as orc-from-pane per explicit user override (seed §3.9 framework discipline waived for this sprint).

### 2026-05-19 — orc — sprint-9 plan drafted (Library Manager shell)

- Drafted from the build-prompt at `docs/reference/mascho-design-handoff-cda-library/library-manager-handoff/handoff/build-prompt.md` + the two untracked design briefs in `docs/`.
- Eight tasks across two lanes (lane-1 shell + routing; lane-2 panel UX). Dependency graph: `vendor-assets` + `shell-route` start parallel (Wave 0); five tasks fan out from `shell-route` once it lands (Wave 1: `load-library-css`, `breadcrumb-switcher`, `sidebar-panels`, `landing-grid`, `panel-placeholder`); `history-and-shared` is the final closer (Wave 2) after all five Wave 1 tasks complete.
- No drive/hardware dependency — chosen specifically to ship in the RMA drive-replacement window (per `ISSUES.md` drive-hardware-failure). Sprint-7's outstanding operator `smoke-visual-pass` and sprint-2/6.5's outstanding real-rig smokes are explicitly NOT pulled in here; they stay deferred until the RMA arrives.
- Roster: two lanes named `lane-1` / `lane-2` per the sprint-6.5/7/8 nomenclature; panes TBD at workspace launch via tmax. The profile's `drivers`/`pipeline` formal roster is not used this sprint — all work is `archivist/service/` (pipeline territory) split into two lanes for parallelism per seed §3.2.
- New design briefs (`docs/LIBRARY-MANAGER-PROPOSAL.md`, `docs/design/2026-05-18-library-manager-design-brief.md`) are currently untracked; `vendor-assets` adds them to git.
- Path correction noted: handoff vendored under `mascho-design-handoff-cda-library/` (typo for `mashco`); `vendor-assets` relocates to the canonical spelling.
