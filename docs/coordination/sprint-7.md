---
project: cd-archivist
sprint: sprint-7
created: 2026-05-16T00:00:00.000Z
updated: 2026-05-16T00:00:00.000Z
status: draft
---

# cd-archivist — coordination doc (sprint-7)

> Strict template per Session O2=B / seed §12 Phase 8. The dashboard
> reads this as the canonical substrate (seed §3.7); orc emits
> `coord-doc-stale` cards when drift is detected (§3.8 / O7=A).
>
> Section headings are load-bearing — keep them as-is so the parser can
> find them. Section bodies are markdown-flexible.

## Plan Source

- Type: inline
- Path: this document (`## Active Sprint Plan` section)
- Active unit: sprint-7
- Upstream design handoff:
  `docs/mashco-design-system-handoff/cd-archivist/handoff/Build prompt.md`

## Sprint Goals

- **Wire in the Mash Co. design system.** Vendor `colors_and_type.css`
  → `static/css/tokens.css` and `cda-styles.css` → `static/css/cda.css`.
  Add a FastAPI static mount. Load Bricolage Grotesque + Inter Tight +
  JetBrains Mono via Google Fonts. Wire the full favicon family + PWA
  manifest + apple-touch icon.
- **Build the `cd/a` brand mark.** The chunky-extruded recipe from the
  build prompt (NOT a flat italic). Three size variants (header / splash
  / marketing). Replace the current text wordmark.
- **Migrate the kanban CSS** off the inline `<style>` block in
  `kanban_page.py` and onto the imported `tokens.css` + `cda.css`. The
  only allowed inline CSS in shipped templates is the
  CSS-custom-property-as-data pattern
  (`style="--progress: 65%"`, `style="--track-count: 13"`) — used for
  dynamic per-element values the stylesheet consumes via `var()`.
- **Refactor card anatomy to the spec.** Header row (56×56 thumbnail +
  slug eyebrow + title + artist line); status line in mono with the
  specific format (`ripping track 7 · sector 24,318 · 1 retry · 04:12
  elapsed`); chip row; per-column left-border accent (3px pulp
  ripping / 4px ember damaged / 3px sky beets-id / 3px amber-or-ember
  review / 3px moss library); track-segment colors mapped to specific
  tokens (`--moss / --sky / --ember / --ink-3`) + 1px white inset 2px
  outline when identified.
- **Build the Beets-candidates section.** New
  `GET /api/disc/<folder>/candidates` endpoint backed by
  `archivist/service/mb_client.py` (sprint-5
  `D-mb-query-direct-not-beets`). Expanded-card-body section renders up
  to 5 ranked candidates: score chip · release + MBID · "Apply"
  button. Top candidate has amber-tinted background. Apply POSTs to
  the existing `/api/disc/<folder>/accept-top-candidate` with the
  picked MBID.
- **New layout details.** 8px column headlamp dots; live-status chip
  in header (pulsing green dot + "ripping · DISC-XXXX" when active,
  "idle" treatment otherwise); 5-cell rig-stats group (Ripped · In
  review · Partial · Storage · Uptime) in a bordered group;
  CSS-drawn disc-photo placeholder (conic-gradient glow); source.json
  syntax highlight in drawer card-detail mode (`pre.cda-json` +
  inline `.k/.s/.n/.b` spans); drawer mode toggles in header nav.
- **Destructive-action confirmation gate + transitions.** Second-click
  confirms redo / rerip / skip / delete with the spec's hint text.
  Cards entering a new column fade in (200ms `--ease-out`); cards
  leaving fade out then remove. Track segments fill smoothly. "Live
  updating" elements flash a 200ms moss-border then fade.
- **Targeted voice pass.** Sentence case in source (eyebrows are
  CSS-uppercased), no emoji, project vocabulary, specific error states.
  Targeted scope per K1 brainstorm follow-up: status lines, error
  messages, button labels. Full sweep deferred to sprint-8.
- **Preserve the music-pipeline contract.** Additive only. No
  `source.json` schema changes this sprint. No state-machine touches.
- **Three-lane parallel execution.** Two existing agent panes
  (drivers, pipeline) plus a third Claude Code session in pane %28
  for this sprint. Sprint-7 is entirely pipeline-domain work
  (UI + service surface); the drivers + pane-2 agents take pipeline
  tasks for the sprint. Brief each agent that they are "pipeline-lane
  agent N" for sprint-7 only.
- **TDD discipline preserved.** Wave 1 = failing tests
  (parallel-safe); Wave 2 = impls (depends-gated). No Wave 0. Wave 3
  = operator-driven visual smoke against `cda.mattmariani.com`.

> **Scope-hierarchy reminder.** Bucket A (asset wire-up) is the
> foundation everything else depends on — it MUST land first. Bucket B
> (CSS migration + brand mark) re-skins the page and unblocks every
> visual task. Buckets C (card anatomy), D (beets candidates), E
> (layout details) are the load-bearing visual work, parallel-safe
> after A/B. Bucket F (gates + transitions) is polish. Bucket G
> (targeted voice pass) is touch-up.

## Active Initiatives

- _None — sprint-7 plan below is the substrate._

## Active Sprint Plan

<!-- What ships in sprint-8+ (out of scope here):
     - Full voice pass — every visible string reviewed against the design-system
       voice rules. Sprint-7 does targeted; sprint-8 does the sweep.
     - Tail-log filter UI (per-rip, per-card query params on /api/logs/tail).
     - Force-re-run beets ID action.
     - Edit-by-hand metadata in library cards.
     - Sort/filter controls per column.
     - Cache build_kanban_state disk-walk with filesystem-event invalidation.
     - Alert / notification strip in header.
     - Wire operator_hints into beets search (carried from sprint-6).
     - Empty-tag MB-fallback suppression in beets.
     - Light-mode theme (status quo dark per K1.9).
     - Multi-drive support, containerized cd-archivist itself,
       live cam preview, AcoustID submission.
     - Full sprint-6.5 carry-over: cdplay.service install (still missing,
       still firing exit-5 warnings every rip; non-blocking). -->

### Wave 1 — Failing tests (parallel-safe)

#### Bucket A — Asset wire-up (lane-1)

- [x] {agent: lane-1, id: test-static-mount}
  Failing tests for FastAPI static file mounting.
  `tests/service/test_static_mount.py`: (a) `GET /static/css/tokens.css`
  returns 200 with `text/css`; (b) `GET /static/css/cda.css` returns 200;
  (c) `GET /static/img/brand/cd-a-favicon-32x32.png` returns 200 with
  `image/png`; (d) `GET /static/manifest.webmanifest` returns 200 with
  `application/manifest+json`; (e) the kanban HTML emits the four
  favicon `<link>` tags + apple-touch + manifest + theme-color meta per
  the build prompt's snippet; (f) the kanban HTML loads
  `tokens.css` BEFORE `cda.css` in the `<head>`.

- [x] {agent: lane-1, id: test-font-loading}
  Failing tests for Google Fonts loading.
  `tests/service/test_font_loading.py`: (a) the page `<head>` includes
  the Google Fonts preconnect + stylesheet `<link>` for Bricolage
  Grotesque (weights 600 + 800) + Inter Tight (400 + 500 + 700) +
  JetBrains Mono (400 + 500); (b) tokens.css imports the same families;
  (c) NO system-font fallback `<style>` overrides exist that would
  bypass the brand fonts.

#### Bucket B — CSS migration + brand mark (lane-1)

- [x] {agent: lane-1, id: test-inline-css-removed}
  Failing tests asserting the inline `<style>` block is gone from
  `kanban_page.py`. `tests/service/test_kanban_page.py` additions:
  (a) the rendered page has at most one `<style>` element AND that
  element contains only the CSS-custom-property-as-data pattern
  comments (or none); (b) every CSS class used in the rendered markup
  resolves against either `tokens.css` or `cda.css` (asserted by
  grepping the static files for each class name extracted from the
  rendered HTML); (c) the only `style="..."` attributes in the
  rendered output use the `--<name>: <value>` custom-property pattern
  (no direct `width:` / `color:` / `display:` etc.).

- [x] {agent: lane-1, id: test-brand-mark}
  Failing tests for the `cd/a` brand mark.
  `tests/service/test_brand_mark.py`: (a) the header renders a
  `<span class="cda-brand-mark">cd/a</span>` element; (b) `cda.css`
  defines `.cda-brand-mark` with `font-family: var(--font-display)`,
  `font-weight: 800`, `font-style: italic`, `letter-spacing: -0.05em`,
  `color: var(--mash-pulp)`, `-webkit-text-stroke`, `paint-order:
  stroke fill`, and a multi-layer `text-shadow` extrude per the
  build prompt's recipe; (c) the size variants
  `.cda-brand-mark--header` (22px) exists; the splash and marketing
  variants exist in CSS as `--splash` (84px) and `--marketing`
  (240px) but are not required to be used in the kanban page.

#### Bucket C — Card anatomy refactor (lane-2 / pipeline)

- [x] {agent: lane-2, id: test-card-header-row}
  Failing tests for the new card header row.
  `tests/service/test_card_anatomy.py`: (a) each card renders a
  `.card-head` element containing a 56×56 `.thumb` (either
  `<img class="thumb">` with `src` OR a `<div class="thumb
  thumb--placeholder">` when no photo), a `.slug` eyebrow with the
  disc folder slug, a `.title` line with the album title or folder
  name fallback, and a `.artist` line; (b) the order is
  thumbnail-left then text-block-right; (c) the slug uses
  `font-family: var(--font-mono)` per `cda.css`.

- [x] {agent: lane-2, id: test-status-line}
  Failing tests for the status line format.
  `tests/service/test_card_anatomy.py` additions:
  (a) cards in Capture-active state render a status line like
  `ripping track 7 · sector 24,318 · 1 retry · 04:12 elapsed`
  (mono, dot-separator, lowercase verbs);
  (b) cards in Review render
  `weak match · beets returned 0.42` or
  `no match · 13 tracks · no embedded tags`;
  (c) cards in Library render
  `stored · matched 0.97 · imported 2026-05-16 13:18`;
  (d) cards in Capture-damaged render
  `halted · 3 unrecoverable sectors · track 6`;
  (e) the status line uses `.cda-status` class which `cda.css`
  styles `font-family: var(--font-mono); color: var(--ink-7); font-size:
  12px;`.

- [x] {agent: lane-2, id: test-chip-row}
  Failing tests for the chip row.
  `tests/service/test_card_anatomy.py` additions:
  (a) `.chip-row` element holds 0–4 chips depending on card state;
  (b) chips for VA / BURNED / MIX / WEAK MATCH · 0.42 /
  MUSICBRAINZ · 0.97 are emitted in the right cases;
  (c) operator-asserted chips have `.chip--asserted` class
  (dashed border via `cda.css`); system-confirmed chips have
  `.chip--confirmed` class (solid + halo); (d) the per-card
  left-border accent matches the column AND state per the build
  prompt's table — assert via class names like
  `.card--accent-pulp`, `.card--accent-pulp-ripping`,
  `.card--accent-ember-damaged`, `.card--accent-sky`,
  `.card--accent-amber`, `.card--accent-ember`,
  `.card--accent-moss`.

- [x] {agent: lane-2, id: test-track-segments}
  Failing tests for track-segment rendering.
  `tests/service/test_card_anatomy.py` additions:
  (a) `.track-bar` element with `style="--track-count: N"` where N
  is the disc's track count; (b) one `.track-cell` per track with
  state class `--clean` / `--recovered` / `--unrecoverable` /
  `--pending` / `--ripping`; (c) when `--ripping`, the cell also
  has `style="--progress: X%"` for the in-flight progress fill;
  (d) when a track is identified (post-Beets-ID), the cell has
  `.track-cell--identified` class which `cda.css` styles with
  `box-shadow: inset 0 0 0 1px rgba(255,255,255,0.85)`.

#### Bucket D — Beets candidates (lane-3)

- [x] {agent: lane-3, id: test-candidates-endpoint}
  Failing tests for `GET /api/disc/<folder>/candidates`.
  `tests/service/test_candidates_endpoint.py`:
  (a) response shape is `{"candidates": [{"mbid": str, "score":
  float, "artist": str, "title": str, "year": int|null,
  "track_count": int|null, "country": str|null}], "source":
  "musicbrainzngs"}`;
  (b) returns up to 5 candidates, sorted by score descending;
  (c) when `source.json.identifiers.musicbrainz_disc_id` is
  populated, the endpoint runs a disc-id lookup first and
  prepends that hit at score 1.0;
  (d) when only AcoustID fingerprints exist, the endpoint runs
  `mb_client.search_by_fingerprint`;
  (e) when neither exists AND `operator_hints.artist` /
  `operator_hints.album` are populated, runs a
  metadata search;
  (f) 404 when the disc folder does not exist;
  (g) 503 with `{"error": "musicbrainz unavailable"}` on
  network failure (mockable).

- [x] {agent: lane-3, id: test-candidates-section-ui}
  Failing tests for the candidates UI inside the expanded card body.
  `tests/service/test_expanded_card.py` additions:
  (a) the candidates section renders only when the candidates
  endpoint returns a non-empty list (asserted via async fetch in
  the page's JS — test asserts the JS source contains the
  conditional render guard);
  (b) up to 5 candidate rows render, each with a `.score-chip`
  (left), `.candidate-meta` (middle with release + MBID), and an
  `.apply-btn` (right);
  (c) the top candidate row has class `.candidate--top` (which
  `cda.css` styles with an amber-tinted background);
  (d) Apply button has `data-mbid="<the-mbid>"` and POSTs to
  `/api/disc/<folder>/accept-top-candidate` with body `{mbid:
  data-mbid}` — assert via JS source content.

#### Bucket E — New layout details (split: lane-1, lane-2, lane-3)

- [x] {agent: lane-1, id: test-column-headlamps}
  Failing tests for the 8px stage headlamp dots.
  `tests/service/test_kanban_page.py` additions:
  (a) each column header has a `.headlamp` element with class
  `.headlamp--pulp` (Capture), `.headlamp--sky` (Beets ID),
  `.headlamp--amber` (Review), `.headlamp--moss` (In library);
  (b) `cda.css` styles `.headlamp` as `width: 8px; height: 8px;
  border-radius: 50%; background: var(--mash-pulp)` (etc per
  modifier); (c) headlamp colors do NOT render as full column
  background tints.

- [x] {agent: lane-2, id: test-live-status-chip}
  Failing tests for the header live-status chip.
  `tests/service/test_kanban_page.py` additions:
  (a) the header renders a `.live-status` element with a `.dot`
  child and text content;
  (b) when active rip in flight, text reads
  `ripping · DISC-<slug>` and the dot has class
  `.dot--pulse-moss`;
  (c) when idle, text reads `idle` and the dot has class
  `.dot--quiet`;
  (d) `cda.css` defines a `@keyframes pulse` used by
  `.dot--pulse-moss` with `var(--moss)`.

- [x] {agent: lane-2, id: test-rig-stats-group}
  Failing tests for the centered rig-stats group.
  `tests/service/test_kanban_page.py` additions:
  (a) the header contains a `.rig-stats` element with 5 `.stat-cell`
  children: Ripped / In review / Partial / Storage / Uptime;
  (b) each cell has a `.stat-value` (mono, weight 700) and a
  `.stat-label` (eyebrow, CSS-uppercased);
  (c) Ripped + In review + Partial values derive from the
  kanban payload counts; Storage + Uptime come from a new
  `/api/rig/stats` endpoint (see Bucket E lane-3 task below);
  (d) `.rig-stats` is a single bordered group (visual unit,
  not 5 disconnected cells).

- [x] {agent: lane-3, id: test-rig-stats-endpoint}
  Failing tests for `GET /api/rig/stats`.
  `tests/service/test_rig_stats_endpoint.py`:
  (a) response shape `{"storage": {"used_bytes": int,
  "total_bytes": int, "human": "26.4 GB / 64.0 GB"}, "uptime":
  {"seconds": int, "human": "1d 22h"}}`;
  (b) storage derives from `shutil.disk_usage(music_root)`;
  (c) uptime derives from process start time
  (`time.monotonic` against a module-init timestamp);
  (d) human strings follow the build-prompt mono shorthand rules.

- [x] {agent: lane-3, id: test-disc-photo-placeholder}
  Failing tests for the CSS-drawn disc-photo placeholder.
  `tests/service/test_card_anatomy.py` additions:
  (a) cards without a real disc photo render a
  `<div class="thumb thumb--placeholder">` instead of `<img>`;
  (b) `cda.css` styles `.thumb--placeholder` with a
  `conic-gradient` background per the build prompt;
  (c) the right-drawer drive-mode body also uses this
  placeholder at larger size when no card is selected.

- [x] {agent: lane-3, id: test-source-json-highlight}
  Failing tests for source.json syntax highlight in the
  drawer card-detail body.
  `tests/service/test_right_drawer.py` additions:
  (a) the card-detail body renders source.json inside a
  `<pre class="cda-json">`;
  (b) each JSON key is wrapped in `<span class="k">`, strings
  in `<span class="s">`, numbers in `<span class="n">`,
  booleans/nulls in `<span class="b">`;
  (c) a new helper `archivist/service/json_highlight.py::
  highlight(json_obj) -> str` exists and is unit-tested
  separately for the span wrapping;
  (d) no external highlighting library is added to
  `pyproject.toml`.

- [x] {agent: lane-1, id: test-drawer-mode-toggles}
  Failing tests for explicit drawer mode toggle buttons.
  `tests/service/test_right_drawer.py` additions:
  (a) header nav contains two buttons
  `.drawer-toggle--drive` and `.drawer-toggle--card` with
  `aria-pressed` indicating active mode;
  (b) clicking the drive-toggle clears the selected card and
  swaps the drawer body to drive-mode;
  (c) clicking the card-toggle re-opens the last-selected
  card in the drawer (or no-ops when none has been selected
  this session).

#### Bucket F — Destructive-action gates + transitions (lane-2)

- [x] {agent: lane-2, id: test-destructive-gate}
  Failing tests for second-click destructive-action confirmation.
  `tests/service/test_destructive_gate.py`:
  (a) clicking `redo` / `rerip-tracks` / `skip` / `delete` once
  swaps the button label to `confirm: <action>` and applies
  `.btn--confirm-armed`; (b) clicking again within 5 seconds
  fires the actual POST; clicking elsewhere or waiting >5s
  reverts the arm state; (c) a `<p class="confirm-hint">` renders
  below the buttons with the build-prompt hint text verbatim
  ("Destructive actions require a second click to confirm. The
  partial flac files stay on disk until you choose.").

- [x] {agent: lane-2, id: test-transitions}
  Failing tests for card transitions + live-update flash.
  `tests/service/test_transitions.py`:
  (a) `cda.css` defines a `.card--entering` class with
  `animation: fadeIn 200ms var(--ease-out)`;
  (b) `.card--leaving` class with `animation: fadeOut 200ms
  var(--ease-out)`;
  (c) `.flash-moss` class with a short `box-shadow` keyframe
  pulsing `var(--moss)` border;
  (d) the kanban JS adds `.card--entering` to cards new this
  poll cycle and `.flash-moss` to cards whose payload changed
  this cycle (assert via JS source content).

#### Bucket G — Targeted voice pass (lane-3)

- [x] {agent: lane-3, id: test-voice-pass-status-lines}
  Failing tests for targeted voice pass on status lines + button
  labels + error messages.
  `tests/service/test_voice_pass.py`:
  (a) all status-line templates in `card_evolution.py` (or
  wherever Bucket C lands them) match the build-prompt operator-
  voice examples — sentence case, mono dot-separator, project
  vocabulary;
  (b) all button labels in the kanban + expanded card body
  + drawer are in sentence case (no Title Case, no SHOUTING
  except in CSS-uppercased eyebrows);
  (c) all error states surfaced in the right-drawer card-detail
  body or in `/review` cards' "why" explainer follow the
  specific-error pattern (`track 4 · sector 12,044 · gave up
  after 8 retries`), not generic ("Something went wrong");
  (d) no emoji or smart-quote characters in any
  shipped template — only the allowed Unicode glyphs
  (▸ ▾ ↵ ↑ ↓ ↗ ↻).

### Wave 2 — Implementations

#### Bucket A — Asset wire-up (lane-1)

- [ ] {agent: lane-1, depends: test-static-mount, depends: test-font-loading, id: impl-asset-wire-up}
  (1) Add a FastAPI static file mount in `archivist/service/app.py`:
  `app.mount("/static", StaticFiles(directory="archivist/service/static"))`.
  Create `archivist/service/static/` and subdirs `css/`, `img/brand/`.
  (2) Copy assets from
  `docs/mashco-design-system-handoff/cd-archivist/` per the build prompt's
  table: `colors_and_type.css` → `static/css/tokens.css`,
  `cda-styles.css` → `static/css/cda.css`, all six favicon PNGs +
  maskable + apple-touch → `static/img/brand/`, `manifest.webmanifest`
  → `static/manifest.webmanifest`.
  (3) Add the favicon family + manifest + apple-touch-icon + theme-color
  meta tags to `kanban_page.py`'s `<head>` per the build-prompt snippet.
  (4) Add Google Fonts preconnect + stylesheet `<link>` tags for
  Bricolage Grotesque (600, 800) + Inter Tight (400, 500, 700) +
  JetBrains Mono (400, 500).
  Commit: `feat(sprint-7): impl-asset-wire-up — vendor Mash Co. tokens
  + favicons + fonts`.

#### Bucket B — CSS migration + brand mark (lane-1)

- [ ] {agent: lane-1, depends: test-inline-css-removed, depends: test-brand-mark, id: impl-css-migration-brand-mark}
  (1) Strip the inline `<style>` block from `kanban_page.py`. Re-route
  every existing class to either `tokens.css` (variables only) or
  `cda.css` (component rules). Where existing class names conflict with
  the design system's names, rename in the templates AND tests.
  (2) Allowed inline style attribute pattern (whitelisted): CSS custom
  properties only (`style="--progress: 65%"`, `style="--track-count:
  13"`). No raw `width:` / `color:` / `display:` etc. attributes. If you
  hit a place where this pattern doesn't suffice, STOP and flag to orc
  before adding any other inline style. Inline style as a "this isn't
  working easily" workaround is explicitly disallowed.
  (3) Implement the `cd/a` brand mark per the build prompt's recipe.
  Three size variants: `.cda-brand-mark--header` (22px) used in the
  header; `--splash` (84px) and `--marketing` (240px) defined in
  `cda.css` for future use. The header uses
  `<span class="cda-brand-mark cda-brand-mark--header">cd/a</span>`
  with `transform: translateY(-2px)` per the build-prompt note about
  keeping the extrude shadow from kissing the bottom border.
  Commit: `feat(sprint-7): impl-css-migration-brand-mark`.

#### Bucket C — Card anatomy refactor (lane-2 / pipeline)

- [ ] {agent: lane-2, depends: test-card-header-row, depends: test-status-line, depends: test-chip-row, depends: test-track-segments, id: impl-card-anatomy}
  Refactor the card-render helper(s) in `kanban_page.py` (or split out
  to a new `archivist/service/card_render.py`) to emit the new anatomy:
  (1) `.card-head` with thumbnail + slug + title + artist line;
  (2) status line via a new
  `archivist/service/status_line.py::format(card) -> str` that maps
  card state → the spec's exact one-line format;
  (3) chip row builder that emits VA / BURNED / MIX / WEAK MATCH /
  MUSICBRAINZ chips per card state, with `.chip--asserted` for
  operator-asserted values and `.chip--confirmed` for system-confirmed;
  (4) `.track-bar` with `style="--track-count: N"` and per-cell state
  classes per the test spec, plus `style="--progress: X%"` on the
  in-flight cell during a rip;
  (5) `.track-cell--identified` class added when the card's beets ID
  pass has identified the corresponding track. Source: a new
  helper `archivist/service/track_identification.py::identified_tracks
  (folder) -> set[int]` that reads beets state (or returns a stub for
  now if the wiring isn't trivial — leave a TODO and pin in a
  `D-track-identification-source` decision-log entry).
  (6) Per-column left-border accent class applied based on column +
  card state.
  Commit: `feat(sprint-7): impl-card-anatomy`.

#### Bucket D — Beets candidates (lane-3)

- [ ] {agent: lane-3, depends: test-candidates-endpoint, id: impl-candidates-endpoint}
  Implement `GET /api/disc/<folder>/candidates` in
  `archivist/service/app.py`. Use `archivist/service/mb_client.py` for
  MB queries. Flow:
  (1) read source.json for the disc folder;
  (2) if `identifiers.musicbrainz_disc_id` present, do an MB disc-id
  lookup and prepend the result at score 1.0;
  (3) if AcoustID fingerprints present in chroma cache (look up
  pattern: scan rip.log for fpcalc output or query the chroma plugin
  state), do a fingerprint lookup and append results;
  (4) if neither AND `operator_hints.artist|album` present, do an
  MB metadata search;
  (5) dedupe by MBID, sort by score desc, return top 5;
  (6) handle network failure with 503 + error payload;
  (7) cache results in memory for 5 minutes per folder to avoid
  hammering MB.
  Commit: `feat(sprint-7): impl-candidates-endpoint`.

- [ ] {agent: lane-3, depends: test-candidates-section-ui, depends: impl-candidates-endpoint, id: impl-candidates-section-ui}
  Add the candidates section to the expanded card body in
  `kanban_page.py`. Template emits a section placeholder + the JS
  fetches `/api/disc/<folder>/candidates` on card-expand. Renders
  up to 5 rows; top row gets `.candidate--top`. Apply button is
  wired to POST `/api/disc/<folder>/accept-top-candidate` with the
  picked MBID — note: this changes the existing endpoint's body
  contract from no-body to `{mbid: str}` — update the existing
  sprint-6.5 impl to accept either the previous "top candidate"
  no-body call (find the top score server-side) OR the new
  explicit-MBID body (additive, backward-compat).
  Commit: `feat(sprint-7): impl-candidates-section-ui`.

#### Bucket E — Layout details

- [ ] {agent: lane-1, depends: test-column-headlamps, id: impl-column-headlamps}
  Add `.headlamp` elements to each column header in `kanban_page.py`
  with the per-stage modifier classes. CSS already in `cda.css`.

- [ ] {agent: lane-2, depends: test-live-status-chip, depends: test-rig-stats-group, id: impl-header-live-and-stats}
  Implement the live-status chip + rig-stats group in the header.
  Pulse animation already in `cda.css`. Stats values read from
  `/api/kanban` (counts) + `/api/rig/stats` (storage + uptime —
  fetched once per minute since these change slowly). Commit:
  `feat(sprint-7): impl-header-live-and-stats`.

- [ ] {agent: lane-3, depends: test-rig-stats-endpoint, id: impl-rig-stats-endpoint}
  Implement `GET /api/rig/stats` in `archivist/service/app.py`.
  Uses `shutil.disk_usage` and a module-init `time.monotonic`
  start. Module-init time captured in `app.py` at startup.

- [ ] {agent: lane-3, depends: test-disc-photo-placeholder, id: impl-disc-photo-placeholder}
  Card render helper emits `<div class="thumb thumb--placeholder">`
  for cards without a real photo. Right-drawer drive-mode body
  uses a larger variant. CSS already in `cda.css`.

- [ ] {agent: lane-3, depends: test-source-json-highlight, id: impl-source-json-highlight}
  Implement `archivist/service/json_highlight.py::highlight(obj)
  -> str` that walks a JSON-serializable object and emits
  `<pre class="cda-json">` content with `.k/.s/.n/.b` spans.
  Right-drawer card-detail body uses this. Unit-test with
  small fixture objects.

- [ ] {agent: lane-1, depends: test-drawer-mode-toggles, id: impl-drawer-mode-toggles}
  Add header nav `.drawer-toggle--drive` + `.drawer-toggle--card`
  buttons. JS state tracks `lastSelectedCard`; toggle-card
  re-opens that card in the drawer.

#### Bucket F — Gates + transitions (lane-2)

- [ ] {agent: lane-2, depends: test-destructive-gate, id: impl-destructive-gate}
  Implement second-click confirmation in the kanban JS. Track
  per-button armed state with a 5s timeout; render the hint text
  below the destructive-action button group. Apply to: redo,
  rerip-tracks, skip, delete (and any future destructive actions
  via the `data-destructive="true"` attribute pattern).

- [ ] {agent: lane-2, depends: test-transitions, id: impl-transitions}
  Implement card transitions in the JS poll handler: diff the new
  kanban payload against the previous one; add `.card--entering`
  to new cards, `.card--leaving` to vanishing cards (then remove
  after 200ms), `.flash-moss` to cards whose source.json hash
  changed.

#### Bucket G — Targeted voice pass (lane-3)

- [ ] {agent: lane-3, depends: test-voice-pass-status-lines, id: impl-voice-pass-targeted}
  Sweep visible strings per the test spec. Specifically: all
  status-line templates, all button labels in the kanban +
  expanded card body + drawer, all error states in
  review-explainer + drawer card-detail body. Sentence-case
  everywhere; project vocabulary verbatim; specific-error pattern
  for failures. NO emoji; only the allowed Unicode glyphs.
  Commit: `feat(sprint-7): impl-voice-pass-targeted`.

### Wave 3 — Visual smoke (operator-driven)

- [ ] {agent: operator, id: smoke-visual-pass}
  Deploy sprint-7 to the CM4 (`git pull && pip install -e
  '.[dev]' && systemctl --user restart cd-archivist`). Open
  `cda.mattmariani.com` in a desktop browser AND a phone browser.
  Verify against the build prompt's Definition of Done checklist:
  - cd/a mark renders chunky + extruded (not flat italic)
  - All four favicon sizes resolve; PWA manifest present
  - Each column has the right 8px headlamp dot color
  - Cards render the new anatomy (thumbnail + slug + title +
    artist + status + chips + track bar)
  - Track segments evolve correctly (color per state +
    outline when identified)
  - Operator-asserted chips have dashed borders; system-confirmed
    have solid + halo
  - Expanded card body shows the 4 sections in the right order
  - Beets candidates section returns real candidates for an
    in-review disc; Apply button works end-to-end
  - Header live-status chip pulses when ripping, "idle" when
    not; rig-stats group shows real numbers
  - Right drawer toggles correctly between drive + card mode
  - Bottom drawer collapsed/expanded behavior unchanged
  - Destructive actions require second click + show hint text
  - Polling cadence flips 1s ↔ 5s
  - No `bg-purple-*` / Tailwind palette colors in compiled CSS
  - Bricolage Grotesque loads (visible in dev-tools network)
  - Mobile bucket tabs render at narrow viewport

## Agent Roster

| Agent | Pane | Lane | Owns |
|---|---|---|---|
| lane-1 | %23 (formerly drivers) | foundation | `archivist/service/app.py` (static mount + new endpoints assigned to lane-1), `archivist/service/static/` (vendored asset tree), `archivist/service/kanban_page.py` (Bucket A & B only — `<head>` + brand mark + CSS-import wire-up), `tests/service/test_{static_mount,font_loading,inline_css_removed,brand_mark,column_headlamps,drawer_mode_toggles}.py` |
| lane-2 | %24 (pipeline) | card UI + polish | `archivist/service/card_render.py` (new) + `kanban_page.py` (card markup sections), `archivist/service/status_line.py` (new), `archivist/service/track_identification.py` (new), `tests/service/test_{card_anatomy,live_status_chip,rig_stats_group,destructive_gate,transitions}.py` |
| lane-3 | %28 (new Claude Code session in pane 2) | endpoints + data | `archivist/service/app.py` (new endpoints: candidates, rig-stats), `archivist/service/json_highlight.py` (new), `archivist/service/mb_client.py` (extend for candidates query), `tests/service/test_{candidates_endpoint,candidates_section_ui,rig_stats_endpoint,disc_photo_placeholder,source_json_highlight,voice_pass}.py` |

**Three-lane brief — to give each agent at dispatch:** "Sprint-7 is
entirely pipeline-domain work; you have been assigned the lane-N
slice. Drivers-domain agents are loaned into pipeline lanes for this
sprint to triple our parallelism. Do not modify state-machine /
ripper / drivers code — your scope is `archivist/service/` only. Other
two lanes are running in parallel; file ownership above keeps you
out of each other's way."

**Cross-lane coordination points:**
- `archivist/service/app.py` is touched by all three lanes (different
  endpoints). Stage-and-commit narrowly per lane; expect to rebase if
  two lanes touch the same `@app.get` block. Lane-1 lands the static
  mount first (Bucket A); lanes 2/3 then add their endpoints atop.
- `kanban_page.py` is touched by lane-1 (Bucket A/B head + brand mark)
  and lane-2 (Bucket C card markup). Lane-1's Bucket B finishes
  before lane-2's Bucket C starts impls — Wave 2 ordering enforces.
- Tests live in `tests/service/` for all three lanes; per-test-file
  ownership above avoids overlap.

## Decision Log

> Architecture decisions to ratify at planning. Resolved decisions
> from the design handoff are listed first; open ones at the bottom
> with **OPEN**.

### 2026-05-16 — D-design-system-as-source-of-truth — Mash Co. handoff drives every visual decision

Settled. The build prompt at
`docs/mashco-design-system-handoff/cd-archivist/handoff/Build prompt.md`
is the source of truth for visual design. `colors_and_type.css` and
`cda-styles.css` are imported verbatim; we do not redefine tokens or
component classes. New components added must use existing tokens
and follow established patterns.

### 2026-05-16 — D-inline-css-whitelist — only CSS-custom-property-as-data inline style allowed

Settled. The only allowed `style=` attribute in shipped templates is
the pattern `style="--<name>: <value>"` where the CSS file consumes
the variable via `var()`. Examples: `style="--progress: 65%"` for
progress fill, `style="--track-count: 13"` for grid columns. Inline
style as a "this isn't working easily" workaround is explicitly
disallowed — if a real exception is needed, the implementing agent
flags orc before adding it. Future inline-CSS exceptions get pinned
as numbered amendments to this decision.

### 2026-05-16 — D-candidates-source-priority — disc-id → fingerprint → operator hints

Settled. The candidates endpoint queries MB in this priority order:
(1) `musicbrainz_disc_id` lookup if present (prepended at score 1.0);
(2) AcoustID fingerprint lookup if chroma cache exists; (3) metadata
search using `operator_hints.artist|album` if neither of the above
yields results. Each tier deduped by MBID, sorted by score, top 5
returned.

### 2026-05-16 — D-three-lane-parallel-pipeline — drivers + pane-2 agents take pipeline tasks for sprint-7 only

Settled. Sprint-7 is entirely pipeline-domain work
(`archivist/service/`). For this sprint only, the drivers-pane agent
and the new pane-2 Claude Code session are temporarily assigned to
pipeline lanes (lane-1 and lane-3 respectively). Per-lane file
ownership in the Agent Roster prevents merge conflicts. Reverts to
drivers-domain roster at sprint-8.

### 2026-05-16 — D-track-identification-source — **OPEN** (lane-2 picks during impl-card-anatomy)

Open. The "outline on identified track segments" rule needs a
data source for which tracks beets has identified. Options to
resolve during impl: (a) parse `beets-import.log` for per-track
"identified" lines; (b) query the beets web API
(`http://cm4:8337/item/<id>`) per track; (c) re-derive from the
candidates endpoint results. Lane-2 picks the simplest workable
option and pins. If none are clean, stub the helper to return
`set()` (all tracks unidentified) and ship the outline machinery
without the data — sprint-8 wires the real source.

### 2026-05-16 — D-candidates-cache-ttl — **OPEN** (lane-3 confirms during impl-candidates-endpoint)

Open. The candidates endpoint proposes a 5-minute in-memory cache to
avoid hammering MusicBrainz. Lane-3 confirms the TTL value + cache
key (folder vs. folder + hints-mtime) during impl.

### 2026-05-16 — D-mobile-brand-mark-size — **OPEN** (lane-1 confirms during impl-css-migration-brand-mark)

Open. The brand prompt specifies header 22px, splash 84px, marketing
240px. The current kanban uses the header variant only; mobile
viewport may want a smaller header (16–18px). Lane-1 confirms whether
to add a `--mobile` variant or keep the header variant scaled by
viewport.

## Ratification Log

> User-ratified decisions. Format:
> `### {{date}} — {{decision-id}} — {{summary}}`.

- _None yet._

## Contract Changes

> Additive-only changes to API.

### 2026-05-16 — new endpoints

- `GET /api/disc/<folder>/candidates` — MB-backed candidates list
  for the Beets-candidates UI section.
- `GET /api/rig/stats` — storage + uptime for the header rig-stats
  group.

### 2026-05-16 — `POST /api/disc/<folder>/accept-top-candidate` accepts optional `{mbid: str}` body

Sprint-6.5 shipped this endpoint with no-body semantics (server picks
top candidate). Sprint-7 extends to accept an explicit MBID in the
request body, dispatched by the Beets-candidates UI's Apply buttons.
Backward-compat preserved: no body still means "top candidate."

### 2026-05-16 — kanban HTML structure changes (not API but client-visible)

Substantial markup refactor per the design handoff: new class names
(`.cda-brand-mark`, `.headlamp--*`, `.thumb`, `.thumb--placeholder`,
`.card-head`, `.slug`, `.title`, `.artist`, `.cda-status`,
`.chip-row`, `.chip--asserted`, `.chip--confirmed`,
`.track-bar`, `.track-cell--*`, `.live-status`, `.rig-stats`,
`.stat-cell`, `.candidate-row`, `.candidate--top`, `.score-chip`,
`.apply-btn`, `.cda-json` + `.k/.s/.n/.b` spans, `.drawer-toggle--*`,
`.btn--confirm-armed`, `.card--entering`, `.card--leaving`,
`.flash-moss`). No external consumers depend on these class names.

## Blockers

<!-- One bullet per active blocker. -->

- _None._

## Sprint-8 Candidates

<!-- Items captured during sprint-7 that should be picked up at
sprint-8 planning. -->

- **Full voice pass** — every visible string reviewed against the
  design-system voice rules. Sprint-7 does targeted; sprint-8 does
  the sweep.
- **Track identification data source** — if sprint-7 stubs
  `identified_tracks()` to return `set()`, sprint-8 wires the real
  source (beets-import.log parse, beets web API, or candidates
  re-derivation per `D-track-identification-source`).
- **All sprint-6.5 → sprint-7 carry-overs already in the
  Sprint-7 Candidates list:** tail-log filter UI, force-re-run
  beets ID action, edit-by-hand metadata, sort/filter controls,
  cache `build_kanban_state` disk-walk, alert/notification strip,
  wire operator_hints into beets search, empty-tag MB-fallback
  suppression.
- **`cdplay.service` cleanup** — original sprint-6 candidate
  (decouple-not-install was the choice; revisit if eject path
  ever fails in the wild).

## Activity Log

<!-- Per-agent updates land here, newest first. -->

### 2026-05-16 — lane-3 — Wave 1 failing tests landed (6 tasks, 6 commits)

All 6 lane-3 Wave 1 failing-test tasks shipped:
- `test-candidates-endpoint` → `tests/service/test_candidates_endpoint.py`
  (7 cases — shape, sort+cap, disc-id prepend, fingerprint fallback,
  operator-hints metadata search, 404 missing folder, 503 on MB
  failure; fakes injected via monkeypatching `mb_client.get_mb_client`)
- `test-candidates-section-ui` → `tests/service/test_candidates_section_ui.py`
  (4 cases pinning `.score-chip` / `.candidate-meta` / `.apply-btn` /
  `.candidate--top` + `data-mbid` POST to `accept-top-candidate`)
- `test-rig-stats-endpoint` → `tests/service/test_rig_stats_endpoint.py`
  (5 cases — shape, shutil.disk_usage parity, monotonic uptime,
  storage + uptime mono-shorthand regex)
- `test-disc-photo-placeholder` → `tests/service/test_disc_photo_placeholder.py`
  (3 cases — card `.thumb--placeholder` div, conic-gradient in cda.css,
  larger variant in drive-mode drawer)
- `test-source-json-highlight` → `tests/service/test_source_json_highlight.py`
  (5 cases — helper module import, .k/.s/.n/.b span wrapping, nested
  containers, drawer cda-json reference, no external highlight library
  in pyproject)
- `test-voice-pass-status-lines` → `tests/service/test_voice_pass.py`
  (7 cases — canonical phrases in status_line.py, no SHOUTING /
  marketing copy, sentence-case button labels, specific-error pattern
  in review_explainer + damaged_disc, no emoji, no smart quotes,
  no emoji in rendered HTML; one current title-case offender ("In
  Library") flagged for impl-voice-pass-targeted to fix)

Per-lane file ownership respected — no overlap with lane-1 or lane-2;
each test file is new and lane-3-owned per the roster. Per the user-
explicit task spec some tests live in lane-3 sibling files rather than
the lane-2 `test_card_anatomy.py` / pre-existing `test_expanded_card.py`
/ `test_right_drawer.py` to keep concurrent edits safe.

One open decision deferred to Wave 2:
- `D-candidates-cache-ttl` — TTL value + cache-key shape (folder vs.
  folder+hints-mtime) confirmed during `impl-candidates-endpoint`.

### 2026-05-16 — lane-2 (pipeline) — Wave 1 failing tests landed (8 tasks, 5 commits)

All 8 lane-2-owned Wave 1 failing-test tasks shipped. Tests fail
for the right reasons (missing classes, missing cda.css file,
missing JS-source markers) — the Wave 1 contract is "these fail
until Wave 2 impls them." No file overlap with lane-1 or lane-3
per the roster; my additions to `test_kanban_page.py` are
append-only at the file tail.

**Bucket C — card anatomy (4 tasks, 1 commit):**
- `68cfcb7` test-{card-header-row, status-line, chip-row,
  track-segments} — new `tests/service/test_card_anatomy.py`
  pinning the full card-anatomy contract per the build prompt:
  `.card-head` with 56×56 `.thumb` (img OR `.thumb--placeholder`)
  + `.slug` + `.title` + `.artist`; `.cda-status` mono status
  line with per-state exact formats (`"ripping track 7 ·
  sector 24,318 · 1 retry · 04:12 elapsed"`, `"weak match ·
  beets returned 0.42"`, etc.); `.chip-row` with VA / BURNED /
  MIX / WEAK MATCH · <score> / MUSICBRAINZ · <score> +
  `.chip--asserted` (dashed) vs `.chip--confirmed` (solid +
  halo); `.card--accent-*` classes per the build-prompt
  column-and-state table; `.track-bar` with
  `style="--track-count: N"` + per-cell state classes
  (`--clean` / `--recovered` / `--unrecoverable` / `--pending`
  / `--ripping`); in-flight cell with `style="--progress: X%"`;
  `.track-cell--identified` with the 1px white inset 2px
  outline rule in cda.css.

**Bucket E — layout details lane-2 slice (2 tasks, 1 commit):**
- `ff99bbc` test-{live-status-chip, rig-stats-group} — appended
  to `tests/service/test_kanban_page.py`. Header `.live-status`
  with `.dot` child (`"ripping · DISC-<slug>"` + `.dot--pulse-moss`
  active / `"idle"` + `.dot--quiet` idle); cda.css `@keyframes
  pulse` driving the moss dot. Header `.rig-stats` with exactly
  5 `.stat-cell` children (Ripped / In review / Partial /
  Storage / Uptime); `.stat-value` mono weight-700; `.rig-stats`
  has its own border (bordered group, not 5 disconnected cells);
  Storage + Uptime reference `/api/rig/stats` (lane-3 ships the
  endpoint).

**Bucket F — gates + transitions (2 tasks, 2 commits):**
- `002410d` test-destructive-gate — new
  `tests/service/test_destructive_gate.py`. Destructive buttons
  carry `data-destructive="true"` + `data-action="<name>"`;
  inline JS source contains `btn--confirm-armed`, the
  `confirm:` label-swap, a `5000`ms revert timer, and a
  document-level click handler for outside-click disarm.
  `<p class="confirm-hint">` renders the build-prompt verbatim
  text on damaged cards and is absent on healthy cards.
- `e81ea1d` test-transitions — new
  `tests/service/test_transitions.py`. cda.css defines
  `.card--entering { animation: fadeIn 200ms var(--ease-out) }`,
  `.card--leaving` (fadeOut 200ms), and `.flash-moss` with a
  `var(--moss)` reference (direct or via named `@keyframes`).
  Kanban JS source carries `.card--entering`, `.flash-moss`,
  and `.card--leaving` so the poll handler can add them on
  diff.

Wave 2 lane-2 queue gates on lane-1's Bucket A landing
(`archivist/service/static/css/cda.css` must exist before most
of my impls go green): `impl-card-anatomy`,
`impl-header-live-and-stats`, `impl-destructive-gate`,
`impl-transitions`.

### 2026-05-16 — lane-1 — Wave 1 failing tests landed (Buckets A, B, E slice)

- All 6 lane-1 Wave-1 tasks complete; each test file fails for the
  right reason (impl not yet written). Five atomic commits:
  - `test(sprint-7): test-static-mount` — new
    `tests/service/test_static_mount.py`: asserts
    `/static/css/{tokens,cda}.css` + `/static/img/brand/*` +
    `/static/manifest.webmanifest` resolve, head emits favicon
    family + apple-touch + manifest + `theme-color #07090c`, and
    tokens.css loads BEFORE cda.css.
  - `test(sprint-7): test-font-loading` — new
    `tests/service/test_font_loading.py`: asserts Google Fonts
    preconnect (fonts.googleapis.com + fonts.gstatic.com) + family
    `<link>` for Bricolage Grotesque (600+800) / Inter Tight
    (400+500+700) / JetBrains Mono (400+500); tokens.css `@import`s
    the same; no `-apple-system` / `BlinkMacSystemFont` fallback
    overrides in shipped HTML.
  - `test(sprint-7): test-inline-css-removed,test-column-headlamps`
    — appended to `tests/service/test_kanban_page.py`: at most one
    `<style>` element and only CSS-custom-property-as-data inline
    style allowed per D-inline-css-whitelist; every class in the
    rendered HTML resolves against tokens.css or cda.css; 8px
    `.headlamp` dots in each column header with `--pulp` / `--sky`
    / `--amber` / `--moss` modifiers backed by recipes in cda.css;
    forbidden full-column tint classes asserted absent.
  - `test(sprint-7): test-brand-mark` — new
    `tests/service/test_brand_mark.py`: asserts
    `<span class="cda-brand-mark cda-brand-mark--header">cd/a</span>`
    in header; cda.css `.cda-brand-mark` declares font-display 800
    italic, -0.05em letter-spacing, `var(--mash-pulp)`,
    `-webkit-text-stroke`, `paint-order: stroke fill`, and a 5+
    layer `text-shadow` extrude; size variants `--header` (22px),
    `--splash` (84px), `--marketing` (240px) all defined.
  - `test(sprint-7): test-drawer-mode-toggles` — appended to
    `tests/service/test_right_drawer.py` (plus `import re`):
    asserts header nav `.drawer-toggle--drive` + `.drawer-toggle--card`
    buttons with `aria-pressed`; drive-toggle defaults
    `aria-pressed="true"` at first render; both selector strings +
    a `lastSelectedCard` (or `last_selected_card`) state reference
    appear in the inline JS.
- Sprint-7 plan boxes for the six lane-1 Wave-1 tasks all ticked.
- Lane-2 and lane-3 Wave-1 tasks still pending; no file overlap.

### 2026-05-16 — planner — sprint-7 plan drafted

- Drafted from
  `docs/mashco-design-system-handoff/cd-archivist/handoff/Build prompt.md`.
- Four resolved decisions from the handoff (D-design-system-as-source-
  of-truth, D-inline-css-whitelist, D-candidates-source-priority,
  D-three-lane-parallel-pipeline) + three open decisions
  (D-track-identification-source, D-candidates-cache-ttl,
  D-mobile-brand-mark-size) deferred to impl.
- Seven buckets across three lanes: A (asset wire-up, lane-1),
  B (CSS migration + brand mark, lane-1), C (card anatomy, lane-2),
  D (beets candidates, lane-3), E (layout details, split across
  all three lanes), F (gates + transitions, lane-2), G (targeted
  voice pass, lane-3).
- Wave 1 = 22 failing-test tasks; Wave 2 = 14 impl tasks; Wave 3
  = 1 operator-driven visual smoke.
- Three-lane parallel execution: drivers pane (lane-1, foundation),
  pipeline pane (lane-2, card UI + polish), new pane-2 Claude Code
  session (lane-3, endpoints + data). Per-lane file ownership keeps
  agents out of each other's way; cross-lane coordination points
  flagged in the roster.
