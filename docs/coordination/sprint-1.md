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

- **Hardware-facing driver primitives.** A drive-state probe (`CDROM_DRIVE_STATUS` ioctl), an LED orchestrator (Tasmota HTTP), a camera burst wrapper (ffmpeg, 15-frame keep-last), and an audio-CD ripper (`cdparanoia` → `flac`) — each a small, typed, fake-tested unit. No state machine glue this sprint.
- **Manifest schema v0.2.** Pydantic model and atomic read/write matching the §Manifest sketch in `docs/design/high-level-design.md` (schema_version `"0.2"`, `media_type`, `captures[]`, `rips[]`, `pairings[]`, `metadata`, `errors`). Idempotent on rewrite.
- **Disc archival skeleton.** `prepare_disc_folder(disc_id)` creates the canonical `CD_NNNN/{manifest.json, captures/, audio/, logs/, review/}` layout with an initial manifest; `next_disc_id()` allocates the next free identifier atomically (lockfile); a `single_session` `PairingRecord` is in place for forward-compat.
- **TDD discipline on every primitive.** Each component has a `test-X` task that lands first and an `impl-X` task that makes it pass. Subprocess calls (cdparanoia, ffmpeg, flac) and HTTP (Tasmota) are stubbed; nothing in sprint-1 touches the real `/dev/sr0`, real webcam, or live Tasmota.

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

<!-- What ships in sprint-2 (out of scope here):
     - state machine wiring drive-state → capture → rip → eject
     - FastAPI status surface
     - cdplay.service stop/restart across drive-claim windows
     - VIDIOC_STREAMON recovery via USB unbind/rebind
     - end-to-end happy path on the real CM4
     Sprint-1 ships primitives only, fake-tested. -->

### Wave 0 — Scaffold

- [ ] {agent: pipeline, id: pipeline-scaffold} Initialize the `archivist/` Python package: create empty package directories `archivist/{drivers,pipeline,models}/__init__.py` and `tests/{drivers,pipeline}/__init__.py`; write `pyproject.toml` (Python 3.11+, dependencies: `pydantic`, `requests`, runtime; `pytest`, `pytest-mock`, `ruff` dev); write `ruff.toml` (line-length 100, target-version py311, default selections); write `pytest.ini` or `[tool.pytest.ini_options]` in pyproject (test paths = `tests/`, addopts strict markers); write `tests/conftest.py` with shared fixtures: a `tmp_disc_root` factory fixture (yields a tmp dir laid out like `/srv/cd-archivist/discs/`) and a `fake_subprocess` fixture for stubbing `subprocess.run` / `subprocess.Popen` cleanly.
  - **Acceptance:** Files created: `pyproject.toml`, `ruff.toml`, `tests/conftest.py`, and the empty `__init__.py` files listed above. `pytest --collect-only` runs cleanly (collects zero tests, no errors). `ruff check archivist tests` returns 0. The package is installable in editable mode (`pip install -e .` succeeds) — verify locally, no commit needed.

### Wave 1 — Failing tests (parallel-safe; each implicit-depends on `pipeline-scaffold`)

- [ ] {agent: drivers, id: test-drive-status} Failing test for `read_drive_status(device: Path) -> Literal["no-disc","tray-open","drive-not-ready","disc-ok"]`. Tests stub the low-level ioctl/`fcntl.ioctl` call (or whatever the impl chooses — the test fixture mocks the syscall return value) and assert each of the four return states. Includes one test asserting the function raises `OSError` cleanly when the device path does not exist — no swallowing.
  - **Acceptance:** New file `tests/drivers/test_drive.py`. `pytest tests/drivers/test_drive.py` fails with import-error or NotImplementedError because `archivist/drivers/drive.py` doesn't exist yet. Five test cases: no-disc, tray-open, drive-not-ready, disc-ok, missing-device-raises.

- [ ] {agent: drivers, id: test-led} Failing tests for the Tasmota client class `LEDPanel(base_url: str)` with three methods: `power_on() -> bool`, `power_off() -> bool`, `status() -> Literal["on","off","unknown"]`. Tests mock `requests.get` (or `httpx` — drivers picks); cover (a) happy path for each method against `cmnd=Power%20On|Off|Power`; (b) network errors (`ConnectionError`, `Timeout`) return `False` / `"unknown"` and log a warning, **never raise**; (c) malformed JSON response is treated as `"unknown"`.
  - **Acceptance:** New file `tests/drivers/test_led.py`. `pytest tests/drivers/test_led.py` fails (`archivist/drivers/led.py` missing). Six-ish test cases covering happy/network-failure/malformed paths across the three methods. Documented invariant: `LEDPanel` methods never raise; failure is logged and surfaced via return value.

- [ ] {agent: drivers, id: test-camera} Failing tests for `capture_frame(device: Path, out_path: Path, *, frames: int = 15) -> Path | None`. Tests mock `subprocess.run` (use the `fake_subprocess` fixture from `conftest.py`); cover (a) success: subprocess returns code 0, function returns `out_path` and `out_path` is the file the test wrote a fixture JPG into; (b) non-zero exit code returns `None` and logs the stderr; (c) `FileNotFoundError` (ffmpeg missing) returns `None` and logs; (d) `out_path.parent` is created if missing.
  - **Acceptance:** New file `tests/drivers/test_camera.py`. A 1-pixel fixture JPG under `tests/fixtures/sample.jpg` (or generated inline). `pytest tests/drivers/test_camera.py` fails because `archivist/drivers/camera.py` is missing. Four test cases. Documented invariant: function never raises on subprocess failure; returns `None`.

- [ ] {agent: drivers, id: test-ripper} Failing tests for the `Ripper` Protocol and the `CDAudioRipper` implementation. Define `RipResult` dataclass (Pydantic or stdlib `@dataclass`) with fields `status: Literal["success","partial","fail"]`, `tracks: list[Path]` (the FLAC files that landed), `errors: list[str]`. Tests: (a) `CDAudioRipper.detect(Path("/dev/sr0"))` returns `"audio_cd"` when stubbed `CDROM_DISC_STATUS` ioctl reports audio; (b) `rip(device, out_dir)` happy path: subprocess mock returns code 0, fake produces stub `track01.wav` files, flac call succeeds, result.status == `"success"` and `tracks` lists the `.flac` files; (c) cdparanoia partial success (some tracks ripped, some failed) → status `"partial"`, partial tracks listed, errors populated; (d) cdparanoia hard fail → status `"fail"`, tracks empty.
  - **Acceptance:** New file `tests/drivers/test_ripper.py`. `pytest tests/drivers/test_ripper.py` fails (`archivist/drivers/ripper.py` missing). Four test cases. The `Ripper` Protocol has `media_types: set[str]`, `detect(device) -> str | None`, `rip(device, out_dir) -> RipResult` (exactly the signature in `docs/design/high-level-design.md` §"Pluggable ripper interface").

- [ ] {agent: drivers, id: test-manifest} Failing tests for `Manifest` Pydantic model and `read_manifest(path) -> Manifest` / `write_manifest(path, manifest) -> None`. Schema matches the §"Manifest sketch" in `high-level-design.md`: `schema_version: Literal["0.2"]`, `disc_id: str`, `media_type: Literal["audio_cd"]` (extensible), `created_at: datetime`, `status: str`, `captures: list[CaptureRecord]`, `rips: list[RipRecord]`, `pairings: list[PairingRecord]`, `metadata: dict`, `errors: list[str]`. Tests: (a) round-trip: write then read returns equal object; (b) idempotent write: writing the same manifest twice produces byte-identical files; (c) atomic write: implementation uses tmp-file + `os.replace` (test by inspecting that a `.tmp` sibling is gone after success); (d) schema_version mismatch on read raises `ValueError`; (e) unknown fields rejected at parse (Pydantic `extra="forbid"`).
  - **Acceptance:** New files `tests/drivers/test_manifest.py` and possibly `tests/drivers/conftest.py` for a `sample_manifest` fixture. `pytest tests/drivers/test_manifest.py` fails (`archivist/models/manifest.py` missing). Five test cases.

- [ ] {agent: pipeline, id: test-disc-id} Failing tests for `next_disc_id(discs_root: Path) -> str`. Tests use the `tmp_disc_root` conftest fixture. Covers: (a) empty root → returns `"CD_0001"`; (b) root with `CD_0001/`, `CD_0003/`, `CD_0007/` → returns `"CD_0008"` (max + 1, gaps don't matter); (c) ignores non-CD_NNNN entries (`scratch/`, `README.md`); (d) atomic under concurrent invocation: simulate two concurrent calls (use threads or `multiprocessing.Pool`) — both succeed, no two callers receive the same ID. Implementation hint for impl-disc-id: a tiny `.disc-id.lock` lockfile via `fcntl.flock`.
  - **Acceptance:** New file `tests/pipeline/test_disc_id.py`. `pytest tests/pipeline/test_disc_id.py` fails (`archivist/pipeline/disc_id.py` missing). Four test cases including the concurrency one.

- [ ] {agent: pipeline, id: test-folder} Failing tests for `prepare_disc_folder(disc_id: str, discs_root: Path) -> Path`. Covers: (a) returns `discs_root / disc_id`; (b) creates subdirectories `captures/`, `audio/`, `logs/`, `review/`; (c) writes an initial `manifest.json` whose contents parse cleanly via the manifest reader and have `schema_version="0.2"`, the given `disc_id`, `media_type="audio_cd"`, `status="created"`, empty `captures/rips/pairings/errors`, an ISO `created_at`; (d) idempotent: calling twice on the same disc-id+root does not raise and does not overwrite an existing populated manifest (existence of `manifest.json` is the guard).
  - **Acceptance:** New file `tests/pipeline/test_folder.py`. `pytest tests/pipeline/test_folder.py` fails (`archivist/pipeline/folder.py` missing). Four test cases. Documented invariant: `prepare_disc_folder` is idempotent and never overwrites.

- [ ] {agent: pipeline, id: test-pairing} Failing tests for `make_pairing(method: Literal["single_session"], confidence: Literal["high","medium","low"]="high") -> PairingRecord` and `attach_pairing(manifest: Manifest, pairing: PairingRecord) -> Manifest`. Covers: (a) `make_pairing("single_session")` returns a record with `method="single_session"`, `confidence="high"`, an ISO `created_at`; (b) `attach_pairing` appends to `manifest.pairings` and returns the updated manifest (does not mutate the input — or, if it does, document that explicitly); (c) `attach_pairing` is type-safe on the `method` literal.
  - **Acceptance:** New file `tests/pipeline/test_pairing.py`. `pytest tests/pipeline/test_pairing.py` fails (`archivist/pipeline/pairing.py` missing). Three test cases.

### Wave 2 — Implementations

- [ ] {agent: drivers, depends: test-drive-status, id: impl-drive} Implement `archivist/drivers/drive.py` exposing `read_drive_status(device: Path)`. Use `fcntl.ioctl` with `CDROM_DRIVE_STATUS` constant (`0x5326` on Linux) and the documented return values (`CDS_NO_INFO=0`, `CDS_NO_DISC=1`, `CDS_TRAY_OPEN=2`, `CDS_DRIVE_NOT_READY=3`, `CDS_DISC_OK=4`); map to the four-state literal. Open the device with `os.open(device, os.O_RDONLY | os.O_NONBLOCK)`, close in a `finally`. The `OSError` path bubbles up from `os.open`.
  - **Acceptance:** `pytest tests/drivers/test_drive.py` — 5 PASS. `archivist/drivers/drive.py` exists, ≤60 lines, typed throughout.

- [ ] {agent: drivers, depends: test-led, id: impl-led} Implement `archivist/drivers/led.py` exposing `LEDPanel`. Use `requests` (sync, ~5s timeout) against the three Tasmota URLs from `docs/operations/cm4-setup.md`. Wrap each call in try/except for `requests.exceptions.RequestException`; on failure log via `logging.warning("LED %s failed: %s", action, exc)` and return the documented sentinel. Parse `{"POWER":"ON"|"OFF"}` for `status()`; any other shape returns `"unknown"`.
  - **Acceptance:** `pytest tests/drivers/test_led.py` — all PASS. `archivist/drivers/led.py` exists. Invariant test (no method raises) passes.

- [ ] {agent: drivers, depends: test-camera, id: impl-camera} Implement `archivist/drivers/camera.py` exposing `capture_frame`. Call ffmpeg via `subprocess.run` with the exact argv from `docs/operations/cm4-setup.md` (`ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 1280x720 -i <device> -frames:v <frames> -y <out_path>`). Ensure `out_path.parent` exists with `mkdir(parents=True, exist_ok=True)`. Catch `subprocess.CalledProcessError`, `FileNotFoundError`, and `subprocess.TimeoutExpired` — return `None` on any of them. No retry logic in sprint-1 (the USB unbind/rebind recovery is sprint-2 scope).
  - **Acceptance:** `pytest tests/drivers/test_camera.py` — 4 PASS. `archivist/drivers/camera.py` exists. Never-raises invariant holds.

- [ ] {agent: drivers, depends: test-ripper, id: impl-ripper} Implement `archivist/drivers/ripper.py` exposing `Ripper` Protocol and `CDAudioRipper` class. `media_types = {"audio_cd"}`. `detect` uses `fcntl.ioctl` with `CDROM_DISC_STATUS` (`0x5327`) — `CDS_AUDIO` returns `"audio_cd"`, anything else returns `None`. `rip` spawns `cdparanoia -B -d <device> -- "1-" <out_dir>` via `subprocess.run`, then walks `out_dir/track*.wav` and pipes each through `flac --best`; collects resulting `.flac` paths into `RipResult.tracks`. Cdparanoia non-zero exit with some WAVs produced → `"partial"`. No WAVs at all → `"fail"`. All succeed → `"success"`.
  - **Acceptance:** `pytest tests/drivers/test_ripper.py` — 4 PASS. `archivist/drivers/ripper.py` exists. `RipResult` is exported and reusable from the pipeline package.

- [ ] {agent: drivers, depends: test-manifest, id: impl-manifest} Implement `archivist/models/manifest.py` exposing `Manifest`, `CaptureRecord`, `RipRecord`, `PairingRecord`, `read_manifest`, `write_manifest`. Pydantic `BaseModel` with `model_config = ConfigDict(extra="forbid")`. `write_manifest` writes to `<path>.tmp` then `os.replace(tmp, path)` for atomicity. `read_manifest` raises `ValueError` if `schema_version != "0.2"`. JSON uses `model_dump_json(indent=2)` plus a trailing newline — that's what makes the idempotent-write test pass.
  - **Acceptance:** `pytest tests/drivers/test_manifest.py` — 5 PASS. `archivist/models/manifest.py` exists. Atomic-write invariant verified by the test.

- [ ] {agent: pipeline, depends: test-disc-id, id: impl-disc-id} Implement `archivist/pipeline/disc_id.py` exposing `next_disc_id(discs_root: Path) -> str`. Acquire a `discs_root / .disc-id.lock` via `fcntl.flock(LOCK_EX)`, scan entries matching `CD_\d{4}`, compute `max + 1`, release lock. Pad with zero-fill to width 4 (`f"CD_{n:04d}"`). If no entries match, return `"CD_0001"`.
  - **Acceptance:** `pytest tests/pipeline/test_disc_id.py` — 4 PASS, including the concurrency test. `archivist/pipeline/disc_id.py` exists.

- [ ] {agent: pipeline, depends: test-folder, depends: impl-manifest, id: impl-folder} Implement `archivist/pipeline/folder.py` exposing `prepare_disc_folder(disc_id: str, discs_root: Path) -> Path`. Compute target = `discs_root / disc_id`. If `target / "manifest.json"` already exists, return `target` unchanged (idempotent guard). Otherwise `mkdir(parents=True, exist_ok=True)` for the subdirs `captures/`, `audio/`, `logs/`, `review/`, then call `write_manifest(target / "manifest.json", initial_manifest)` with the documented initial shape.
  - **Acceptance:** `pytest tests/pipeline/test_folder.py` — 4 PASS. `archivist/pipeline/folder.py` exists.

- [ ] {agent: pipeline, depends: test-pairing, depends: impl-manifest, id: impl-pairing} Implement `archivist/pipeline/pairing.py` exposing `make_pairing` and `attach_pairing`. `make_pairing` builds a `PairingRecord` (imported from `archivist.models.manifest`) with `method`, `confidence`, `created_at=datetime.now(UTC)`. `attach_pairing` returns a copy of the manifest with the pairing appended (`manifest.model_copy(update={"pairings": [*manifest.pairings, pairing]})`).
  - **Acceptance:** `pytest tests/pipeline/test_pairing.py` — 3 PASS. `archivist/pipeline/pairing.py` exists. Forward-compat note: future detached-capture workflows add `method="timestamp_window"` etc; today only `"single_session"` is used.

## Agent Roster

<!-- O5=A — owns / doesNotTouch live here, not in per-agent profiles. The
     dashboard reads this table to flag pane activity that touches another
     agent's doesNotTouch territory. -->

| Agent | Owns | Does not touch |
|---|---|---|
| drivers | `archivist/drivers/{drive,led,camera,ripper}.py`, `archivist/models/manifest.py`, `tests/drivers/` | `archivist/pipeline/`, `archivist/service/` |
| pipeline | `archivist/pipeline/{disc_id,folder,pairing}.py`, `tests/pipeline/`, `pyproject.toml`, `ruff.toml`, `conftest.py` | `archivist/drivers/` internals (consumes their public interfaces) |

Both panes run Claude Code. The meeting points across the agent boundary are the public interfaces of `archivist.models.manifest` (used by `pipeline/folder.py` and `pipeline/pairing.py`) and `archivist.drivers.ripper.RipResult` (used downstream once the state machine lands in sprint-2). The scaffold task is owned by `pipeline` because it owns `pyproject.toml`, `ruff.toml`, and `conftest.py`.

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

### 2026-05-14 — planner — sprint plan drafted

- Replaced the two-machine wave plan with a single-CM4 drivers + pipeline primitives plan: 1 scaffold + 8 TDD pairs = 17 tasks across two agents (`drivers`, `pipeline`).
- Goals re-framed as deliverables (driver primitives, manifest v0.2, disc archival skeleton, TDD discipline); FastAPI + state machine + cdplay coexistence + real-rig E2E explicitly deferred to sprint-2.
- Agent roster updated to the new `archivist/` package layout — old `src/cd_archivist/{...}` paths removed; cross-agent meeting points are `archivist.models.manifest` and `archivist.drivers.ripper.RipResult`.

### 2026-05-13 — orc — sprint-1 authored + workspace launched

- project adopted by orc-tower
- sprint-1 goals + 12-task wave plan committed (Wave 1 contracts, Wave 2 implementations, Wave 3 integration)
- agent roster: software + hardware, both Claude Code
- workspace launched: `tmax launch cd-archivist-sprint`
  - **tmax workspace name:** `cd-archivist-sprint`
  - **tmux session name:** `cd-archivist-cd-archivist-sprint` (composed by tmax, asymmetric — capture for warren PATCH per sibling-agent spec `docs/superpowers/specs/2026-05-12-orc-pane-in-left-drawer-and-idle-ping-design.md`)
  - panes verified: %16 orc-agent (orc-tower cwd), %17 software (cd-archivist cwd), %18 hardware (cd-archivist cwd)
- orc-agent orientation prompt sent next
