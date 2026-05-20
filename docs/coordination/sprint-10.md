---
project: cd-archivist
sprint: sprint-10
created: 2026-05-19T00:00:00.000Z
updated: 2026-05-19T00:00:00.000Z
status: active
---

# cd-archivist — coordination doc (sprint-10)

> Strict template per Session O2=B / seed §12 Phase 8. The dashboard
> reads this as the canonical substrate (seed §3.7); orc emits
> `coord-doc-stale` cards when drift is detected (§3.8 / O7=A).
>
> Section headings are load-bearing — keep them as-is so the parser can
> find them. Section bodies are markdown-flexible.

## Plan Source

- Type: inline
- Path: this document (`## Active Sprint Plan` section)
- Active unit: sprint-10
- Upstream proposal: `docs/LIBRARY-MANAGER-PROPOSAL.md`
- Upstream brief: `docs/design/2026-05-18-library-manager-design-brief.md`
- Sprint-9 (predecessor): Library Manager shell + placeholders
- Sprint-9 build-prompt §8 enumerates the deferred per-panel UX
  decisions this sprint resolves.

## Sprint Goals

Make the four Library panels actually do their jobs

Disk · Inbox · Downloads · Library — replace the "in design" placeholders with live data and real operator actions.

## Active Initiatives

- _None — sprint-10 plan below is the substrate._

## Active Sprint Plan

<!-- Inline plan parsed by orc-tower's InlineArtifactSource. Per-panel
     module split keeps lane-1 and lane-2 off each other's files. -->

- [x] {agent: lane-1, id: setup-clients-package} Establish the service-clients pattern that all four panels will share. Create `archivist/service/clients/__init__.py` and `archivist/service/clients/README.md` documenting the contract: each client module exposes a thin typed wrapper around one external surface (filesystem walk, REST API, Subsonic API). Functions raise typed exceptions on failure; URLs and tokens come from environment variables (`SPOOTY_API_URL`, `SPOOTY_API_TOKEN`, `NAVIDROME_URL`, `NAVIDROME_USER`, `NAVIDROME_PASS`, `MUSIC_INBOX_DIR`, `MUSIC_REVIEW_DIR`, `MUSIC_ARCHIVE_DIR`). Add `archivist/service/library_panels.py` dispatcher that delegates `render_panel(panel_id)` to per-panel helper modules (`library_disk_panel.py` etc.) — keep the placeholder fallback in place for any panel whose helper module hasn't been written yet. Lane-2's T1b runs in parallel.
  - **Acceptance:** `archivist/service/clients/` exists with `__init__.py` + `README.md`; `library_panels.py` dispatches to per-panel modules with the placeholder fallback (verified by an existing-suite run: 677/677 still green). `pip install -e .` succeeds. No client implementations yet — that's the panel-impl tasks.

- [x] {agent: lane-2, id: chassis-poll-dispatcher} Wire per-panel polling cadence into `archivist/service/chassis_js.py`. Each panel viewport declares its desired poll interval via `<meta name="library-poll-ms" content="N">` (or absent → no polling). Add a small dispatcher that reads the meta on `/library/{panel_id}` load and `setInterval`s a fetch against a per-panel endpoint (the endpoint URL also comes from a meta tag). Cadences: Disk 30000, Inbox 5000, Downloads 1000 during active / 5000 idle, Library none. Drive-status polling (already in place) is unchanged. The dispatcher must be a no-op on `/rip` (it stays kanban-only there).
  - **Acceptance:** `chassis_js.py` exports the new polling dispatcher; `tests/service/test_chassis_poll.py` covers (a) no-op when no meta present, (b) fires fetch on interval when meta is present, (c) clears on page-hide. Existing tests still green.

- [ ] {agent: lane-1, depends: setup-clients-package, id: disk-impl} Implement the Disk panel end-to-end. New `archivist/service/clients/disk_client.py` with `get_disk_usage() -> DiskUsageSnapshot` reading `shutil.disk_usage()` for the three mounts (`/`, `/mnt/seagate`, `/mnt/archive`) and filesystem walks under each for per-surface breakdown (inbox / library / archive / spooty). Snapshot is a dataclass with `mounts: list[MountUsage]` where each `MountUsage` carries `mount_path`, `total_bytes`, `used_bytes`, `available_bytes`, `pct_used`, `surfaces: dict[str, int]`. New `/api/library/disk` endpoint in `app.py` returning the snapshot JSON. New `archivist/service/library_disk_panel.py` rendering three usage-bar rows + per-surface drilldown table. Thresholds: `pct_used < 60` → `--mash-pulp`, `60-85` → `--amber`, `> 85` → `--ember` (build-prompt §3). Mounts that don't exist (e.g., dev machine without `/mnt/seagate`) render as "not mounted" — graceful.
  - **Acceptance:** `tests/service/test_library_disk.py` covers the disk_client snapshot (mocked shutil + filesystem), the `/api/library/disk` endpoint shape, and the rendered HTML structure (three rows, threshold classes, drilldown table). `curl https://cda.mattmariani.com/library/disk` shows real per-mount usage live. Existing suite still green.

- [ ] {agent: lane-2, depends: setup-clients-package,chassis-poll-dispatcher, id: inbox-impl} Implement the Inbox panel end-to-end. New `archivist/service/clients/inbox_client.py` with `list_inbox_folders() -> list[InboxFolder]` walking `$MUSIC_INBOX_DIR` and `$MUSIC_INBOX_DIR/spooty/`. Each `InboxFolder`: `name`, `path`, `source` (`"cd_rip"` or `"spooty"`), `file_count`, `size_bytes`, `last_modified` (ISO), `ready_marker_present` (bool). New `/api/library/inbox` endpoint (list). New `/api/library/inbox/import-now` POST endpoint taking `{folder: str}` and invoking the appropriate beets path (`bin/process-ready-auto <folder>` for CD rips, `spooty-import.sh <folder>` for spooty content) via subprocess — fire-and-forget with a 30s timeout; returns `{status: "started"|"failed", message: str}`. New `archivist/service/library_inbox_panel.py` rendering one row per folder with name, source tag, file count, size, last-modified, READY pip, and an "import now" button. Refresh cadence: 5s via the chassis-poll-dispatcher.
  - **Acceptance:** `tests/service/test_library_inbox.py` covers inbox_client folder enumeration (tmp_path fixture with both subdirs + READY markers), `/api/library/inbox` endpoint shape, `/api/library/inbox/import-now` happy + error paths, and rendered HTML structure (row count, source tag, READY pip, import-now button). Live walk of `/srv/music/inbox/` on the CM4 returns real folders. Existing suite still green.

- [ ] {agent: lane-2, depends: setup-clients-package,chassis-poll-dispatcher, id: downloads-impl} Implement the Downloads (Spooty) panel end-to-end. New `archivist/service/clients/spooty_client.py` proxying the spooty REST API at `$SPOOTY_API_URL` (default `http://192.168.6.38:3003/api`). Read-only methods: `list_playlists()`, `list_tracks(playlist_id)`. Mutating methods: `submit_playlist(url)`, `retry_track(id)`, `delete_track(id)`, `retry_playlist(id)`. Use `requests` with a 5s timeout; raise `SpootyUnavailable` on connection failure. New endpoints in `app.py` under `/api/library/downloads/*` matching the client methods (the proxy is thin — cda forwards the operator action and returns the spooty response verbatim). New `archivist/service/library_downloads_panel.py` rendering one row per playlist + per-track pip strip (green=ok, pulp=active, ember=error, empty=pending) + submit-playlist form + per-track retry/delete affordances + retry-whole-playlist button. Stats header: Playlists · Tracks · Done · Errors. Refresh cadence: 1000ms during active, 5000ms idle.
  - **Acceptance:** `tests/service/test_library_downloads.py` covers the spooty_client with a mocked requests session (happy paths + SpootyUnavailable on connection error), each `/api/library/downloads/*` endpoint, and the rendered HTML structure (playlist rows, per-track pips with correct state classes, action buttons). Live `/library/downloads` shows real spooty state if `SPOOTY_API_URL` is reachable; degrades to a "spooty unavailable" empty state otherwise. Existing suite still green.

- [ ] {agent: lane-1, depends: setup-clients-package, id: library-impl} Implement the Library (browse) panel end-to-end. New `archivist/service/clients/subsonic_client.py` with read-only Subsonic API calls against `$NAVIDROME_URL` using `$NAVIDROME_USER` / `$NAVIDROME_PASS` (Subsonic auth — username + token + salt). Methods: `search(query: str, limit: int = 20)` (uses `search3.view`) and `get_newest_albums(limit: int = 10)` (uses `getAlbumList2.view` with `type=newest`). Raise `NavidromeUnavailable` on connection failure. New `/api/library/browse` endpoint (search; takes `?q=`) + `/api/library/browse/recent` endpoint (10 most-recent). New `archivist/service/library_browse_panel.py` rendering a search input (debounced 300ms client-side, fires `/api/library/browse?q=`) + the 10 most-recent imports list + a prominent "Open Navidrome ↗" CTA linking to `$NAVIDROME_URL`. No polling — search is on-input. Recent list refreshes only on full panel load.
  - **Acceptance:** `tests/service/test_library_browse.py` covers the subsonic_client search + getAlbumList2 calls with a mocked requests session, each `/api/library/browse*` endpoint, and the rendered HTML structure (search input wired to the endpoint, recent list with thumb + name + relative-time, Navidrome CTA href). Live `/library/library` shows real recent-imports if `NAVIDROME_URL` is reachable; degrades to an empty state with the CTA still working otherwise. Existing suite still green.

- [ ] {agent: lane-1, depends: disk-impl,inbox-impl,downloads-impl,library-impl, id: deploy-and-smoke} Final integration. Verify all four panel routes render real data end-to-end on the deployed CM4 surface. Update `docs/operations/cm4-setup.md` (or sibling) with the new env vars: `SPOOTY_API_URL`, `NAVIDROME_URL`, `NAVIDROME_USER`, `NAVIDROME_PASS`, `MUSIC_INBOX_DIR`, `MUSIC_REVIEW_DIR`, `MUSIC_ARCHIVE_DIR`. Update `archivist.service` systemd unit (or note in the docs) for any new env vars the operator needs to set. Hard-refresh `cda.mattmariani.com/library/{downloads,inbox,disk,library}` and confirm each renders the real surface. Update `CHANGELOG.md` with sprint-10 entries. Update `FEATURES.md` to mark the four panels as `shipped` (was `placeholder` after sprint-9).
  - **Acceptance:** All four `/library/{panel_id}` routes return 200 with live data on the CM4 (curl + visual smoke). `docs/operations/cm4-setup.md` documents the new env vars. `CHANGELOG.md` + `FEATURES.md` updated. Full test suite green. Mark sprint-10 `status: closed` with a final activity-log entry.

## Agent Roster

> Canonical roster for sprint-10. Two lanes; both Claude Code; both
> running with cwd inside the cd-archivist repo via `--add-dir`.

| Agent | Pane | Lane | Owns |
|---|---|---|---|
| lane-1 | (TBD at workspace launch) | setup + disk + library + deploy | `archivist/service/clients/__init__.py`, `archivist/service/clients/README.md`, `archivist/service/clients/disk_client.py` (new), `archivist/service/clients/subsonic_client.py` (new), `archivist/service/library_panels.py` (dispatcher edit only), `archivist/service/library_disk_panel.py` (new), `archivist/service/library_browse_panel.py` (new), `archivist/service/app.py` (`/api/library/disk`, `/api/library/browse`, `/api/library/browse/recent` route additions only), `tests/service/test_library_disk.py`, `tests/service/test_library_browse.py`, `docs/operations/cm4-setup.md` (env-var additions only), `CHANGELOG.md` + `FEATURES.md` (sprint-10 entries only) |
| lane-2 | (TBD at workspace launch) | chassis-poll + inbox + downloads | `archivist/service/chassis_js.py` (poll-dispatcher edit only), `archivist/service/clients/inbox_client.py` (new), `archivist/service/clients/spooty_client.py` (new), `archivist/service/library_inbox_panel.py` (new), `archivist/service/library_downloads_panel.py` (new), `archivist/service/app.py` (`/api/library/inbox`, `/api/library/inbox/import-now`, `/api/library/downloads/*` route additions only), `tests/service/test_chassis_poll.py`, `tests/service/test_library_inbox.py`, `tests/service/test_library_downloads.py` |

**Cross-lane coordination:**
- `archivist/service/app.py` route additions: both lanes append new routes near the existing `_mount_library_routes` block. Each lane stages narrowly to its own added routes; merge-conflict risk is low because endpoints are disjoint. lane-1 lands disk + library; lane-2 lands inbox + downloads.
- `archivist/service/library_panels.py` is touched by lane-1 once (dispatcher edit in `setup-clients-package`). After that, both lanes only add new per-panel modules that the dispatcher imports — they don't edit `library_panels.py` again.
- `archivist/service/chassis_js.py` is touched by lane-2 once (poll-dispatcher in `chassis-poll-dispatcher`). lane-1 doesn't touch it.
- Cross-lane meeting point: the per-panel meta tags (`<meta name="library-poll-ms" content="N">`, `<meta name="library-poll-endpoint" content="/api/...">`) consumed by lane-2's dispatcher are written by both lanes inside their per-panel render modules. Contract: meta tag name + format is decided in `chassis-poll-dispatcher` and documented in `chassis_js.py`'s docstring.

## Decision Log

_No decisions yet._

## Ratification Log

_No ratifications yet._

## Contract Changes

_No contract changes yet._

## Blockers

- _None._

## Activity Log

<!-- Per-agent updates land here, newest first. -->

### 2026-05-19 — lane-2 — chassis-poll-dispatcher closed

- Extended `archivist/service/chassis_js.py` with a per-panel polling
  dispatcher that reads `<meta name="library-poll-ms">` +
  `<meta name="library-poll-endpoint">` at page load. Absent meta →
  no-op (so `/rip`, the landing grid, and the Library/browse panel
  stay quiet). Present meta → `setInterval(pollTick, ms)` fetches the
  endpoint and re-broadcasts the result on a `library:poll-tick`
  custom event for per-panel modules to consume.
- Pause/resume wired via `visibilitychange`: hidden tabs clear the
  timer; visible tabs restart from current meta (so a panel switching
  active/idle cadence via meta `content` mutation just works). Start
  is idempotent — duplicate startPolling() calls short-circuit.
- Drive-status polling (chassis-level, /api/drive/status @ 5s) is
  untouched and runs alongside the new dispatcher.
- Contract for the per-panel meta tags is documented in the module
  docstring so lane-1's `library_disk_panel` / `library_browse_panel`
  and lane-2's `library_inbox_panel` / `library_downloads_panel` all
  emit the right shape (cadences from sprint-10 plan: Disk 30000,
  Inbox 5000, Downloads 1000 active / 5000 idle, Library none).
- New test file `tests/service/test_chassis_poll.py` (15 tests)
  covers the three sprint-10 acceptance criteria — no-op when meta
  absent, fetch fires on interval when present, clears on page-hide
  — via structural assertions against the JS source (no JS runtime
  in this suite, matching the existing chassis-JS test pattern).
- Full suite: 692/692 green (677 + 15 new).

### 2026-05-19 — lane-1 — setup-clients-package closed

- Scaffolded `archivist/service/clients/` with `__init__.py` + `README.md`
  documenting the contract: one module per external surface, typed
  return values, typed `*Unavailable` exceptions on transport failure,
  env-var configuration (read at call time, not import time), 5s HTTP
  timeouts. README enumerates the env-var ownership table that the
  four panel-impl tasks will reuse.
- Refactored `archivist/service/library_panels.py` into a dispatcher:
  `render_panel(panel_id)` looks up the spec, resolves the per-panel
  module via a `_PANEL_MODULES` map (`disk → library_disk_panel`,
  `library → library_browse_panel`, etc.), and calls its `render(spec)`.
  Falls back to the sprint-9 placeholder when the per-panel module is
  absent or lacks a `render` callable — this is the seam Wave 1 lands
  into without further edits to `library_panels.py`.
- No client implementations yet (per task scope). `pip install -e .`
  succeeds; full suite stays at 677/677 green.

### 2026-05-19 — orc — sprint-10 plan drafted (Library Manager v1 panels)

- Drafted from `LIBRARY-MANAGER-PROPOSAL.md`, the design brief, the build-prompt §8 follow-up list, and the JSX reference panels (`DownloadsPanel`, etc.).
- Seven tasks across two lanes: one Wave 0 setup per lane (clients package + chassis-poll dispatcher), then four parallel panel impls in Wave 1 (one per panel), then a single deploy + smoke closer in Wave 2.
- Per-panel module split (`library_disk_panel.py`, `library_inbox_panel.py`, `library_downloads_panel.py`, `library_browse_panel.py`) keeps lane-1 and lane-2 off each other's files. `library_panels.py` becomes a thin dispatcher.
- Service-clients pattern (sprint-10 §setup-clients-package) lands the `archivist/service/clients/` package and the env-var-driven contract that all four panel impls reuse. Each client is one module with one typed wrapper around one external surface.
- Polling cadence is wired through a shared dispatcher in `chassis_js.py` (sprint-10 §chassis-poll-dispatcher); each panel declares its desired interval via a `<meta name="library-poll-ms">` tag in its render output.
- Auth carry-over: spooty has no auth currently. The Cloudflare Access service-token follow-up (per the proposal §Auth) is NOT pulled in this sprint — sprint-10 ships against LAN-or-tunnel access patterns that already exist. When destructive actions ship (`delete-track`, etc.), they remain LAN-safe until Access is configured separately.
- Sprint-9 (Library Manager shell) closed cleanly earlier today; this sprint replaces the four "in design" placeholders with real panels.
- Roster: lane-1 / lane-2 nomenclature continues (panes TBD at workspace launch). Per the goal directive this sprint runs as proper orc-tower orchestration — orc dispatches prompts to project agents via the warren API, no orc-from-pane work on the project code itself.
