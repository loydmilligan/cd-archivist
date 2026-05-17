---
project: cd-archivist
sprint: sprint-6.5
created: 2026-05-16T00:00:00.000Z
updated: 2026-05-16T00:00:00.000Z
status: draft
---

# cd-archivist — coordination doc (sprint-6.5)

> Strict template per Session O2=B / seed §12 Phase 8. The dashboard
> reads this as the canonical substrate (seed §3.7); orc emits
> `coord-doc-stale` cards when drift is detected (§3.8 / O7=A).
>
> Section headings are load-bearing — keep them as-is so the parser can
> find them. Section bodies are markdown-flexible.

## Plan Source

- Type: inline
- Path: this document (`## Active Sprint Plan` section)
- Active unit: sprint-6.5
- Upstream brainstorm: `~/.config/taw/wiki/Projects/cd-archivist/docs/brainstorming/sprint-6.5-kanban-usability.md`

## Sprint Goals

- **Fix the phantom-`audio` builder bug.** `build_kanban_state` walks
  into each disc folder's `audio/` (and `captures/`, `logs/`, `review/`)
  subdirectory and treats it as its own disc. Every disc currently
  appears twice in the kanban. Table stakes.
- **Make cards expandable.** Inline accordion, one-at-a-time, spacebar
  toggle when focused, `?` tooltip surfacing keyboard nav. Expanded
  body holds actionable controls in three labeled sections: **Hints ·
  Manual Steps · Damaged-Disc Actions**.
- **Card visual-evolution as cards transit the pipeline.** Per-track
  segments gain an outline when beets has identified the track.
  Artist/Album chips glow (Mash Co. `--ok` treatment) when
  system-confirmed; render with a dashed border when operator-asserted
  only. Disc-photo thumbnail until album art lands, then album art
  replaces it. Damaged cards get a red-shadow treatment.
- **Layout shell:** header (wordmark + compact stats + drawer-toggle
  buttons; no alert strip in v1), right-side slide-out drawer
  (drive-status by default; selected-card heavy-detail when a card is
  clicked), bottom log drawer (collapsed default).
- **Column scrolling + count badges** with per-bucket default sort
  (Capture newest-first with active rip pinned; Beets ID newest;
  Review by "why" priority then newest; Library newest).
- **Adaptive polling.** 1s during active rip, 5s when idle. Read
  active-rip signal from the `/api/kanban` response payload itself.
- **High-leverage actions on the collapsed card.** "Process partial
  as-is" + "Redo" buttons on Capture-bucket damaged cards; "Accept
  top candidate" on Review-bucket cards when a high-confidence
  candidate exists.
- **New endpoints:** `GET /api/logs/tail?limit=N`, `GET /api/drive/status`.
- **Mobile bucket-tab fallback** — single-column with a segmented
  control to switch buckets, single CSS breakpoint.
- **Preserve the music-pipeline contract.** Additive only. No
  `source.json` schema changes this sprint. No state-machine touches
  beyond the new DriveStatus snapshot exposure.
- **TDD discipline preserved.** Wave 1 = failing tests (parallel-safe);
  Wave 2 = impls (depends-gated). No Wave 0 (no operator setup). Wave 3
  = real-rig smoke (the disc-id validation thread carried over from
  sprint-5 closes here).

> **Scope-hierarchy reminder.** Bucket A (builder fix) is table stakes —
> the kanban is unusable with phantom cards. Bucket B (card UI evolution)
> + Bucket C (layout shell) are the load-bearing usability work. Bucket
> D + E (endpoints + adaptive polling) are smaller but enable B and C.
> Bucket F (drivers DriveStatus exposure) feeds the right-drawer detail.

## Active Initiatives

- _None — sprint-6.5 plan below is the substrate._

## Active Sprint Plan

<!-- What ships in sprint-7+ (out of scope here):
     - Tail-log filter UI (per-rip, per-card query params on /api/logs/tail).
     - Force-re-run beets ID action.
     - Edit-by-hand metadata in library cards.
     - Sort/filter controls per column.
     - Cache build_kanban_state disk-walk with filesystem-event invalidation.
     - Alert / notification strip in header.
     - Wire operator_hints into beets search (carried from sprint-6 Sprint-7 Candidates).
     - In-UI beets candidate selection (Review v2).
     - Empty-tag MB-fallback suppression in beets.
     - Visual language redesign (status quo per K1.9).
     - Multi-drive support, containerized cd-archivist itself,
       live cam preview, AcoustID submission. -->

### Wave 1 — Failing tests (parallel-safe)

#### Bucket A — Builder fixes (pipeline)

- [x] {agent: pipeline, id: test-fix-phantom-audio}
  Failing tests for the directory-walk fix in
  `archivist/service/disc_card_builder.py::build_kanban_state`.
  `tests/service/test_disc_card_builder.py` additions:
  (a) fixture disc folder containing
  `{audio/track01.flac, captures/disc-photo.jpg, logs/rip.log,
  review/.gitkeep, source.json}` produces exactly ONE `DiscCard`,
  not five; (b) the card's `audio_count` reflects the number of
  flac files (not the count of subdirectories); (c) the walker
  treats `{audio, captures, logs, review}` as data subdirectories
  per disc, not as nested discs. Regression-pin the bug observed
  on cda.mattmariani.com 2026-05-16.

- [x] {agent: pipeline, id: test-per-bucket-sort}
  Failing tests for default sort per bucket in
  `build_kanban_state`. `tests/service/test_kanban_sort.py`:
  (a) Capture-bucket cards sort with the active-rip overlay
  pinned to position 0, then failed/partial cards, then
  successful cards, each tier newest-first;
  (b) Beets-ID bucket sorts newest-first;
  (c) Review bucket sorts by "why in review" priority
  (partial/damaged → weak-match → no-match → no-id-and-no-tags),
  then newest-first within priority;
  (d) Library bucket sorts newest-first;
  (e) the priority enum is exposed so the UI can chip-label it.

#### Bucket B — Card UI evolution (pipeline)

- [x] {agent: pipeline, id: test-card-state-evolution}
  Failing tests for the visual-evolution renderer.
  `tests/service/test_card_evolution.py`:
  (a) a card whose `source.json` has `identifiers.musicbrainz_disc_id`
  populated AND has any chroma fingerprint result writes
  `data-track-identified-{N}="true"` on the corresponding track-cell
  segments;
  (b) a card with `detected_metadata.album_artist` and `.album`
  populated by beets renders artist/album chips with class
  `chip--confirmed` (Mash Co. `--ok`-derived treatment);
  (c) a card with `operator_hints.artist` or `.album` populated but
  no beets confirmation renders those chips with class
  `chip--asserted` (dashed border);
  (d) a card whose `source.json` has `status.partial=True` OR
  `status.rip_success=False` renders with class
  `card--damaged` (red-shadow);
  (e) thumbnail src prefers `library/<album>/cover.*` when the disc
  is in Library, falls back to `<folder>/disc-photo.jpg` otherwise.

- [x] {agent: pipeline, id: test-expand-mechanic}
  Failing tests for click-to-expand + keyboard.
  `tests/service/test_kanban_page.py` additions:
  (a) cards have `aria-expanded="false"` and `tabindex="0"`;
  (b) the page includes a `?` tooltip element (`<button
  aria-label="keyboard help">?</button>`) at top-right of the
  kanban with `data-keyboard-help` attribute populated; (c) the
  page emits a `<script type="module">` that wires spacebar to
  toggle the focused card AND `preventDefault()` to suppress
  browser page-down behavior; (d) only one card may be expanded
  at a time — opening a second card collapses the first
  (assert via the page's inline JS via a test using
  `playwright` if available; otherwise assert the JS source
  contains the one-at-a-time guard).

- [x] {agent: pipeline, id: test-expanded-card-sections}
  Failing tests for the expanded card body sections.
  `tests/service/test_expanded_card.py`:
  (a) expanded body renders three labeled `<section>` elements
  with `data-section="hints"`, `data-section="manual-steps"`,
  `data-section="damaged-actions"`; (b) the hints section
  contains the operator-hints UI (VA + Burned toggles, Artist
  + Album inputs, per-track table conditionally rendered when
  both toggles on); (c) the manual-steps section pulls content
  from the review-explainer endpoint when card.bucket=="review";
  (d) the damaged-actions section is hidden unless
  `card.partial=true OR card.status=="failed"`.

- [x] {agent: pipeline, id: test-collapsed-card-actions}
  Failing tests for high-leverage actions on collapsed cards.
  `tests/service/test_collapsed_card_actions.py`:
  (a) Capture-bucket card with `card--damaged` renders two
  buttons in the collapsed body: "Process partial" (POSTs to
  `/api/disc/<folder>/process-partial`) and "Redo" (POSTs to
  `/api/disc/<folder>/redo?confirm=true`); (b) Review-bucket
  card with `card.top_candidate_score >= 0.85` renders an
  "Accept top match" button that POSTs to a new
  `/api/disc/<folder>/accept-top-candidate`; (c) non-damaged
  Capture cards and low-confidence Review cards render NO
  collapsed-card buttons (no false-affordances).

#### Bucket C — Layout shell (pipeline)

- [x] {agent: pipeline, id: test-header-bar}
  Failing tests for the page header.
  `tests/service/test_kanban_page.py` additions:
  (a) page renders a `<header>` element with three regions:
  `.header-left` (wordmark "cd-archivist" + daemon state dot —
  green when active, red when stopped, derived from
  `/api/kanban` response presence), `.header-stats` (compact
  counts: total-discs / in-review / partial — derived from the
  kanban payload), `.header-right` (drawer-toggle buttons +
  link-out to navidrome + link-out to beets web UI);
  (b) drawer-toggle buttons have `aria-controls` pointing at
  the right drawer and bottom drawer elements respectively;
  (c) no notification/alert strip is present (D-no-alerts-v1).

- [x] {agent: pipeline, id: test-right-drawer}
  Failing tests for the right-side slide-out drawer.
  `tests/service/test_right_drawer.py`:
  (a) drawer element exists with `id="right-drawer"`,
  `aria-hidden="true"` default, slide-in CSS transform;
  (b) when no card is selected, drawer body renders the
  drive-status template populated from `/api/drive/status`
  (current track, sector progress, retries, photo state,
  elapsed time);
  (c) when a card is clicked, drawer body swaps to the
  card-detail template (rip-log tail via
  `/api/disc/<folder>/log/tail`, full source.json JSON,
  disc-photo at full size); (d) drawer-toggle button in the
  header AND clicking a card both open the drawer.

- [x] {agent: pipeline, id: test-bottom-drawer}
  Failing tests for the bottom log drawer.
  `tests/service/test_bottom_drawer.py`:
  (a) drawer element exists with `id="bottom-drawer"`,
  `aria-hidden="true"` default, slide-up CSS transform;
  (b) when expanded, drawer body renders a `<pre>` tailing
  `/api/logs/tail?limit=200` and refreshes on the same poll
  cadence as the kanban; (c) drawer state (collapsed/expanded)
  persists in localStorage under
  `cd-archivist:bottom-drawer:open`.

- [x] {agent: pipeline, id: test-column-scroll-badges}
  Failing tests for independent column scroll + count badges.
  `tests/service/test_kanban_page.py` additions:
  (a) each `.column` element has `overflow-y: auto` and a
  `max-height` calc'd against viewport;
  (b) each column header includes a `.count-badge` showing
  the card count: "REVIEW (6)";
  (c) column header is `position: sticky; top: 0` so it
  doesn't scroll away.

- [x] {agent: pipeline, id: test-mobile-bucket-tabs}
  Failing tests for the mobile single-column fallback.
  `tests/service/test_mobile_kanban.py`:
  (a) at viewport ≤ 720px, the kanban renders a
  `<nav class="bucket-tabs">` with four buttons (one per
  bucket) and only one column is visible at a time;
  (b) tab selection persists in localStorage under
  `cd-archivist:mobile-bucket`;
  (c) default tab is "Capture".

#### Bucket D — Endpoints (pipeline)

- [x] {agent: pipeline, id: test-logs-tail-endpoint}
  Failing tests for `GET /api/logs/tail`.
  `tests/service/test_logs_tail_endpoint.py`:
  (a) returns the last N lines of the daemon's
  `ARCHIVIST_LOG_PATH` log, default N=200, max N=2000;
  (b) response shape is
  `{"lines": ["...", "..."], "log_path": "/path/to/log",
  "truncated": bool}`;
  (c) 404 when the log file is missing;
  (d) `?limit=N` query param honored; (e) per-rip and
  per-card filter query params are NOT implemented in v1
  (sprint-7) but the endpoint accepts and ignores them
  without erroring.

- [x] {agent: pipeline, id: test-drive-status-endpoint}
  Failing tests for `GET /api/drive/status`.
  `tests/service/test_drive_status_endpoint.py`:
  (a) returns
  `{"state": "idle"|"ripping"|"stabilizing"|"capturing",
  "current_disc": "<folder>"|null,
  "current_track": int|null, "track_total": int|null,
  "sector_current": int|null, "sector_total": int|null,
  "retries_on_current_track": int|null, "photo_state":
  "pending"|"capturing"|"done"|null, "elapsed_seconds":
  float|null}`;
  (b) when idle, all fields except `state` are null and
  state is "idle";
  (c) data is sourced from a `DriveStatus` object on
  `LoopState` populated by drivers' `impl-drive-status-snapshot`.

#### Bucket E — Adaptive polling (pipeline)

- [x] {agent: pipeline, id: test-adaptive-polling}
  Failing tests for adaptive poll cadence.
  `tests/service/test_kanban_page.py` additions:
  (a) page emits two poll-interval values in
  `<meta name="kanban-poll-ms-active" content="1000">` and
  `<meta name="kanban-poll-ms-idle" content="5000">`;
  (b) the kanban response includes a new top-level
  `active_rip: bool` field;
  (c) the page JS reads `active_rip` from each response and
  switches interval accordingly; assert the JS source
  contains both interval references and the switching
  guard.

#### Bucket F — Drive-status snapshot (drivers)

- [x] {agent: drivers, id: test-drive-status-snapshot}
  Failing tests for the new `DriveStatus` exposure.
  `tests/state_machine/test_drive_status.py`:
  (a) `DriveStatus` dataclass exists in
  `archivist/state_machine/drive_status.py` with the fields
  from the `/api/drive/status` contract above;
  (b) `LoopState` gains a
  `drive_status: DriveStatus = field(default_factory=DriveStatus)`
  attribute;
  (c) during a rip, the ripper progress callback updates
  `drive_status.current_track`, `.sector_current`,
  `.sector_total`, `.retries_on_current_track`;
  (d) STABILIZE / CAPTURE transitions update `drive_status.state`
  and `.photo_state`;
  (e) idle state resets all transient fields to None and state
  to "idle";
  (f) thread-safety: `drive_status` is updated from the
  ripper-streaming thread and read from the FastAPI thread —
  a `threading.Lock` protects mutations, or the dataclass is
  rebuilt and atomic-swapped per update.

### Wave 2 — Implementations

#### Bucket A — Builder fixes (pipeline)

- [x] {agent: pipeline, depends: test-fix-phantom-audio, id: impl-fix-phantom-audio}
  In `archivist/service/disc_card_builder.py`, change the
  directory walk so it iterates `{music_root}/{review,library,
  archive,failed,inbox}/` only at the **first** level — each
  immediate child is a disc folder, and the walker does not
  recurse into the disc folder's children. Disc-folder-internal
  structure (`audio/`, `captures/`, `logs/`, `review/`,
  `source.json`, `disc-photo.jpg`, `rip.log`, `READY/PROCESSING
  markers`) is read directly via `disc_dir / "<name>"` patterns,
  not by recursive walks. Commit: `fix(sprint-6.5):
  impl-fix-phantom-audio — stop treating disc subdirs as nested
  discs`.

- [x] {agent: pipeline, depends: test-per-bucket-sort, id: impl-per-bucket-sort}
  Implement default sort per bucket per the test spec. Add a
  `ReviewPriority` enum
  (`PARTIAL=0, WEAK_MATCH=1, NO_MATCH=2, NO_ID_NO_TAGS=3`) and
  expose it on `DiscCard.review_priority` for Review-bucket
  cards. Pin the algorithm in a new decision-log entry
  `D-default-sort-v1`.

#### Bucket B — Card UI evolution (pipeline)

- [x] {agent: pipeline, depends: test-card-state-evolution, id: impl-card-state-evolution}
  In `archivist/service/kanban_page.py`, render the card-state
  evolution: outline classes on track-cell segments when
  identified; `chip--confirmed` vs `chip--asserted` classes on
  metadata chips per the test spec; thumbnail src logic per
  bucket; `card--damaged` class. Add corresponding CSS in the
  inline `<style>` block using Mash Co. tokens (`--ok` for
  confirmed glow; `--line-dashed` for asserted; `--meat-red` for
  damaged shadow). Pin Mash Co. token mapping in
  `D-card-evolution-tokens`.

- [x] {agent: pipeline, depends: test-expand-mechanic, id: impl-expand-mechanic}
  Implement click + spacebar expand. New inline `<script
  type="module">` block in `kanban_page.py`. Click handler on
  `[data-card-id]` toggles `aria-expanded` and the associated
  expanded body's visibility; tracks a single "currently
  expanded" card id in module-scope state and collapses the
  previous one on each new toggle. Spacebar handler attached
  to focused cards (`tabindex="0"`); `preventDefault()` when
  the focused element is a card to suppress page-down. `?`
  tooltip element renders keyboard nav: "Space — expand
  focused card · Tab — move between cards · Esc — collapse
  expanded card".

- [x] {agent: pipeline, depends: test-expanded-card-sections, id: impl-expanded-card-sections}
  Render the three expanded-body sections (Hints, Manual Steps,
  Damaged-Disc Actions). Hints section reuses the
  operator-hints UI from sprint-6 `impl-operator-hints` (move
  it from collapsed body to here). Manual Steps section renders
  the review-explainer output (only for Review-bucket cards).
  Damaged-Disc Actions section renders the three buttons
  (process-partial / redo / rerip-tracks with track-checkbox
  list) wired to the sprint-6 endpoints — only visible when
  the card is in damaged state.

- [x] {agent: pipeline, depends: test-collapsed-card-actions, id: impl-collapsed-card-actions}
  Implement high-leverage collapsed-card buttons. For
  Capture-bucket damaged cards: "Process partial" + "Redo"
  buttons rendered in the collapsed body's `.card-actions` row.
  For Review-bucket cards with `top_candidate_score >= 0.85`:
  "Accept top match" button. Add new endpoint `POST
  /api/disc/<folder>/accept-top-candidate` that invokes
  `beet import --search-id <top_mbid>` and routes the folder
  per the existing process-ready-auto logic. Lock the
  `0.85` threshold in `D-accept-top-candidate-threshold`.

#### Bucket C — Layout shell (pipeline)

- [x] {agent: pipeline, depends: test-header-bar, id: impl-header-bar}
  Render the header per the test spec. Daemon-state dot derives
  from kanban payload (present = active; absent/error = stopped).
  Stats counts derive from `len(buckets.<name>)` and the
  `partial` chip count across all cards. Link-outs to
  navidrome/beets web UI sourced from env vars
  `NAVIDROME_URL`, `BEETS_WEB_URL` (default "" → button hidden
  if unset). No alert strip.

- [x] {agent: pipeline, depends: test-right-drawer, id: impl-right-drawer}
  Implement the right-side drawer with two body templates:
  drive-status (default, no card selected) and card-detail
  (when a card is clicked). The card-click handler from
  `impl-expand-mechanic` ALSO opens the right drawer and
  populates the card-detail body. Drawer is independent of
  the expand state — closing the drawer doesn't collapse the
  card, and vice versa. Drive-status template polls
  `/api/drive/status` on the kanban poll cadence (adaptive).
  Card-detail template fetches
  `/api/disc/<folder>/log/tail` + reads the card's `source.json`
  from the kanban payload + serves the disc photo via
  `/review/<folder>/disc-photo.jpg` (re-use existing static
  routes). Drawer width: 420px desktop; full-screen on mobile.

- [x] {agent: pipeline, depends: test-bottom-drawer, id: impl-bottom-drawer}
  Implement the bottom log drawer. Collapsed default height
  32px (just the toggle bar); expanded 240px. State persisted
  to localStorage. When expanded, polls `/api/logs/tail` on
  the kanban cadence.

- [x] {agent: pipeline, depends: test-column-scroll-badges, id: impl-column-scroll-badges}
  Implement column independent scroll + sticky headers +
  count badges. Adjust the kanban grid to use
  `grid-template-rows: auto 1fr` per column so the header is
  fixed and the card list scrolls. Count badges read from
  `len(buckets.<name>)` server-side and render in the column
  header markup.

- [x] {agent: pipeline, depends: test-mobile-bucket-tabs, id: impl-mobile-bucket-tabs}
  CSS-driven mobile breakpoint at `max-width: 720px`. Bucket-tabs
  segmented control renders below the header on mobile; tab
  selection persisted in localStorage. Pin breakpoint in
  `D-mobile-breakpoint-v1`.

#### Bucket D — Endpoints (pipeline)

- [x] {agent: pipeline, depends: test-logs-tail-endpoint, id: impl-logs-tail-endpoint}
  Add `GET /api/logs/tail` to `archivist/service/app.py`. Reads
  `ARCHIVIST_LOG_PATH` env (already used by the daemon), uses
  efficient seek-from-end if file is large.

- [x] {agent: pipeline, depends: test-drive-status-endpoint, id: impl-drive-status-endpoint}
  Add `GET /api/drive/status` to `archivist/service/app.py`.
  Reads from `loop_state.drive_status` (populated by drivers'
  `impl-drive-status-snapshot`). Returns the contract shape per
  the test spec.

#### Bucket E — Adaptive polling (pipeline)

- [x] {agent: pipeline, depends: test-adaptive-polling, id: impl-adaptive-polling}
  Add `active_rip: bool` to the `/api/kanban` response payload.
  Update the inline JS poll loop to read `active_rip` and
  switch interval between 1000ms and 5000ms accordingly. The
  switch happens at the END of each response cycle, so the
  next setTimeout uses the correct cadence. Pin in
  `D-adaptive-polling-cadence`.

#### Bucket F — Drive-status snapshot (drivers)

- [x] {agent: drivers, depends: test-drive-status-snapshot, id: impl-drive-status-snapshot}
  Implement `archivist/state_machine/drive_status.py::DriveStatus`
  dataclass + `LoopState.drive_status` attribute + thread-safe
  updates from the ripper progress callback and state-machine
  transitions. Pin the schema in
  `D-drive-status-snapshot-schema`.

### Wave 3 — Real-rig smoke (operator-driven)

- [ ] {agent: operator, id: smoke-deploy-and-validate}
  Deploy sprint-6.5 to the CM4 (`git pull && pip install -e
  '.[dev]' && systemctl --user restart cd-archivist`). Open
  `cda.mattmariani.com` and verify:
  - Phantom-`audio` cards no longer appear.
  - Header renders wordmark / stats / drawer toggles.
  - Right drawer toggles open and shows drive-status when no
    card selected.
  - Bottom drawer toggles open and shows daemon log tail.
  - Clicking a card inline-expands it and ALSO populates the
    right drawer with detail.
  - Spacebar toggles a focused card.
  - Columns scroll independently with count badges.
  - At narrow viewport, bucket-tab control appears.
  - Pop a burned 1:1 album in: confirm the active rip pins
    to the top of Capture, drive-status drawer updates each
    second, kanban switches to 5s polling after rip lands,
    and `source.json.identifiers.musicbrainz_disc_id`
    populates (**closes sprint-5 carryover validation**).

## Agent Roster

| Agent | Owns | Does not touch |
|---|---|---|
| pipeline | `archivist/service/` (existing + new files: `kanban_page.py` rewrite, new `right_drawer.py` / `bottom_drawer.py` / `card_evolution.py` helpers as needed), `archivist/service/app.py` (new endpoints + `active_rip` field), `tests/service/`, `pyproject.toml`, `ruff.toml`, `docs/coordination/sprint-6.5.md` | `archivist/drivers/`, `archivist/state_machine/` internals (consumes DriveStatus via LoopState) |
| drivers | `archivist/state_machine/drive_status.py` (new), `archivist/state_machine/loop.py` (LoopState attribute + update calls only), `archivist/drivers/ripper.py` (progress-callback DriveStatus updates), `tests/state_machine/test_drive_status.py` | `archivist/service/`, `archivist/pipeline/`, UI surfaces |

Roster carries forward from sprint-6 with one scope shift:
sprint-6.5 is overwhelmingly pipeline work (10 of 11 impl tasks).
Drivers has one task (DriveStatus exposure) that unblocks pipeline's
`/api/drive/status` endpoint. Drivers should land
`impl-drive-status-snapshot` early in Wave 2 so pipeline can wire it
into the endpoint impl.

## Decision Log

> Architecture decisions to ratify at planning. Resolved decisions
> from the brainstorm are listed first; open ones at the bottom with
> **OPEN**.

### 2026-05-16 — D-pipeline-as-mental-model — cards transit left-to-right; column = pipeline step

Settled in brainstorm K1.5. Each bucket is one step in the
ingestion pipeline; layout, sort defaults, and card visual-evolution
all reinforce this framing. Not a "kanban of tasks" — a visualization
of where each disc is in the flow.

### 2026-05-16 — D-card-state-evolution — visual treatment changes as cards progress

Settled in brainstorm K1.6. Track segments gain outline on beets-ID;
artist/album chips glow when system-confirmed (`chip--confirmed`); render
with dashed border when operator-asserted (`chip--asserted`); disc-photo
thumbnail until album art lands; `card--damaged` class for failed/partial.

### 2026-05-16 — D-no-alerts-v1 — header has no notification/alert strip in v1

Settled in brainstorm K1.2 sub-brainstorm (header = H-D minus alerts).
Wordmark left, compact stats center, drawer-toggle + nav buttons right.
Alert strip deferred to sprint-7.

### 2026-05-16 — D-card-evolution-tokens — confirmed = --ok glow; asserted = dashed --line; damaged = --meat-red shadow

**Resolved during impl-card-state-evolution.** Final mapping:

- `chip--confirmed` (system-confirmed metadata): background
  `var(--ok)`, text `var(--bg)`, `box-shadow: 0 0 4px var(--ok)`.
  Loud — beets resolved this and we trust it.
- `chip--asserted` (operator-asserted only, not confirmed):
  background `transparent`, `border: 1px dashed var(--line)`,
  text `var(--ink)`. Quiet — the operator typed this; beets has
  not yet agreed.
- `card[data-state="damaged"]` (partial or rip_success=False):
  left-border switches to `--meat-red`, plus
  `box-shadow: 0 0 12px 2px rgba(255, 74, 74, 0.35)`. Visible
  across the entire kanban without forcing a separate column.
- `track-cell--identified` (beets identified this track):
  `outline: 1px solid var(--ok)`. Subtle — the per-track bar
  stays scannable.

Selected via `data-*` attributes (not class names) so the test
suite can assert class-name absence on unmatched cards via plain
string-search.

### 2026-05-16 — D-default-sort-v1 — ReviewPriority enum + per-bucket tie-breakers

**Resolved during impl-per-bucket-sort.** Final algorithm:

- **Capture:** active-rip overlay pinned at index 0; then damaged
  tier (`partial=True OR rip_success=False`) newest-mtime-first;
  then healthy tier newest-mtime-first.
- **Beets ID:** newest-mtime-first (bucket is empty pending
  sprint-7 work; ordering is a pre-commitment).
- **Review:** `ReviewPriority` IntEnum `(PARTIAL=0, WEAK_MATCH=1,
  NO_MATCH=2, NO_ID_NO_TAGS=3)` ascending; mtime-descending
  within priority tier. Priority derived from
  `status.beets_review_reason` (preferred) → tail of
  `beets-import.log` → presence of `musicbrainz_disc_id`.
- **Library:** newest-mtime-first, capped at
  `KANBAN_LIBRARY_RETENTION` (default 20).

Enum values are contractual — the UI keys chip labels off them.

### 2026-05-16 — D-accept-top-candidate-threshold — 0.85

**Resolved during impl-collapsed-card-actions.** The "Accept top
match" collapsed-card button surfaces when
`top_candidate.score >= 0.85`. Below threshold the button is
absent — the operator must expand and review manually. The
threshold itself is also enforced server-side in
`POST /api/disc/<folder>/accept-top-candidate` (409 below
threshold) so the UI gating can't be bypassed by a stale page.

Sprint-7 may tighten or loosen after real review-bucket data
accumulates; the value lives in `ACCEPT_TOP_THRESHOLD` and
the corresponding endpoint check.

### 2026-05-16 — D-mobile-breakpoint-v1 — max-width: 720px

**Resolved during impl-mobile-bucket-tabs.** Single CSS breakpoint
at `max-width: 720px` (`MOBILE_BREAKPOINT_PX`). Below the breakpoint
the kanban collapses to one column; the `.bucket-tabs` segmented
control becomes visible; only the active-mobile column renders.
Selection persists under `cd-archivist:mobile-bucket` localStorage
key. Default tab is "capture".

### 2026-05-16 — D-adaptive-polling-cadence — 1000ms active / 5000ms idle

**Resolved during impl-adaptive-polling.** Two cadences exposed
via meta tags (`kanban-poll-ms-active` / `kanban-poll-ms-idle`)
so they can be tuned without code changes. JS reads `active_rip`
from each `/api/kanban` response and schedules the next setTimeout
with the matching interval. On fetch error, falls back to the
idle interval to avoid hammering a struggling daemon.

Rationale: 1s during an active rip keeps the drive-status drawer
fresh enough that the operator doesn't second-guess the photo
capture window (~2s for the manual-eject step), while 5s idle
keeps the loaded CM4 from grinding when nothing is happening.

### 2026-05-16 — D-drive-status-snapshot-schema — RLock + state-transition mapping

Resolved during `impl-drive-status-snapshot`. Final decisions:

**Thread-safety mechanism: `threading.RLock`** (not `Lock`, not
atomic-swap). Rationale: state-transition paths (`_set_state` →
`_sync_drive_status_for_transition`) and the `_set_photo_state`
helper both acquire the lock; the inner `update_from_progress_line`
helper acquires it too. With a plain `Lock`, a caller that already
held the lock and then invoked a helper would deadlock. `RLock`
permits re-entry from the same thread. Atomic-swap-via-replacement-
dataclass was rejected because the LoopState field is a long-lived
reference held by FastAPI handlers; rebinding the field per update
introduces a separate read-after-rebind race and forces every reader
to re-resolve the attribute.

**State-transition mapping** (State enum → `drive_status.state`):

| State enum             | `drive_status.state` | Side effects             |
| ---------------------- | -------------------- | ------------------------ |
| IDLE / WAITING /       | `"idle"`             | **Reset all transient    |
| WAITING_REMOVE / ERROR |                      | fields to None**         |
| STABILIZE /            | `"stabilizing"`      | (current_disc set via    |
| STABILIZE_PARTIAL      |                      | `patch["disc_id"]`)      |
| RIP                    | `"ripping"`          | progress callback fans   |
|                        |                      | sector / retry / track   |
|                        |                      | into snapshot            |
| EJECT                  | `"capturing"`        | (drive opens tray)       |
| CAPTURE                | `"capturing"`        | photo_state walks        |
|                        |                      | pending → capturing →    |
|                        |                      | done                     |

Rationale: 4-bucket `state` is for the operator UI's coarse phase
indicator; EJECT is folded into "capturing" because from the operator
view the post-rip step is the photo capture (the tray opening is
just the mechanical prerequisite). ERROR maps to "idle" + full reset
because the operator's recovery action is "eject and try again" —
the snapshot should reflect "nothing happening right now" rather
than holding stale rip context.

**photo_state lifecycle:** `pending` set at the top of
`_from_capture` / `_from_stabilize_partial`; `capturing` set
immediately before `capture_disc(...)`; `done` set on successful
return; left at `capturing` (NOT cleared) when `capture_disc` raises,
so the UI shows the partial state until the next idle reset clears
it.

## Ratification Log

> User-ratified decisions. Format:
> `### {{date}} — {{decision-id}} — {{summary}}`.

- _None yet._

## Contract Changes

> Additive-only changes to `source.json` / API.

### 2026-05-16 — `GET /api/kanban` response gains `active_rip: bool`

Top-level field. True when any card is in the Capture bucket with an
in-progress state; false otherwise. Drives the adaptive-poll cadence
on the client.

### 2026-05-16 — `GET /api/kanban` response cards gain `review_priority: int | null`

Populated for Review-bucket cards only (per `D-default-sort-v1`).
Other cards have `null`. The kanban payload pre-sorts cards within
the Review bucket by this priority so the client doesn't need to
re-sort.

### 2026-05-16 — new endpoints

- `GET /api/logs/tail?limit=N` — daemon log tail.
- `GET /api/drive/status` — drive snapshot for the right-drawer
  default body.
- `GET /api/disc/<folder>/log/tail` — per-disc rip-log tail for the
  right-drawer card-detail body.
- `POST /api/disc/<folder>/accept-top-candidate` — Review-bucket
  high-confidence one-click accept.

No `source.json` schema changes this sprint.

## Blockers

<!-- One bullet per active blocker. Format:
     `- [<agent>] <one-line blocker> — <link or reference>`. Resolved
     blockers move to the Activity Log. -->

- _None._

## Sprint-7 Candidates

<!-- Items captured during sprint-6.5 that should be picked up at
sprint-7 planning. -->

- **Tail-log filter UI** (per-rip, per-card query params on
  `/api/logs/tail`). Backend already accepts and ignores; sprint-7
  adds the UI controls + backend filtering.
- **Force re-run beets ID** action on Beets-ID-bucket cards.
- **Edit-by-hand metadata** in Library-bucket cards.
- **Sort/filter controls per column** (sprint-6.5 ships defaults
  only).
- **Cache `build_kanban_state` disk-walk** with filesystem-event
  invalidation (inotify or mtime polling). Becomes necessary once
  the library has hundreds of discs.
- **Alert / notification strip in header** (H-C from the K1.2
  sub-brainstorm).
- **Wire `operator_hints` into beets search** (carried forward
  from sprint-6's Sprint-7 Candidates — album-level + per-track
  hints feed `beet import --set` or per-track `musicbrainzngs`
  search + tag-write before `--singletons` import).
- **In-UI beets candidate selection (Review v2)** — web wrapper for
  the beets candidate picker. Blocked on sprint-5's
  "beets-CLI traceback-spam on tag-less flacs" finding.
- **Empty-tag MB-fallback suppression** in beets (or bypass beets'
  interactive path entirely via `musicbrainzngs` direct).

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

### 2026-05-16 — pipeline — Wave 2 impls landed (14 tasks, 4 commits)

All 14 pipeline-owned Wave 2 impl tasks shipped. Full suite
497/497 green; ruff clean on touched files. Five OPEN decisions
RESOLVED inline (D-card-evolution-tokens, D-default-sort-v1,
D-accept-top-candidate-threshold, D-mobile-breakpoint-v1,
D-adaptive-polling-cadence).

Commits (atomic per scope; multi-task commits where the work
shared a single file):

- `6f1cec2` impl-{fix-phantom-audio, per-bucket-sort} —
  builder rewrite. `_iter_disc_folders` takes an explicit
  `depth` kwarg (library=2, everything else=1); audio-count
  flac-fallback prefers `audio/*.flac` (canonical) before the
  root-level (legacy). `ReviewPriority` IntEnum + DiscCard.
  review_priority + top_candidate added. `_sort_review`
  by (priority, -mtime); `_sort_capture` pins active rip,
  then damaged tier newest, then healthy newest. Capture
  bucket now walks failed/ + inbox/ at depth=1.
- `53a9d10` impl-logs-tail-endpoint — `GET /api/logs/tail`
  with limit clamping [1, 2000], `truncated` flag, 404 on
  missing log, accept-and-ignore future filter params.
  Reads `ARCHIVIST_LOG_PATH` env (falls back to daemon's
  log_path).
- `b6c17b0` impl-drive-status-endpoint — `GET /api/drive/status`
  reads `loop_state.drive_status` (populated by drivers'
  `impl-drive-status-snapshot`); default-idle when attribute
  is missing.
- `5b7ba8a` impl-{card-state-evolution, expand-mechanic,
  expanded-card-sections, collapsed-card-actions, header-bar,
  right-drawer, bottom-drawer, column-scroll-badges,
  mobile-bucket-tabs, adaptive-polling} — full
  `archivist/service/kanban_page.py` rewrite (705
  insertions / 88 deletions) + two new endpoints in app.py
  (`POST /api/disc/<folder>/accept-top-candidate`,
  `GET /api/disc/<folder>/log/tail`) + the `active_rip`
  field on `/api/kanban`. Ten task IDs landed together
  because they all render to the same HTML document.

Two sprint-6 tests updated in the kanban-page commit for the
contract evolution: `test_kanban_response_shape` now accepts the
new top-level `active_rip` field, and
`test_page_carries_poll_interval_meta_tag` accepts either the
legacy single `kanban-poll-ms` or the new adaptive pair
(`-active`/`-idle`).

The five OPEN decisions resolved during impl with full
rationale recorded in the Decision Log above:
- D-card-evolution-tokens — confirmed=`--ok` glow, asserted=dashed
  `--line`, damaged=`--meat-red` shadow; styled via `data-*`
  attributes so class-name absence assertions hold.
- D-default-sort-v1 — ReviewPriority `(PARTIAL=0, WEAK_MATCH=1,
  NO_MATCH=2, NO_ID_NO_TAGS=3)` + per-bucket tie-breakers.
- D-accept-top-candidate-threshold — `0.85`, enforced both client-
  and server-side.
- D-mobile-breakpoint-v1 — `max-width: 720px`.
- D-adaptive-polling-cadence — `1000ms` active / `5000ms` idle,
  meta-tag-driven so operators can re-tune without code changes.

Wave 3 queue: operator-driven `smoke-deploy-and-validate` on the
CM4. This also closes sprint-5's `musicbrainz_disc_id` real-rig
validation thread.

### 2026-05-16 — drivers — Wave 2 impl-drive-status-snapshot landed (1 task, 1 commit)

Single drivers Wave 2 task closed; landed early per the roster note
so pipeline can wire `impl-drive-status-endpoint` against it.

- **impl-drive-status-snapshot** (this commit) — new
  `archivist/state_machine/drive_status.py` with the `DriveStatus`
  dataclass (9 fields per the test contract + `lock:
  threading.RLock` factory, `repr=False, compare=False` so equality
  is data-only) and a `update_from_progress_line(ds, line)` parser
  that bumps `current_track` on `:outputting track N` (resets
  retries to 0 on track change), `sector_current` /
  `retries_on_current_track` on `scsi_read error:` lines, no-ops on
  unrelated lines. Mutations all wrap in `with ds.lock:`.
- LoopState (`archivist/service/app.py`): minimal additive touch —
  one new field
  `drive_status: DriveStatus = field(default_factory=DriveStatus)`
  + the `from archivist.state_machine.drive_status import
  DriveStatus` import. **Cross-agent note:** `service/app.py` is
  pipeline-owned per the roster but the field is a sibling of
  `rip_progress` / `last_tick_at` and required to satisfy the
  test contract; touch scope held to the one field + import.
- `archivist/state_machine/loop.py`: three update sites added.
  (1) `_set_state` calls a new `_sync_drive_status_for_transition`
  helper that maps the State enum to the 4-bucket `drive_status.
  state` and resets all transient fields on return-to-idle states
  (IDLE / WAITING / WAITING_REMOVE / ERROR). Active-cycle mapping:
  STABILIZE & STABILIZE_PARTIAL → "stabilizing"; RIP → "ripping";
  EJECT & CAPTURE → "capturing". (2) The rip's `_on_progress`
  callback fans the raw line into `update_from_progress_line` so
  sector/retry/track updates land live during the rip. (3)
  `_from_capture` and `_from_stabilize_partial` walk `photo_state`
  through `pending → capturing → done` via a new `_set_photo_state`
  helper (left at `capturing` on exception so the UI shows the
  partial state until the next idle reset).
- D-drive-status-snapshot-schema resolved: `threading.RLock` (not
  Lock, not atomic-swap), State→drive_status.state mapping table,
  photo_state lifecycle pinned in the Decision Log entry.

Verified: pytest tests/state_machine/test_drive_status.py → 13/13
PASS; full drivers + state-machine + pipeline + test_main_logging
suites → 218/218 PASS; ruff check clean on touched code (the
pre-existing F841 at loop.py:620 is sprint-4 era, not in this
task's slice). The 64 failures elsewhere in `pytest tests/` are
pipeline's in-flight Wave 2 reds under `tests/service/`.

Unblocks: pipeline's `impl-drive-status-endpoint` (reads from
`loop_state.drive_status` for `GET /api/drive/status`).

### 2026-05-16 — drivers — Wave 1 failing test landed (1 task, 1 commit)

Single drivers Wave 1 task closed.

- **test-drive-status-snapshot** (this commit) — new file
  `tests/state_machine/test_drive_status.py` with 13 failing tests
  for the not-yet-implemented
  `archivist.state_machine.drive_status` module + the
  `LoopState.drive_status` attribute (impl lands in
  `impl-drive-status-snapshot`). Locks in: (a) the 9-field
  DriveStatus dataclass shape + defaults (state="idle", everything
  else None) and typed-value acceptance; (b) `LoopState.drive_status`
  defaulting to a fresh DriveStatus per instance (`default_factory`,
  NOT a shared default); (c) the
  `update_from_progress_line(drive_status, line)` helper — bumps
  `current_track` on `:outputting track N`, sets `sector_current` +
  `retries_on_current_track` on `scsi_read error: sector=X retry=N`,
  resets retries on track change, no-ops on unrelated lines; (d)
  state-machine transitions: STABILIZE → `drive_status.state =
  "stabilizing"`, RIP → `"ripping"`, CAPTURE → photo_state walks
  pending → capturing → done; (e) IDLE reset zeroes all transient
  fields back to None; (f) thread-safety — DriveStatus exposes a
  context-manager `lock` attribute, and a smoke test runs 8 workers
  × 50 bumps and asserts the final accumulator equals 400 (no torn
  updates).

Test posture: reuses `_FakeDrive` / `_FakeRipper` / `_FakeCamera` /
`_FakeLED` / `_Clock` from `tests/state_machine/test_loop.py` via
package import (the established pattern from sprint-6's
test_cdplay_decoupled). State-machine tests construct a `LoopState`
and wire it into `ArchivistLoop` via the existing `loop_state=`
parameter — no constructor changes needed for the test scaffolding.
The transitional-state tests are lenient on mid-flight timing
(synchronous fake rip can advance through ripping → capturing →
idle in a single tick) to keep the contract on observable end-state
rather than tick-by-tick lockstep.

Verified: `pytest tests/state_machine/test_drive_status.py` →
13/13 FAIL with `ModuleNotFoundError: archivist.state_machine.
drive_status` (the test module imports the not-yet-existing
target lazily inside each case so collection itself stays clean).
`ruff check tests/state_machine/test_drive_status.py` clean.

Wave 2 queue: `impl-drive-status-snapshot` (single task, unblocks
pipeline's `/api/drive/status` endpoint). Per the agent-roster
note, drivers should land this early in Wave 2.

### 2026-05-16 — pipeline — Wave 1 failing tests landed (14 of 15)

- Shipped in 8 commits, several bundled per bucket:
  - `03dcaae` test-fix-phantom-audio
  - `b25046c` test-per-bucket-sort
  - `3d60d99` test-card-state-evolution
  - `09d9499` test-{expand-mechanic, header-bar, column-scroll-badges, adaptive-polling}
  - `de03535` test-expanded-card-sections
  - `11782dc` test-collapsed-card-actions
  - `4a952dd` test-{right-drawer, bottom-drawer, mobile-bucket-tabs}
  - `ec677e9` test-{logs-tail-endpoint, drive-status-endpoint}
- All 14 pipeline tests fail-as-expected (no impl yet, contracts pinned).
- Activity Log + checkbox ticks were applied retroactively by orc
  (agents shipped commits but didn't bookkeep the doc).

### 2026-05-16 — drivers — Wave 1 failing test landed (1 of 1)

- `5579c15` test-drive-status-snapshot.
- DriveStatus dataclass + LoopState attribute + ripper progress
  callback hooks + state-machine transition hooks + idle-reset +
  threading.Lock — all pinned in failing tests.
- Ready for pipeline's `/api/drive/status` impl to wire against.

### 2026-05-16 — planner — sprint-6.5 plan drafted

- Drafted from the K1 brainstorm at
  `~/.config/taw/wiki/Projects/cd-archivist/docs/brainstorming/sprint-6.5-kanban-usability.md`.
- Three resolved decisions from the brainstorm
  (D-pipeline-as-mental-model, D-card-state-evolution, D-no-alerts-v1)
  + six open decisions deferred to impl
  (D-card-evolution-tokens, D-default-sort-v1,
  D-accept-top-candidate-threshold, D-mobile-breakpoint-v1,
  D-adaptive-polling-cadence, D-drive-status-snapshot-schema).
- Six buckets (A: builder fixes; B: card UI evolution; C: layout
  shell; D: endpoints; E: adaptive polling; F: drivers DriveStatus).
  Wave 1 = 14 failing-test tasks; Wave 2 = 11 impl tasks; Wave 3 =
  1 operator-driven smoke that also closes sprint-5's
  disc-id real-rig validation thread.
- Heavy pipeline sprint; drivers has one task that unblocks
  pipeline's `/api/drive/status`. Drivers should land
  `impl-drive-status-snapshot` early.
