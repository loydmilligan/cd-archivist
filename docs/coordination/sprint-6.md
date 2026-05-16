---
project: cd-archivist
sprint: sprint-6
created: 2026-05-16T00:00:00.000Z
updated: 2026-05-16T00:00:00.000Z
status: draft
---

# cd-archivist — coordination doc (sprint-6)

> Strict template per Session O2=B / seed §12 Phase 8. The dashboard
> reads this as the canonical substrate (seed §3.7); orc emits
> `coord-doc-stale` cards when drift is detected (§3.8 / O7=A).
>
> Section headings are load-bearing — keep them as-is so the parser can
> find them. Section bodies are markdown-flexible.

## Plan Source

- Type: inline
- Path: this document (`## Active Sprint Plan` section)
- Active unit: sprint-6

## Sprint Goals

- **Replace the single-line status surface with a candidate-disc
  kanban.** Per `docs/design/2026-05-16-candidate-disc-kanban-status.md`.
  One card per disc, three columns (Capture → Beets ID → Review /
  Library), per-track bar (green / empty / red / blue) on every card,
  visuals (disc photo, cover art) where available, collapsed-by-default
  with expand-on-demand. This replaces `GET /`'s current text status.
- **Land first-class damaged-disc UI handling.** When a rip fails or is
  cancelled mid-flight, the card surfaces three explicit actions:
  (1) **process partial as-is** (route clean tracks through the rest
  of the pipeline with `source.json.status.partial=True`),
  (2) **redo entire capture** (discard + restart),
  (3) **pick tracks to (re-)rip** (checkbox list of every TOC track,
  pre-selected by success/failure state, merges new + existing flacs).
- **Engine-side fail-fast on damaged discs.** Stop cdparanoia after a
  configurable retry threshold instead of grinding for 25 min on
  unreadable sectors. Preserve partial flacs to disk for the
  damaged-disc UI to pick up.
- **Remove the `cdplay.service` dependency.** The state machine's
  `systemctl start/stop cdplay.service` calls fire `exit 5` warnings
  on every rip on the production CM4. Strip them; the eject path
  uses `eject /dev/sr0` directly. No deployment artifact owed.
- **Preserve the music-pipeline contract.** Additive only.
  `source.json` gains `status.partial`, `status.failed_tracks`, and
  per-track provenance; existing fields untouched. `READY` / `FAILED` /
  `PROCESSING` semantics unchanged.
- **TDD discipline preserved.** Wave 1 = failing tests
  (parallel-safe); Wave 2 = impls (depends-gated). No Wave 0 operator
  setup (sprint-6 is all in-repo). No Wave 3 pytest — operator-driven
  smoke against the dogfood rig per the sprint-4 / sprint-5 cadence.

> **Scope-hierarchy reminder.** The kanban surface is the load-bearing
> scope. Without it, every weak-match or damaged disc still requires
> an ssh session to debug. The damaged-disc UI is the highest-leverage
> use case (sprint-5 surfaced two RATM failures in one afternoon).
> Engine-side fail-fast is the substrate that makes the UI's "stop
> and salvage" action work without 25-minute waits. The
> `cdplay.service` decouple is small but it removes recurring log
> noise and unblocks the eject path's reliability.

## Active Initiatives

- _None — sprint-6 plan below is the substrate._

## Active Sprint Plan

<!-- What ships in sprint-7+ (out of scope here):
     - In-UI beets candidate selection (v2 of the Review screen — see
       sprint-5 Sprint-6 Candidates note on beets-CLI traceback-spam).
       Sprint-6 ships Review v1: list + "why in review" + manual
       instructions only.
     - Live cam preview / animated disc-photo capture.
     - Server-Sent Events / WebSocket live transport (sprint-6 uses
       polling at 2s; SSE deferred unless polling proves insufficient).
     - Editable per-track metadata in the kanban card (rename titles by
       hand). v1 surfaces what beets resolved; doesn't let you edit.
     - Acoustid fingerprint SUBMISSION (we lookup, we don't contribute).
     - Multi-drive support — single /dev/sr0 only. -->

### Wave 1 — Failing tests (parallel-safe)

#### Bucket A — Engine-side fail-fast + partial preservation (drivers)

- [ ] {agent: drivers, id: test-fail-fast-detection}
  Failing tests for cdparanoia retry-threshold detection.
  `tests/drivers/test_ripper_failfast.py`:
  (a) feed a synthetic stderr stream with N retries on the same sector
  → ripper aborts within K seconds of crossing the threshold;
  (b) sense codes matching "Target hardware fault" trigger immediate
  abort regardless of retry count;
  (c) clean rip (no sector errors) completes without triggering abort.
  Default threshold proposal: 3 retries on a single sector OR any
  ASC=3e (Target hardware fault) sense code — agent picks final
  numbers during impl and documents in `D-failfast-threshold`.

- [ ] {agent: drivers, id: test-partial-output-preserve}
  Failing tests for partial-rip preservation.
  `tests/drivers/test_ripper_partial.py`: when fail-fast aborts at
  track N, the previously-successful tracks 1..N-1 are NOT deleted;
  `RipResult` returns `RipStatus.PARTIAL` with `successful_tracks:
  list[int]` and `failed_track: int | None` populated. `_RipResult`
  schema gains a `partial` boolean. Existing happy-path tests still
  pass with `RipStatus.SUCCESS` and the new fields defaulted.

#### Bucket B — Kanban surface (pipeline)

- [ ] {agent: pipeline, id: test-disc-card-builder}
  Failing tests for the disc-card data builder.
  `tests/service/test_disc_card_builder.py`:
  (a) walking a fixture `/srv/music/{review,library,archive}/`
  directory tree produces one `DiscCard` per disc folder with the
  correct bucket assignment (review-folder → Review bucket;
  library album → In Library bucket; archive folder → also In
  Library bucket with `archived: True`);
  (b) per-card fields derived from `source.json` populate correctly
  (track_count, photo_path, disc-id, rip start/end timestamps);
  (c) when an active `LoopState` overlay is provided, the
  currently-ripping disc appears as a Capture-bucket card with the
  in-flight per-track state; (d) per-track bar state map
  ({success, fail, in_progress, pending} → {green, red, blue, empty})
  renders correctly from a synthetic `Cycle` state.

- [ ] {agent: pipeline, id: test-kanban-api}
  Failing tests for `GET /api/kanban`.
  `tests/service/test_kanban_endpoint.py`: response shape is
  `{ buckets: { capture: [DiscCard], beets_id: [DiscCard],
  review: [DiscCard], library: [DiscCard] } }`; library bucket is
  capped at the configurable retention (default 20 newest); the
  endpoint returns 200 with an empty buckets payload when no discs
  exist; the in-progress disc lands in `capture` with `progress:
  {percent, current_stage}`.

- [ ] {agent: pipeline, id: test-kanban-page-render}
  Failing tests for the kanban HTML page at `GET /`.
  `tests/service/test_kanban_page.py`: page renders 4 column
  headers (Capture, Beets ID, Review, In Library); cards render
  with collapsed-state markup (status line + progress bar +
  per-track bar); cards have an `aria-expanded` toggle attribute;
  the page polls `/api/kanban` (poll interval lands in a `<meta
  name="kanban-poll-ms">` tag for test assertion); Mash Co.
  tokens applied (`--ink`, `--ok`, `--warn`, `--info`).

#### Bucket C — Damaged-disc UI actions (pipeline)

- [ ] {agent: pipeline, id: test-damaged-card-actions}
  Failing tests for the three damaged-disc actions on a Capture
  card whose rip aborted with `RipStatus.PARTIAL`.
  `tests/service/test_damaged_disc_endpoints.py`:
  (a) `POST /api/disc/<folder>/process-partial` — moves the disc
  folder out of `.ripping/` into `inbox/` with `READY` marker,
  updates `source.json` with `status.partial=True` +
  `status.failed_tracks` + per-track `provenance.attempt_id`,
  triggers the normal post-rip hook;
  (b) `POST /api/disc/<folder>/redo` — deletes the partial
  folder, the next disc insert starts fresh;
  (c) `POST /api/disc/<folder>/rerip-tracks` body =
  `{tracks: [int]}` — validates track numbers against the TOC,
  invokes a `partial_rerip(device, track_indices)` driver call,
  merges resulting flacs with existing successful ones,
  appends provenance entries.

- [ ] {agent: pipeline, id: test-review-page-explainer}
  Failing tests for the Review v1 screen at `GET /review`.
  `tests/service/test_review_page_v1.py`: each card in the
  review-folder list shows a "why in review" explanation derived
  from `source.json` + the beets-import log
  (e.g. "beets returned no candidates", "AcoustID empty match
  + tag-less flacs", "weak match: top score 0.28 below
  threshold"); each card has a "manual steps" expandable section
  with the literal shell commands the operator would run
  (`docker exec -it cd_beets beet import --search-id <MBID>
  /review/<folder>` etc.); no interactive controls in v1.

#### Bucket D — cdplay.service decouple (drivers)

- [ ] {agent: drivers, id: test-cdplay-removed}
  Failing tests confirming the state machine no longer calls
  `systemctl start/stop cdplay.service`.
  `tests/state_machine/test_cdplay_decoupled.py`: spy on the
  `systemctl` driver during a full rip cycle and assert no
  `cdplay.service` invocations occur; eject still fires via the
  ejector driver. The driver-level systemctl wrapper itself is
  not removed (other future units may want it) — only the
  `cdplay.service` references go.

### Wave 2 — Implementations

#### Bucket A — Engine-side fail-fast + partial preservation (drivers)

- [ ] {agent: drivers, depends: test-fail-fast-detection, id: impl-fail-fast-detection}
  Implement retry-threshold detection in
  `archivist/drivers/ripper.py`. Watch cdparanoia stderr for
  `scsi_read error: sector=X length=Y retry=N` lines; when N
  exceeds the configured threshold on the same sector, send
  SIGTERM to the cdparanoia subprocess. Also abort on
  `ASC=3e ASCQ=2` (Target hardware fault). Default threshold:
  3 retries, configurable via env
  `ARCHIVIST_RIP_RETRY_THRESHOLD`. Document threshold + rationale
  in a new decision-log entry `D-failfast-threshold`.

- [ ] {agent: drivers, depends: test-partial-output-preserve, id: impl-partial-output-preserve}
  Implement partial preservation. After fail-fast abort:
  (1) successfully-completed flacs stay in the working dir;
  (2) the `_RipResult` returned has
  `status=RipStatus.PARTIAL`,
  `successful_tracks=[1..N-1]`,
  `failed_track=N`,
  `partial=True`;
  (3) the state machine routes a partial-rip cycle into a new
  pseudo-state `STABILIZE_PARTIAL` that captures the photo
  (same as success) and writes `source.json` with
  `status.rip_success=False`, `status.partial=True`,
  `status.failed_tracks=[N, N+1, ...]` (mark N and everything
  after as failed since we never reached them);
  (4) folder is moved into `failed/` instead of being deleted,
  preserving the partial flacs + rip.log + source.json + photo.

#### Bucket B — Kanban surface (pipeline)

- [ ] {agent: pipeline, depends: test-disc-card-builder, id: impl-disc-card-builder}
  Implement `archivist/service/disc_card_builder.py::
  build_kanban_state(music_root: Path, loop_state: LoopState | None)
  -> KanbanState`. Walks
  `{music_root}/{inbox,review,library,archive,failed}/` for
  terminal-state cards; layers `loop_state.cycle` if present
  for the active rip. `DiscCard` model:
  `{folder, bucket, source_json: dict | None, photo_path: str |
  None, track_bar: list[TrackState], progress: Progress | None,
  archived: bool, partial: bool, failed_tracks: list[int]}`.

- [ ] {agent: pipeline, depends: test-kanban-api, id: impl-kanban-api}
  Add `GET /api/kanban` to `archivist/service/app.py`. Calls
  `build_kanban_state`, returns JSON. Library bucket capped at
  `KANBAN_LIBRARY_RETENTION` env (default 20, newest first).
  Backward-compat: keep `GET /api/status` returning the old
  payload for any consumers; new endpoint is additive.

- [ ] {agent: pipeline, depends: test-kanban-page-render, id: impl-kanban-page}
  Replace `GET /`'s single-line HTML with the kanban page.
  Four column layout, Mash Co. tokens (`--ink` for default text,
  `--info` for capture, `--ok` for success states, `--warn` for
  review, `--meat-red` accent for partial/failed). Cards
  collapse by default; expand reveals the full `source.json`
  + rip.log tail + (for Review-bucket cards) the "why" explainer.
  Polling: every 2 seconds, page fetches `/api/kanban` and
  diff-updates the DOM. Poll interval in `<meta
  name="kanban-poll-ms" content="2000">` for testability.
  Per-track bar: a flexbox row of `<span class="track-cell
  track-cell--{state}">` segments, one per track.

#### Bucket C — Damaged-disc UI actions (pipeline)

- [ ] {agent: pipeline, depends: test-damaged-card-actions, id: impl-damaged-disc-actions}
  Three endpoints + the corresponding card UI controls:
  - `POST /api/disc/<folder>/process-partial` — moves
    `failed/<folder>/` to `inbox/<folder>/`, writes `READY`,
    updates `source.json` per the test spec, triggers
    `process-ready-auto` via the existing hook.
  - `POST /api/disc/<folder>/redo` — deletes `failed/<folder>/`
    after a confirmation flag (`?confirm=true`); no auto-rip
    starts (operator manually re-inserts disc).
  - `POST /api/disc/<folder>/rerip-tracks` — body
    `{tracks: [int]}`. Validates against the TOC stored in
    `source.json` (or freshly read via `libdiscid` if absent).
    Calls a new driver primitive
    `archivist/drivers/ripper.py::partial_rerip(device,
    track_indices) -> _RipResult`; the impl uses
    `cdparanoia -B <range> -d <device> -- <out>/` with the
    range translated from `track_indices`. Result flacs are
    merged into the existing `audio/` dir; per-track
    provenance entries appended to `source.json` with a new
    `attempt_id` (UUID).

  Card UI: in the damaged-state card body (expanded), render
  three buttons + a `<details>` block containing the per-track
  checkbox list (one checkbox per TOC track, pre-checked for
  failed tracks). The "pick tracks" button submits the form.

- [ ] {agent: pipeline, depends: test-review-page-explainer, id: impl-review-page-v1}
  Implement the Review v1 screen at `GET /review` (replaces or
  augments the current `/review` list). Each card has:
  - **Why in review** — derived from
    `archivist/service/review_explainer.py::explain(folder) ->
    str`. Sources: `source.json.status.beets_review_reason` (if
    populated by post-hook), tail of `beets-import.log` for the
    folder, presence/absence of `musicbrainz_disc_id`,
    AcoustID match score (cached from chroma if available).
  - **Manual steps** — a `<details>` block with copy-paste
    shell commands the operator can run on the CM4. Generated
    from a template per failure mode.
  - **Links** — disc photo, the folder path, a "open in beets
    web UI" link to `http://cm4:8337/`.

#### Bucket D — cdplay.service decouple (drivers)

- [ ] {agent: drivers, depends: test-cdplay-removed, id: impl-cdplay-decouple}
  Remove the `systemctl start cdplay.service` /
  `systemctl stop cdplay.service` calls from
  `archivist/state_machine/loop.py`. The eject path uses the
  existing ejector driver (`eject /dev/sr0` or whatever it
  currently shells to). The `systemctl` wrapper itself stays
  (other future units may use it). Document the decision in
  `D-cdplay-decouple-not-install`.

## Agent Roster

| Agent | Owns | Does not touch |
|---|---|---|
| drivers | `archivist/drivers/{ripper,disc_id,led,camera,systemctl,usb_discovery,rip_log,drive,ejector}.py`, `archivist/models/manifest.py`, `archivist/models/source.py` (failed-tracks additions only), `archivist/state_machine/loop.py` (cdplay-decouple + STABILIZE_PARTIAL routing only), `tests/drivers/`, `tests/state_machine/test_cdplay_decoupled.py` | `archivist/service/`, `archivist/pipeline/`, all UI surfaces |
| pipeline | `archivist/service/` (incl. new `disc_card_builder.py`, `review_explainer.py`, new `/api/kanban`, `/api/disc/*` routes, kanban HTML, Review v1 page), `archivist/pipeline/source_json.py` (provenance + partial fields), `tests/service/`, `tests/pipeline/test_source_json_builder.py` (provenance additions), `pyproject.toml`, `ruff.toml`, `docs/coordination/sprint-6.md` | `archivist/drivers/` internals (consumes their public interfaces) |

Roster carries forward from sprint-5 with two scope notes:
- drivers touches `archivist/state_machine/loop.py` for the
  STABILIZE_PARTIAL state and the cdplay-decouple. Pipeline must NOT
  edit the state machine in this sprint to avoid merge conflicts.
- pipeline touches `archivist/models/source.py` only for the
  provenance + partial fields; the driver-side additions (failed
  tracks counter, etc.) belong to drivers.

## Decision Log

> Architecture decisions to ratify at planning. Resolved decisions move
> to the top of the log; open decisions stay at the bottom with **OPEN**.

### 2026-05-16 — D-card-data-source — disk-derived for terminal cards + LoopState overlay for active rip

Selected during sprint-6 planning. The kanban derives Review/Library/
Archive cards from walking the music root directories; the
currently-active rip is layered on top from `LoopState`. Rejected
alternatives: (a) refactor `LoopState` into a persisted multi-disc
list — too large a state-machine touch for sprint-6; (b) in-memory
rolling list of last N disc states — loses history on restart and
introduces a separate truth source from disk. The disk-derived
approach inherently shows history, requires no state-machine
changes, and only needs LoopState for live-rip progress.

### 2026-05-16 — D-cdplay-decouple-not-install — remove the dependency rather than install a stub unit

Selected during sprint-6 planning. The state machine's
`systemctl start/stop cdplay.service` calls fire `exit 5` warnings on
every rip on the production CM4 and contribute to the broken eject
path. Rejected alternatives: (a) install a stub
`cdplay.service` user unit — adds a deployment artifact for no
runtime benefit; (b) both decouple + install — over-engineered for a
non-existent playback feature. Future playback features can re-add a
dedicated service when actually needed.

### 2026-05-16 — D-kanban-buckets-v1 — three primary buckets + Library, no separate "Damaged" bucket

Selected during sprint-6 planning (kanban brief Q1 + Q3 resolved
together). The kanban has **four** columns: Capture, Beets ID,
Review, In Library. There is no intermediate "Tagging" or
"Awaiting confirm" bucket — beets-ID is the gate, and resolved discs
move directly to Library or Review. Failed/damaged discs stay in
the Capture bucket with a red state until the operator picks an
action (process-partial / redo / pick-tracks). Rationale: simpler
mental model; fewer state transitions; the per-track bar already
carries the "this is damaged" signal.

### 2026-05-16 — D-library-retention-v1 — last 20 newest-first

Selected during sprint-6 planning (kanban brief Q2). The Library
bucket shows the 20 most-recent successful imports (combined
`/srv/music/library/` + `/srv/music/archive/`), newest first.
Configurable via `KANBAN_LIBRARY_RETENTION` env. Rejected: infinite
scroll (premature for v1), time-window-based (operationally less
predictable). Sprint-7+ can add filter / search / pagination if
warranted.

### 2026-05-16 — D-live-update-transport-v1 — polling at 2s

Selected during sprint-6 planning (kanban brief Q4). The kanban
page polls `/api/kanban` every 2000ms. Rejected: Server-Sent Events
(adds a new transport channel + middleware; defer until polling
proves insufficient under real load). Interval lives in a `<meta
name="kanban-poll-ms">` tag so it can be tuned without code changes
and asserted in tests.

### 2026-05-16 — D-failfast-threshold — **OPEN** (drivers picks during impl)

Open decision. The fail-fast threshold (default proposal: 3 retries
on a single sector OR any Target hardware fault sense code) gets
finalized during `impl-fail-fast-detection` and documented here.
Test spec is parameterized; drivers picks the exact numbers.

### 2026-05-16 — D-source-json-provenance-schema — **OPEN** (pipeline drafts during impl)

Open decision. The exact shape of per-track provenance in
`source.json` (one `attempt_id` per rip attempt, plus a
`tracks[].provenance` array? or a flat `provenance: [{attempt_id,
tracks: [int], started_at, ended_at}]` log?) gets settled by
pipeline during `impl-disc-card-builder` and recorded here. Either
way the data must let the kanban show "track 6 came from attempt 2"
when expanded.

## Ratification Log

> User-ratified decisions. Format: `### {{date}} — {{decision-id}} — {{summary}}`.

- _None yet._

## Contract Changes

> Additive-only changes to `source.json` / API. Breaking changes go in
> a Decision Log entry first.

### 2026-05-16 — `source.json.status.partial: bool` + `source.json.status.failed_tracks: list[int]`

Two new fields under `status`, both optional with safe defaults
(`partial: false`, `failed_tracks: []`). Populated by drivers'
`impl-partial-output-preserve` when a rip aborts mid-flight. Existing
consumers see no change when `partial=False`.

### 2026-05-16 — `source.json.provenance: list[ProvenanceEntry]` — **shape TBD via D-source-json-provenance-schema**

Optional. Records each rip attempt's `attempt_id`, the track indices
it produced, and the start/end timestamps. Populated by `partial_rerip`
calls. Absent on disks that ripped successfully on the first pass.

### 2026-05-16 — new endpoints

- `GET /api/kanban` — kanban state for the UI.
- `POST /api/disc/<folder>/process-partial` — accept partial rip.
- `POST /api/disc/<folder>/redo` — discard partial rip.
- `POST /api/disc/<folder>/rerip-tracks` — re-rip selected tracks.

`GET /api/status` remains for backward compatibility. `GET /`'s
response body changes from text status to the kanban HTML page.

## Blockers

<!-- One bullet per active blocker. Format:
     `- [<agent>] <one-line blocker> — <link or reference>`. Resolved
     blockers move to the Activity Log. -->

- _None._

## Sprint-7 Candidates

<!-- Items captured during sprint-6 that should be picked up at
sprint-7 planning. -->

- **In-UI beets candidate selection (Review v2).** Web wrapper for
  beets candidate selection — picks an MBID and triggers
  `beet import --search-id`. Existing substrate at `/api/review/*`
  (sprint-5) needs to be wired into the kanban Review bucket. Blocked
  by sprint-5's "beets interactive traceback-spam on tag-less flacs"
  finding; must fix that first (or bypass beets' interactive path
  entirely and use `musicbrainzngs` direct).
- **Empty-tag MB-fallback suppression.** Configure or patch beets so
  that when source flacs have no embedded tags, beets does NOT fall
  back to a metadata search with `query=&` (which 400s). Either a
  beets config knob or a small plugin.
- **Editable per-track metadata in the kanban card.** Sprint-6 lets
  the operator pick which tracks to re-rip; sprint-7 lets them
  rename a track title by hand if beets got it slightly wrong.
- **SSE live transport.** Replace 2s polling with Server-Sent Events
  if polling proves expensive or laggy on the CM4 under multi-disc
  load.

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

### 2026-05-16 — planner — sprint-6 plan drafted

- Drafted from `docs/design/2026-05-16-candidate-disc-kanban-status.md`
  + sprint-5's Sprint-6 Candidates section.
- Five architecture decisions resolved at planning time
  (D-card-data-source, D-cdplay-decouple-not-install,
  D-kanban-buckets-v1, D-library-retention-v1,
  D-live-update-transport-v1). Two open decisions deferred to impl
  (D-failfast-threshold, D-source-json-provenance-schema).
- Four buckets (A: drivers fail-fast + partial; B: pipeline kanban
  surface; C: pipeline damaged-disc UI + Review v1; D: drivers
  cdplay decouple). Wave 1 = 6 failing-test tasks; Wave 2 = 6
  impl tasks. No Wave 0 — sprint-6 is all in-repo.
