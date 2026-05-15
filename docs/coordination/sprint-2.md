---
project: cd-archivist
sprint: sprint-2
created: 2026-05-14T00:00:00.000Z
updated: 2026-05-14T00:00:00.000Z
---

# cd-archivist — coordination doc (sprint-2)

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
- Active unit: sprint-2

## Sprint Goals

- **End-to-end pipeline on the real CM4.** Glue the sprint-1 driver primitives + pipeline functions into a working state machine: drive-state poll → STABILIZE → capture (ambient + lit) → rip → eject → idle. A single inserted audio CD produces a populated `CD_NNNN/` (manifest reflecting reality, FLACs under `audio/`, JPGs under `captures/`).
- **`cdplay.service` coexistence.** The archivist claims `/dev/sr0` cleanly: stops `cdplay.service` before opening the device, restarts it after eject. Drive-claim windows are bounded and logged; a crash mid-rip never leaves the player permanently down.
- **Webcam recovery.** When ffmpeg fails with the documented `VIDIOC_STREAMON` error after long idle, the camera driver retries via USB sysfs unbind/rebind. The USB bus path is **auto-discovered at startup** by walking `/sys/class/video4linux/video*/device/uevent` and matching on the webcam's USB vendor:product ID (`0c45:6366` for the documented Microdia rig); `ARCHIVIST_CAMERA_USB_PATH` remains as a fallback override (per `D-camera-autodiscover` below). Retry budget is bounded; capture remains best-effort (rip never blocks on the cam).
- **FastAPI status surface on the LAN, in Mash Co. dress.** A local web service exposes current drive state, current disc-id, last rip status, and a tail of the pipeline log on port **8228**. Reachable from a phone/laptop on the same subnet. Read-only this sprint — no control endpoints, no review UI. The page is dressed in the **Mash Co. design system** (cd-archivist becomes the system's second consumer after Orc Tower); see `D-design-system` below.
- **TDD discipline preserved.** Every implementable unit lands as a `test-X` in Wave 1 (fakes only — no real `/dev/sr0`, no real Tasmota, no real USB) and `impl-X` in Wave 2. Real-rig validation lives in Wave 3 as a manual smoke checklist, not pytest.
- **Bare-metal this sprint.** Sprint-2 ships bare-metal (`python -m archivist` over ssh, host systemd + NOPASSWD sudoers for `cdplay.service` + USB unbind/rebind). Containerization is **postponed** — the Docker decision is unmade and gets revisited after sprint-2 closes; the entrypoint is written to be container-ready so the eventual call (Docker or stay bare-metal) is reversible.

> **Scope-hierarchy reminder.** The hardware E2E path (Wave 3 `smoke-checklist`) is the load-bearing scope this sprint. The Mash Co. UI integration (Wave 0 `vendor-design-tokens`, Wave 2 `impl-service`) is the visible-progress scope. If the design-system integration slips, the hardware E2E still ships against a bare-bones page — the FastAPI surface is wired and reachable either way; only the dressing is at risk.

## Active Initiatives

<!-- Each initiative is one heading, e.g. `### Initiative — short name`,
     with a 1-2 sentence body. Include a status tag in the heading
     (e.g. "[in-flight]", "[blocked]", "[done]"). When `methodology.
     planning: inline` is configured, the Active Sprint Plan below
     replaces this section's role; treat this one as a high-altitude
     narrative summary or omit. -->

- _None — sprint-2 plan below is the substrate._

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

<!-- What ships in sprint-3+ (out of scope here):
     - Navidrome / music serving
     - OCR / metadata extraction from disc photos
     - Review UI (browse scanned discs, edit metadata)
     - Discogs / MusicBrainz lookup
     - Wii / SMB / cm4 file-sharing
     - `archivist.service` systemd unit (postponed per D-systemd-defer;
       paired with the Docker decision and revisited together)
     - Containerization (Dockerfile, docker-compose.yml, container-runtime
       packaging) — explicitly NOT decided yet (see D-docker-postpone).
       Sprint-2 runs bare-metal so the hardware path (VIDIOC_STREAMON,
       cdplay coexistence, USB unbind/rebind ioctls) can be debugged
       without a container layer in between. The Docker question gets
       revisited after sprint-2 closes — Docker, bare-metal-with-systemd,
       or some hybrid are all still on the table.
     Sprint-2 ships the working v1 archival station: insert disc,
     get a populated CD_NNNN/, see status in a browser. -->

### Wave 0 — Scaffold + sprint-1 follow-ups

- [ ] {agent: pipeline, id: tests-pkg} Make `tests/` a proper Python package so cross-module fixtures resolve cleanly. Add `tests/__init__.py` (empty). Move the `FakeCompletedProcess` shim that `tests/drivers/test_ripper.py` inlined in sprint-1 into `tests/conftest.py` as a shared helper (`fake_completed_process(returncode, stdout="", stderr="")`), and rewrite `test_ripper.py` to import it. Verify the `tmp_disc_root` and `fake_subprocess` fixtures from `tests/conftest.py` are now reachable from any test file via the standard pytest fixture discovery (no `from tests.conftest import ...` needed — that was the symptom).
  - **Acceptance:** `tests/__init__.py` exists. `tests/conftest.py` exports `fake_completed_process` (or equivalent). `tests/drivers/test_ripper.py` no longer defines its own shim. `pytest tests/` — all 43 sprint-1 tests still PASS. `ruff check tests/` clean.

- [ ] {agent: drivers, id: led-params-refactor} Per the sprint-1 follow-up and `D-led-params` (Decision Log below): switch `LEDPanel`'s Tasmota request from a manually-built URL to `requests.get(f"{base_url}/cm", params={"cmnd": cmnd}, timeout=5)`. `requests` handles encoding, the URL construction is one line shorter, and tests can introspect via `resp.request.url` or the `params=` kwarg. Update `tests/drivers/test_led.py` accordingly: the existing URL-introspection assertions need to change shape (assert against the `params=` kwarg of the mocked `requests.get`, or against the final `prepared.url`, author's choice — but the three Tasmota commands `Power On`, `Power Off`, `Power` must still be covered, and the "never raises" invariant still holds).
  - **Acceptance:** `archivist/drivers/led.py` uses `params={...}`. `tests/drivers/test_led.py` PASSES with updated assertion shape. The "never raises" invariant still holds. `D-led-params` already in Decision Log; no new entry needed at task close.

- [ ] {agent: pipeline, id: service-scaffold} Scaffold the new package directory `archivist/service/` with empty `__init__.py`, plus the new `archivist/state_machine/` package directory with empty `__init__.py`. Also create `archivist/service/static/` (for the vendored design tokens — populated by `vendor-design-tokens`). Add `tests/service/__init__.py` and `tests/state_machine/__init__.py`. Add runtime deps to `pyproject.toml`: `fastapi>=0.115`, `uvicorn[standard]>=0.30`, `httpx>=0.27` (the last is dev-only — used by FastAPI's TestClient). Bump pytest config testpaths if needed (currently just `tests/`, which already covers the new dirs). No code yet — Wave 1 lands the failing tests against these empty packages.
  - **Acceptance:** New empty packages: `archivist/service/`, `archivist/service/static/` (empty dir + `.gitkeep` if needed), `archivist/state_machine/`, `tests/service/`, `tests/state_machine/`. `pyproject.toml` declares the three new deps. `pip install -e ".[dev]"` succeeds. `pytest --collect-only` collects the existing 43 tests with no new errors. `ruff check archivist tests` clean.

- [ ] {agent: pipeline, id: vendor-design-tokens} Vendor the **Mash Co. design system** color + type tokens into the cd-archivist tree so the FastAPI status page can dress itself in the same visual language as Orc Tower (per `D-design-system` below). The system lives at `/home/loydmilligan/Projects/Mash Co. Design System/`. Two viable installs — pick the simpler one given the inline-HTML constraint:
  - **(preferred)** Copy `colors_and_type.css` directly to `archivist/service/static/tokens.css`. The published `sync-to-consumer.mjs` script vendors the system into `<consumer>/src/vendor/design/`, which is an npm/TS-shaped layout that doesn't map cleanly onto a Python package — a single-file copy keeps the integration shallow. Record the source path + a short comment at the top of the file noting the source repo + the date copied.
  - **(alt)** Run `node /home/loydmilligan/Projects/Mash\ Co.\ Design\ System/scripts/sync-to-consumer.mjs <consumer-path>` if the agent decides the full vendored bundle (dist + assets) is worth the directory cruft. Probably overkill for this sprint.
  - No Python changes in this task. The tokens file is plumbing — it gets consumed by `impl-service` in Wave 2.
  - Surface a follow-up item in the Activity Log: the Mash Co. README's "Products in scope" table doesn't list cd-archivist. Don't update the README in this sprint — that's a cross-repo touch the user wants to make themselves with full context.
  - **Acceptance:** `archivist/service/static/tokens.css` exists, contains `--ink-` and `--mash-pulp` token definitions and the Google Fonts `@import` line, with a header comment naming the source repo + commit-or-date. No Python files touched. `ruff check` clean (still). Activity Log entry filed noting the README follow-up.

- [ ] {agent: pipeline, id: cm4-setup-docs} Append a "NOPASSWD sudo fragment" subsection to `docs/operations/cm4-setup.md` documenting the sudoers snippet the archivist needs on the CM4 for (a) `systemctl stop cdplay.service` / `systemctl start cdplay.service` and (b) `tee /sys/bus/usb/drivers/usb/{unbind,bind}` for the camera-recovery path. Provide the fragment as a copy-pasteable code block targeting `/etc/sudoers.d/cd-archivist`, with a short note explaining why each line is needed. **Don't auto-install it** — the user installs it by hand on the CM4 the first time they wire up the rig. Sudoers config is not a runtime dependency of any pytest task in this sprint (the Wave 1 tests use `fake_subprocess`).
  - **Acceptance:** `docs/operations/cm4-setup.md` has a new subsection (e.g. `## NOPASSWD sudo fragment`) with the snippet, the install command (`sudo visudo -f /etc/sudoers.d/cd-archivist`), and a 1-line per-rule justification. No code or sudoers files written outside the docs.

### Wave 1 — Failing tests (parallel-safe; each implicit-depends on the Wave 0 scaffold tasks)

- [ ] {agent: drivers, depends: service-scaffold, id: test-eject} Failing tests for `eject(device: Path) -> bool` in `archivist/drivers/drive.py` (extends the existing module). Tests stub `fcntl.ioctl` and assert: (a) issues `CDROMEJECT` (`0x5309`); (b) returns `True` on success; (c) returns `False` on `OSError` (drive busy) and logs a warning — never raises; (d) `os.open` is non-blocking, just like `read_drive_status`.
  - **Acceptance:** Four new test cases appended to `tests/drivers/test_drive.py`. `pytest tests/drivers/test_drive.py` fails on the new ones (`AttributeError: ... has no attribute 'eject'`). Existing 5 cases still PASS.

- [ ] {agent: drivers, depends: service-scaffold, id: test-camera-recovery} Failing tests for the new `capture_frame_with_recovery(device, out_path, *, frames=15, discover_usb_path=None, retries=1) -> Path | None` in `archivist/drivers/camera.py` (sibling to the existing `capture_frame`). `discover_usb_path` is an injected callable returning `str | None` — production wires in `discover_camera_usb_path` from `impl-usb-discovery` (per `D-camera-autodiscover`). On the first ffmpeg failure that looks like a `VIDIOC_STREAMON` error, the function calls `discover_usb_path()` to resolve the USB bus path, performs a USB sysfs unbind/rebind via two `subprocess.run` calls writing the resolved path to `/sys/bus/usb/drivers/usb/unbind` then `/bind`, sleeps ~2s (use a patched `time.sleep` in tests), and retries `capture_frame` once. If the discovery callable returns `None`, the recovery is skipped and the function returns `None` immediately (no path → nothing to rebind). Tests cover: (a) first-attempt success → no recovery, no sleep called, discovery not called; (b) first-attempt fails with stderr containing `VIDIOC_STREAMON`, second-attempt succeeds → returns `out_path`, `discover_usb_path` was called before the unbind, recovery commands fired with the discovered argv; (c) first fails non-streamon (e.g. `Device or resource busy`) → returns `None` without recovery (no false-positive rebinds); (d) second attempt also fails → returns `None`, recovery attempted exactly once even with `retries=1`; (e) `VIDIOC_STREAMON` failure but `discover_usb_path()` returns `None` → returns `None`, no `subprocess.run` calls for unbind/bind, warning logged. Use `fake_subprocess` from conftest.
  - **Acceptance:** New file `tests/drivers/test_camera_recovery.py` (or extend `test_camera.py`). Function does not exist yet → tests fail at import / `AttributeError`. Five cases. Documented invariant: never raises; recovery is bounded by `retries`; only triggers on `VIDIOC_STREAMON`-shaped failures; recovery is a no-op when discovery yields no path.

- [ ] {agent: drivers, depends: tests-pkg, id: test-usb-discovery} Failing tests for `discover_camera_usb_path(*, vendor_product: str = "0c45:6366", env_var: str = "ARCHIVIST_CAMERA_USB_PATH") -> str | None` (lives in `archivist/drivers/usb_discovery.py` or as a sibling function in `archivist/drivers/camera.py` — author's call). Walks `/sys/class/video4linux/video*/device/uevent` looking for a `PRODUCT=` (or equivalent) line matching the configured vendor:product ID; returns the USB bus path (e.g. `1-1.2.2`) for the lowest-numbered `videoN` match. If no match, falls back to `os.environ.get(env_var)`; if that's also unset, returns `None` and logs a clear error (the state machine treats `None` as "no camera, skip captures"). Tests **must not touch real `/sys`** — mock `pathlib.Path.glob` and the per-file reads (mock `Path.read_text` or open `uevent` via a patched `open`). Cover: (a) sysfs match → returns the right bus path for the matching `videoN`; (b) two matches (`video0` + `video2`) → returns the lowest-numbered one; (c) no sysfs match + env var set → returns env value; (d) no sysfs match + env var unset → returns `None` and logs a warning containing the expected vendor:product. Use `monkeypatch` for env vars and `unittest.mock.patch` for filesystem mocks. The default `vendor_product` matches the documented Microdia rig from `docs/operations/cm4-setup.md` (line 11: `idVendor 0c45:6366`); if the impl agent finds the value drifted on the real CM4 during smoke, they grab the actual ID via `lsusb` and update both the default and `cm4-setup.md` as part of the same task close.
  - **Acceptance:** New file `tests/drivers/test_usb_discovery.py`. `pytest tests/drivers/test_usb_discovery.py` fails (module/function missing). Four cases. Documented invariant: never reads real `/sys` in tests; never raises; logs clearly when falling back to env or returning `None`.

- [ ] {agent: drivers, depends: service-scaffold, id: test-systemctl} Failing tests for `archivist/drivers/systemctl.py` exposing `stop_unit(name: str) -> bool` and `start_unit(name: str) -> bool`. Wraps `subprocess.run(["sudo", "systemctl", "stop"|"start", name], ...)`. Tests: (a) returncode 0 → `True`; (b) non-zero → `False` with stderr logged, never raises; (c) `FileNotFoundError` (sudo/systemctl missing — useful for non-Pi dev machines) → `False` with a clear log line. Use `fake_subprocess`.
  - **Acceptance:** New file `tests/drivers/test_systemctl.py`. `pytest tests/drivers/test_systemctl.py` fails (module missing). Three cases per function (six total). Documented invariant: never raises.

- [ ] {agent: pipeline, depends: service-scaffold, id: test-capture-sequence} Failing tests for `archivist/pipeline/capture.py` exposing `capture_disc(disc_dir: Path, *, camera, led, settle_seconds: float = 0.5) -> list[CaptureRecord]`. Implements the documented LED dance from `docs/operations/cm4-setup.md` §"Capture pipeline LED dance": led off → settle → ambient burst (3 frames into `disc_dir/captures/disc_front_ambient_NNN.jpg`) → led on → settle → lit burst (3 frames) → led off. `camera` and `led` are injected dependencies (Protocols matching `capture_frame` and `LEDPanel.power_on`/`power_off`/`status`). Returns one `CaptureRecord` for ambient and one for lit, each listing the JPGs that actually landed. Tests inject fakes; cover (a) happy path produces both records with 3 image_paths each; (b) Tasmota unreachable (`led.power_on()` returns `False`) → still produces an ambient record, lit record may be empty or absent, never raises (LED failure is best-effort per design); (c) camera returns `None` for some frames → records list only the JPGs that succeeded, no errors raised; (d) `led.power_off` is called in a `finally` so the LED never gets stuck on after an exception in the lit-burst loop.
  - **Acceptance:** New file `tests/pipeline/test_capture.py`. `pytest tests/pipeline/test_capture.py` fails (`archivist/pipeline/capture.py` missing). Four cases. Documented invariant: LED is restored to off in all paths.

- [ ] {agent: pipeline, depends: service-scaffold, id: test-rip-orchestrate} Failing tests for `archivist/pipeline/rip.py` exposing `rip_disc(disc_dir: Path, device: Path, *, ripper) -> RipRecord`. Wraps a `Ripper` (the Protocol from `archivist.drivers.ripper`): calls `ripper.rip(device, disc_dir / "audio")`, translates the `RipResult` into a `RipRecord` (fields `status`, `tracks` as relative POSIX paths under `audio/`, `errors`). Tests inject a fake ripper; cover (a) success → `RipRecord(status="success", tracks=["audio/track01.flac", ...], errors=[])`; (b) partial → record reflects partial status with errors; (c) fail → record with empty tracks, errors populated; (d) tracks are stored as POSIX relative paths (`audio/track01.flac`), never absolute, regardless of where `disc_dir` lives.
  - **Acceptance:** New file `tests/pipeline/test_rip.py`. `pytest tests/pipeline/test_rip.py` fails (`archivist/pipeline/rip.py` missing). Four cases.

- [ ] {agent: pipeline, depends: service-scaffold, id: test-state-machine} Failing tests for `archivist/state_machine/loop.py` exposing the `ArchivistLoop` class — the heart of sprint-2. Constructor takes injected dependencies: `discs_root: Path`, `device: Path`, `drive` (callable returning `DriveStatus`), `ripper`, `camera`, `led`, `services` (the systemctl wrapper), `clock` (callable for `time.monotonic`), `sleeper` (callable for `time.sleep` — both injected so tests don't actually sleep). State enum: `IDLE | WAITING | STABILIZE | CAPTURE | RIP | EJECT`. `tick()` method advances one transition based on the current drive status. Tests inject fakes; cover: (a) IDLE + status `tray-open` → WAITING; (b) WAITING + status `disc-ok` → STABILIZE with timer set; (c) STABILIZE + clock advanced past 2s → CAPTURE → calls `services.stop_unit("cdplay.service")` then `capture_disc` then transitions to RIP; (d) RIP → calls `rip_disc`, writes the manifest with capture+rip+pairing records, transitions to EJECT; (e) EJECT → calls `drive.eject(device)`, then `services.start_unit("cdplay.service")`, transitions to IDLE; (f) crash recovery: if `rip_disc` raises (it shouldn't, but defensively), `services.start_unit("cdplay.service")` is still called via try/finally so the player is never left stopped. Manifest after a full cycle has `status="ripped"`, one captures (ambient+lit), one rips entry, one pairings entry.
  - **Acceptance:** New file `tests/state_machine/test_loop.py`. `pytest tests/state_machine/test_loop.py` fails (`archivist/state_machine/loop.py` missing). Six cases plus a happy-path full-cycle test. Documented invariants: `cdplay.service` start/stop are paired (try/finally); `LED` is restored to off in all paths (delegated to `capture_disc`); the disc folder is created via `prepare_disc_folder` exactly once per cycle.

- [ ] {agent: pipeline, depends: service-scaffold, id: test-service-status} Failing tests for `archivist/service/app.py` exposing `create_app(loop_state: LoopState, log_path: Path) -> FastAPI` and `LoopState` (a small dataclass the loop writes into: `state: str`, `disc_id: str | None`, `last_rip_status: str | None`, `last_updated: datetime`). Two GET routes: `GET /api/status` returns JSON `{state, disc_id, last_rip_status, last_updated}`; `GET /api/log?lines=200` returns the last N lines of `log_path` as `text/plain`. Use FastAPI's `TestClient` (httpx-backed). Tests cover: (a) `/api/status` returns the current `LoopState` snapshot; (b) `/api/log` tails a fixture log file, default 200 lines, capped at 1000; (c) missing log file → 200 with empty body, never 500; (d) `loop_state` updates between calls are reflected (proves no stale caching).
  - **Acceptance:** New file `tests/service/test_app.py`. `pytest tests/service/test_app.py` fails (`archivist/service/app.py` missing). Four cases.

- [ ] {agent: pipeline, depends: service-scaffold, depends: vendor-design-tokens, id: test-service-ui} Failing test for `GET /` serving a single-file HTML status page dressed in the **Mash Co. design system**. The page polls `/api/status` every 2s via vanilla JS (no framework), shows current state / disc-id / last-rip-status in big readable text, and has a small `<pre>` tail of `/api/log`. Test asserts:
  - (a) `GET /` returns 200, `text/html`.
  - (b) the response body contains the strings `cd-archivist` (page title), `/api/status` (the polling endpoint), and `/api/log` (the log endpoint) — i.e. the wiring is real, not mocked away.
  - (c) the response includes the design tokens — assert that the body contains both `--ink-` and `--mash-pulp` (proves tokens are wired, whether via inline `<style>` or via a `<link rel="stylesheet" href="/static/tokens.css">` tag whose served file contains them).
  - (d) the body includes `data-theme="dark"` on the `<html>` tag (dark-first per the design system).
  - (e) visible labels use **sentence case** — assert no occurrence of common all-caps non-eyebrow strings (e.g. `INSERT A CD`, `WAITING FOR DISC` as full-sentence labels) and no Title Case in body copy. The test does this with a small allowlist for legitimate eyebrow strings (e.g. `WHAT NEXT`, `WAITING`, `STABILIZE`, `CAPTURE`, `RIP`, `EJECT`, `IDLE`, `ERROR`) — uppercase is allowed only on those eyebrow segments and must use the `t-eyebrow` class or equivalent inline style.
  - (f) **no emoji** anywhere in the body — assert with a regex against the Unicode emoji ranges (`\U0001F300-\U0001FAFF`, `☀-➿`, etc.). Functional Unicode glyphs (`▸ ▾ ↵ ↑ ↓ ↗ ↻`) are allowed.
  - No DOM/JS testing — that's manual smoke acceptance in Wave 3.
  - **Acceptance:** Test added to `tests/service/test_app.py`. Fails until the route + HTML template land. The HTML lives inline in `app.py` or as a sibling string constant — no Jinja, no template engine. Tokens served either inline (a `<style>` block containing the `--ink-*` / `--mash-*` definitions) or from `archivist/service/static/tokens.css` via a mounted `StaticFiles`.

### Wave 2 — Implementations

- [ ] {agent: drivers, depends: test-eject, id: impl-eject} Implement `eject(device: Path) -> bool` in `archivist/drivers/drive.py`. `CDROMEJECT = 0x5309`. Open device with `os.open(device, os.O_RDONLY | os.O_NONBLOCK)`, issue `fcntl.ioctl(fd, CDROMEJECT)` in a try/finally that closes the fd. Catch `OSError` (drive busy is the common case during a rip), log via `logging.warning("eject %s failed: %s", device, exc)`, return `False`. Success path returns `True`.
  - **Acceptance:** `pytest tests/drivers/test_drive.py` — all 9 PASS (5 existing + 4 eject). `ruff check archivist/drivers/drive.py` clean.

- [ ] {agent: drivers, depends: test-usb-discovery, id: impl-usb-discovery} Implement `discover_camera_usb_path` in `archivist/drivers/usb_discovery.py` (or `camera.py` — match the location chosen in `test-usb-discovery`). Walk `Path("/sys/class/video4linux").glob("video*/device/uevent")`, parse each `uevent` for the `PRODUCT=` line (Linux uevent format encodes vendor/product as `vendor/product/bcd`, e.g. `0c45/6366/100`); a match returns the USB bus path read from the sibling `device/` symlink resolution (or pulled from another uevent field — author picks based on what's actually in the file on the documented rig). When multiple `videoN` match, sort by the integer `N` and return the lowest. On no match, read `os.environ.get(env_var)` and return that (may be `None`). On `None`, `logging.warning("camera USB path: no sysfs match for %s and %s unset", vendor_product, env_var)` and return `None`. Wraps all filesystem operations in try/except so a missing `/sys/class/video4linux` (e.g. dev laptop) returns `None` cleanly rather than raising. Tests must keep passing without touching real `/sys`.
  - **Acceptance:** `pytest tests/drivers/test_usb_discovery.py` — 4 PASS. `ruff check archivist/drivers/usb_discovery.py` (or `camera.py`) clean. Module ≤80 lines.

- [ ] {agent: drivers, depends: test-camera-recovery, depends: impl-usb-discovery, id: impl-camera-recovery} Implement `capture_frame_with_recovery` in `archivist/drivers/camera.py` (the existing `capture_frame` stays as-is — recovery wraps it). Constructor/parameter takes the `discover_usb_path` callable (default `None` so unit tests can inject a fake; `__main__.py` wires in the real `discover_camera_usb_path`). On first failure, inspect `result.stderr` for the substring `VIDIOC_STREAMON`. If present and `retries > 0`, call `discover_usb_path()` to resolve the bus path; if it returns `None`, log a warning and return `None` without attempting recovery. Otherwise run `subprocess.run(["sudo", "tee", "/sys/bus/usb/drivers/usb/unbind"], input=usb_path, ...)` then `["sudo", "tee", ".../bind"]`, `time.sleep(2)`, retry `capture_frame`. Decrement `retries`. Other ffmpeg failures return `None` immediately. Recovery commands themselves use a try/except that logs and gives up — never raises. Note in a code comment that this requires NOPASSWD sudo for `tee` against those sysfs paths (already documented in `docs/operations/cm4-setup.md` per `cm4-setup-docs`).
  - **Acceptance:** `pytest tests/drivers/test_camera_recovery.py` — 5 PASS. Existing `tests/drivers/test_camera.py` still 5 PASS. `ruff check archivist/drivers/camera.py` clean.

- [ ] {agent: drivers, depends: test-systemctl, id: impl-systemctl} Implement `archivist/drivers/systemctl.py` exposing `stop_unit` and `start_unit`. `subprocess.run(["sudo", "systemctl", action, name], capture_output=True, text=True, timeout=10)`. Catch `FileNotFoundError`, `subprocess.TimeoutExpired`, log + return `False`. Non-zero exit → log stderr + return `False`. `True` only on returncode 0. Document the NOPASSWD sudo requirement in module docstring (cross-link to `docs/operations/cm4-setup.md` § "NOPASSWD sudo fragment" landed by `cm4-setup-docs`).
  - **Acceptance:** `pytest tests/drivers/test_systemctl.py` — 6 PASS. `ruff check archivist/drivers/systemctl.py` clean. Module ≤50 lines.

- [ ] {agent: pipeline, depends: test-capture-sequence, depends: impl-manifest, id: impl-capture} Implement `archivist/pipeline/capture.py` exposing `capture_disc`. Call signature matches the test. Filenames follow `docs/operations/cm4-setup.md` convention: `disc_front_ambient_001.jpg` ... `disc_front_ambient_003.jpg`, then `disc_front_lit_001.jpg` ... `disc_front_lit_003.jpg` (3 frames per burst — design says 10–15 per actual ffmpeg invocation, which the camera driver handles internally; the burst loop here is the number of distinct stills written). Use `time.sleep(settle_seconds)` directly (the state-machine tests inject a sleeper into the loop, not into `capture_disc` — capture is a leaf operation). Wrap the lit-burst section in try/finally so `led.power_off()` runs even on exception. Build `CaptureRecord(capture_id=..., lighting=..., image_paths=[...])` from the JPGs that actually exist on disk after each burst (filter out `None` returns from the camera).
  - **Acceptance:** `pytest tests/pipeline/test_capture.py` — 4 PASS. `ruff check archivist/pipeline/capture.py` clean. LED-restored invariant verified by test.

- [ ] {agent: pipeline, depends: test-rip-orchestrate, depends: impl-manifest, id: impl-rip} Implement `archivist/pipeline/rip.py` exposing `rip_disc`. Calls `ripper.rip(device, disc_dir / "audio")`. Translates `RipResult.tracks` (absolute `Path`s) to POSIX relative strings via `track.relative_to(disc_dir).as_posix()`. Returns a `RipRecord(status, tracks, errors)`.
  - **Acceptance:** `pytest tests/pipeline/test_rip.py` — 4 PASS. `ruff check archivist/pipeline/rip.py` clean.

- [ ] {agent: pipeline, depends: test-state-machine, depends: impl-eject, depends: impl-systemctl, depends: impl-capture, depends: impl-rip, id: impl-state-machine} Implement `archivist/state_machine/loop.py` exposing `ArchivistLoop`, the `LoopState` snapshot, and a top-level `run(loop, *, poll_interval=2.0)` driver function. State enum (use `enum.Enum`): `IDLE`, `WAITING`, `STABILIZE`, `CAPTURE`, `RIP`, `EJECT`. `tick()` reads drive status, advances at most one state, and returns the new state. Full happy-path cycle on STABILIZE→CAPTURE: `services.stop_unit("cdplay.service")` (log warning if `False` but proceed — the rip is what matters); `next_disc_id(discs_root)` → `prepare_disc_folder(disc_id, discs_root)` → `capture_disc(disc_dir, camera=..., led=...)` → `rip_disc(disc_dir, device, ripper=...)` → write the final manifest with the assembled captures + rip + a `single_session` pairing → transition to EJECT. EJECT calls `drive.eject(device)` then `services.start_unit("cdplay.service")` in a try/finally — the player restart is sacred. Updates `LoopState` (the dataclass shared with the FastAPI app) at every transition. Module docstring documents the invariants: cdplay-paired, LED-restored (delegated), idempotent disc-folder creation. The top-level `run` is a `while True: tick(); sleep(poll_interval)` loop suitable for being launched from a `python -m archivist.state_machine`.
  - **Acceptance:** `pytest tests/state_machine/` — all PASS. `ruff check archivist/state_machine/` clean. Module's public surface is `ArchivistLoop`, `LoopState`, `State` enum, `run` function — exported from `archivist/state_machine/__init__.py`.

- [ ] {agent: pipeline, depends: test-service-status, depends: test-service-ui, depends: vendor-design-tokens, id: impl-service} Implement `archivist/service/app.py` exposing `create_app(loop_state, log_path)` returning a `FastAPI` instance with `GET /`, `GET /api/status`, `GET /api/log?lines=N`. `LoopState` dataclass lives here too (or in a sibling `archivist/service/state.py` — author's call). Log endpoint: `subprocess`-free — read with `Path.open()`, `deque(f, maxlen=lines)` for memory-bounded tailing. Default `lines=200`, cap at 1000.
  - **HTML page (Mash Co. dressed).** Single inline string constant (or sibling `_PAGE_HTML = """..."""` in `app.py`). The HTML follows these patterns lifted from `/home/loydmilligan/Projects/Mash Co. Design System/README.md`:
    - `<html data-theme="dark">` (dark-first).
    - **Tokens** — either: (a) link `archivist/service/static/tokens.css` via `<link rel="stylesheet" href="/static/tokens.css">` (mount `StaticFiles(directory="archivist/service/static")` at `/static`); or (b) inline a `<style>` block with the relevant `--ink-*`, `--mash-pulp`, `--moss`, `--amber`, `--ember`, `--sky`, `--bone`, `--font-body`, `--font-mono`, `--r-3..r-6`, `--s-1..s-6` variables. Author picks based on whether the Google Fonts `@import` round-trip belongs in the head (link) or in the page CSS (inline). Document the choice in a code comment.
    - **Fonts** — load `Inter Tight` + `JetBrains Mono` from Google Fonts at view-time (Bricolage Grotesque is overkill for this single page; skip it). Add a code comment noting the tradeoff: the page renders correctly only when the CM4 has internet at view-time. The system is on the LAN — that's accepted.
    - **Layout** — sticky top app-bar (`position: sticky; top: 0; background: rgba(13, 17, 22, 0.85); backdrop-filter: blur(12px);`) holding the page title `cd-archivist` (sentence case for body copy, but the brand mark stays as-typed). One main column (`max-width: 720px; margin: 0 auto; padding: var(--s-5);`) holding a single card.
    - **State card** — `background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-4); padding: var(--s-5);` plus a **left-border accent** matching the current state's semantic color: `IDLE → var(--moss)`, `WAITING / STABILIZE / CAPTURE / RIP → var(--sky)`, `EJECT → var(--amber)`, `ERROR → var(--ember)`. Apply via a per-state CSS class set by the polling JS (e.g. swap `card--moss`, `card--sky`, etc. on the card element).
    - **Eyebrow + body title pattern** — the card header is two lines: an uppercase eyebrow `WHAT NEXT · CD-ARCHIVIST` (use `text-transform: uppercase; letter-spacing: 0.08em; color: var(--fg-muted); font-size: var(--fs-xs);`) and a body title in sentence case driven by the current state — e.g. IDLE → `Insert a CD to begin.`, STABILIZE → `Stabilizing the disc.`, CAPTURE → `Capturing the disc photos.`, RIP → `Ripping audio.`, EJECT → `Ejecting.`, ERROR → `Something failed — see the log.`.
    - **Log tail** — `<pre>` with `font-family: var(--mono); font-size: var(--fs-sm); color: var(--fg-muted); background: var(--ink-2); padding: var(--s-3); border-radius: var(--r-3); max-height: 320px; overflow: auto;`.
    - **Voice** — sentence case on every label. "you" / imperative ("Insert a CD", "Eject in progress" — never "Let's eject" or "We're ripping"). No emoji. No exclamation marks. No "🚀". Eyebrow strings are the only place uppercase is allowed.
    - **JS** — vanilla `fetch` polling every 2s for `/api/status` and `/api/log?lines=80`. Update card class + body title + log tail in place. On a successful update, flash a 200ms `border-color: var(--moss)` then fade — the "live updating" cue from the design system.
  - **Acceptance:** `pytest tests/service/` — all PASS. `ruff check archivist/service/` clean. Manual sanity (not gated on CI): `uvicorn archivist.service.app:create_app --factory --port 8228` boots and `/` renders in a browser; the page is unmistakably Mash Co. (slate-and-pulp, dark-first, sentence case, no emoji).

- [ ] {agent: pipeline, depends: impl-state-machine, depends: impl-service, depends: impl-usb-discovery, id: impl-entrypoint} Wire a single CLI entrypoint that boots both the loop and the FastAPI server in one process: `archivist/__main__.py`. It constructs `LoopState`, calls `discover_camera_usb_path()` once at startup and logs the resolved path (or a clear "no camera found — captures will be skipped" warning if it returns `None`), builds the `ArchivistLoop` with real driver instances (`read_drive_status`, `CDAudioRipper()`, `capture_frame_with_recovery` wired with the discovery callable, `LEDPanel("http://192.168.5.186")`, `systemctl.stop_unit/start_unit`, `time.monotonic`, `time.sleep`), starts the FastAPI app via `uvicorn` programmatically on `0.0.0.0:8228` in a background thread, then runs the loop in the foreground. Defaults: `device=/dev/sr0`, `discs_root=/srv/cd-archivist/discs`, `log_path=/srv/cd-archivist/logs/archivist.log`, `port=8228`. Configurable via env vars: `ARCHIVIST_DEVICE`, `ARCHIVIST_DISCS_ROOT`, `ARCHIVIST_LOG_PATH`, `ARCHIVIST_PORT` (default `8228` per `D-port-8228`), `ARCHIVIST_CAMERA_USB_PATH` (override-only — discovery is primary per `D-camera-autodiscover`; this env is the fallback path the discovery function consults when sysfs match fails) — all read in the same `os.environ.get("X", default)` pattern. Logging is configured via `logging.basicConfig` writing to both stderr and `log_path`. **Container-readiness (forward-compat, not a sprint-3 commitment):** this entrypoint should be written so its env-var-driven config and stdout-friendly logging are container-ready (no log file path that requires host bind-mounts beyond the documented `discs_root` + `log_path`; SIGTERM-graceful shutdown — install a signal handler that stops the uvicorn server and breaks the state-machine loop cleanly). The Docker question is postponed (`D-docker-postpone`); writing this way costs nothing extra and keeps the option open without committing to it.
  - **Acceptance:** `python -m archivist --help` prints a 1-screen help block. No new pytest tests required (dependency-injection seams are exercised by Wave 1/2 tests; this file is glue only). `ruff check archivist/__main__.py` clean. SIGTERM to the process triggers a clean shutdown (manually verified, not gated on CI).

### Wave 3 — Real-rig E2E (manual smoke; not pytest)

- [ ] {agent: pipeline, depends: impl-entrypoint, id: smoke-checklist} Write `docs/operations/sprint-2-smoke.md` — a numbered checklist for running the full pipeline against the real CM4 + real drive + real cam + real Tasmota. Sections: (1) preflight (`/srv/cd-archivist/discs` exists and is writable; `cdplay.service` is `active`; webcam responds to `v4l2-ctl --list-devices`; Tasmota responds to `curl http://192.168.5.186/cm?cmnd=Power`; sudoers fragment from `docs/operations/cm4-setup.md` § "NOPASSWD sudo fragment" is installed at `/etc/sudoers.d/cd-archivist`); (2) start the archivist (`python -m archivist` over ssh — systemd unit and Docker packaging are both postponed per `D-systemd-defer` / `D-docker-postpone`); (3) browse to `http://cm4:8228/` from a phone and confirm the status page renders **and looks like Mash Co.** (dark slate background, pulp-orange accent on the page title or the live-flash, sentence-case copy, no emoji); (4) insert a known audio CD and observe the state transitions in the web UI: WAITING → STABILIZE → CAPTURE → RIP → EJECT → IDLE — the card's left-border accent should swap colors as the state advances; (5) verify the on-disk artifact: `ls /srv/cd-archivist/discs/CD_NNNN/` shows `manifest.json`, populated `captures/` with 6 JPGs (3 ambient + 3 lit), populated `audio/` with N FLACs matching the CD's track count; `jq . manifest.json` shows `status="ripped"`, the captures, the rip record, the single_session pairing; (6) verify `cdplay.service` is `active` again post-eject.
  - **Fallback note (UI scope):** If `vendor-design-tokens` or `impl-service` slipped or shipped half-dressed, run the smoke against the bare-bones page anyway — the hardware path is what closes this sprint. The dressing can land in a fast follow-up. Log the slip in the Activity Log entry that closes this task.
  - **Acceptance:** Document committed at `docs/operations/sprint-2-smoke.md`. The author has run through it once on the real CM4 with one real CD and recorded the resulting `CD_NNNN` id + a short note of what worked / what surprised them in the Activity Log entry that closes this task. Any defects found get logged as Activity Log entries (and become sprint-3 candidates), not as in-flight task changes — sprint-2 closes once the happy path completes once.

- [ ] {agent: drivers, depends: smoke-checklist, id: smoke-camera-recovery} Manual recovery test: with the archivist running and idle, leave the cam untouched for ≥10 minutes (the documented onset window for `VIDIOC_STREAMON` flake), then insert a disc. Confirm that if ffmpeg's first-attempt fails with `VIDIOC_STREAMON`, the recovery path fires (USB unbind/rebind) and the second attempt succeeds. If the cam doesn't actually flake during the test window, document that and leave the recovery code in place untested-in-the-wild — log this honestly in the Activity Log.
  - **Acceptance:** Activity Log entry recording either (a) recovery fired and worked, or (b) cam didn't flake during the window — recovery code is exercised by Wave 1 unit tests but not yet observed in the wild. Either outcome is acceptable for closing this task.

## Agent Roster

<!-- O5=A — owns / doesNotTouch live here, not in per-agent profiles. The
     dashboard reads this table to flag pane activity that touches another
     agent's doesNotTouch territory. -->

| Agent | Owns | Does not touch |
|---|---|---|
| drivers | `archivist/drivers/{drive,led,camera,ripper,systemctl}.py`, `archivist/models/manifest.py`, `tests/drivers/` | `archivist/pipeline/`, `archivist/state_machine/`, `archivist/service/` |
| pipeline | `archivist/pipeline/{disc_id,folder,pairing,capture,rip}.py`, `archivist/state_machine/`, `archivist/service/` (incl. `archivist/service/static/`), `archivist/__main__.py`, `tests/pipeline/`, `tests/state_machine/`, `tests/service/`, `tests/__init__.py`, `tests/conftest.py`, `pyproject.toml`, `ruff.toml`, `docs/operations/cm4-setup.md`, `docs/operations/sprint-2-smoke.md` | `archivist/drivers/` internals (consumes their public interfaces) |

Same two agents as sprint-1 — no new role added. Justification: the new surface (state machine, FastAPI app, CLI entrypoint, smoke doc, docs touch-ups, vendored CSS file) is all orchestration / glue / docs, which is the pipeline agent's existing remit. The drivers agent picks up `systemctl.py` and the camera-recovery extension because they're hardware-facing primitives.

**External read-only dependency:** the **Mash Co. design system** at `/home/loydmilligan/Projects/Mash Co. Design System/`. The pipeline agent reads `README.md`, `SKILL.md`, and `colors_and_type.css` from there to land `archivist/service/static/tokens.css`, but **never writes** to that repo this sprint. Updating the Mash Co. README's "Products in scope" table to list cd-archivist is an explicit cross-repo follow-up the user owns.

Cross-agent meeting points expand: sprint-1 had `archivist.models.manifest` and `archivist.drivers.ripper.RipResult`; sprint-2 adds `archivist.drivers.camera.capture_frame_with_recovery`, `archivist.drivers.drive.eject`, and `archivist.drivers.systemctl.{stop_unit,start_unit}` — all consumed by `archivist/state_machine/loop.py`.

## Decision Log

<!-- Each entry: `### {{date}} — {{decision-id}} — {{summary}}` with a
     short body. Tower's audit log (~/.orc-tower/<slug>/audit/) is
     canonical for decision-request resolutions; this section is the
     project-readable mirror (N7) — orc proposes entries via
     ratification cards. -->

### 2026-05-14 — D-led-params — switch to `requests` `params=` dict

The sprint-1 `LEDPanel` built its Tasmota request URL by hand. Sprint-2
switches to `requests.get(f"{base_url}/cm", params={"cmnd": cmnd}, timeout=5)`.
Rationale: idiomatic, `requests` handles encoding, the URL construction is
one line shorter, and tests can introspect via `resp.request.url` or the
`params=` kwarg. The `tests/drivers/test_led.py` URL-introspection
assertions update shape in the same task (`led-params-refactor`) — they
still cover the three Tasmota commands (`Power On`, `Power Off`, `Power`)
and the "never raises" invariant. Implications: none beyond the test
update; the Tasmota wire format is unchanged.

### 2026-05-14 — D-design-system — adopt Mash Co. v0.1.0 for cd-archivist UI surfaces

cd-archivist becomes the **second consumer** of the Mash Co. design
system at `/home/loydmilligan/Projects/Mash Co. Design System/`, after
Orc Tower. Rationale: per the system's README, Mash Co. exists for Orc
Tower and future Mash Co. tools by the same operator; cd-archivist is a
homelab tool by that same operator; the dark-first slate-and-pulp voice
fits the tool's posture (a CM4 sitting in a closet that you check from
your phone). Integration is deliberately **shallow this sprint**: vendor
`colors_and_type.css` into `archivist/service/static/tokens.css` and
consume the tokens from a single inline-HTML page in `app.py`. No
component library, no build step, no JS framework, no Jinja. Implications:
(a) the FastAPI status surface in this sprint and any review UI in
sprint-3+ build on the same token foundation; (b) updates to the design
system can be re-pulled by re-running the copy (or `sync-to-consumer.mjs`);
(c) the Mash Co. README's "Products in scope" table needs cd-archivist
added — that's a cross-repo follow-up the user owns, not part of this
sprint.

### 2026-05-14 — D-port-8228 — FastAPI status surface listens on 8228

Locked the FastAPI port to **8228** (default for `ARCHIVIST_PORT`).
Rationale: avoids common dev ports (3000, 5000, 8000, 8080) so the
archivist can coexist with whatever else the operator runs on the LAN
without collision; memorable; not in any well-known service range.
Implications: smoke checklist and any future docs reference
`http://cm4:8228/`; firewall rules on the CM4 (if any) need to allow it
inbound on the LAN subnet.

### 2026-05-14 — D-systemd-defer — `archivist.service` systemd unit postponed (paired with the Docker decision)

Sprint-2 boots the archivist via `python -m archivist` over ssh per the
smoke checklist. Rationale: a systemd unit (auto-start on boot, restart
on crash, journald logging) is genuinely useful but introduces install /
permissions / logging-routing decisions that distract from the load-bearing
sprint-2 goal of getting the pipeline running once on real hardware.
The systemd-vs-Docker-vs-hybrid deployment shape gets revisited together
after sprint-2 closes (see `D-docker-postpone`); systemd isn't *committed*
to a future sprint, just taken off sprint-2's plate. Implications:
sprint-2's "deployment" model is "ssh in and run it"; logs go to `stderr`
+ the configured `log_path`; a crash means the operator restarts it by
hand.

### 2026-05-14 — D-camera-autodiscover — webcam USB sysfs path is auto-discovered, env is fallback

The camera's USB bus path is **auto-discovered at startup** by walking
`/sys/class/video4linux/video*/device/uevent` and matching on the
webcam's USB vendor:product ID (default `0c45:6366`, the documented
Microdia rig from `docs/operations/cm4-setup.md` line 11). When multiple
`videoN` entries match, the lowest-numbered one wins. If sysfs yields no
match, the discovery function falls back to `ARCHIVIST_CAMERA_USB_PATH`;
if that's also unset, it returns `None` and the state machine treats
that as "no camera, skip captures" without raising. Rationale: the
sprint-1 plan parked this as an env-var-only knob, but the env var
pattern is fragile in practice — operators forget to set it after a
re-image, the documented bus path drifts when a USB hub gets
re-cabled, and the "right" value is already deterministically derivable
from sysfs. Auto-discovery removes a config burden from the happy path
without removing operator escape hatches. The env var rationale (rig
overrides, dev-laptop testing) moves to **fallback only**: it kicks in
when sysfs doesn't have the expected vendor:product (a different webcam
plugged in, dev machine without `/sys/class/video4linux`, etc.).
Implications: new `discover_camera_usb_path` function in
`archivist/drivers/usb_discovery.py` (or `camera.py`) with its own test
file; `capture_frame_with_recovery` takes the discovery callable as an
injected dep instead of a `usb_path=` string; `__main__.py` calls
discovery once at startup and logs the resolved path (or a clear "no
camera found" warning). If the documented vendor:product ID drifts on
the real CM4, the impl agent re-checks via `lsusb` during smoke and
updates the default + `cm4-setup.md` together.

### 2026-05-14 — D-docker-postpone — containerization decision postponed (NOT committed to sprint-3)

Sprint-2 ships **bare-metal**: `python -m archivist` over ssh, host
systemd + NOPASSWD sudoers for `cdplay.service` start/stop and USB
unbind/rebind. No `Dockerfile`, no `docker-compose.yml`, no container
runtime in the picture *for sprint-2*.

**The Docker question is unmade, not deferred to a specific sprint.**
Sprint-2 takes containerization off the table for *this* sprint
because the hardware path needs to be debugged without a container
layer in between (`VIDIOC_STREAMON` flake, `cdplay.service`
coexistence, `/dev/sr0` ioctls, USB sysfs writes — every layer of
indirection like container userns, device cgroup rules,
`--privileged` semantics, bind-mount path mismatches is a layer of
confusion when something doesn't work on the real rig the first
time). Once sprint-2 proves the pipeline end-to-end on the documented
rig, the operator (you) revisits the deployment shape. Options on the
table at that point — none preferred, none ruled out:
  (a) Dockerize with documented `--privileged` + device passthrough
      (`--device /dev/sr0`, `--device /dev/video0`).
  (b) Stay bare-metal, add the `archivist.service` systemd unit
      (`D-systemd-defer`) for boot-survival.
  (c) Something hybrid (e.g. archivist in Docker, host-side helper
      script for systemctl over a mounted unix socket).

Implications for sprint-2: `impl-entrypoint` is written to be
container-ready (env-var-driven config, stdout-friendly logging,
SIGTERM-graceful shutdown) — this costs nothing extra and keeps
option (a) cheap if it wins. The smoke checklist runs
`python -m archivist` directly. The systemd-unit decision
(`D-systemd-defer`) is also still open and gets paired with the
Docker question at sprint close.

## Ratification Log

<!-- Same shape as Decision Log; entries land here when a
     ratification-needed card resolves with kind "ratified". -->

_No ratifications yet._

## Contract Changes

<!-- API / schema / coord-doc-template changes that other agents must
     respect. Each entry: `### {{date}} — {{summary}}` + body listing
     before/after. The dashboard surfaces unprocessed entries as
     "contract changes since you last looked." -->

_No contract changes yet. Note: `archivist/drivers/drive.py` gains an `eject` function and `archivist/drivers/camera.py` gains `capture_frame_with_recovery` — both additive, no break. New module `archivist/drivers/systemctl.py` is brand-new surface. New static asset path `archivist/service/static/tokens.css` is a vendored copy from the Mash Co. design system — re-syncable. Manifest schema is unchanged this sprint (still v0.2)._

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

### 2026-05-14 — planner — sprint-2 targeted overrides (port, USB autodiscover, Docker postponed)

- **Port:** locked FastAPI port `8765 → 8228`. Renamed Decision Log entry `D-port-8765 → D-port-8228`; updated all in-doc references (Sprint Goals, `impl-entrypoint`, `impl-service` manual sanity, `smoke-checklist`).
- **Webcam discovery:** flipped from env-var-only to **auto-discover with env fallback** (`D-camera-usb-env → D-camera-autodiscover`). Discovery walks `/sys/class/video4linux/video*/device/uevent` matching vendor:product `0c45:6366` (the documented Microdia rig, line 11 of `cm4-setup.md`). New tasks: `test-usb-discovery` (Wave 1, drivers, depends `tests-pkg`) + `impl-usb-discovery` (Wave 2, drivers, depends `test-usb-discovery`). Revised: `test-camera-recovery` (dropped custom-`usb_path` case; replaced with discovery-injection assertion + a no-discovery-result no-op case), `impl-camera-recovery` (now takes injected discovery callable), `impl-entrypoint` (calls discovery once at startup, logs resolved path or warning, wires callable into the recovery factory; env var demoted to override consumed inside discovery).
- **Docker:** added `D-docker-postpone` — sprint-2 stays bare-metal; the Docker question is **unmade**, not deferred to a specific sprint. Options on the table at sprint-2 close (per the Decision Log entry): full Docker with `--privileged` + device passthrough, bare-metal-with-systemd, or hybrid. `impl-entrypoint` is written container-ready (env-var config, stdout-friendly logging, SIGTERM-graceful shutdown) — costs nothing extra and keeps the option cheap if it wins.
- New totals: Wave 0 = 5, Wave 1 = 9 (was 8), Wave 2 = 9 (was 8), Wave 3 = 2 → **25 tasks** (was 23).
- Things noticed: (a) `cm4-setup.md` documents the camera as `Microdia Vitade AF (UVC, idVendor 0c45:6366)` not "GENBOLT" — the override referenced GENBOLT but the doc uses the actual chipset vendor; the impl agent should verify with `lsusb` during smoke and update both the discovery default and `cm4-setup.md` if the value drifts. (b) The historical Activity Log entry below still references `D-port-8765` and `D-camera-usb-env` by their old names — left as-is since it's an accurate snapshot of the prior revision; this entry supersedes it.

### 2026-05-14 — planner — sprint-2 revised (Mash Co. integration + open-question lock-ins)

- Locked the five open questions surfaced in the original draft. Four landed as Decision Log entries: `D-led-params` (params dict), `D-port-8765` (FastAPI port), `D-systemd-defer` (sprint-3), `D-camera-usb-env` (`ARCHIVIST_CAMERA_USB_PATH`). The fifth (NOPASSWD sudo) landed as a doc fragment task `cm4-setup-docs` — sudoers stays a manual install on the CM4, not a runtime dep of any pytest task.
- Added Mash Co. design-system integration as a deliberately-shallow visible-progress scope. New tasks: `vendor-design-tokens` (Wave 0, copies `colors_and_type.css` to `archivist/service/static/tokens.css`), and `cm4-setup-docs` (Wave 0, sudoers fragment doc). Revised: `test-service-ui` (now asserts tokens, dark theme, sentence case, no emoji) and `impl-service` (full Mash Co. dressing — sticky app-bar, single state card, left-border accent by state, eyebrow + sentence-case body title, mono log tail, vanilla-JS polling with 200ms moss flash).
- Logged `D-design-system` recording the adoption decision and the cross-repo follow-up: the Mash Co. README's "Products in scope" table doesn't list cd-archivist. The user owns that update — not done in this sprint.
- Roster `pipeline` owns expanded to include `archivist/service/static/` and `docs/operations/cm4-setup.md`. Mash Co. design system flagged as an external read-only dependency.
- New totals: Wave 0 = 5 (was 3), Wave 1 = 8, Wave 2 = 8, Wave 3 = 2 → **23 tasks** (was 21). UI scope is non-blocking for the hardware E2E per the Sprint Goals fallback note + Wave 3 fallback bullet.

### 2026-05-14 — planner — sprint-2 drafted

- 3 waves, 21 tasks total: Wave 0 (3 scaffold/follow-up), Wave 1 (8 failing-test tasks), Wave 2 (8 impl tasks), Wave 3 (2 manual smoke tasks). Wave 1 + Wave 2 are 16 paired TDD units (8 pairs).
- Goals re-framed around the deferred-from-sprint-1 list: state machine, FastAPI surface, cdplay.service coexistence, VIDIOC_STREAMON recovery, real-rig E2E.
- Roster stays at two agents (`drivers`, `pipeline`); new owns paths added for `archivist/state_machine/`, `archivist/service/`, `archivist/__main__.py`, `archivist/drivers/systemctl.py`, and the new test packages.
- Two sprint-1 follow-ups landed in Wave 0: `tests/__init__.py` + shared `FakeCompletedProcess` (tests-pkg), and `LEDPanel` `params=` refactor with a Decision Log entry (led-params-refactor).
- Sprint-2 is the "make it real" sprint: at close, inserting an audio CD into the CM4's drive should produce a populated `CD_NNNN/` and the user should be able to watch it happen on their phone.
