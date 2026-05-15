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

#### Bucket D — operator review-recapture (mid-sprint amendment)

<!-- Added 2026-05-15 per D-review-recapture-mvp: a stripped-down
     version of the sprint-4 manual-capture spec lands in sprint-3
     because operator-recapture is high-value and the slice that
     ships here (off-on-off mini-dance into review/, no manifest
     touch, no LED toggle, no upload) is much narrower than the
     full sprint-4 design. See docs/design/2026-05-15-manual-
     capture-and-album-art.md for the full sprint-4 scope. -->

- [x] {agent: pipeline, id: test-review-recapture} Failing tests for
  `POST /api/library/CD_NNNN/recapture`. Endpoint orchestrates a
  single off→on→off mini-capture sequence (one ambient frame with the
  LED off, one lit frame with the LED on, then LED off again) and
  saves both stills into `CD_NNNN/review/`. Tests, against a fake
  camera + fake LED + fake `LoopState`: (a) **happy path** — endpoint
  invokes camera+LED in the documented order (`led.power_off()` is a
  no-op if already off, `camera.capture_frame(...)`, `led.power_on()`,
  `camera.capture_frame(...)`, `led.power_off()` — record the call
  sequence on the fakes and assert ordering); response JSON returns
  `{"ambient": "review/review_ambient_<ISO_TS>.jpg", "lit": "review/
  review_lit_<ISO_TS>.jpg"}`. (b) **409 when the loop owns the
  camera** — fixture `LoopState(state=CAPTURE)` and `LoopState(state=
  EJECT)` both yield HTTP 409 with a body explaining the busy
  condition; assert no camera/LED calls were made. (c) **404 when
  CD_NNNN doesn't exist** — `discs_root` empty (or contains a
  different disc-id) → 404, no side effects. (d) **filename
  convention** — files land in `<disc_dir>/review/` named
  `review_ambient_{ISO_TS}.jpg` and `review_lit_{ISO_TS}.jpg` where
  the timestamp is shared between the pair (so they sort together);
  `review/` directory is created if absent (it's already created by
  `prepare_disc_folder`, but the endpoint must not assume it exists
  on a disc captured before sprint-3). (e) **LED failure tolerated**
  — fake LED whose `power_on` / `power_off` raise are honoured by
  the `LEDPanel` "never raises" invariant: capture still proceeds,
  the two stills still land on disk, and the response JSON includes
  an `errors` array naming the LED failure (response shape:
  `{"ambient": "...", "lit": "...", "errors": ["led power_on
  failed: ..."]}` on partial degradation; `errors` omitted on full
  success).
  - **Acceptance:** New file `tests/service/test_review_recapture.py`
    (or appended to `tests/service/test_library.py` — author's
    call). Five cases. Fails until `impl-review-recapture`. State-
    machine fakes follow the same shape as the existing library
    tests (constructable `LoopState` + injected fakes via
    `create_app`).

### Wave 2 — Implementations

#### Bucket A — sprint-2 polish

- [x] {agent: pipeline, depends: test-rip-progress, depends: test-rip-
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

- [x] {agent: drivers, depends: test-systemctl-scope, id: impl-systemctl-
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

- [x] {agent: drivers, depends: test-drive-missing, id: impl-drive-missing}
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

- [x] {agent: pipeline, depends: impl-drive-missing, id: impl-loop-device-
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

- [x] {agent: pipeline, depends: test-library-list, depends: test-library-
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

  **Review-photo surfacing (sprint-3 mid-sprint amendment per
  `D-review-recapture-mvp`).** The detail page also lists any files in
  `CD_NNNN/review/` alongside the existing `captures/` thumbnails,
  under a separate section header (sentence case — e.g. "operator
  review captures"). Each review file gets a thumbnail + filename;
  served via the same path-traversal-guarded `FileResponse` shape
  (extend the existing `/library/{disc_id}/captures/{filename}` route
  to also accept `review` as the subdirectory, or add a sibling
  `/library/{disc_id}/review/{filename}` route — author's call). The
  detail template also gains a **"Take a review photo"** button that
  triggers a client-side 3-2-1 countdown (vanilla JS, ~15 lines) and
  POSTs to `/api/library/CD_NNNN/recapture` (endpoint lands in
  `impl-review-recapture`); on success, the page refreshes the review/
  section. No new template file — all of this lives inside the
  existing detail-page HTML in `app.py`. Review files are NOT added
  to the manifest in sprint-3 — they surface from the directory
  listing only (manifest schema bump deferred to sprint-4 per the
  decision log).

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

#### Bucket D — operator review-recapture (mid-sprint amendment)

- [x] {agent: pipeline, depends: test-review-recapture, depends: impl-
  library, id: impl-review-recapture} Implement
  `POST /api/library/CD_NNNN/recapture` in `archivist/service/app.py`.
  The route is registered alongside the other `/library/...` routes
  and is only mounted when `discs_root` is configured (same gate as
  the rest of the library surface). Steps:
  1. **Busy check.** Read the injected `LoopState`; if
     `loop_state.state in {State.CAPTURE, State.EJECT}` (the two
     phases where the auto pipeline owns the camera), return HTTP
     409 with a JSON body explaining the busy condition. No camera
     or LED touch on this path.
  2. **Disc-existence check.** Resolve `discs_root / disc_id`; if
     the directory doesn't exist (or `disc_id` doesn't match
     `CD_\d{4}`), return 404. Reuse the same path-resolution +
     traversal guard helper as the existing capture/audio routes.
  3. **Orchestrate the off→on→off sequence.** Call a new helper —
     `recapture_review(disc_dir, *, camera, led) ->
     ReviewRecaptureResult` — which lives in
     `archivist/pipeline/review_capture.py` (new file; do **not**
     fold into `capture_disc` — different intent: review_capture is
     single-shot per lighting condition, where `capture_disc` is
     the multi-frame auto pipeline). The helper:
     - generates a single ISO timestamp shared between the pair
       (`datetime.now(timezone.utc).isoformat().replace(":", "-")`
       or similar filesystem-safe shape);
     - ensures `disc_dir / "review"` exists (`mkdir(parents=True,
       exist_ok=True)`);
     - calls `led.power_off()` (defensive — LED should already be
       off; the `LEDPanel` never-raises invariant means a failure
       just appends to the errors list and continues);
     - calls `camera.capture_frame(disc_dir / "review" /
       f"review_ambient_{ts}.jpg", frames=15)` — the inner ffmpeg
       keep-last-frame behavior is fine for stills here;
     - calls `led.power_on()`;
     - calls `camera.capture_frame(disc_dir / "review" /
       f"review_lit_{ts}.jpg", frames=15)`;
     - calls `led.power_off()` in a finally so the LED is always
       restored;
     - returns the relative paths (`"review/review_ambient_..."`
       and `"review/review_lit_..."`) plus an `errors: list[str]`
       collected from any LED failures.
  4. **Response shape.** `{"ambient": "review/...", "lit":
     "review/...", "errors": [...]}` — `errors` key omitted when
     empty (or present-but-empty — author's call; the test asserts
     it's absent on full success).
  5. **No manifest write.** Per `D-review-recapture-mvp`, sprint-3
     does NOT touch the manifest. The review files surface in the
     library detail page from a directory listing of
     `disc_dir / "review"`. Sprint-4 promotes review/ files into
     the manifest when album-art lands.

  Dependency note: `depends: impl-library` because the detail-page
  surface (the "Take a review photo" button + countdown JS + the
  review/ listing) is amended into `impl-library`'s scope. The POST
  endpoint and the helper are independent from that — they share
  only the route-registration block in `app.py`.
  - **Acceptance:** `tests/service/test_review_recapture.py` (or
    the appended `test_library.py` cases) all pass. Full suite
    green. Ruff clean. Manual sanity: with the rig powered, browse
    to `/library/CD_NNNN`, click "Take a review photo", watch the
    3-2-1 countdown, see two new files appear under `review/` in
    the page after the POST returns.

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

### 2026-05-15 — D-review-recapture-mvp — minimum-useful operator recapture lands in sprint-3; full manual-capture spec defers to sprint-4

Mid-sprint scope expansion. The operator-recapture workflow (a button
on the library detail page that takes a fresh review photo of the
disc / case after the auto pipeline has finished) is high-value — it
unblocks the operator from physically rerunning the rig when the
auto-capture missed the print or caught a glare. The full sprint-4
manual-capture-and-album-art spec
(`docs/design/2026-05-15-manual-capture-and-album-art.md`) is a
sprint of its own; this decision carves out the smallest useful
slice and lands it now while everything else in sprint-3 is still
warm.

**What ships in sprint-3:**

- **One button + 3-2-1 countdown.** "Take a review photo" on the
  existing `/library/CD_NNNN` detail page; countdown rendered
  client-side (vanilla JS) gives the operator time to position the
  disc/case in front of the cam.
- **Off-on-off mini-dance, server-side.** Backend takes one ambient
  frame (LED off), turns LED on, takes one lit frame, turns LED
  off. Always this sequence in sprint-3 — no LED-mode toggle.
- **Two files into `review/`.** `review_ambient_{ISO_TS}.jpg` and
  `review_lit_{ISO_TS}.jpg` (shared timestamp so the pair sorts
  together) under the existing `CD_NNNN/review/` subdirectory
  (already created by `prepare_disc_folder`).
- **Detail-page listing.** The `/library/CD_NNNN` page lists
  `review/` files alongside the existing `captures/` thumbnails,
  under a separate section header.
- **Basic busy check.** HTTP 409 if `LoopState.state in {CAPTURE,
  EJECT}` (the two phases the auto pipeline owns the camera). No
  fancy locking.

**What does NOT ship in sprint-3 (deferred to sprint-4 per the
existing design doc):**

- LED-mode toggle (off/on/both) — sprint-3 always does the off→on
  →off mini-dance.
- Album-art upload (multipart form, categories like
  `front`/`back`/`disc`/`booklet`, magic-byte validation) — full
  sprint-4 scope.
- Manifest schema bump — review/ files are NOT added to the manifest
  in sprint-3. They live on disk and surface in the UI from the
  directory listing only. Sprint-4 brings the manifest into the
  picture when album-art lands; this keeps the schema stable
  through sprint-3.
- Live alignment overlay — already sprint-5+ in the design doc.
- Race-condition handling beyond the 409 busy check.

**Why review/ and not captures/.** `captures/` is the auto pipeline's
domain (the 6 ambient/lit pairs that `capture_disc` writes). Mixing
operator stills into the same directory would muddy the pipeline's
output and risk confusing the eventual OCR/metadata pass. `review/`
keeps the two streams separated and surfaces them as logically
distinct sections in the library UI.

**Why no manifest touch in sprint-3.** The schema bump that promotes
review files into the manifest is part of the album-art work in
sprint-4 — both manifest changes ship together so the schema
version increments once, not twice in successive sprints. Until then
the directory listing is the source of truth for review files.

Implications: 1 new Wave 1 task (`test-review-recapture`), 1 new
Wave 2 task (`impl-review-recapture`), and an amendment to
`impl-library` that adds the review/ section + button + countdown
to the detail-page template. New helper file
`archivist/pipeline/review_capture.py` (does NOT reuse
`capture_disc` — different intent: single-shot per lighting
condition vs. multi-frame burst). New `POST /api/library/CD_NNNN/
recapture` route registered alongside the existing `/library/...`
routes. No changes to manifest schema, drivers, state machine, or
the auto pipeline.

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

### 2026-05-15 — orc — sprint-3 closed

26 of 27 tasks `[x]` (the 1 remaining is the explicitly-optional `test-log-stream`). All three buckets shipped:

- **Bucket A polish** (9 tasks): impl-systemctl-scope, impl-find-unit-scope, impl-drive-missing, impl-rip-stderr-stream, impl-loop-device-missing, impl-rip-error-recovery, impl-log-fallback, impl-last-tick, impl-rip-progress + impl-status-ui (UI side of progress bar / liveness / log follow / ERROR accent).
- **Bucket B capture-timing redesign** (1 impl): impl-capture-after-eject — capture moves to post-EJECT, manifest write splits into rip-result-now + captures-after.
- **Bucket C review UI** (1 impl): impl-library — `/library` grid + `/library/CD_NNNN` detail + asset serving with traversal guard.
- **Bucket D operator review-recapture** (mid-sprint addition per `D-review-recapture-mvp`, 3 commits): test-review-recapture, impl-review-recapture, amendment to impl-library adding "Take a review photo" button + countdown.

**Decision Log entries ratified:** D-cdplay-scope, D-eject-time-capture, D-rip-failure-error, D-review-recapture-mvp.

**Hardware bring-up validation (CD_0018, 2026-05-15):**
- Real disc end-to-end: WAITING → STABILIZE → RIP → EJECT → CAPTURE → IDLE — full cycle in ~13 minutes.
- 12 FLACs ripped cleanly into `audio/` (the trailing-slash fix from sprint-2 polish proven on real hardware).
- 6 captures landed in `captures/` POST-eject, showing the disc face clearly with handwritten label legible ("AFI - Black Sails in the Sunset"). Capture-timing redesign validated.
- `last_rip_status: "success"` reported by the API. First successful end-to-end rip on the real rig.

**Polish queue items surfaced during validation (carried to sprint-4 backlog):**
- #11 library page filter by rip status (default success-only)
- #12 ripper keeps WAVs alongside FLACs (~2x disk usage per disc)
- #13 `rip_progress` field never populates — parser doesn't match cdparanoia's actual stderr format
- (Plus the 10 items already in the queue at sprint-3 start, most of which sprint-3 directly addressed.)

**Sprint-4 scope decided** (`project_cd_archivist_sprint4_scope.md` in orc memory): music-pipeline output contract conformance per `docs/ripper-handoff-for-claude-code.md`. The earlier manual-capture-and-album-art design doc is demoted to sprint-5 candidate.

### 2026-05-15 — pipeline — Bucket D operator review-recapture landed (3 commits)

Sprint-3 mid-sprint amendment per `D-review-recapture-mvp` shipped in
three atomic commits. Three tasks closed:

- **test-review-recapture** (commit `5c30fa4`) — 8 failing test cases
  in `tests/service/test_review_recapture.py`: happy-path off→on→off
  ordering with response shape (`{"ambient", "lit"}`, optional
  `errors`); 409 parametrized over `LoopState.state in {CAPTURE,
  EJECT}` with zero camera/LED calls; 404 on unknown disc + invalid
  id shape; shared ISO timestamp between the ambient/lit pair;
  `review/` dir created on first call; LED never-raises (captures
  proceed, `errors[]` surfaces).

- **impl-review-recapture** (commit `2980f8f`) — new
  `archivist/pipeline/review_capture.py` (`recapture_review(disc_dir,
  *, camera, led) -> ReviewRecaptureResult` — single-shot per
  lighting, intentionally NOT folded into `capture_disc` per task
  scope). `create_app` gains optional `recapture_camera` /
  `recapture_led` kwargs; `POST /api/library/{disc_id}/recapture`
  (busy gate + path-traversal-guarded disc resolution) and
  `GET /library/{disc_id}/review/{filename}` (JPG asset serving with
  the same `_resolve_under` guard as captures/audio) mount only when
  both are wired. No manifest write — sprint-4 promotes review/
  files into the schema with album art.

- **amend impl-library** (commit `8bae907`) — detail-page HTML in
  `_LIBRARY_DETAIL_HTML` gains a "take a review photo" button with a
  ~30-line vanilla-JS 3-2-1 countdown that POSTs to the new endpoint
  and reloads on success; a separate "review photos" card lists
  files from `disc_dir / "review/"` (directory listing only).
  Production wiring in `archivist/__main__.py` now passes the camera
  closure + `LEDPanel(led_base)` through to `create_app` so the rig
  serves the endpoint.

**Suite:** 139/139 green across `tests/{service,state_machine,
pipeline,test_main_logging}` after Bucket D commits. `ruff check`
clean on all changed paths. Pre-existing 7 failures in
`tests/drivers/test_ripper.py` are in drivers' lane (uncommitted WIP
in `archivist/drivers/ripper.py` on master) and orthogonal to this
work. Mash Co. invariants preserved (sentence case, no decorative
emoji, eyebrows ≤2 words). Sprint-3 pipeline scope is complete; the
remaining drivers-owned `impl-systemctl-scope` and any open
ripper-test work are outside this agent's owns paths.

### 2026-05-15 — planner — sprint-3 mid-sprint amendment: operator review-recapture (Bucket D)

Per `D-review-recapture-mvp` (Decision Log above): a stripped-down
slice of the sprint-4 manual-capture spec
(`docs/design/2026-05-15-manual-capture-and-album-art.md`) lands in
sprint-3 as a new Bucket D. The MVP is one button + 3-2-1 countdown
on `/library/CD_NNNN` that POSTs to a new `/api/library/CD_NNNN/
recapture` endpoint, which runs an off→on→off mini-dance and writes
two stills (`review_ambient_<TS>.jpg`, `review_lit_<TS>.jpg`) into
`CD_NNNN/review/`. No manifest touch (schema stable through
sprint-3); no LED-mode toggle, no album-art upload, no overlay
(all sprint-4+).

**Delta to sprint-3 plan:**

- **+1 Wave 1 task:** `test-review-recapture` (pipeline). Five
  cases: happy-path call ordering + JSON shape; 409 when
  `LoopState.state in {CAPTURE, EJECT}`; 404 on unknown disc;
  filename + `review/` directory invariants; LED-failure tolerated
  per the `LEDPanel` never-raises invariant.
- **+1 Wave 2 task:** `impl-review-recapture` (pipeline; depends
  on `test-review-recapture` and `impl-library`). New POST endpoint
  in `archivist/service/app.py` plus a new helper file
  `archivist/pipeline/review_capture.py` (does NOT reuse
  `capture_disc` — different intent: single-shot per lighting
  vs. multi-frame burst).
- **Amendment to `impl-library`:** detail-page template gains a
  "Take a review photo" button + 3-2-1 countdown JS + a "operator
  review captures" section listing `review/` files alongside
  `captures/` thumbnails. The asset-serving route is extended (or
  a sibling route added) to serve `review/<filename>` with the
  same path-traversal guard. Because `impl-library` is already
  marked `[x]`, this amendment is queued as a follow-up commit on
  the same task — pipeline picks it up alongside
  `impl-review-recapture`.

**New totals:** 27 tasks (Wave 1 = 16, Wave 2 = 11) — was 25 (15/10);
optional `test-log-stream` was skipped per prior log entry so the
landed count is 26 tasks (15/11) once Bucket D fully lands. Sprint
buckets are now A (sprint-2 polish), B (capture-timing redesign),
C (review UI), D (operator review-recapture).

**Decision Log entry added:** `D-review-recapture-mvp` captures the
deliberate scope decision and the explicit deferrals to sprint-4.
**No Contract Changes entry** — the new endpoint is additive on the
service surface; no signature or schema changes ripple to other
agents.

User reviews this draft before commit + agent kickoff.

### 2026-05-15 — drivers — Wave 2 impls landed (3 tasks, 3 commits)

All drivers-owned Wave 2 tasks closed. Full repo 150/150 PASS;
drivers suite 65/65 PASS; `ruff check archivist/ tests/drivers/`
clean.

- **impl-systemctl-scope** (`1064267`) — D-cdplay-scope option (a).
  `stop_unit(name, *, scope="system")` / `start_unit(name, *,
  scope="system")` gain a keyword-only Scope literal. `scope="system"`
  keeps the existing `["sudo", "systemctl", action, name]` argv;
  `scope="user"` switches to `["systemctl", "--user", action, name]`
  (no sudo, the user manager is per-uid). New
  `find_unit_scope(name) -> "system" | "user" | None` probes both
  managers via `is-active`; system wins on a tie, `FileNotFoundError`
  on a dev box returns `None` with a warning. The matching entrypoint
  wiring (`_Services` cache at startup) and the `cm4-setup.md`
  user-scope-no-sudo note are pipeline-owned per the agent roster —
  leaving for them.
- **impl-drive-missing** (`6209a5e`) — `DriveStatus` extended with
  the `"device-missing"` literal. `read_drive_status` wraps `os.open`
  in a narrow try/except that catches only `FileNotFoundError` and
  returns `"device-missing"`; every other `OSError` (PermissionError,
  EIO, …) still bubbles. Contract change: the sprint-1
  `test_missing_device_raises` test (which asserted `OSError` must
  bubble) was renamed to `test_missing_device_returns_device_missing`
  and updated to the new contract — the `PermissionError`-still-raises
  invariant is covered by a separate case added in `test-drive-missing`.
  Unblocks `impl-loop-device-missing` (pipeline).
- **impl-rip-stderr-stream** (`22d46bb`) — completes the driver-side
  half of `impl-rip-progress` (pipeline already shipped the parser,
  `LoopState.rip_progress`, and forward-compat
  `inspect.signature`-based callback forwarding from `rip_disc`).
  `CDAudioRipper.rip` gains an optional `progress_callback`. Factored
  out `_run_cdparanoia_streaming(argv, progress_callback)` that uses
  `subprocess.Popen(..., stdout=PIPE, stderr=PIPE, bufsize=1, text=
  True)` and iterates `proc.stderr` line-by-line: each line is
  appended to captured-stderr (so failure exit codes still surface
  diagnostic context — the 2026-05-14 silent-failure root cause),
  logged at INFO via `archivist.drivers.ripper`, and passed to
  `progress_callback` if set (broad-except guarded so a bad callback
  doesn't kill the rip). Sprint-1 test fixtures that patched
  `subprocess.run` for cdparanoia were migrated to two small helpers
  (`_install_cdparanoia_popen`, `_install_flac_run`) — behavior
  unchanged. **Pipeline's live RIP-progress UI is no longer a fiction:
  `LoopState.rip_progress` will tick per stderr line during real rips.**
  No checkbox to flip — `impl-rip-progress` was already `[x]`
  pipeline-side; this commit completes its driver-side scope.

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

### 2026-05-14 — pipeline — Wave 2 impls landed (8 tasks, 8 commits — 59/59 green)

All pipeline-owned Wave 2 tasks closed. Full pipeline test suite:
59 passing, ruff clean across `archivist` + `tests`.

- **impl-last-tick** (83eae9b) — LoopState renamed `last_updated`
  → `state_entered_at` (advances on transitions); added `last_tick_at`
  (heartbeat, updates every tick) and `rip_progress: str | None`.
  `/api/status` JSON exposes all three; old `last_updated` key gone.
  Loop's `_heartbeat()` is called at the top of every `tick()`.
- **impl-log-fallback** (b0acda9) — `_configure_logging` no longer
  raises on unwritable log dir. Try/except around `mkdir` and
  `FileHandler`; falls back to stderr-only with a warning naming
  the path + `ARCHIVIST_LOG_PATH` env var. Manual handler wiring
  (no `basicConfig(force=True)`) so pytest's caplog isn't nuked.
- **impl-rip-error-recovery** (b00ba99) — terminal `ERROR` state per
  `D-rip-failure-error`. `_from_rip` wraps `rip_disc` in try/except;
  failures (raised OR `status="fail"`) restart cdplay, record
  `status="rip_failed"` + exception text in `manifest.errors`, and
  park in ERROR. Only `tray-open` exits ERROR back to IDLE.
- **impl-capture-after-eject** (0d12ba1) — flow restructure per
  `D-eject-time-capture`: STABILIZE→RIP no longer runs capture;
  RIP→EJECT writes the first manifest with the rip outcome;
  EJECT runs eject + cdplay restart + 3s settle sleep then
  transitions to CAPTURE; CAPTURE runs `capture_disc` against the
  open tray and writes the second manifest adding captures without
  disturbing the rip record. Capture failures preserve the rip
  record + append the error.
- **impl-status-ui** (6e25d80) — `_PAGE_HTML` updated for all
  sprint-3 UI contracts: relative-time labels rendered in JS from
  `state_entered_at` / `last_tick_at`; RIP progress bar with
  `--sky` fill on `--ink-2` track (hidden when `rip_progress` is
  null, parses the percent from the label); log-follow chip with
  `data-follow="on"` default and standard tail -f scroll-up auto-
  disable; `card--ember` class-swap on `state === "ERROR"`. Top
  nav (status / library) added.
- **impl-library** (c937781) — new `/library` browser. `create_app`
  gains optional `discs_root` kwarg; when set, four routes mount:
  list (Mash Co. card grid sorted by disc_id desc with semantic
  card-accent class by status — `card--moss` / `card--amber` /
  `card--ember`); detail (formatted manifest dump in `<pre>`, 6-
  thumbnail capture grid, track list with byte-formatted sizes
  and inline `<audio controls preload="none">` per FLAC, optional
  `logs/` tail); two `FileResponse` routes for captures + audio
  with a path-traversal guard (`Path.resolve()` + `relative_to`
  check; rejects `../`, URL-encoded variants, absolute paths).
  `__main__.py` passes `discs_root` through.
- **impl-loop-device-missing** (1270450) — rate-limited warning when
  `drive()` returns `"device-missing"`: one log per disconnect, flag
  resets on recovery so re-disappearance is re-logged. Loop stays
  in IDLE while missing. Added the two `tests/state_machine/` cases
  the drivers' `test-drive-missing` task body specified (the test
  file is in pipeline's owns). Forward-compat — works today; goes
  live once drivers ships `impl-drive-missing`.
- **impl-rip-progress** (ce5c056) — new `archivist/pipeline/rip_
  progress.py` with `parse_cdparanoia_progress(line) → str | None`
  (recognises "Progress: NN% complete (track N of M)" and bare
  "(track N)" lines). `rip_disc` gains optional `progress_callback`
  and forwards to `ripper.rip` only if the ripper signature accepts
  it (inspect.signature) — forward-compat with today's
  `CDAudioRipper.rip` which doesn't. State machine builds a closure
  that parses the line + writes the result into
  `loop_state.rip_progress`, with a `finally` that clears the
  label when the rip ends. Live wiring activates once drivers
  ships `impl-rip-stderr-stream`.

**Cross-agent coordination notes:**
- Drivers still have not landed `impl-drive-missing` or
  `impl-rip-stderr-stream`. Both pipeline impls that depend on them
  are forward-compatible: the loop handles `"device-missing"`
  whenever the driver starts returning it, and the rip-progress
  callback flows through whenever the ripper accepts it.
- `tests/state_machine/test_loop.py` gained two cases for the
  device-missing rate limit. The drivers' `test-drive-missing`
  task body asked for tests in `tests/state_machine/`, which is
  pipeline's owns; documenting here so it's clear who did it.

Sprint-3 pipeline scope complete pending drivers' remaining Wave 2
impls (`impl-systemctl-scope`, `impl-drive-missing`,
`impl-rip-stderr-stream`).

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
