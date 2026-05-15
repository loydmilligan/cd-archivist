---
project: cd-archivist
sprint: sprint-3
created: 2026-05-14T00:00:00.000Z
updated: 2026-05-14T00:00:00.000Z
---

# cd-archivist — coordination doc (sprint-3)

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
- Active unit: sprint-3

## Sprint Goals

- **Polish from the sprint-2 hardware bring-up.** Seven concrete fixes
  surfaced by the 2026-05-14 real-rig E2E: visible RIP progress, a
  per-tick liveness signal distinct from per-transition timestamps,
  cdplay scope-aware stop/start (mpv lives in the user manager on the
  dogfood CM4 — system-scope `systemctl stop` can't see it), graceful
  degradation when the log directory isn't writable, log-tail
  rate-limiting when `/dev/sr0` is missing, RIP-failure recovery (state
  no longer sticks at `RIP` until a process restart), and auto-scrolling
  log tail with a follow toggle.
- **Capture-timing redesign — eject-time capture.** Move `capture_disc`
  from the STABILIZE→RIP transition to *after* `drive.eject(device)` in
  the EJECT handler so the camera sees the disc face on an open tray
  rather than the side of the rig on a closed tray. New flow:
  `IDLE → WAITING → STABILIZE → RIP → EJECT (tray opens) → CAPTURE
  (tray open, disc visible) → IDLE`. Manifest writes split: rip-result
  lands at end-of-RIP (so a successful rip is preserved even if the
  later capture fails); captures land at end-of-CAPTURE.
- **Read-only review UI on `/library`.** A second FastAPI surface — the
  library browser — lets the operator see what's been captured, audit
  it, and play back FLACs in the browser before any further pipeline
  work. Read-only this sprint; editing comes later. Dressed in the same
  Mash Co. tokens as the status surface (`archivist/service/static/
  tokens.css`), card grid with semantic-color left-border accents per
  rip status.
- **TDD discipline preserved.** Every implementable unit lands as a
  `test-X` in Wave 1 and an `impl-X` in Wave 2. New review-UI endpoints
  use FastAPI's `TestClient`; the seven polish items each get a
  targeted test where applicable (fallback-to-stderr logging,
  `last_tick_at` field on `LoopState`, ERROR state transition,
  rate-limited device-missing log lines, etc.).
- **No new manual smoke this sprint.** The existing
  `docs/operations/sprint-2-smoke.md` still covers the hardware path;
  the review UI is verified by `TestClient` plus a manual "browse to
  `/library` after a rip" check at the end of `impl-library`.

> **Scope-hierarchy reminder.** The capture-timing redesign (Bucket B)
> and the polish items that block usability of the running rig (Bucket A
> items 1, 3, 6) are the load-bearing scope this sprint — without them
> the dogfood loop is painful to use. The review UI (Bucket C) is the
> visible-progress scope; if it slips, the polish + capture-timing work
> still ships and the rig becomes pleasant to operate.

## Active Initiatives

<!-- Each initiative is one heading, e.g. `### Initiative — short name`,
     with a 1-2 sentence body. Include a status tag in the heading
     (e.g. "[in-flight]", "[blocked]", "[done]"). When `methodology.
     planning: inline` is configured, the Active Sprint Plan below
     replaces this section's role; treat this one as a high-altitude
     narrative summary or omit. -->

- _None — sprint-3 plan below is the substrate._

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
     (Activity Log, Decision Log) but plan changes are author-driven. -->

<!-- What ships in sprint-4+ (out of scope here):
     - OCR / AI metadata extraction from disc photos (planned via
       OpenRouter per `D-ocr-openrouter` in operator memory)
     - Discogs / MusicBrainz lookup
     - Navidrome / music serving
     - Editable review UI (tag corrections, manual track-name fixes)
     - `archivist.service` systemd unit (still postponed per
       `D-systemd-defer`)
     - Containerization / Docker (still postponed per `D-docker-postpone`)
     - The Mash Co. README "Products in scope" cd-archivist addition
       (cross-repo touch, operator-owned) -->

### Wave 1 — Failing tests (parallel-safe)

#### Bucket A — sprint-2 polish

- [x] {agent: pipeline, id: test-rip-progress} Failing tests for parsing
  cdparanoia's per-track stderr progress and surfacing it on
  `LoopState`. Add a `rip_progress: str | None` field to
  `archivist/service/app.py::LoopState` (default `None`) and a parser
  helper `parse_cdparanoia_progress(line: str) -> str | None` (location:
  `archivist/pipeline/rip.py` or a sibling `archivist/pipeline/
  rip_progress.py` — author's call). Parser cases: (a) a "Ripping from
  sectors..." track-N line yields `"track 4/12, 0%"`-shape; (b) a `##:
  -2 [wrote]` smiley/percent line updates the percent for the in-flight
  track; (c) lines that aren't progress return `None`. Then a status
  test: `GET /api/status` returns `rip_progress` in the JSON when set,
  `None` when not. The wiring to actually update the field while ripping
  lands in `impl-rip-progress`.
  - **Acceptance:** New file `tests/pipeline/test_rip_progress.py` (or
    appended to `tests/pipeline/test_rip.py`) with ≥4 parser cases.
    `tests/service/test_app.py` gets one new case asserting
    `/api/status` round-trips `rip_progress`. Both fail until impl.

- [x] {agent: pipeline, id: test-last-tick} Failing tests for a new
  `last_tick_at: datetime` field on `LoopState` that updates every loop
  iteration (not just on transitions). The existing `last_updated` is
  renamed to `state_entered_at` and only updates on transitions
  (semantic clarity — see Contract Changes below). Tests: (a)
  `LoopState` has both fields with sensible defaults; (b) calling
  `loop.tick()` updates `last_tick_at` even when the state doesn't
  change (e.g. WAITING + `disc-ok` not yet stable → still WAITING, but
  `last_tick_at` advances); (c) state *transitions* update both
  `last_tick_at` and `state_entered_at`; (d) `/api/status` returns both
  fields as ISO strings. The HTML page rendering both ("WAITING
  (entered 2m ago, last tick 1s ago)") is verified by `test-status-ui-
  liveness` below.
  - **Acceptance:** Tests in `tests/state_machine/test_loop.py` and
    `tests/service/test_app.py`. Fail until impl. Note: this is a
    breaking rename of `LoopState.last_updated → state_entered_at`;
    captured under Contract Changes.

- [x] {agent: drivers, id: test-systemctl-scope} Failing tests for the
  scope-aware refactor of `archivist/drivers/systemctl.py`. Per
  `D-cdplay-scope` (Decision Log below), the chosen approach is
  **option (a)**: `stop_unit(name, *, scope: Literal["system","user"]
  = "system") -> bool` and `start_unit(name, *, scope=...) -> bool`,
  plus a new helper `find_unit_scope(name: str) -> Literal["system",
  "user"] | None` that runs `systemctl --user is-active <name>` and
  `systemctl is-active <name>` and returns whichever scope reports the
  unit (system wins on a tie). Tests: (a) `scope="system"` → argv is
  `["sudo", "systemctl", "stop", name]` (existing behavior); (b)
  `scope="user"` → argv is `["systemctl", "--user", "stop", name]` (no
  sudo — user-scope units don't need it); (c) `find_unit_scope` returns
  `"user"` when only the user-manager call returns `active`; (d)
  returns `"system"` when only the system call returns `active`; (e)
  returns `None` when neither does; (f) all-`False` paths still log and
  never raise.
  - **Acceptance:** Tests added to `tests/drivers/test_systemctl.py`.
    Existing 6 cases continue to pass after the signature gains a
    keyword-only param with a `"system"` default. New cases fail until
    impl.

- [x] {agent: pipeline, id: test-log-fallback} Failing tests for the
  graceful-degradation path in `archivist/__main__.py::_configure_
  logging`. When `log_path.parent` cannot be created (e.g.
  `PermissionError` writing under `/srv/...` from a laptop dev shell),
  the function logs a warning naming the path + the
  `ARCHIVIST_LOG_PATH` env var and falls back to stderr-only logging
  rather than raising. Tests: (a) happy path — writable parent → both
  handlers attached (StreamHandler + FileHandler); (b) `PermissionError`
  on `mkdir` → only StreamHandler attached, warning logged with the
  path and env-var name; (c) `OSError` on `FileHandler` construction
  (parent dir exists but file isn't creatable) → same fallback. Use
  `monkeypatch` on `Path.mkdir` and on `logging.FileHandler`.
  - **Acceptance:** New file `tests/test_main_logging.py` (placed at
    the top of `tests/` since `archivist/__main__.py` lives at the
    package root and there's no existing `tests/main/` dir). Three
    cases. Fails until `_configure_logging` is refactored.

- [x] {agent: drivers, id: test-drive-missing} Failing tests for
  distinguishing "device missing" from "device returned an error" in
  `archivist/drivers/drive.py`. Add a sentinel return value or a typed
  exception — proposal: extend the `DriveStatus` literal with
  `"device-missing"` and have `read_drive_status` catch `FileNotFound
  Error` from `os.open` and return that, while other `OSError`s still
  bubble (permission denied, I/O error, etc., are real failures the
  loop should see). Tests: (a) `FileNotFoundError` on `os.open` →
  returns `"device-missing"`, no log spam; (b) `PermissionError` →
  still raises (it's not transient); (c) the four existing
  `DriveStatus` codes still map as before. Then in
  `tests/state_machine/test_loop.py` add a test: with the drive
  callable returning `"device-missing"`, the loop logs the condition
  exactly once (a class-level `_logged_device_missing` flag, or a
  rate-limited helper) regardless of how many `tick()`s pass.
  - **Acceptance:** Tests appended to `tests/drivers/test_drive.py`
    and `tests/state_machine/test_loop.py`. Driver-level cases fail
    on the new literal; loop-level case fails on the rate-limit
    behavior. Existing 9 drive tests + existing loop tests still pass
    after the literal extension (the new value is never returned in
    the existing test paths).

- [x] {agent: pipeline, id: test-rip-error-recovery} Failing test for
  the RIP→ERROR (or RIP→WAITING-after-backoff) recovery path. Per
  `D-rip-failure-error` (Decision Log) the chosen recovery is a
  terminal `ERROR` state that the loop sits in until the operator ejects
  the disc (tray-open observed → returns to IDLE). Add `ERROR` to the
  `State` enum. Wire `_from_rip` so that if `rip_disc` raises *or*
  returns a `RipRecord(status="fail")`, the loop: (i) writes the
  manifest with the failure recorded (`status="rip_failed"`,
  `last_rip_status="fail"`), (ii) calls `services.start_unit` for
  cdplay (the existing `_cdplay_stopped` invariant), (iii) transitions
  to `ERROR`. From `ERROR`, the only out is `tray-open` →
  `EJECT`-equivalent cleanup → `IDLE`. Tests: (a) `rip_disc` raises →
  cdplay restarted, manifest reflects failure, state == ERROR; (b)
  `rip_disc` returns `status="fail"` → same; (c) ERROR + `tray-open` →
  IDLE with `_cycle` cleared; (d) ERROR + any other drive status →
  stays ERROR (no spinning). The existing
  `test_rip_raise_still_starts_cdplay` (the crash-recovery invariant)
  must still pass — this is a strict superset.
  - **Acceptance:** Tests added to `tests/state_machine/test_loop.py`.
    Four new cases plus existing crash-recovery test still passing.
    Fails until impl-rip-error-recovery.

- [x] {agent: pipeline, id: test-status-ui-liveness} Failing UI test
  for the status page rendering both timestamps ("entered Xm ago, last
  tick Ns ago"), and an auto-scrolling log tail with a "follow"
  toggle. Reuses the existing `tests/service/test_app.py`. Asserts:
  (a) `GET /` body contains `state_entered_at` and `last_tick_at`
  references in the JS (proves the polling loop reads both); (b) body
  contains a `data-follow="on"` attribute on the `<pre class="log">`
  element by default; (c) body contains a chip-style toggle button
  (look for `id="log-follow-toggle"` or class `chip`); (d) the JS
  contains a `scrollTop = scrollHeight` line gated on the follow flag
  (a substring check, not a runtime assertion). No DOM/JS evaluation —
  same posture as sprint-2's UI tests.
  - **Acceptance:** Test added to `tests/service/test_app.py`. Fails
    until `app.py` HTML/JS is updated.

- [x] {agent: pipeline, id: test-rip-progress-ui} Failing UI test for
  the RIP progress bar. Asserts: (a) the page contains an element with
  `id="rip-progress"` (or class `progress-bar`); (b) the JS reads
  `s.rip_progress` from `/api/status` and updates that element; (c)
  the bar uses `--sky` for the fill (active rip color, matching the
  existing card-accent semantics) and `--ink-2` for the track. No
  visual rendering test — same substring posture.
  - **Acceptance:** Test added to `tests/service/test_app.py`. Fails
    until impl-status-ui.

- [x] {agent: drivers, id: test-rip-stderr-stream} Failing tests for
  live-streaming cdparanoia stderr in `archivist/drivers/ripper.py`.
  Today `CDAudioRipper.rip` uses `subprocess.run(..., capture_output=
  True)` which buffers stderr until the process exits — on the
  2026-05-14 real-rig rip, cdparanoia ran 10 minutes, exited 0,
  produced no WAVs, and the only error surfaced was "cdparanoia exit
  0 produced no WAVs" with zero diagnostic context. Refactor target:
  `subprocess.Popen` with line-buffered stderr iteration; each line
  is (a) logged at INFO to the archivist logger and (b) passed to an
  optional `progress_callback: Callable[[str], None] | None` keyword
  argument. Tests use a fake `Popen` (monkeypatch
  `subprocess.Popen`) that yields three stderr lines with a small
  delay between each: assert (a) the callback is invoked **once per
  line, in order, before the process exits** (not buffered until
  exit — verify by recording call timestamps or by having the fake
  block on a sentinel after the second line and asserting the first
  two callbacks already fired); (b) each line is logged at INFO
  level via `caplog`; (c) on a non-zero exit code, the captured
  stderr lines are still accessible to the caller (either via the
  exception raised or a return-value attribute) so the failure is
  debuggable; (d) `progress_callback=None` (the default) doesn't
  raise. Pairs with `test-rip-progress` (the parser tests) — that
  task asserts what the parsed lines look like; this task asserts
  the lines reach the parser at all, in real time.
  - **Acceptance:** Tests added to `tests/drivers/test_ripper.py`.
    Four cases. Fail until `impl-rip-progress` lands the Popen
    refactor (which is the same impl task; this test enforces the
    streaming semantics).

- [ ] {agent: pipeline, id: test-log-stream} _Optional, can be deferred
  if Wave 1 is too wide_ — failing test for streaming cdparanoia
  stderr live to `/api/log` while RIP is in flight. The simplest impl:
  `rip_disc` opens the log file in append mode and writes parsed
  progress lines as they arrive, so the existing `_tail_log` deque
  picks them up on the next poll. Test: with a fake ripper that yields
  three progress lines, `/api/log?lines=10` after the rip contains all
  three. _Marked optional — drop if Wave 1 is too wide; the
  `rip_progress` field on `/api/status` is the load-bearing surface._
  - **Acceptance:** Test in `tests/pipeline/test_rip.py`. Fails until
    impl. **Optional — close as `[x]` with a "skipped, see Activity
    Log" entry if scope demands.**

#### Bucket B — capture-timing redesign

- [x] {agent: pipeline, id: test-capture-after-eject} Failing tests for
  the new capture-timing flow. State machine: STABILIZE → RIP (no
  capture) → EJECT (drive.eject + cdplay restart) → CAPTURE (settle
  sleep + capture_disc against the now-open tray) → IDLE. Add
  `EJECT_SETTLE_SECONDS = 3.0` constant in `archivist/state_machine/
  loop.py`. Tests in `tests/state_machine/test_loop.py`: (a) full
  happy-cycle now produces the new ordering — capture call observed
  *after* eject call (assert via the recorded fake call sequence); (b)
  the settle sleep fires (sleeper called with `EJECT_SETTLE_SECONDS`
  between eject and capture); (c) the manifest write splits into two
  — one at end-of-RIP recording the rip result (status=`"ripped"` or
  `"rip_failed"`, `rips: [rip_record]`, `pairings: [single_session]`,
  `captures: []`), one at end-of-CAPTURE recording the captures
  (`captures: [ambient, lit]`, status unchanged); (d) capture failure
  after a successful rip leaves the rip record intact in the manifest
  (status remains `"ripped"`, `rips` populated, `captures: []` with a
  note in `errors`); (e) cdplay restart still happens via the existing
  `_from_eject` try/finally — capture failures don't break the
  cdplay-paired invariant. Update existing `test_full_cycle` and
  `test_rip_raise_still_starts_cdplay` to reflect the new ordering.
  - **Acceptance:** Tests revised in `tests/state_machine/test_loop.
    py`. Existing tests that assert "capture before rip" flip to
    "capture after eject". Fails until impl-capture-after-eject.

- [x] {agent: pipeline, id: test-capture-sequence-update} Update the
  existing `tests/pipeline/test_capture.py` if any case asserts that
  `capture_disc` runs against a *closed* tray (none should — the
  function is a leaf operation that doesn't know about tray state, the
  flow change is in the caller). This task confirms the leaf
  invariants still hold after the call site moves: ambient → led_on →
  lit → led_off; LED restored in finally. **Likely a no-op edit** —
  close as `[x]` with an Activity Log note if the existing tests are
  already loop-state-agnostic.
  - **Acceptance:** Either confirmed-no-changes-needed (close with
    note) or minimal edits keeping all 4 cases green.

#### Bucket C — review UI

- [x] {agent: pipeline, id: test-library-list} Failing test for `GET /
  library`. Uses FastAPI `TestClient`. Tests: (a) returns 200,
  `text/html`; (b) under a fixture `discs_root` containing
  `CD_0001/`, `CD_0002/`, `CD_0003/` with manifests of varying status
  (`"ripped"`, `"rip_failed"`, `"created"`), the body contains all
  three disc-ids; (c) thumbnail src points to `/library/CD_NNNN/
  captures/<filename>` for the first lit capture (or first capture if
  no lit); (d) per-card metadata shows track count from
  `manifest.rips[0].tracks` length and the `created_at` ISO; (e) the
  card's left-border accent class corresponds to rip status
  (`card--moss` for ripped, `card--amber` for partial/created,
  `card--ember` for failed); (f) Mash Co. invariants still hold
  (`data-theme="dark"`, sentence case body copy, no emoji — reuse the
  helpers from the existing UI tests).
  - **Acceptance:** New file `tests/service/test_library.py`. Fails
    until `impl-library` adds the route. Six cases.

- [x] {agent: pipeline, id: test-library-detail} Failing test for `GET
  /library/CD_NNNN`. Tests: (a) returns 200 for an existing disc; (b)
  returns 404 for a non-existent disc; (c) body contains the formatted
  manifest dump (a `<pre>` with the JSON); (d) body contains 6
  thumbnail `<img>` tags (3 ambient + 3 lit) sourcing from
  `/library/CD_NNNN/captures/<filename>`; (e) body contains a track
  list with file sizes (formatted as KB/MB) for each FLAC under
  `audio/`; (f) each track has an HTML5 `<audio controls
  src="/library/CD_NNNN/audio/<filename>">` element so the browser can
  play it inline; (g) if `logs/` directory is populated, body includes
  a `<pre>` log tail (use the same `deque`-based tail helper as the
  status surface).
  - **Acceptance:** Cases added to `tests/service/test_library.py`.
    Fails until impl. Seven cases.

- [x] {agent: pipeline, id: test-library-asset-serving} Failing tests
  for the file-serving endpoints: `GET /library/CD_NNNN/captures/
  <filename>` and `GET /library/CD_NNNN/audio/<filename>`. Tests: (a)
  capture endpoint serves an existing JPG with content-type `image/
  jpeg`; (b) audio endpoint serves an existing FLAC with content-type
  `audio/flac` (so the browser's built-in audio player plays it
  inline); (c) path traversal attempts (`../../etc/passwd`, absolute
  paths, symlinks pointing outside `discs_root`) return 404, never
  serve out-of-tree files — verify by constructing a tmp `discs_root`
  with a fixture `CD_0001/captures/x.jpg` and asserting traversal
  attempts fail; (d) missing files return 404; (e) unknown disc-id
  returns 404. Uses FastAPI's `FileResponse`.
  - **Acceptance:** Cases added to `tests/service/test_library.py`.
    Five cases. Fails until impl. The path-traversal case is
    load-bearing — read-only browsing of arbitrary files would be a
    real bug.

### Wave 2 — Implementations

#### Bucket A — sprint-2 polish

- [ ] {agent: pipeline, depends: test-rip-progress, depends: test-rip-
  stderr-stream, id: impl-rip-progress} Implement the
  cdparanoia-progress parser, the live stderr-streaming refactor of
  the ripper, and wire both into `LoopState`. Add
  `parse_cdparanoia_progress(line: str) -> str | None` to
  `archivist/pipeline/rip.py` (or a sibling). Refactor
  `CDAudioRipper.rip` (in `archivist/drivers/ripper.py`) from
  `subprocess.run(..., capture_output=True)` to **`subprocess.Popen`
  with line-buffered stderr iteration**: `Popen(..., stderr=
  subprocess.PIPE, stdout=subprocess.PIPE, bufsize=1, text=True)`,
  then `for line in proc.stderr: ...` so each line is observed
  **as it arrives** rather than buffered until exit. For each
  stderr line: (a) log at INFO to the archivist logger via
  `logger.info(line.rstrip())` so live progress AND failures are
  visible in `/api/log` and the journal; (b) invoke the optional
  `progress_callback: Callable[[str], None] | None = None` keyword
  argument so the state machine can update `loop_state.rip_progress`
  live. Retain the captured stderr lines (e.g. accumulate into a
  list) so non-zero exit codes still surface diagnostic context to
  the caller — that's what made the 2026-05-14 silent failure
  unreadable. `archivist/pipeline/rip.py::rip_disc` accepts
  `progress_callback` and forwards it. The state machine's
  `_from_rip` passes a closure that runs `parse_cdparanoia_progress`
  on each line and writes the parsed value to
  `loop_state.rip_progress`. `LoopState.rip_progress: str | None =
  None` field added. `/api/status` JSON includes it. **This impl
  satisfies polish item #1 (visible RIP progress) and polish item #8
  (live stderr streaming / debuggable failures) together — they
  share the Popen refactor, splitting them would duplicate it.**
  - **Acceptance:** Both `test-rip-progress` and
    `test-rip-stderr-stream` cases pass. Existing `tests/drivers/
    test_ripper.py` still passes (the new keyword is optional with
    `None` default; the Popen refactor preserves the existing
    return contract on success). `ruff check` clean.

- [x] {agent: pipeline, depends: test-last-tick, id: impl-last-tick}
  Refactor `LoopState`: rename `last_updated → state_entered_at`, add
  `last_tick_at: datetime`. The state-machine `_set_state` updates
  both fields on transitions; a new `_tick_heartbeat()` method updates
  only `last_tick_at` and is called at the top of every `tick()`.
  Also update `archivist/__main__.py` if anywhere references
  `LoopState.last_updated` (a quick grep — there shouldn't be any
  outside the two files). `/api/status` returns both as ISO strings.
  Update the HTML page to render "entered Xm ago, last tick Ns ago"
  (covered by `impl-status-ui` below).
  - **Acceptance:** `tests/state_machine/`, `tests/service/`, full
    suite green. Note in Activity Log: this is the breaking rename
    captured under Contract Changes.

- [ ] {agent: drivers, depends: test-systemctl-scope, id: impl-systemctl-
  scope} Implement option (a) per `D-cdplay-scope`. `stop_unit(name,
  *, scope="system")` and `start_unit(name, *, scope="system")` gain
  the keyword-only param. Argv: `scope="system"` keeps `["sudo",
  "systemctl", action, name]`; `scope="user"` becomes `["systemctl",
  "--user", action, name]` (no sudo, the user manager is per-uid). Add
  `find_unit_scope(name)` that runs `systemctl is-active <name>`
  followed by `systemctl --user is-active <name>` (both with `check=
  False`); returns `"system"` if the first reports `active`, `"user"`
  if only the second does, `None` if neither. Update the entrypoint
  in `archivist/__main__.py::_Services` to call `find_unit_scope("cdplay.
  service")` once at startup and store the result; `stop_unit`/`start_
  unit` adapter methods then forward the cached scope. If discovery
  returns `None`, log a warning and pass `scope="system"` (today's
  behavior — best-effort). Update `docs/operations/cm4-setup.md` with
  a note about the user-scope sudoers fragment NOT being needed for
  the user-scope path.
  - **Acceptance:** `tests/drivers/test_systemctl.py` all pass. Full
    suite green. `docs/operations/cm4-setup.md` updated. `_Services`
    in entrypoint discovers scope at startup (one extra log line).

- [x] {agent: pipeline, depends: test-log-fallback, id: impl-log-fallback}
  Refactor `_configure_logging` in `archivist/__main__.py` to handle
  parent-mkdir failure: try `log_path.parent.mkdir(parents=True,
  exist_ok=True)` inside try/except `OSError`; on failure log to
  stderr (using a temporarily-configured root logger) a warning naming
  `log_path` and the `ARCHIVIST_LOG_PATH` env var, and skip the
  `FileHandler`. Same try/except around `FileHandler(log_path)`
  construction. The StreamHandler always attaches. The function
  always returns; FastAPI surface comes up regardless. `/api/log` will
  return empty when `log_path` doesn't exist (already handled by
  `_tail_log`).
  - **Acceptance:** `tests/test_main_logging.py` passes. Manual
    sanity: `ARCHIVIST_DISCS_ROOT=/tmp/foo python -m archivist`
    starts cleanly with stderr-only logs and a clear warning naming
    the unwritable default log path.

- [ ] {agent: drivers, depends: test-drive-missing, id: impl-drive-missing}
  Extend `DriveStatus` literal in `archivist/drivers/drive.py` to
  include `"device-missing"`. Wrap `os.open(device, ...)` in a
  try/except that catches **only** `FileNotFoundError` and returns
  `"device-missing"`; all other `OSError`s still bubble. `read_drive_
  status`'s docstring updated to document the new value. The state-
  machine side (`_logged_device_missing` rate-limit) lands in
  `impl-loop-device-missing` below. _drivers' part of this task is
  small; closes when `tests/drivers/test_drive.py` is green._
  - **Acceptance:** `tests/drivers/test_drive.py` all pass. Existing
    `eject` tests untouched.

- [ ] {agent: pipeline, depends: impl-drive-missing, id: impl-loop-device-
  missing} In `archivist/state_machine/loop.py`, add a class-level
  flag `_device_missing_logged: bool = False` (or use a `time.
  monotonic()`-based once-per-minute rate limiter). When `_drive()`
  returns `"device-missing"`, log a warning the first time and stay in
  IDLE. On any non-`"device-missing"` return, reset the flag so a
  subsequent disconnect is logged again. Loop never advances past
  IDLE while the device is missing.
  - **Acceptance:** New loop test from `test-drive-missing` passes.
    Existing loop tests still pass.

- [x] {agent: pipeline, depends: test-rip-error-recovery, id: impl-rip-
  error-recovery} Add `ERROR` to the `State` enum. Modify `_from_rip`:
  wrap `rip_disc` in try/except. On exception OR
  `rip_record.status == "fail"`: write the manifest with `status=
  "rip_failed"`, `last_rip_status="fail"`, the rip record (if any) in
  `rips`, and the pairing still attached; restart cdplay via the
  existing `_cdplay_stopped` mechanism; transition to `ERROR`. Add
  `_from_error` handler: on `tray-open` from `_drive()`, run the same
  cleanup as `_from_eject` (clear `_cycle`, clear `_stabilize_since`)
  and transition to `IDLE`; on any other status, stay in `ERROR`.
  Update the FastAPI status surface to map `ERROR` to the `--ember`
  card-accent color (already in the planned color scheme — just needs
  the case in the JS class-swap).
  - **Acceptance:** `tests/state_machine/` all pass including the new
    cases. Manual sanity: trigger a rip with a known-bad CD (or a
    fake ripper) — state lands in ERROR, eject returns to IDLE.

- [x] {agent: pipeline, depends: test-status-ui-liveness, depends: test-
  rip-progress-ui, id: impl-status-ui} Update `archivist/service/app.
  py::_PAGE_HTML`. Changes:
  1. **Liveness rendering** — under the existing `<div class="meta">`,
     replace the single "updated" line with two: "entered" (relative
     "Xm ago" computed in JS from `state_entered_at`) and "last tick"
     (relative "Ns ago" from `last_tick_at`). The relative-time helper
     is ~10 lines of vanilla JS.
  2. **RIP progress bar** — under the state-line, conditionally
     render a `<div id="rip-progress-wrap" hidden>` containing
     `<div id="rip-progress-track" class="progress-track"><div
     id="rip-progress-fill" class="progress-fill"></div></div>` with
     a sibling `<span id="rip-progress-label">`. CSS uses `--ink-2`
     for track, `--sky` for fill. JS shows the wrap when
     `s.rip_progress` is truthy; parses the percent from the string;
     sets `fill.style.width = pct + "%"`; sets the label text.
  3. **Auto-scroll log tail with follow toggle** — wrap the existing
     `<pre class="log">` in a flex column with a chip-style button
     `<button id="log-follow-toggle" class="chip" data-follow="on">
     follow</button>`. JS: maintain a `follow` boolean (default
     `true`); after each `pollLog()` update, if `follow`, set
     `pre.scrollTop = pre.scrollHeight`. Clicking the chip toggles
     `follow` and updates the button's `data-follow` attribute and
     visual state (use `--accent` for on, `--fg-quiet` for off).
     Detect manual scroll-up (e.g. `pre.addEventListener("scroll",
     ...)` checking distance from bottom > N px) and auto-disable
     follow — standard `tail -f` behavior.
  4. **ERROR state** — JS class-swap for `card--ember` when
     `s.state === "ERROR"`. Body title for ERROR: `"Something failed
     — see the log."` (sentence case, em-dash).
  - **Acceptance:** `tests/service/test_app.py` all pass. Manual
    sanity: `python -m archivist`, browse to `:8228/`, scroll log
    tail manually → follow toggles off; click chip → toggles back
    on, jumps to bottom.

#### Bucket B — capture-timing redesign

- [x] {agent: pipeline, depends: test-capture-after-eject, depends: impl-
  rip-error-recovery, id: impl-capture-after-eject} Restructure
  `archivist/state_machine/loop.py` per `D-eject-time-capture`:
  1. Remove the `capture_disc` call from `_from_stabilize`. STABILIZE
     after 2s now does: `stop_unit("cdplay.service", scope=...)`,
     `next_disc_id`, `prepare_disc_folder`, transition to RIP.
     `_cycle.captures` stays `None` until CAPTURE runs.
  2. `_from_rip` (per `impl-rip-error-recovery`) calls `rip_disc`,
     writes the **first manifest** (rip-result-now: `status=
     "ripped"`, `rips: [rip_record]`, `pairings: [single_session]`,
     `captures: []`), transitions to EJECT. The pairing is attached
     here — single-session pairing is logically about "this rip",
     not "these captures".
  3. `_from_eject` calls `drive.eject(self._device)` then immediately
     `services.start_unit(_CDPLAY, scope=...)` in a try/finally
     (existing cdplay-paired invariant). After cdplay restart, sleep
     `EJECT_SETTLE_SECONDS = 3.0` via the injected sleeper, then
     transition to a new `CAPTURE` state — captures run *next* tick
     so the loop heartbeat is preserved (don't fold capture inline
     here; the open tray takes 2-4s to physically open and the user
     should see a state transition to CAPTURE in the UI).
  4. Add `_from_capture`: calls `capture_disc(disc_dir, camera=...,
     led=...)` against the disc folder; writes the **second
     manifest** (read-modify-write to add the captures without
     touching `status` or `rips`). On capture failure (any
     exception from `capture_disc` — it's not supposed to raise but
     defend anyway), append the error string to `manifest.errors`,
     leave `captures: []`, and proceed. Transition to IDLE; clear
     `_cycle`.
  5. Update `Cycle` dataclass: `captures` no longer set in
     STABILIZE; populated in `_from_capture`.
  - **Acceptance:** `tests/state_machine/test_loop.py` all pass
    including the new capture-after-eject cases. `tests/pipeline/
    test_capture.py` still passes (leaf op unchanged). The
    cdplay-paired invariant test still passes.

#### Bucket C — review UI

- [ ] {agent: pipeline, depends: test-library-list, depends: test-library-
  detail, depends: test-library-asset-serving, id: impl-library} Add
  the library browser to `archivist/service/app.py`. `create_app(loop_
  state, log_path, *, discs_root: Path | None = None) -> FastAPI`
  gains an optional `discs_root`; `archivist/__main__.py` passes the
  configured `discs_root` through. New routes:
  - `GET /library` — scans `discs_root` for `CD_\d{4}/manifest.json`,
    reads each via `read_manifest`, sorts by `disc_id` descending
    (newest first), renders a Mash Co. card grid. Per card: thumbnail
    (first `lit` capture, or first capture, or a placeholder
    `<div class="thumb-empty">no capture</div>`); disc-id as the
    card title; rip status badge; track count; created timestamp
    (relative "2h ago"); click goes to `/library/CD_NNNN`.
    Card-accent color via class:
      - `card--moss` if `manifest.status == "ripped"` and
        `manifest.rips[0].status == "success"`;
      - `card--amber` if `status == "ripped"` and
        `rips[0].status == "partial"` (or `status == "created"`);
      - `card--ember` if `status == "rip_failed"` or
        `rips[0].status == "fail"`.
  - `GET /library/CD_NNNN` — single disc page: card with the formatted
    manifest dump in a `<pre>` (use `manifest.model_dump_json(indent=
    2)`); a 6-thumbnail grid (each clickable to the full-size capture
    URL — open in new tab via `target="_blank"`); a track list with
    file sizes (`format_bytes(path.stat().st_size)` helper) and
    inline `<audio controls preload="none" src="...">` per FLAC; if
    `logs/` directory is populated, a `<pre class="log">` tail.
  - `GET /library/{disc_id}/captures/{filename}` — `FileResponse(disc_
    dir / "captures" / filename, media_type="image/jpeg")`. Validate
    `disc_id` matches `CD_\d{4}`; resolve the path via
    `(disc_dir / "captures" / filename).resolve()` and assert it's
    under `disc_dir.resolve()` (path-traversal guard); 404 on any
    failure.
  - `GET /library/{disc_id}/audio/{filename}` — same shape with
    `media_type="audio/flac"`.

  Both pages reuse the existing `tokens.css` and the same Mash Co.
  patterns: dark-first, sentence case, no emoji, eyebrows ≤2 words,
  card has full border + 3px left-border accent. Add a top nav strip
  to both `/` (the status page) and `/library` so the operator can
  switch between them — small `<nav>` with two text links in the page
  header.
  - **Acceptance:** All `tests/service/test_library.py` cases pass.
    Existing `tests/service/test_app.py` still passes (the `/`
    surface gains a nav link but no behavior change). Manual sanity:
    `python -m archivist` against a `discs_root` with at least one
    `CD_NNNN/`, browse to `/library`, see the grid, click into a
    disc, see captures + manifest + playable FLACs. Any path-
    traversal attempt 404s.

## Agent Roster

<!-- O5=A — owns / doesNotTouch live here, not in per-agent profiles. The
     dashboard reads this table to flag pane activity that touches another
     agent's doesNotTouch territory. -->

| Agent | Owns | Does not touch |
|---|---|---|
| drivers | `archivist/drivers/{drive,led,camera,ripper,systemctl,usb_discovery}.py`, `archivist/models/manifest.py`, `tests/drivers/` | `archivist/pipeline/`, `archivist/state_machine/`, `archivist/service/`, `archivist/__main__.py` |
| pipeline | `archivist/pipeline/{disc_id,folder,pairing,capture,rip,rip_progress}.py`, `archivist/state_machine/`, `archivist/service/` (incl. `archivist/service/static/`), `archivist/__main__.py`, `tests/pipeline/`, `tests/state_machine/`, `tests/service/`, `tests/test_main_logging.py`, `tests/__init__.py`, `tests/conftest.py`, `pyproject.toml`, `ruff.toml`, `docs/operations/cm4-setup.md`, `docs/operations/sprint-2-smoke.md`, `docs/coordination/sprint-3.md` | `archivist/drivers/` internals (consumes their public interfaces) |

Same two agents as sprint-1 / sprint-2 — no new role added. Drivers
picks up two scoped changes: `read_drive_status` gains a `"device-
missing"` literal value, and `systemctl.{stop,start}_unit` gains a
`scope=` keyword + a new `find_unit_scope` helper. Pipeline does
everything else: state-machine restructure (capture-after-eject + ERROR
state + rate-limited device-missing logging + `last_tick_at` field),
status UI updates (RIP progress bar, liveness rendering, log-follow
toggle), and the new review UI (`/library` list + detail + asset
serving).

**Cross-agent meeting points expand:** sprint-2 had `archivist.drivers.
camera.capture_frame_with_recovery`, `archivist.drivers.drive.eject`,
`archivist.drivers.systemctl.{stop_unit,start_unit}`. Sprint-3 changes
the `systemctl` signatures (scope kwarg) and the `drive.read_drive_
status` return type (extended literal) — both consumed by `archivist/
state_machine/loop.py`. Captured under Contract Changes.

**External read-only dependency:** the **Mash Co. design system** at
`/home/loydmilligan/Projects/Mash Co. Design System/` — the review UI
extends the existing token consumption (`archivist/service/static/
tokens.css`) but does not re-vendor or update tokens this sprint. The
README "Products in scope" addition remains an operator-owned
cross-repo follow-up.

## Decision Log

<!-- Each entry: `### {{date}} — {{decision-id}} — {{summary}}` with a
     short body. Tower's audit log (~/.orc-tower/<slug>/audit/) is
     canonical for decision-request resolutions; this section is the
     project-readable mirror (N7) — orc proposes entries via
     ratification cards. -->

### 2026-05-14 — D-cdplay-scope — `systemctl` wrapper gains a `scope=` kwarg; entrypoint auto-discovers cdplay's scope

The sprint-2 `systemctl` wrapper assumed system scope (`["sudo",
"systemctl", ...]`). On the dogfood CM4, `cdplay` is launched via
`systemd-run --user` and lives in the user manager — the system-scope
wrapper can't see it, so `stop_unit("cdplay.service")` returns
`False` and the rip races against an active mpv process holding
`/dev/sr0`.

**Chosen approach: option (a) from the task body — scoped wrapper +
auto-discovery.** `stop_unit` and `start_unit` gain a keyword-only
`scope: Literal["system", "user"] = "system"`. A new helper
`find_unit_scope(name) -> Literal["system","user"] | None` runs
`systemctl is-active` against both managers and returns whichever
reports the unit; the `__main__.py::_Services` adapter calls it once
at startup for `cdplay.service` and caches the result.

**Why option (a) over (b) `release_drive(/dev/sr0)` via `fuser -k`:**
(a) preserves the by-name-restart property the cdplay-paired
invariant depends on (kill-by-device gives no restart hook); (a) is
the smaller change to existing tests; (a) leaves the door open to
managing other system services later (e.g. a future
`mpd.service`-based cdplay) without re-architecting. The `fuser -k`
approach stays available as a future fallback if the user-scope path
turns out to be insufficient on a different rig.

Implications: `archivist/drivers/systemctl.py` signature change
(keyword-only param with backwards-compatible default — existing
callers continue to work); new `find_unit_scope` helper; `archivist/
__main__.py::_Services` discovers scope at startup and forwards it;
`docs/operations/cm4-setup.md` updated to note the user-scope path
doesn't need the system-scope sudoers fragment. Tracked under
Contract Changes.

### 2026-05-14 — D-eject-time-capture — capture moves from STABILIZE→RIP to after EJECT

Sprint-2 captures fire while the tray is still closed. The cam ends
up looking at the side of the rig, not the disc face. The agreed fix
is to move `capture_disc` to *after* `drive.eject(device)` so the
camera sees an open tray with the disc visible.

**New state flow:** `IDLE → WAITING → STABILIZE → RIP → EJECT (tray
opens) → CAPTURE (tray open, disc visible) → IDLE`. CAPTURE becomes a
real, observable state in the FastAPI status UI (it was previously
folded into the STABILIZE→RIP tick).

**Settle delay:** `EJECT_SETTLE_SECONDS = 3.0` — the tray motor takes
2-4s to physically open after `drive.eject` returns. The settle sleep
fires inside `_from_eject` after cdplay restart but before the state
transitions to CAPTURE; the actual `capture_disc` call happens in the
next tick's `_from_capture`. This preserves the loop heartbeat (one
state advance per tick) and gives the FastAPI UI a chance to render
"capturing".

**Manifest write split:** previously one atomic write at end-of-RIP
recorded captures + rip + pairing together. Now the write splits in
two: `_from_rip` writes rip-result-now (`status="ripped"` or
`"rip_failed"`, `rips`, `pairings`, `captures: []`); `_from_capture`
does a read-modify-write to add the captures without touching the
rip-side fields.

**Trade-off explicitly accepted:** a failed rip means no preserved
photo (the loop transitions to ERROR, never reaches CAPTURE). The
trade-off the other way — capturing first then ripping — would
preserve the photo of a disc that fails to rip but defers the rip
failure observation. Rip-result is the load-bearing artifact; photo
is supplementary metadata.

Implications: state-machine restructure; CAPTURE becomes an observable
state with its own card-accent color (currently `--sky` per the
WAITING/STABILIZE/CAPTURE/RIP grouping — keep it `--sky` since it's
still "in flight"); manifest write is no longer atomic across rip +
capture (each is atomic on its own). Test changes: any "capture
before rip" assertions flip; `tests/state_machine/test_loop.py` and
`tests/pipeline/test_capture_sequence.py` (if it asserts call order)
need updating.

### 2026-05-14 — D-rip-failure-error — RIP failure transitions to a terminal `ERROR` state

Sprint-2's `_from_rip` had no failure path — a `rip_disc` exception
was caught by the top-level `tick()` except block (`logger.exception
("tick raised; continuing")`), but the state never advanced past
`RIP`. Observed on the 2026-05-14 smoke: cdparanoia
`FileNotFoundError` left the loop stuck at `RIP` indefinitely, only
recoverable by restarting the process.

**Chosen recovery: terminal `ERROR` state, eject-to-clear.** RIP
failure (exception OR `RipResult.status == "fail"`) writes a
failure-marked manifest (`status="rip_failed"`, `last_rip_status=
"fail"`), restarts cdplay (existing `_cdplay_stopped` invariant), and
transitions to `ERROR`. From `ERROR`, the only out is observing
`tray-open` from `_drive()` — the operator ejects the (presumed
broken) disc by hand, which returns the loop to IDLE via the same
`_cycle`-clearing cleanup as `_from_eject`. Any other drive status
keeps the loop in ERROR.

**Why a terminal state and not auto-retry-after-backoff:** the
sprint-2 failure mode (cdparanoia FileNotFoundError) was a permanent
condition on that disc — retrying without operator intervention would
have looped forever. A terminal state forces the operator to
acknowledge the failure (by ejecting); auto-retry can be added later
behind a config flag if the failure-mode mix shifts toward transient
failures.

Implications: `State` enum gains `ERROR`; `_from_rip` wraps `rip_
disc` in try/except and checks `RipResult.status`; new `_from_error`
handler; FastAPI status UI maps ERROR to `--ember` card-accent.
Removes the "tick raised; continuing" silent-swallow for RIP failures
specifically — other tick exceptions are still logged-and-continued.

## Ratification Log

<!-- Same shape as Decision Log; entries land here when a
     ratification-needed card resolves with kind "ratified". -->

_No ratifications yet._

## Contract Changes

<!-- API / schema / coord-doc-template changes that other agents must
     respect. Each entry: `### {{date}} — {{summary}}` + body listing
     before/after. The dashboard surfaces unprocessed entries as
     "contract changes since you last looked." -->

### 2026-05-14 — `archivist.drivers.systemctl` signature gains scope kwarg

- **Before:** `stop_unit(name: str) -> bool`, `start_unit(name: str)
  -> bool`. argv always `["sudo", "systemctl", action, name]`.
- **After:** `stop_unit(name: str, *, scope: Literal["system","user"]
  = "system") -> bool`, same on `start_unit`. When `scope="user"`,
  argv is `["systemctl", "--user", action, name]` (no sudo). New
  helper `find_unit_scope(name: str) -> Literal["system","user"] |
  None`. Default keeps existing call sites working without changes.
- **Consumers:** `archivist/__main__.py::_Services` (forwards a cached
  scope discovered at startup); `archivist/state_machine/loop.py` (no
  direct change — `_Services` is the seam).

### 2026-05-14 — `archivist.drivers.drive.DriveStatus` literal extended

- **Before:** `Literal["no-disc", "tray-open", "drive-not-ready",
  "disc-ok"]`. `read_drive_status` raises `OSError` (including
  `FileNotFoundError`) when the device path doesn't exist.
- **After:** `Literal["no-disc", "tray-open", "drive-not-ready",
  "disc-ok", "device-missing"]`. `read_drive_status` catches
  `FileNotFoundError` only and returns `"device-missing"`; other
  `OSError`s (`PermissionError`, `BlockingIOError`, real I/O errors)
  still raise.
- **Consumers:** `archivist/state_machine/loop.py` (handles
  `"device-missing"` with a once-per-disconnect log line, never
  advances past IDLE while the device is gone). The FastAPI status
  surface renders this as a state value when surfaced.

### 2026-05-14 — `archivist.service.app.LoopState` field rename + addition

- **Before:** `LoopState(state, disc_id, last_rip_status, last_updated)`.
- **After:** `LoopState(state, disc_id, last_rip_status,
  state_entered_at, last_tick_at, rip_progress)`. `last_updated` is
  renamed to `state_entered_at` (semantic clarity — it only updated on
  transitions); `last_tick_at` is new and updates on every loop
  iteration; `rip_progress: str | None` is new (cdparanoia per-track
  parse, e.g. `"track 4/12, 23%"`).
- **Consumers:** `archivist/state_machine/loop.py` (the loop is the
  sole writer); `archivist/service/app.py::api_status` (returns all
  three new/renamed fields as ISO strings / strings); the inline HTML
  page (renders the relative-time pair and the progress bar). No
  external consumers — `LoopState` is a private contract between the
  loop and the service.

### 2026-05-14 — `archivist.service.app.create_app` gains optional `discs_root`

- **Before:** `create_app(loop_state, log_path) -> FastAPI`.
- **After:** `create_app(loop_state, log_path, *, discs_root: Path |
  None = None) -> FastAPI`. When `discs_root` is provided, the
  `/library`, `/library/{id}`, `/library/{id}/captures/{file}`, and
  `/library/{id}/audio/{file}` routes are registered. When `None`,
  these routes are not registered (404) — keeps the surface
  back-compat for any future test that constructs `create_app`
  without a discs root.
- **Consumers:** `archivist/__main__.py::main` (passes the env-driven
  `discs_root`); tests in `tests/service/test_library.py` (pass a
  fixture root).

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

### 2026-05-14 — drivers — Wave 1 failing tests landed (3 tasks, 3 commits)

All drivers-owned Wave 1 tasks closed. Loop-side assertions for
`test-drive-missing` deferred to pipeline (state-machine territory).

- **test-systemctl-scope** (`3f21947`) — 8 cases appended to
  `tests/drivers/test_systemctl.py` per `D-cdplay-scope` option (a).
  Three test the `scope=` kwarg on the existing API (TypeError until
  impl): `scope="system"` keeps `["sudo", "systemctl", ...]`,
  `scope="user"` switches to `["systemctl", "--user", ...]` for both
  stop and start (no sudo on user scope). Five test the new
  `find_unit_scope(name) -> Literal["system","user"] | None`
  (ImportError until impl): user-only, system-only, both-active tie
  goes to system, neither-active returns `None`, `FileNotFoundError`
  on systemctl returns `None` with a warning. `find_unit_scope` is
  imported lazily inside `_find_unit_scope()` so the existing 6
  cases still PASS at collection.
- **test-drive-missing** (`dcb9bba`) — 2 cases appended to
  `tests/drivers/test_drive.py`. `FileNotFoundError` on `os.open`
  → `read_drive_status` returns the new `"device-missing"` literal
  (fails today: raw `FileNotFoundError` bubbles); `PermissionError`
  still raises (passes today — confirms we're not over-catching).
  The matching loop-level rate-limited-log test belongs to
  `tests/state_machine/test_loop.py`, which pipeline owns; left for
  them to land alongside `impl-loop-device-missing`.
- **test-rip-stderr-stream** (`d132e9f`) — 4 cases appended to
  `tests/drivers/test_ripper.py` for the Popen + live-streaming
  refactor. The load-bearing case is
  `test_rip_stderr_callback_fires_before_process_exit`: a
  `_FakePopen` blocks on a gate after emitting 2 lines, the test
  runs `rip()` in a thread and asserts ≥2 callbacks have fired
  *before* `wait()` returns — proving the new shape isn't just
  buffered playback. Why this refactor: the 2026-05-14 real-rig
  rip exited 0 with zero diagnostic context because
  `capture_output=True` buffered everything until exit. The
  `progress_callback=None` default test trivially passes today —
  future-proofs the API shape post-impl.

Verified: full drivers suite passes the previously-green cases.
`ruff check tests/drivers/` clean.

### 2026-05-14 — pipeline — Wave 1 failing tests landed (10 tasks, 10 commits)

All pipeline-owned Wave 1 tasks closed; test-log-stream skipped per
operator instruction ("OPTIONAL — skip if Wave 1 gets too wide").

- **test-rip-progress** (0769ea6) — `tests/pipeline/test_rip_progress.py`
  with 5 parser cases; one new case in `tests/service/test_app.py`
  asserting `/api/status` round-trips a `rip_progress` field.
- **test-last-tick** (8a36a6a) — fixture and existing snapshot test
  in `tests/service/test_app.py` updated to construct LoopState with
  `state_entered_at` + `last_tick_at` (rename per Contract Changes);
  3 new cases in `tests/state_machine/test_loop.py` asserting the
  heartbeat semantics (transition advances both, no-transition tick
  only advances `last_tick_at`).
- **test-log-fallback** (cbeb6c3) — `tests/test_main_logging.py` with
  3 cases for `_configure_logging` stderr-only fallback when the log
  dir can't be created. Side cleanup: removed the legacy
  `tests/test_disc_id.py` + `tests/test_pairing.py` (referenced the
  dead `cd_archivist` package) and dropped the corresponding
  `--ignore-glob=tests/test_*.py` from `pyproject.toml`.
- **test-rip-error-recovery** (2c74d5a) — updated
  `test_rip_exception_still_restarts_cdplay` to assert the new
  terminal ERROR state (loop now catches the rip exception instead
  of letting it propagate); 3 new cases for `RipResult(status="fail")
  → ERROR`, `ERROR + tray-open → IDLE`, `ERROR + other → stays ERROR`.
- **test-status-ui-liveness** (c1cde00) — 2 cases asserting the page
  references both `state_entered_at` and `last_tick_at` in the JS;
  log tail has `data-follow="on"` + `id="log-follow-toggle"` and the
  scrollTop/scrollHeight follow logic.
- **test-rip-progress-ui** (cf4abd7) — 1 case asserting the page has
  an element with `id="rip-progress*"`, reads `s.rip_progress` from
  the polling JS, and uses `--sky` (fill) + `--ink-2` (track).
- **test-capture-after-eject** (e2f13b3) — Bucket B central piece:
  reshaped existing happy-path tests to reflect the post-eject
  capture flow (STABILIZE→RIP no longer fires camera/led; the cycle
  is 6 ticks not 5: IDLE→WAITING→STABILIZE→RIP→EJECT→CAPTURE→IDLE).
  New cases: capture-after-eject ordering, sleeper(3.0) between
  eject and capture, two-write manifest split, capture failure
  preserves rip record.
- **test-capture-sequence-update** (2c4570b) — no-op close per task
  acceptance: `tests/pipeline/test_capture.py` is already
  loop-state-agnostic; the move is a caller restructure only.
- **test-library-list** (755689c) — new file
  `tests/service/test_library.py` with 6 list-page cases (HTML, all
  three disc-ids, thumbnails, semantic card-accent classes
  card--moss/amber/ember by status, track-count metadata, Mash Co.
  invariants reused from test_app.py).
- **test-library-detail** (2bd814b) — 7 detail-page cases (HTML,
  unknown→404, manifest dump in `<pre>`, 6 thumbnails, `<audio
  controls>` per FLAC with `/library/CD_NNNN/audio/...` src, file
  sizes formatted, log tail when `logs/` populated).
- **test-library-asset-serving** (e61e5d0) — 5 asset-serving cases
  including the load-bearing path-traversal guard (plants a secret
  outside discs_root and asserts traversal attempts never leak it).

**Skipped:** `test-log-stream` (optional per operator + task body
"can be deferred if Wave 1 is too wide"). The `rip_progress` field
on `/api/status` from `test-rip-progress` carries the load-bearing
surface; live log streaming is fast-follow if needed.

Wave 2 impls follow.

### 2026-05-14 — planner — sprint-3 drafted

- 2 waves, **25 tasks** total. Wave 1 = 15 failing-test tasks
  (Bucket A polish: 10 incl. 1 optional `test-log-stream`; Bucket B
  capture-timing: 2; Bucket C review UI: 3). Wave 2 = 10 impl tasks
  (Bucket A: 8; Bucket B: 1; Bucket C: 1). Optional task
  `test-log-stream` is marked droppable if Wave 1 is too wide;
  dropping it brings totals to 24 / Wave 1 = 14.
- Goals re-framed around three buckets surfaced by the 2026-05-14
  hardware E2E: **polish** (RIP progress visibility, per-tick
  liveness, scope-aware cdplay stop/start, log-dir graceful
  degradation, device-missing rate-limit, RIP-failure ERROR state,
  log-tail follow toggle); **capture-timing redesign**
  (`D-eject-time-capture`); **review UI** (read-only `/library`
  surface).
- Three Decision Log entries proposed (`D-cdplay-scope`,
  `D-eject-time-capture`, `D-rip-failure-error`) — these ratify when
  sprint-3 starts; the user reviews this draft first.
- Four Contract Change entries captured (systemctl scope kwarg,
  DriveStatus literal extension, LoopState rename + new fields,
  create_app gains optional discs_root).
- Roster stays at two agents (drivers, pipeline). Drivers gets two
  scoped changes (drive.py literal, systemctl.py scope kwarg);
  pipeline does the rest (state-machine restructure, status UI
  updates, review UI).
- Sprint-3 ships the "make it pleasant" sprint: at close, the
  operator can insert a CD, watch the RIP progress bar advance, see
  the disc face captured against an open tray, and browse the
  resulting library on `/library` with playable FLACs in the
  browser.
