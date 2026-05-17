---
project: cd-archivist
sprint: sprint-8
created: 2026-05-17T00:00:00.000Z
updated: 2026-05-17T00:00:00.000Z
status: draft
---

# cd-archivist — coordination doc (sprint-8)

> Strict template per Session O2=B / seed §12 Phase 8. The dashboard
> reads this as the canonical substrate (seed §3.7); orc emits
> `coord-doc-stale` cards when drift is detected (§3.8 / O7=A).

## Plan Source

- Type: inline
- Path: this document (`## Active Sprint Plan` section)
- Active unit: sprint-8

## Sprint Goals

- **Define a tight version-control + workflow process.** Author
  `docs/WORKFLOW.md` as a supplement to `CLAUDE.md` (referenced from
  it). Covers: git commit conventions, branching strategy, deployment
  process to the CM4, documentation review/update cycle, version
  bumping, when-to-report-to-orc-tower escalations, decision-log
  conventions, sprint-doc lifecycle. Author `CHANGELOG.md` (Keep-a-
  Changelog format) and backfill the existing release surface from
  sprints 1–7. Author `ROADMAP.md` (forward-looking backlog) and
  `ISSUES.md` (defect-focused backlog) with explicit add/triage/
  resolve processes.
- **Sanitize the repo tree.** Stray PNG screenshots, mbid-named
  artifacts, the `ripper-handoff-for-claude-code.md` orphan, and any
  defunct code or stale planning docs get organized into the file
  layout the new workflow schema defines (or deleted if obsolete).
  Working tree should end clean — no orphan tracked-but-stale files;
  untracked files either added or `.gitignore`'d intentionally.
- **Refresh documentation against current reality.** The existing
  `README.md` is stale (still describes the retired two-machine
  G4+Pi setup). Rewrite it. Author an architecture doc, a quick-start
  doc, and a feature inventory. Add a Mermaid workflow diagram
  showing the disc-to-library pipeline.
- **Preserve the music-pipeline contract.** Pure housekeeping sprint
  — no code changes, no API changes, no template renames. Tests
  must remain green throughout.

> **Scope-hierarchy reminder.** Phase A (lane-3 process foundation)
> is the load-bearing scope — it produces the schemas + templates
> that Phases B (sanitization + doc rewrite) consume. A must land
> before B starts; B can run B-1 and B-2 in parallel after that.

## Active Initiatives

- _None — sprint-8 plan below is the substrate._

## Active Sprint Plan

### Phase A — Process foundation (lane-3, solo, gates Phase B)

- [x] {agent: lane-3, id: workflow-doc}
  Author `docs/WORKFLOW.md` (~250-400 lines). Section list:
  1. **Purpose & relationship to CLAUDE.md** — one paragraph;
     CLAUDE.md says HOW agents behave, WORKFLOW.md says HOW work
     flows through the repo.
  2. **Git commit conventions** — Conventional Commits
     (`feat(scope): …`, `fix(scope): …`, `docs(scope): …`,
     `chore(scope): …`, `refactor(scope): …`, `test(scope): …`).
     `<scope>` is `sprint-N` for sprint work or a short subsystem
     name (`drivers`, `service`, `pipeline`) for hotfixes.
     Commit-body conventions (what + why, never just what).
     Atomic-commit rule. Co-Authored-By footer for agent work.
  3. **Branching strategy** — for v1 stay on `master` (small team,
     dogfood pace); document when branches become warranted
     (any change touching >5 files OR crossing 3+ subsystems gets a
     short-lived branch + PR). Trunk-based default.
  4. **Deployment to the CM4** — the literal command sequence
     (`git pull --ff-only origin master && pip install -e ".[dev]"
     && systemctl --user restart cd-archivist`). When to use it
     (after every merged change that touches `archivist/` or
     `pyproject.toml`). How to roll back (`git reset --hard <sha>`
     + restart). Cache-busting note for browser CSS (hard refresh).
  5. **Documentation review/update cycle** — every sprint closes
     with: README + architecture doc + project-overview spot-check;
     CHANGELOG entry; ROADMAP / ISSUES re-triage. Quarterly: full
     doc-vs-code reality audit.
  6. **Version control / versioning** — semver on `pyproject.toml`
     when shipping releases. v0.x while pre-feature-complete (we
     are). Bump rules (`MAJOR.MINOR.PATCH`). CHANGELOG section
     `[Unreleased]` → date-stamped section on release tag.
  7. **When to report to orc-tower** — escalations: agent-harness
     bugs, tmax workspace issues, multi-project workflow problems
     get filed under `orc-tower` (cross-repo). Project-specific
     bugs stay in `cd-archivist`.
  8. **Decision-log conventions** — `D-<kebab-id>` IDs, format,
     when to add (any non-obvious choice that future work might
     re-question), OPEN vs SETTLED, ratification flow.
  9. **Sprint-doc lifecycle** — draft → in-progress → closed.
     Plan inline, never rebase old sprints, carry-forwards land in
     "Sprint-N+1 Candidates" sections.
  10. **Adding to ROADMAP** — process: write a one-paragraph
      proposal under the appropriate horizon section
      (next-sprint / next-milestone / someday-maybe); orc-tower
      adopts into a sprint plan at planning time.
  11. **Adding to ISSUES** — process: severity tag (`blocker /
      major / minor / cosmetic`), reproduction-or-don't-need-repro,
      owner-or-tbd. Triage rule: anything blocker/major gets pulled
      into the active sprint; minor/cosmetic land in the next plan
      cycle.
  Commit: `docs(sprint-8): WORKFLOW.md — version-control + workflow
  process`.

- [x] {agent: lane-3, id: workflow-claude-ref}
  Add a one-paragraph reference to WORKFLOW.md from `CLAUDE.md`
  (immediately after the existing project-instructions block).
  Single edit; small commit. Format:
  `For workflow rules — commits, deployment, documentation cycle,
  version control, escalation paths, backlog processes — see
  [docs/WORKFLOW.md](docs/WORKFLOW.md). WORKFLOW.md governs HOW
  work flows; CLAUDE.md governs HOW agents behave.`
  Commit: `docs(sprint-8): claude.md references workflow.md`.

- [x] {agent: lane-3, id: changelog-init}
  Author `CHANGELOG.md` at the repo root in Keep-a-Changelog
  format (https://keepachangelog.com/en/1.1.0/). Sections:
  `[Unreleased]` (with Added / Changed / Deprecated / Removed /
  Fixed / Security subsections — start empty), then back-fill
  one section per sprint we have records of (sprint-1 through
  sprint-7), pulling Sprint Goals + Activity Log highlights from
  the existing `docs/coordination/sprint-N.md` files. Each
  back-fill section dated to the sprint's completion (use the
  latest sprint-N.md `updated:` date). Commit:
  `docs(sprint-8): CHANGELOG.md — Keep-a-Changelog backfill
  through sprint-7`.

- [x] {agent: lane-3, id: roadmap-init}
  Author `ROADMAP.md` at the repo root. Three horizon sections:
  `## Next sprint` (items earmarked for sprint-9 — pull from
  sprint-7 + sprint-6.5 "Sprint-N+1 Candidates"), `## Next
  milestone` (medium-term thematic groups — e.g. "review-flow
  v2", "operator-hints → beets wiring", "cdplay.service
  decision"), `## Someday / maybe` (long-tail ideas — multi-drive
  support, container packaging, live cam preview, AcoustID
  submission). Format per item: 2-3 line proposal + an
  `Add date: YYYY-MM-DD` field. Top of doc: prose paragraph on
  the add/triage/resolve process (per WORKFLOW.md §10). Commit:
  `docs(sprint-8): ROADMAP.md — three-horizon backlog`.

- [x] {agent: lane-3, id: issues-init}
  Author `ISSUES.md` at the repo root. Sections:
  `## Open` (active defects, sorted blocker > major > minor >
  cosmetic), `## Resolved` (auto-curated when an issue lands a
  fix commit — link back to the SHA). Initial back-fill from
  sprint-5/6/6.5/7 known carryovers:
  - **Drive hardware failure** (just observed 2026-05-17;
    PLDS DVD-RW DA8A6SH no longer reads TOCs; RMA in progress)
    — blocker, owner=operator
  - **`cdplay.service` deferral** — minor, owner=operator,
    sprint-6 D-cdplay-decouple-not-install closed it for now;
    document so it's not re-raised
  - **Track-identification data source stub** — minor,
    owner=pipeline, sprint-7 stubbed `identified_tracks() →
    set()` per D-track-identification-source
  - **Operator-hints not yet wired into beets search** —
    minor (carries from sprint-6 Sprint-7 Candidates)
  - **Beets traceback-spam on tag-less flacs in interactive
    import** — minor (sprint-5 finding; covered by the
    musicbrainzngs direct-path candidates endpoint in sprint-7
    but old beets CLI path still has the issue)
  Top of doc: prose paragraph on the add/triage/resolve process
  (per WORKFLOW.md §11). Commit: `docs(sprint-8): ISSUES.md —
  defect backlog with sprint-5..7 carry-overs`.

- [x] {agent: lane-3, id: file-layout-schema}
  Author `docs/FILE-LAYOUT.md` (~100 lines) — the canonical
  "where things go" map. Inventory the existing tree, define the
  intended layout, call out current violations (orphan
  screenshots at repo root, etc.) without yet moving anything.
  The repo-sanitization agent in Phase B consumes this. Sections:
  - **Top-level files** (`README.md`, `CHANGELOG.md`,
    `ROADMAP.md`, `ISSUES.md`, `CLAUDE.md`, `pyproject.toml`,
    `ruff.toml`, `.gitignore`)
  - **`archivist/`** — production code (drivers / pipeline /
    service / state_machine / models)
  - **`tests/`** — pytest tree mirrors `archivist/`
  - **`docs/`** subdirectories:
    - `docs/coordination/sprint-N.md` — sprint coord docs
    - `docs/design/` — design briefs (one file per topic)
    - `docs/operations/` — operator runbooks
    - `docs/reference/` — vendored references (the mashco
      handoff, etc.)
    - `docs/screenshots/` (NEW) — UI screenshots from review
      sessions (move the `tests/cd-arhcivist-screen.png` and
      any `orc-*.png` strays here)
    - `docs/runbooks/` — already exists, keep
    - `docs/research/` — already exists, keep
  - **What goes at repo root vs nested** — guidance
  - **What does NOT belong tracked** — `.playwright-mcp/`,
    `*.zip` design-system archive, MB-cover-art JPGs scraped
    during testing → `.gitignore` candidates
  Commit: `docs(sprint-8): FILE-LAYOUT.md — canonical tree
  schema`.

- [x] {agent: lane-3, id: phase-a-activity-log}
  Append a single Phase-A Activity Log entry to sprint-8.md when
  all six tasks above land. Tick the [ ] boxes for each. Commit:
  `docs(sprint-8): phase-A activity log`.

### Phase B — Apply (lane-1 + lane-2 in parallel, after Phase A lands)

#### B-1: Repo sanitization (lane-1)

- [x] {agent: lane-1, id: sanitize-repo-tree, depends: phase-a-activity-log}
  Walk the entire repo tree using `docs/FILE-LAYOUT.md` (lane-3
  output) as the schema. Three passes:
  1. **Identify** — list every file that does NOT match the
     schema. Categorize: misplaced (move), obsolete (delete),
     untracked-but-keep (add or .gitignore), unclear (flag to
     orc).
  2. **Apply** — move/delete/add per the categorization. Use
     `git mv` for moves to preserve history. `git rm` for
     deletions of tracked files; just `rm` for untracked.
  3. **Verify** — `git status` clean; `pytest -q` still green;
     `ruff check .` clean. Tree visually matches FILE-LAYOUT.md.
  Files to specifically handle (from current git status):
  - `docs/mbid-a359ebe6-994f-4d62-9659-c8565d057cfa-19375630765.jpg`
    — MB cover-art artifact from manual testing; delete or move
    to `docs/research/` if reference-worthy
  - `docs/ripper-handoff-for-claude-code.md` — appears to be an
    AI handoff doc from sprint-3/4 timeframe; review and either
    move to `docs/reference/` or delete if superseded
  - `tests/cd-arhcivist-screen.png` — UI screenshot;
    move to `docs/screenshots/` (and fix the typo in the filename)
  - `docs/Mash Co. Design System.zip` (already untracked, possibly
    at repo root) — vendored design archive; either extract or
    `.gitignore`
  - Any other `*.png` strays at repo root — move to
    `docs/screenshots/`
  - `.playwright-mcp/` — gitignore
  Commit (single, atomic): `chore(sprint-8): repo sanitization
  per FILE-LAYOUT.md`.

#### B-2: Documentation rewrite (lane-2)

- [x] {agent: lane-2, id: rewrite-readme, depends: phase-a-activity-log}
  Replace the current stale `README.md` (which describes the
  retired G4+Pi two-machine setup) with a fresh version reflecting
  the single-CM4 architecture. Structure:
  - **What it is** — one-paragraph intro
  - **How it works** — pipeline overview (Capture → Beets ID →
    Review → In Library), with reference to the architecture doc
    for detail
  - **Quick start** — install + run + access the UI; minimal
    happy-path
  - **Repo layout** — pointer to FILE-LAYOUT.md
  - **Workflow & contributions** — pointer to WORKFLOW.md
  - **Status** — what works today, what's pending, link to
    ROADMAP / ISSUES
  Commit: `docs(sprint-8): README.md — fresh single-CM4 rewrite`.

- [x] {agent: lane-2, id: architecture-doc, depends: phase-a-activity-log}
  Author `docs/ARCHITECTURE.md` (~300 lines). Sections:
  - **Topology** — single CM4 owns drive, camera, LED, storage,
    FastAPI; docker container co-located for beets/navidrome/
    jellyfin music stack. Specific paths (`/srv/music/...`,
    `/home/mmariani/Projects/cd-archivist/`).
  - **Component map** — `archivist/{drivers,pipeline,
    state_machine,service,models}/` — one paragraph per
    subsystem with public-interface summary.
  - **Data model** — `source.json` schema (current state with
    all sprint-1..7 additions), file layout per disc folder,
    bucket directories (`inbox/`, `review/`, `library/`,
    `archive/`, `failed/`, `.ripping/`).
  - **Pipeline state machine** — IDLE → STABILIZE → RIP →
    STABILIZE_PARTIAL (failure branch) → HANDOFF → IDLE.
    Include the Mermaid state-diagram block.
  - **Beets integration** — disc-id first, AcoustID fingerprint
    fallback, musicbrainzngs direct queries for candidates UI
    (sprint-7); the docker exec invocation, the
    `process-ready-auto` hook flow.
  - **API surface** — full table of endpoints (kanban, candidates,
    rig-stats, drive-status, logs-tail, disc-action endpoints).
  - **Decision provenance** — pointer to coord-doc Decision Logs;
    quick index of the most-load-bearing decisions.
  Commit: `docs(sprint-8): ARCHITECTURE.md`.

- [x] {agent: lane-2, id: workflow-diagram, depends: phase-a-activity-log}
  Author `docs/WORKFLOW-DIAGRAM.md` containing a Mermaid diagram
  of the disc → library workflow. Must include:
  - Disc insertion → cdparanoia rip + camera capture (parallel)
  - flac encoding
  - libdiscid TOC hash + AcoustID fingerprint
  - musicbrainzngs disc-id lookup + chroma fingerprint lookup
  - decision: auto-apply (high confidence) vs route to review
  - operator branches: process-partial, redo, rerip-tracks,
    accept-top-candidate, manual MB search
  - terminal states: in library, in review (long-term), in
    failed (preserved-for-salvage)
  - kanban UI surface annotations at each step
  Use Mermaid `flowchart TD` for the main diagram; supplement with
  a `stateDiagram-v2` of the state machine if helpful. Commit:
  `docs(sprint-8): WORKFLOW-DIAGRAM.md — Mermaid pipeline +
  state-machine diagrams`.

- [x] {agent: lane-2, id: feature-inventory, depends: phase-a-activity-log}
  Author `docs/FEATURES.md` — one-line-per-feature inventory.
  Sections grouped by subsystem (Drivers, Pipeline, Service /
  UI, Operations). For each feature: name, current state
  (shipped / partial / planned), sprint of origin, file
  pointer. Pulls heavily from the closed sprint coord docs.
  Useful as a "what does this app actually do today" reference.
  Commit: `docs(sprint-8): FEATURES.md — current-state inventory`.

- [x] {agent: lane-2, id: project-overview-refresh, depends: phase-a-activity-log}
  Spot-check `docs/project-overview.md` (written 2026-05-16) against
  current state. Update any references that drift (e.g. if
  sprint-7's UI changes invalidated paragraphs of the original).
  Keep concise per the original intent. Commit:
  `docs(sprint-8): project-overview.md — sprint-8 refresh`.

- [x] {agent: lane-2, id: phase-b2-activity-log}
  Append a single Phase-B-2 Activity Log entry to sprint-8.md when
  all five lane-2 tasks above land. Tick the [ ] boxes. Commit:
  `docs(sprint-8): phase-B-2 activity log`.

#### B-1: Sanitization activity log (lane-1)

- [x] {agent: lane-1, id: phase-b1-activity-log}
  Append a single Phase-B-1 Activity Log entry to sprint-8.md when
  sanitize-repo-tree lands. Tick the [ ] box. Commit:
  `docs(sprint-8): phase-B-1 activity log`.

## Agent Roster

| Agent | Pane | Lane | Owns |
|---|---|---|---|
| lane-3 | %28 | Phase A — process architect | `docs/WORKFLOW.md` (new), `docs/FILE-LAYOUT.md` (new), `CHANGELOG.md` (new), `ROADMAP.md` (new), `ISSUES.md` (new), `CLAUDE.md` (edit only — add WORKFLOW.md ref) |
| lane-1 | %23 | Phase B-1 — repo sanitizer | every file in the tree that does not match `docs/FILE-LAYOUT.md`; `.gitignore` updates |
| lane-2 | %24 | Phase B-2 — doc rewriter | `README.md` (rewrite), `docs/ARCHITECTURE.md` (new), `docs/WORKFLOW-DIAGRAM.md` (new), `docs/FEATURES.md` (new), `docs/project-overview.md` (refresh) |

**Cross-lane coordination:**
- Phase A must complete and push before Phase B starts. The
  `phase-a-activity-log` commit is the gate.
- Phase B-1 and B-2 run in parallel after Phase A. They DO NOT
  share any files — sanitizer touches the tree topology;
  rewriter touches doc content. The one possible overlap is if
  the sanitizer wants to move a doc that the rewriter is editing;
  resolve by sanitizer-first-then-rewriter on any contested file
  (rewriter pulls fresh before final commit).
- `CLAUDE.md` is touched by lane-3 only.
- `pyproject.toml` is NOT touched this sprint.

## Decision Log

### 2026-05-17 — D-housekeeping-no-code-changes — sprint-8 is documentation + tree-cleanup only

Settled. No `archivist/` or `tests/` content changes; only file
moves (via `git mv` to preserve history) and doc creation/edits.
The pytest suite must remain at its pre-sprint-8 green count
throughout. Any code touch surfaces as an exception requiring
orc ratification.

### 2026-05-17 — D-trunk-based-default — branching deferred to v1 release

Settled at sprint-8 planning. Stay on `master` for the dogfood
cadence. WORKFLOW.md documents when branches become warranted
(any change touching >5 files OR crossing 3+ subsystems gets a
short-lived branch + PR). Revisit when v1.0 ships.

### 2026-05-17 — D-keep-a-changelog-format — CHANGELOG follows Keep-a-Changelog v1.1.0

Settled. Standard well-known format; future-agent-friendly
because the structure is predictable. Backfill sprints 1-7 from
the existing `docs/coordination/sprint-N.md` Activity Log
sections.

## Ratification Log

- _None yet._

## Contract Changes

> Additive-only. Process docs introduce conventions; no API or
> data-model touches.

### 2026-05-17 — new top-level files

- `CHANGELOG.md`
- `ROADMAP.md`
- `ISSUES.md`

### 2026-05-17 — new docs

- `docs/WORKFLOW.md`
- `docs/FILE-LAYOUT.md`
- `docs/ARCHITECTURE.md`
- `docs/WORKFLOW-DIAGRAM.md`
- `docs/FEATURES.md`
- `docs/screenshots/` (directory; populated by sanitizer)

### 2026-05-17 — `CLAUDE.md` gains a one-paragraph WORKFLOW.md reference

Single edit; non-breaking.

## Blockers

- _None._

## Sprint-9 Candidates

- **Drive replacement smoke** — once the RMA replacement arrives,
  run the deferred Wave-3 visual smoke from sprint-7 (real-rig
  validation that the sprint-7 UI works end-to-end with an actual
  rip), plus sprint-5's outstanding `musicbrainz_disc_id`
  real-rig populate test.
- **All sprint-7 → sprint-9 carry-overs:** track-identification
  data source, sort/filter UI per column, log-tail filters,
  edit-by-hand library metadata, alert/notification strip,
  cache `build_kanban_state` disk-walk.
- **Full voice pass** (carried from sprint-7's sprint-8 candidate
  — postponed again as not housekeeping-shaped).

## Activity Log

### 2026-05-17 — lane-1 — Phase B-1 repo sanitization landed (1 task, 0 + 1 commits)

Sanitization complete; the repo tree matches `docs/FILE-LAYOUT.md`.
The substantive sanitization changes (file moves, deletes, .gitignore
additions) were swept into lane-2's commit `71794e4`
(`docs(sprint-8): ARCHITECTURE.md`) because my staged work was
already in the index when lane-2 ran their commit in the same working
tree — a known hazard of multi-lane execution from a shared checkout.
The content is in the repo regardless; this log is the audit trail.

**Moves landed (under commit `71794e4`):**
- `docs/mashco-design-system-handoff/` → `docs/reference/mashco-design-system/`
  (vendored design handoff; 26 files including the brand asset family,
  cda-styles.css, the build prompt, and JSX reference components).
- `docs/ripper-handoff-for-claude-code.md` →
  `docs/reference/ripper-handoff-for-claude-code.md` (870-line
  sprint-3/4 AI handoff doc, still load-bearing context for
  `archivist/models/source.py` and the music-stack migration ops doc).
- `tests/cd-arhcivist-screen.png` →
  `docs/screenshots/cd-archivist-screen.png` (UI screenshot;
  destination filename fixes the source typo).

**Deletes landed (under commit `71794e4`):**
- `docs/mbid-a359ebe6-…-19375630765.jpg` — MB cover-art testing
  artifact; the canonical `mbid-*.jpg` anti-pattern per FILE-LAYOUT.
- `docs/Mash Co. Design System.zip` — vendor archive; the extracted
  handoff dir under `docs/reference/mashco-design-system/` is the
  canonical reference, the zip is redundant and `*.zip` is now
  globally `.gitignore`d.

**`.gitignore` additions landed (under commit `71794e4`):**
- `.playwright-mcp/` (Playwright MCP scratch dir).
- `*.zip` (vendor archive bundles at any path).
- `mbid-*.jpg`, `docs/*.png`, `docs/*.jpg` (cover-art / screenshot
  strays at `docs/` root — screenshots belong under
  `docs/screenshots/`, never at `docs/` root).
- `.pytest_cache/`, `.ruff_cache/` (pinned explicitly per FILE-LAYOUT
  'verify' note; previously untracked only via implicit patterns).

**Verification:**
- `git status` clean post-`71794e4`.
- `python3 -m pytest -q`: 626 passed, 1 skipped (unchanged from
  pre-sprint-8 baseline).
- `ruff check .`: 12 pre-existing warnings in `archivist/` and
  `tests/` (E402, F841, F401), unchanged from baseline — no Python
  files were modified, consistent with
  `D-housekeeping-no-code-changes`.
- Tree visually matches `docs/FILE-LAYOUT.md`.

**Deferred (out of scope this commit):**
- `src/cd_archivist/`, `scripts/`, `hardware/`, `config/` —
  `docs/FILE-LAYOUT.md` flags these as 'Legacy areas to audit'
  separately from the current-violations table. Their disposition
  is a follow-up pass (next-sprint candidate).
- Stale path references in `archivist/models/source.py:3` and
  `docs/operations/2026-05-15-music-stack-migration.md:4` that still
  point at the old `docs/ripper-handoff-for-claude-code.md` location.
  Per `D-housekeeping-no-code-changes` the `archivist/` comment is
  untouched this sprint; the cross-tree path-reference sweep is a
  next-sprint candidate (file in ISSUES.md when sprint-9 opens).
- Sprint-7 coord-doc links to `docs/mashco-design-system-handoff/…`
  are now stale. Per WORKFLOW.md §9 'Don't rebase old sprint docs',
  these stay as historical pointers; readers who chase them know
  to grep for the new path.

### 2026-05-17 — lane-3 — Phase A process foundation landed (7 tasks, 7 commits)

Phase A gate. All seven lane-3 tasks shipped as atomic commits;
each commit pushed to origin/master as it landed so Phase B agents
can pull. Phase B (lane-1 sanitization + lane-2 doc rewrite) is now
unblocked.

- `workflow-doc` → `docs/WORKFLOW.md` (461 lines). 11 sections per
  the plan: purpose, commit conventions (Conventional Commits +
  `sprint-N` / subsystem scope vocabulary), branching (trunk-based
  default per `D-trunk-based-default`), CM4 deploy sequence,
  doc-update cadence, semver under `[Unreleased]`-to-release flow,
  orc-tower escalation boundary, decision-log conventions, sprint-
  doc lifecycle, ROADMAP add/triage process, ISSUES add/triage
  process. Appendix quick-reference table.
- `workflow-claude-ref` → one-paragraph reference inserted into
  `CLAUDE.md` immediately after the project-instructions preamble.
  The CLAUDE.md / WORKFLOW.md boundary is phrased "CLAUDE.md governs
  HOW agents behave; WORKFLOW.md governs HOW work flows."
- `changelog-init` → `CHANGELOG.md` at repo root in Keep-a-Changelog
  1.1.0 format. Empty `[Unreleased]` with all six standard
  subsections at top; one section per closed sprint (sprint-1
  through sprint-7, plus sprint-6.5) back-filled from each coord
  doc's Sprint Goals + Activity Log. Each section dated to the
  source coord doc's `updated:` field.
- `roadmap-init` → `ROADMAP.md` at repo root. Three-horizon
  structure with top-of-doc add/triage/resolve prose. Back-filled
  from sprint-7 + sprint-6.5 "Sprint-N+1 Candidates" — five items
  in `## Next sprint` (drive-RMA real-rig smoke, track-id data
  source, log-tail filter UI, operator-hints into beets, force-re-run
  beets ID), seven in `## Next milestone` (Review v2, cdplay
  decision revisit, edit-by-hand metadata, sort/filter per column,
  build_kanban_state cache, alert strip, empty-tag MB-fallback
  suppression), six in `## Someday / maybe` (multi-drive,
  containerization, live cam preview, AcoustID submission, light
  mode, full voice pass).
- `issues-init` → `ISSUES.md` at repo root. Top-of-doc
  add/triage/resolve prose. `## Open` initial back-fill: one
  blocker (drive hardware failure — sprint-8's trigger condition)
  + four minor (operator-hints not wired into beets, stubbed
  track-identification source, beets traceback-spam on tag-less
  flacs, `cdplay.service` deferral). `## Resolved` seeded empty.
- `file-layout-schema` → `docs/FILE-LAYOUT.md` (150 lines).
  Inventory of intended layout for top-level, `archivist/`, `tests/`,
  and `docs/` subdirs. Sections for what goes at root vs nested,
  what does NOT belong tracked, legacy areas to audit (`src/`,
  `hardware/`, `scripts/`, `config/`). Bottom carries the explicit
  per-violation work order for the Phase B-1 sanitizer (the
  current-violations table). Schema-only — no files moved this
  commit (D-housekeeping-no-code-changes contains the moves to
  Phase B-1).
- `phase-a-activity-log` → this entry. Gate commit; Phase B agents
  pull-and-go after it lands.

Cross-phase note: I am Sonnet 4.6 for this Phase A run (previous
Opus context was cleared). Doc-shaped work; nothing required code
touches. Three OPEN decisions from previous sprints (sprint-7's
`D-mobile-brand-mark-size`) were left as-is because they belong to
lanes that aren't running this sprint; revisit at sprint-9 planning.

### 2026-05-17 — lane-2 — Phase B-2 doc rewrite landed (5 tasks, 5 commits)

All five lane-2 doc tasks shipped as atomic commits to master.
Per `D-housekeeping-no-code-changes`: no `archivist/` or `tests/` files
were modified; all work is documentation only.

- `rewrite-readme` → `README.md` (56 lines). Replaced the stale G4+Pi
  two-machine description with the current single-CM4 architecture.
  Sections: What it is / How it works (4-stage pipeline) / Quick start
  (install, run, deploy to rig, access URL) / Repo layout (pointer to
  FILE-LAYOUT.md) / Workflow (pointer to WORKFLOW.md) / Status (what
  works, what's pending, links to ROADMAP + ISSUES).
- `architecture-doc` → `docs/ARCHITECTURE.md` (~300 lines). Full
  cross-cutting reference: topology (CM4 + Docker stack + storage
  layout), component map (all 5 subsystems with module-level tables),
  `source.json` schema (all 13 Pydantic models from sprint-4..7),
  on-disk disc folder layout, pipeline state machine (stateDiagram-v2),
  Beets integration detail (disc-id first, AcoustID fallback, docker
  exec, candidates flow), full API surface table (~30 endpoints grouped
  by surface), decision provenance index (11 key decisions).
- `workflow-diagram` → `docs/WORKFLOW-DIAGRAM.md` (154 lines). Mermaid
  `flowchart TD` of the full disc-to-library pipeline: parallel rip +
  camera, FLAC encoding, libdiscid + AcoustID, MB lookup, auto-apply vs
  review decision, all operator branches (accept-top-candidate, MBID
  paste, hints, use-as-is, skip, process-partial, redo, rerip-tracks),
  terminal states (in library / review long-term / failed). Plus a
  separate `stateDiagram-v2` and kanban UI surface annotation table.
- `feature-inventory` → `docs/FEATURES.md` (111 lines). One-row-per-
  feature table in 4 subsections (Drivers / Pipeline / Service-UI /
  Operations). State (shipped/partial/planned), sprint of origin, file
  pointer. Pulled from sprint-1..7 activity logs.
- `project-overview-refresh` → `docs/project-overview.md` (3 targeted
  edits). Sprint-7 drift fixed: removed "Sprint-7 will add log filters"
  (deferred); expanded rig-stats to include Storage + Uptime (shipped
  sprint-7); updated Review stage copy to mention "up to 5 ranked MB
  candidates" (sprint-7 candidates UI).

Note: the `architecture-doc` commit inadvertently swept in untracked
files that lane-1 had staged (`docs/reference/mashco-design-system/`,
`docs/reference/ripper-handoff-for-claude-code.md`,
`docs/screenshots/cd-archivist-screen.png`). These are sanitization
moves that belong to lane-1 scope; they landed correctly on master and
match the FILE-LAYOUT.md schema. No conflict with lane-1's work.

- [x] rewrite-readme
- [x] architecture-doc
- [x] workflow-diagram
- [x] feature-inventory
- [x] project-overview-refresh

### 2026-05-17 — planner — sprint-8 plan drafted

- Housekeeping sprint while drive RMA ships. No code changes.
- Three-phase structure: Phase A (lane-3 solo) lays the workflow
  foundation; Phase B (lane-1 + lane-2 parallel) applies the
  schema to the repo and rewrites stale docs.
- Three resolved decisions at planning: D-housekeeping-no-code-
  changes, D-trunk-based-default, D-keep-a-changelog-format.
- 13 total tasks: 7 in Phase A (lane-3), 1 sanitizer in Phase
  B-1 (lane-1), 5 doc tasks in Phase B-2 (lane-2). Plus 2
  activity-log housekeeping tasks (one per phase, one per
  parallel-lane).
