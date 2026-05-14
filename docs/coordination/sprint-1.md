---
project: cd-archivist
sprint: sprint-1
created: 2026-05-13T02:38:44.641Z
updated: 2026-05-13T02:38:44.641Z
---

# cd-archivist — coordination doc (sprint-1)

> Strict template per Session O2=B / seed §12 Phase 8. The dashboard
> reads this as the canonical substrate (seed §3.7); orc emits
> `coord-doc-stale` cards when drift is detected (§3.8 / O7=A).
>
> Section headings are load-bearing — keep them as-is so the parser can
> find them. Section bodies are markdown-flexible.

## Plan Source

<!-- Identifies which plan substrate orc-tower reads for the "what next"
     project header (per the v1.x sprint-orchestration spec §4.3).
     The source of truth is `methodology.planning` in the tower-side
     profile.md; this section is the project-readable mirror. If the
     two disagree, that is itself a coord-doc-stale signal. -->

- Type: inline
- Path: this document (`## Active Sprint Plan` section)
- Active unit: sprint-1

## Sprint Goals

- **Bootstrap a typed contract between the software (Pi-4 brain) and hardware (Pi-Zero camera node) so both agents can develop in parallel against stubs.**
- Pi-4 side: ingest a fake rip + fake capture session and produce a paired disc folder with a valid `manifest.json`.
- Pi-Zero side: expose a documented HTTP capture endpoint that returns burst image paths, runnable against a real Pi camera.
- Out of scope this sprint: OCR/AI metadata, review UI, Navidrome publication, real G4↔Pi rsync — they land in later sprints once the contract holds.

## Active Initiatives

<!-- Each initiative is one heading, e.g. `### Initiative — short name`,
     with a 1-2 sentence body. Include a status tag in the heading
     (e.g. "[in-flight]", "[blocked]", "[done]"). When `methodology.
     planning: inline` is configured, the Active Sprint Plan below
     replaces this section's role; treat this one as a high-altitude
     narrative summary or omit. -->

- _None yet._

## Active Sprint Plan

<!-- Lightweight task list for the current sprint when `methodology.
     planning: inline` is configured. orc-tower's InlineArtifactSource
     parses this section. Format:

       - [ ] {agent: backend, id: my-task} Body of the task
       - [-] {agent: frontend, depends: my-task} Another task
       - [x] {agent: docs} A done task

     Status:
       - [ ]   pending
       - [-]   in-progress
       - [x]   done
       - [!]   blocked

     Metadata in `{...}` is optional and precedes the body:
       - agent     — must match an entry in `## Agent Roster`
       - depends   — comma-separated; numeric (1-indexed within this
                     section) or slug (matches another task's `id:`)
       - id        — optional slug; makes the task referenceable

     Edit this section directly to add/remove/reorder tasks. orc-tower
     never writes to it; ratification cards propose entries elsewhere
     (Activity Log, Decision Log) but plan changes are author-driven.

     When every task reaches [x], SprintHeader surfaces kickoff buttons
     ("Run sprint review →" / "Plan next sprint →") that pre-fill
     SendPromptModal with the relevant template. The warren never
     auto-sends — the confirmation gate is sacred (CLAUDE.md §3.6).
     See: docs/design/2026-05-05-sprint-kickoff-flow.md -->

### Wave 1 — Contracts + foundations (parallel-safe)

- [ ] {agent: software, id: contract-capture-http} Draft `docs/design/capture-http-contract.md` — the HTTP contract between Pi-4 brain and Pi-Zero camera node. Spec `POST /capture {session_id, burst_count}` → `{capture_id, started_at, ended_at, image_paths[]}`; `GET /healthz`; error shape; LAN-only no-auth posture for v1; JPEG format; path semantics (server-local absolute). Hardware agent reviews before Wave 2.

- [ ] {agent: software, id: test-disc-folder-layout} Failing test: `prepare_disc_folder(disc_id, root) -> Path` creates the standard layout. Covers (a) creates `captures/`/`audio/`/`logs/`/`review/`; (b) writes initial `manifest.json` with `disc_id`, `schema_version`, `created_at`, `status="captured"`; (c) refuses to overwrite an existing populated folder; (d) idempotent for the same disc-id when folder is empty.

- [ ] {agent: software, id: test-ingest-watcher} Failing test: `IngestWatcher` detects new rip directories under `data/incoming/`. Covers (a) new dir triggers `RipDetected` with `rip_id`, `path`, `detected_at`; (b) ignores partial writes; (c) does not re-fire for the same rip.

- [ ] {agent: hardware, id: capture-service-skeleton} Skeleton FastAPI service in `src/cd_archivist/camera/service.py`. `uvicorn cd_archivist.camera.service:app` boots; `GET /healthz` returns `{ok: true, sensor: "unknown"}`; `POST /capture` returns 501 with a clear not-implemented body.

- [ ] {agent: hardware, id: capture-backend-survey} Write `docs/operations/camera-backend-survey.md`: short note on `picamera2` vs `cv2.VideoCapture` vs `fswebcam`, which Pi Camera revision is on hand (user has an older Pi camera + a couple USB webcams), recommended backend, install steps.

### Wave 2 — Implementations (depends: Wave 1)

- [ ] {agent: software, depends: test-disc-folder-layout, id: impl-disc-folder-layout} Implement `prepare_disc_folder` (new `src/cd_archivist/disc_folder.py` or extend `manifest_io.py`). Wave 1 tests pass.

- [ ] {agent: software, depends: test-ingest-watcher, id: impl-ingest-watcher} Implement `IngestWatcher` using `watchdog`. Wave 1 tests pass; runs against `data/incoming/` from `config/default.yaml`.

- [ ] {agent: software, depends: contract-capture-http, id: impl-capture-client} Implement `CaptureClient` (HTTP client, lives on brain) in `src/cd_archivist/camera/client.py`. Tests in `tests/test_capture_client.py` cover success path, timeout, HTTP 5xx, malformed response — typed errors throughout. Uses `httpx`; tests run against a pytest-managed fake HTTP server.

- [ ] {agent: hardware, depends: contract-capture-http, depends: capture-backend-survey, id: impl-capture-burst} Implement burst capture in `src/cd_archivist/camera/capture.py` using the selected backend. `capture_burst(out_dir, count, session_id) -> list[Path]` writes N JPEGs (e.g. `disc_front_001.jpg`); includes a `--fake` mode emitting canned bytes for CI; unit tests in `tests/test_capture_burst.py`.

- [ ] {agent: hardware, depends: impl-capture-burst, id: wire-capture-service} Replace the 501 in `POST /capture` with the real call; service tests pass against `--fake` backend; `GET /healthz` reports configured sensor name.

### Wave 3 — Integration (depends: Wave 2)

- [ ] {agent: software, depends: impl-ingest-watcher, depends: impl-capture-client, id: integration-pipeline-stub} End-to-end stub test: ingest watcher detects a fake rip, calls capture-client against a hardware-side fake server, pairs them via `best_timestamp_pair`, writes a manifest. `tests/test_pipeline_integration.py` covers happy path + the three failure modes (no capture, no rip, ambiguous match → review/).

- [ ] {agent: hardware, depends: wire-capture-service, id: run-capture-against-real-rig} Run the FastAPI capture service on actual Pi Zero with a real camera; capture 5 sample bursts of a CD; record observations (focus distance, lighting, glare, exposure) in `docs/operations/sprint-1-rig-notes.md`; commit sample JPEGs under `docs/operations/sample-captures/`. Surface blockers via decision cards.

- [ ] {agent: software, id: docs-sprint1-recap} Update `README.md` "Current status" to reflect sprint-1 reality + deferred items.

## Agent Roster

<!-- O5=A — owns / doesNotTouch live here, not in per-agent profiles. The
     dashboard reads this table to flag pane activity that touches another
     agent's doesNotTouch territory. -->

| Agent | Owns | Does not touch |
|---|---|---|
| software | `src/cd_archivist/{models,manifest_io,disc_id,disc_folder,pairing,ingest,server,review}`, `tests/`, `docs/design` | `src/cd_archivist/{camera,detection,sync}`, `hardware/`, `scripts/` |
| hardware | `src/cd_archivist/{camera,detection,sync}`, `hardware/`, `scripts/`, `docs/operations` | `src/cd_archivist/{models,manifest_io,pairing,server}` |

Both panes run Claude Code. The capture HTTP contract (Wave 1, `contract-capture-http`) is the meeting point — software builds the client, hardware builds the server, both agree on the wire shape before Wave 2 implementations start.

## Decision Log

<!-- Each entry: `### {{date}} — {{decision-id}} — {{summary}}` with a
     short body. Tower's audit log (~/.orc-tower/<slug>/audit/) is
     canonical for decision-request resolutions; this section is the
     project-readable mirror (N7) — orc proposes entries via
     ratification cards. -->

_No decisions yet._

## Ratification Log

<!-- Same shape as Decision Log; entries land here when a
     ratification-needed card resolves with kind "ratified". -->

_No ratifications yet._

## Contract Changes

<!-- API / schema / coord-doc-template changes that other agents must
     respect. Each entry: `### {{date}} — {{summary}}` + body listing
     before/after. The dashboard surfaces unprocessed entries as
     "contract changes since you last looked." -->

_No contract changes yet._

## Blockers

<!-- One bullet per active blocker. Format:
     `- [<agent>] <one-line blocker> — <link or reference>`. Resolved
     blockers move to the Activity Log. -->

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

### 2026-05-13 — orc — sprint-1 authored + workspace launched

- project adopted by orc-tower
- sprint-1 goals + 12-task wave plan committed (Wave 1 contracts, Wave 2 implementations, Wave 3 integration)
- agent roster: software + hardware, both Claude Code
- workspace launched: `tmax launch cd-archivist-sprint`
  - **tmax workspace name:** `cd-archivist-sprint`
  - **tmux session name:** `cd-archivist-cd-archivist-sprint` (composed by tmax, asymmetric — capture for warren PATCH per sibling-agent spec `docs/superpowers/specs/2026-05-12-orc-pane-in-left-drawer-and-idle-ping-design.md`)
  - panes verified: %16 orc-agent (orc-tower cwd), %17 software (cd-archivist cwd), %18 hardware (cd-archivist cwd)
- orc-agent orientation prompt sent next
