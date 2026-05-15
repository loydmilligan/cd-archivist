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

- [x] {agent: pipeline, id: pipeline-scaffold} Initialize the `archivist/` Python package: create empty package directories `archivist/{drivers,pipeline,models}/__init__.py` and `tests/{drivers,pipeline}/__init__.py`; write `pyproject.toml` (Python 3.11+, dependencies: `pydantic`, `requests`, runtime; `pytest`, `pytest-mock`, `ruff` dev); write `ruff.toml` (line-length 100, target-version py311, default selections); write `pytest.ini` or `[tool.pytest.ini_options]` in pyproject (test paths = `tests/`, addopts strict markers); write `tests/conftest.py` with shared fixtures: a `tmp_disc_root` factory fixture (yields a tmp dir laid out like `/srv/cd-archivist/discs/`) and a `fake_subprocess` fixture for stubbing `subprocess.run` / `subprocess.Popen` cleanly.
  - **Acceptance:** Files created: `pyproject.toml`, `ruff.toml`, `tests/conftest.py`, and the empty `__init__.py` files listed above. `pytest --collect-only` runs cleanly (collects zero tests, no errors). `ruff check archivist tests` returns 0. The package is installable in editable mode (`pip install -e .` succeeds) — verify locally, no commit needed.

### Wave 1 — Failing tests (parallel-safe; each implicit-depends on `pipeline-scaffold`)

- [x] {agent: drivers, id: test-drive-status} Failing test for `read_drive_status(device: Path) -> Literal["no-disc","tray-open","drive-not-ready","disc-ok"]`. Tests stub the low-level ioctl/`fcntl.ioctl` call (or whatever the impl chooses — the test fixture mocks the syscall return value) and assert each of the four return states. Includes one test asserting the function raises `OSError` cleanly when the device path does not exist — no swallowing.
  - **Acceptance:** New file `tests/drivers/test_drive.py`. `pytest tests/drivers/test_drive.py` fails with import-error or NotImplementedError because `archivist/drivers/drive.py` doesn't exist yet. Five test cases: no-disc, tray-open, drive-not-ready, disc-ok, missing-device-raises.

- [x] {agent: drivers, id: test-led} Failing tests for the Tasmota client class `LEDPanel(base_url: str)` with three methods: `power_on() -> bool`, `power_off() -> bool`, `status() -> Literal["on","off","unknown"]`. Tests mock `requests.get` (or `httpx` — drivers picks); cover (a) happy path for each method against `cmnd=Power%20On|Off|Power`; (b) network errors (`ConnectionError`, `Timeout`) return `False` / `"unknown"` and log a warning, **never raise**; (c) malformed JSON response is treated as `"unknown"`.
  - **Acceptance:** New file `tests/drivers/test_led.py`. `pytest tests/drivers/test_led.py` fails (`archivist/drivers/led.py` missing). Six-ish test cases covering happy/network-failure/malformed paths across the three methods. Documented invariant: `LEDPanel` methods never raise; failure is logged and surfaced via return value.

- [x] {agent: drivers, id: test-camera} Failing tests for `capture_frame(device: Path, out_path: Path, *, frames: int = 15) -> Path | None`. Tests mock `subprocess.run` (use the `fake_subprocess` fixture from `conftest.py`); cover (a) success: subprocess returns code 0, function returns `out_path` and `out_path` is the file the test wrote a fixture JPG into; (b) non-zero exit code returns `None` and logs the stderr; (c) `FileNotFoundError` (ffmpeg missing) returns `None` and logs; (d) `out_path.parent` is created if missing.
  - **Acceptance:** New file `tests/drivers/test_camera.py`. A 1-pixel fixture JPG under `tests/fixtures/sample.jpg` (or generated inline). `pytest tests/drivers/test_camera.py` fails because `archivist/drivers/camera.py` is missing. Four test cases. Documented invariant: function never raises on subprocess failure; returns `None`.

- [x] {agent: drivers, id: test-ripper} Failing tests for the `Ripper` Protocol and the `CDAudioRipper` implementation. Define `RipResult` dataclass (Pydantic or stdlib `@dataclass`) with fields `status: Literal["success","partial","fail"]`, `tracks: list[Path]` (the FLAC files that landed), `errors: list[str]`. Tests: (a) `CDAudioRipper.detect(Path("/dev/sr0"))` returns `"audio_cd"` when stubbed `CDROM_DISC_STATUS` ioctl reports audio; (b) `rip(device, out_dir)` happy path: subprocess mock returns code 0, fake produces stub `track01.wav` files, flac call succeeds, result.status == `"success"` and `tracks` lists the `.flac` files; (c) cdparanoia partial success (some tracks ripped, some failed) → status `"partial"`, partial tracks listed, errors populated; (d) cdparanoia hard fail → status `"fail"`, tracks empty.
  - **Acceptance:** New file `tests/drivers/test_ripper.py`. `pytest tests/drivers/test_ripper.py` fails (`archivist/drivers/ripper.py` missing). Four test cases. The `Ripper` Protocol has `media_types: set[str]`, `detect(device) -> str | None`, `rip(device, out_dir) -> RipResult` (exactly the signature in `docs/design/high-level-design.md` §"Pluggable ripper interface").

- [x] {agent: drivers, id: test-manifest} Failing tests for `Manifest` Pydantic model and `read_manifest(path) -> Manifest` / `write_manifest(path, manifest) -> None`. Schema matches the §"Manifest sketch" in `high-level-design.md`: `schema_version: Literal["0.2"]`, `disc_id: str`, `media_type: Literal["audio_cd"]` (extensible), `created_at: datetime`, `status: str`, `captures: list[CaptureRecord]`, `rips: list[RipRecord]`, `pairings: list[PairingRecord]`, `metadata: dict`, `errors: list[str]`. Tests: (a) round-trip: write then read returns equal object; (b) idempotent write: writing the same manifest twice produces byte-identical files; (c) atomic write: implementation uses tmp-file + `os.replace` (test by inspecting that a `.tmp` sibling is gone after success); (d) schema_version mismatch on read raises `ValueError`; (e) unknown fields rejected at parse (Pydantic `extra="forbid"`).
  - **Acceptance:** New files `tests/drivers/test_manifest.py` and possibly `tests/drivers/conftest.py` for a `sample_manifest` fixture. `pytest tests/drivers/test_manifest.py` fails (`archivist/models/manifest.py` missing). Five test cases.

- [x] {agent: pipeline, id: test-disc-id} Failing tests for `next_disc_id(discs_root: Path) -> str`. Tests use the `tmp_disc_root` conftest fixture. Covers: (a) empty root → returns `"CD_0001"`; (b) root with `CD_0001/`, `CD_0003/`, `CD_0007/` → returns `"CD_0008"` (max + 1, gaps don't matter); (c) ignores non-CD_NNNN entries (`scratch/`, `README.md`); (d) atomic under concurrent invocation: simulate two concurrent calls (use threads or `multiprocessing.Pool`) — both succeed, no two callers receive the same ID. Implementation hint for impl-disc-id: a tiny `.disc-id.lock` lockfile via `fcntl.flock`.
  - **Acceptance:** New file `tests/pipeline/test_disc_id.py`. `pytest tests/pipeline/test_disc_id.py` fails (`archivist/pipeline/disc_id.py` missing). Four test cases including the concurrency one.

- [x] {agent: pipeline, id: test-folder} Failing tests for `prepare_disc_folder(disc_id: str, discs_root: Path) -> Path`. Covers: (a) returns `discs_root / disc_id`; (b) creates subdirectories `captures/`, `audio/`, `logs/`, `review/`; (c) writes an initial `manifest.json` whose contents parse cleanly via the manifest reader and have `schema_version="0.2"`, the given `disc_id`, `media_type="audio_cd"`, `status="created"`, empty `captures/rips/pairings/errors`, an ISO `created_at`; (d) idempotent: calling twice on the same disc-id+root does not raise and does not overwrite an existing populated manifest (existence of `manifest.json` is the guard).
  - **Acceptance:** New file `tests/pipeline/test_folder.py`. `pytest tests/pipeline/test_folder.py` fails (`archivist/pipeline/folder.py` missing). Four test cases. Documented invariant: `prepare_disc_folder` is idempotent and never overwrites.

- [x] {agent: pipeline, id: test-pairing} Failing tests for `make_pairing(method: Literal["single_session"], confidence: Literal["high","medium","low"]="high") -> PairingRecord` and `attach_pairing(manifest: Manifest, pairing: PairingRecord) -> Manifest`. Covers: (a) `make_pairing("single_session")` returns a record with `method="single_session"`, `confidence="high"`, an ISO `created_at`; (b) `attach_pairing` appends to `manifest.pairings` and returns the updated manifest (does not mutate the input — or, if it does, document that explicitly); (c) `attach_pairing` is type-safe on the `method` literal.
  - **Acceptance:** New file `tests/pipeline/test_pairing.py`. `pytest tests/pipeline/test_pairing.py` fails (`archivist/pipeline/pairing.py` missing). Three test cases.

### Wave 2 — Implementations

- [x] {agent: drivers, depends: test-drive-status, id: impl-drive} Implement `archivist/drivers/drive.py` exposing `read_drive_status(device: Path)`. Use `fcntl.ioctl` with `CDROM_DRIVE_STATUS` constant (`0x5326` on Linux) and the documented return values (`CDS_NO_INFO=0`, `CDS_NO_DISC=1`, `CDS_TRAY_OPEN=2`, `CDS_DRIVE_NOT_READY=3`, `CDS_DISC_OK=4`); map to the four-state literal. Open the device with `os.open(device, os.O_RDONLY | os.O_NONBLOCK)`, close in a `finally`. The `OSError` path bubbles up from `os.open`.
  - **Acceptance:** `pytest tests/drivers/test_drive.py` — 5 PASS. `archivist/drivers/drive.py` exists, ≤60 lines, typed throughout.

- [x] {agent: drivers, depends: test-led, id: impl-led} Implement `archivist/drivers/led.py` exposing `LEDPanel`. Use `requests` (sync, ~5s timeout) against the three Tasmota URLs from `docs/operations/cm4-setup.md`. Wrap each call in try/except for `requests.exceptions.RequestException`; on failure log via `logging.warning("LED %s failed: %s", action, exc)` and return the documented sentinel. Parse `{"POWER":"ON"|"OFF"}` for `status()`; any other shape returns `"unknown"`.
  - **Acceptance:** `pytest tests/drivers/test_led.py` — all PASS. `archivist/drivers/led.py` exists. Invariant test (no method raises) passes.

- [x] {agent: drivers, depends: test-camera, id: impl-camera} Implement `archivist/drivers/camera.py` exposing `capture_frame`. Call ffmpeg via `subprocess.run` with the exact argv from `docs/operations/cm4-setup.md` (`ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 1280x720 -i <device> -frames:v <frames> -y <out_path>`). Ensure `out_path.parent` exists with `mkdir(parents=True, exist_ok=True)`. Catch `subprocess.CalledProcessError`, `FileNotFoundError`, and `subprocess.TimeoutExpired` — return `None` on any of them. No retry logic in sprint-1 (the USB unbind/rebind recovery is sprint-2 scope).
  - **Acceptance:** `pytest tests/drivers/test_camera.py` — 4 PASS. `archivist/drivers/camera.py` exists. Never-raises invariant holds.

- [x] {agent: drivers, depends: test-ripper, id: impl-ripper} Implement `archivist/drivers/ripper.py` exposing `Ripper` Protocol and `CDAudioRipper` class. `media_types = {"audio_cd"}`. `detect` uses `fcntl.ioctl` with `CDROM_DISC_STATUS` (`0x5327`) — `CDS_AUDIO` returns `"audio_cd"`, anything else returns `None`. `rip` spawns `cdparanoia -B -d <device> -- "1-" <out_dir>` via `subprocess.run`, then walks `out_dir/track*.wav` and pipes each through `flac --best`; collects resulting `.flac` paths into `RipResult.tracks`. Cdparanoia non-zero exit with some WAVs produced → `"partial"`. No WAVs at all → `"fail"`. All succeed → `"success"`.
  - **Acceptance:** `pytest tests/drivers/test_ripper.py` — 4 PASS. `archivist/drivers/ripper.py` exists. `RipResult` is exported and reusable from the pipeline package.

- [x] {agent: drivers, depends: test-manifest, id: impl-manifest} Implement `archivist/models/manifest.py` exposing `Manifest`, `CaptureRecord`, `RipRecord`, `PairingRecord`, `read_manifest`, `write_manifest`. Pydantic `BaseModel` with `model_config = ConfigDict(extra="forbid")`. `write_manifest` writes to `<path>.tmp` then `os.replace(tmp, path)` for atomicity. `read_manifest` raises `ValueError` if `schema_version != "0.2"`. JSON uses `model_dump_json(indent=2)` plus a trailing newline — that's what makes the idempotent-write test pass.
  - **Acceptance:** `pytest tests/drivers/test_manifest.py` — 5 PASS. `archivist/models/manifest.py` exists. Atomic-write invariant verified by the test.

- [x] {agent: pipeline, depends: test-disc-id, id: impl-disc-id} Implement `archivist/pipeline/disc_id.py` exposing `next_disc_id(discs_root: Path) -> str`. Acquire a `discs_root / .disc-id.lock` via `fcntl.flock(LOCK_EX)`, scan entries matching `CD_\d{4}`, compute `max + 1`, release lock. Pad with zero-fill to width 4 (`f"CD_{n:04d}"`). If no entries match, return `"CD_0001"`.
  - **Acceptance:** `pytest tests/pipeline/test_disc_id.py` — 4 PASS, including the concurrency test. `archivist/pipeline/disc_id.py` exists.

- [x] {agent: pipeline, depends: test-folder, depends: impl-manifest, id: impl-folder} Implement `archivist/pipeline/folder.py` exposing `prepare_disc_folder(disc_id: str, discs_root: Path) -> Path`. Compute target = `discs_root / disc_id`. If `target / "manifest.json"` already exists, return `target` unchanged (idempotent guard). Otherwise `mkdir(parents=True, exist_ok=True)` for the subdirs `captures/`, `audio/`, `logs/`, `review/`, then call `write_manifest(target / "manifest.json", initial_manifest)` with the documented initial shape.
  - **Acceptance:** `pytest tests/pipeline/test_folder.py` — 4 PASS. `archivist/pipeline/folder.py` exists.

- [x] {agent: pipeline, depends: test-pairing, depends: impl-manifest, id: impl-pairing} Implement `archivist/pipeline/pairing.py` exposing `make_pairing` and `attach_pairing`. `make_pairing` builds a `PairingRecord` (imported from `archivist.models.manifest`) with `method`, `confidence`, `created_at=datetime.now(UTC)`. `attach_pairing` returns a copy of the manifest with the pairing appended (`manifest.model_copy(update={"pairings": [*manifest.pairings, pairing]})`).
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

### 2026-05-14 — orc — sprint-1 closed

- All 17 tasks across Wave 0 / Wave 1 / Wave 2 are `[x]`. Test totals: drivers 32/32, pipeline 11/11; `ruff check archivist tests` clean.
- Commit chain (sprint scope):
  - `545cc9a` wave 0 scaffold
  - `4cf62e3` wave 1 pipeline failing tests
  - `61d04e2` wave 1 driver failing tests
  - `6bba896` coord-doc — drivers Wave 1 done
  - `273bfa6` impl-disc-id
  - `d3fead6` impl-manifest
  - `0771532` impl-drive
  - `b173f19` impl-folder
  - `03c5a0a` impl-pairing
  - `0f9ddb8` impl-led
  - `3878d89` impl-camera
  - `f03773e` impl-ripper
- Tag: `sprint-1-done` cut at the wrap commit so sprint-2 diffs are scoped cleanly.
- Out-of-scope items deferred to sprint-2 per the Wave 2 comment block (state machine wiring, FastAPI status surface, cdplay.service stop/restart, VIDIOC_STREAMON USB recovery, real-rig E2E).
- Two follow-ups surfaced during impl that are worth carrying into sprint-2 planning:
  - `tests/` has no `__init__.py`; ripper test had to inline a `FakeCompletedProcess` shim instead of importing from `tests/conftest.py`. Decide whether to make `tests/` a package or accept inline duplication.
  - `LEDPanel` pre-encodes `cmnd` into the URL string (vs passing as `params={...}`) so tests can introspect the raw URL — a test-driven choice, not necessarily the right production shape.

### 2026-05-14 — drivers — Wave 2 fully green: impl-led + impl-camera + impl-ripper landed

- `archivist/drivers/led.py` — `LEDPanel(base_url)` with `power_on` / `power_off` / `status`. Pre-encodes the `cmnd` argument via `urllib.parse.quote` and embeds it in the URL (so callers / tests can introspect the raw URL string), 5s timeout. Catches `requests.RequestException` and JSON-decode `ValueError`; logs `"LED %s failed: %s"` and returns the documented sentinel (`False` / `"unknown"`). Never raises. Parses `{"POWER": "ON" | "OFF"}` — any other shape → `"unknown"`. Also fixed a latent bug in `tests/drivers/test_led.py` where the fixture attached an attribute to a bare `list` (Python rejects this); replaced with a typed `_CapturedGets(list)` subclass.
- `archivist/drivers/camera.py` — `capture_frame(device, out_path, *, frames=15) -> Path | None`. ffmpeg argv per `docs/operations/cm4-setup.md`. Ensures `out_path.parent` exists. 30s timeout. Catches `FileNotFoundError` and `subprocess.TimeoutExpired`; also returns `None` on non-zero exit. Stderr is logged in every failure path. Never raises.
- `archivist/drivers/ripper.py` — `Ripper` Protocol + `RipResult` dataclass (`status`, `tracks`, `errors`) + `CDAudioRipper`. `detect` opens device O_RDONLY|O_NONBLOCK and ioctl's `CDROM_DISC_STATUS` (`0x5327`); `CDS_AUDIO` (100) → `"audio_cd"`, else `None`. `rip` calls `cdparanoia -B -d <device> -- "1-" <out_dir>`, globs `track*.wav`, runs `flac --best` per wav, collects `.flac` paths. Status logic: no WAVs → `"fail"`; cdparanoia non-zero exit (or any flac failure) with some WAVs → `"partial"` with `errors` populated; all clean → `"success"`. Also inlined a small `FakeCompletedProcess` shim in `tests/drivers/test_ripper.py` (the cross-package `from tests.conftest import ...` doesn't resolve because `tests/` has no `__init__.py`).
- Verified: `pytest tests/drivers/` — **32/32 PASS** across all five files. `ruff check archivist/ tests/drivers/` clean.
- Commits: `0f9ddb8 feat(sprint-1): impl-led`, `3878d89 feat(sprint-1): impl-camera`, and the following `impl-ripper` commit.
- Drivers Wave 2 is complete. The full drivers public surface (`drive`, `led`, `camera`, `ripper`, `models.manifest`) is implemented and tested. Pipeline's `impl-folder` + `impl-pairing` have been unblocked since `impl-manifest` landed.

### 2026-05-14 — drivers — Wave 2 impl-manifest + impl-drive landed

- `archivist/models/manifest.py` — `Manifest`, `CaptureRecord`, `RipRecord`, `PairingRecord` as Pydantic v2 `BaseModel` with `model_config = ConfigDict(extra="forbid")` on each. Schema matches the §"Manifest sketch" (schema_version Literal `"0.2"`, `media_type` Literal `"audio_cd"`, captures/rips/pairings lists, metadata dict, errors list). `read_manifest` raises `ValueError` on schema_version mismatch *before* Pydantic validation; unknown fields are caught by `extra="forbid"` and surface as `ValidationError` (a `ValueError` subclass). `write_manifest` is atomic: writes to `<path>.tmp` via `model_dump_json(indent=2) + "\n"`, then `os.replace`. Idempotent because the JSON is deterministic for equal inputs.
- `archivist/drivers/drive.py` — `read_drive_status(device: Path) -> DriveStatus`. Opens device with `os.open(device, os.O_RDONLY | os.O_NONBLOCK)` and closes in `finally`. Issues `fcntl.ioctl(fd, CDROM_DRIVE_STATUS)` (`0x5326`); maps `CDS_NO_DISC` / `CDS_TRAY_OPEN` / `CDS_DRIVE_NOT_READY` / `CDS_DISC_OK` to the four-state literal. `OSError` from `os.open` bubbles up unmodified — no swallowing.
- Verified: `pytest tests/drivers/test_manifest.py tests/drivers/test_drive.py` — 10/10 PASS. `ruff check archivist/` clean.
- Commits: `d3fead6 feat(sprint-1): impl-manifest — Pydantic v0.2 schema with atomic write` and the following `impl-drive` commit.
- Unblocks: pipeline `impl-folder` + `impl-pairing` (both import from `archivist.models.manifest`).
- Next: `impl-led`, `impl-camera`, `impl-ripper` remain in the drivers Wave 2 queue.

### 2026-05-14 — drivers — Wave 1 failing tests landed (test-drive-status, test-led, test-camera, test-ripper, test-manifest)

- `tests/drivers/test_drive.py` — 5 cases for `read_drive_status`: `CDS_NO_DISC` → `"no-disc"`, `CDS_TRAY_OPEN` → `"tray-open"`, `CDS_DRIVE_NOT_READY` → `"drive-not-ready"`, `CDS_DISC_OK` → `"disc-ok"`, and missing-device path raises `OSError` (bubbled from `os.open`, no swallowing). Stubs `archivist.drivers.drive.fcntl.ioctl`.
- `tests/drivers/test_led.py` — 10 cases for `LEDPanel`: happy paths for `power_on` / `power_off` / `status` against the Tasmota `cmnd=Power%20On|Off|Power` URLs; network errors (`ConnectionError`, `Timeout`) return `False` / `"unknown"` and log a warning; malformed JSON and unexpected shape return `"unknown"`; never-raises invariant verified against arbitrary `RequestException`. Patches `archivist.drivers.led.requests.get`.
- `tests/drivers/test_camera.py` — 5 cases for `capture_frame` via the `fake_subprocess` fixture: success returns `out_path` with ffmpeg argv asserted; non-zero exit returns `None` and logs stderr; `FileNotFoundError` (ffmpeg missing) returns `None`; `out_path.parent` is created if missing; `subprocess.TimeoutExpired` returns `None`. Never-raises invariant.
- `tests/drivers/test_ripper.py` — 7 cases: `CDAudioRipper` satisfies the `Ripper` Protocol (`media_types`/`detect`/`rip`); `RipResult` dataclass shape; `detect` returns `"audio_cd"` on `CDS_AUDIO`, `None` otherwise; `rip` happy → `"success"` with 3 `.flac` paths; partial cdparanoia exit with some WAVs → `"partial"` with errors populated; hard-fail with no WAVs → `"fail"`, tracks `[]`.
- `tests/drivers/test_manifest.py` — 5 cases for the `Manifest` pydantic model: round-trip equality; idempotent byte-identical write; atomic write (no `.tmp` sibling left behind); `read_manifest` raises `ValueError` on `schema_version != "0.2"`; `extra="forbid"` rejects unknown top-level fields.
- Verified: all five fail at collection as expected — `ModuleNotFoundError` on `archivist.drivers.{drive,led,camera,ripper}` and `archivist.models.manifest`. `ruff check tests/drivers/` clean.
- Commit: `61d04e2 test(sprint-1): wave 1 driver failing tests — drive, led, camera, ripper, manifest`.
- Next: `impl-manifest` (Wave 2) — unblocks pipeline's `impl-folder` + `impl-pairing`.

### 2026-05-14 — pipeline — impl-folder + impl-pairing landed (Wave 2 pipeline done)

- `archivist/pipeline/folder.py` — `prepare_disc_folder(disc_id, discs_root)` creates `<root>/<disc_id>/{captures,audio,logs,review}/` and writes the initial `Manifest` (schema 0.2, `media_type="audio_cd"`, `status="created"`, empty lists, `created_at=datetime.now(UTC)`). Idempotency guard: presence of `manifest.json` short-circuits and returns the target unchanged — re-invocations after downstream mutations (e.g. `status="ripped"`) preserve the existing manifest.
- `archivist/pipeline/pairing.py` — `make_pairing(method, confidence="high")` builds a `PairingRecord` with `created_at=datetime.now(UTC)`. `attach_pairing(manifest, pairing)` returns `manifest.model_copy(update={"pairings": [*manifest.pairings, pairing]})` — input manifest is not mutated. Only `method="single_session"` is wired this sprint; the `Literal` widens when detached-capture workflows land.
- Both consume `archivist.models.manifest` (delivered by drivers in d3fead6). All 11 `tests/pipeline/` cases PASS; ruff clean.
- **Wave 2 pipeline scope complete.** Sprint-1 pipeline owns are done.

### 2026-05-14 — pipeline — impl-disc-id landed

- `archivist/pipeline/disc_id.py`: `next_disc_id(discs_root)` acquires `fcntl.LOCK_EX` on `<discs_root>/.disc-id.lock`, scans for `CD_\d{4}` directories, computes `max + 1` (or 1 if empty), and **reserves the id by mkdir-ing the target directory before releasing the lock** — this is what makes the concurrency test pass; without in-lock reservation two threads would see the same `max` and return duplicates.
- `tests/pipeline/test_disc_id.py` — 4/4 PASS including `test_atomic_under_concurrent_invocation`.
- Started before drivers' impl-manifest because impl-disc-id has no manifest dependency. impl-folder and impl-pairing wait for impl-manifest.
- ruff clean.

### 2026-05-14 — pipeline — Wave 1 failing tests landed (test-disc-id, test-folder, test-pairing)

- `tests/pipeline/test_disc_id.py` — 4 cases: empty root → CD_0001; max+1 ignoring gaps (0001/0003/0007 → 0008); ignores non-`CD_NNNN` entries (scratch dir, README.md, lowercase `cd_0099`); concurrency via `ThreadPoolExecutor` with reservation `mkdir` inside the critical section — asserts two callers get distinct IDs (`CD_0001`, `CD_0002`).
- `tests/pipeline/test_folder.py` — 4 cases: returns `discs_root / disc_id`; creates `captures/audio/logs/review/` subdirs; writes initial `manifest.json` parsing cleanly via `read_manifest` with `schema_version="0.2"`, `media_type="audio_cd"`, `status="created"`, empty lists, non-null `created_at`; idempotency — second call does not overwrite a manifest that was mutated to `status="ripped"` with errors.
- `tests/pipeline/test_pairing.py` — 3 cases: `make_pairing("single_session")` defaults (`confidence="high"`, datetime `created_at`); `confidence` override flows through; `attach_pairing` returns a new `Manifest` with the pairing appended and does not mutate the input (per impl contract `model_copy(update=...)`).
- Verified: all three fail at import as expected (`ModuleNotFoundError: archivist.pipeline.disc_id` / `archivist.models.manifest` / `archivist.pipeline.folder` / `archivist.pipeline.pairing`). `ruff check tests/pipeline/` clean.
- `test-folder` and `test-pairing` are blocked-on-impl-manifest (drivers agent's Wave 2 work) — they import `Manifest`, `PairingRecord`, `read_manifest`. Expected and documented.

### 2026-05-14 — pipeline — Wave 0 scaffold landed

- Created `archivist/{drivers,pipeline,models}/__init__.py` and `tests/{drivers,pipeline}/__init__.py` for the new package layout.
- Rewrote `pyproject.toml` to the sprint-1 spec: Python 3.11+, runtime deps `pydantic`+`requests`, dev deps `pytest`+`pytest-mock`+`ruff`; setuptools find-packages scoped to `archivist*`; `[tool.pytest.ini_options]` with `testpaths=["tests"]` and `--strict-markers --strict-config`. Removed old runtime deps (pyyaml, watchdog, opencv-python, fastapi, uvicorn, etc.) per the new scope — they re-land when sprint-2 needs them.
- Added `ruff.toml` (line-length 100, target-version py311) and `tests/conftest.py` with `tmp_disc_root` factory + `fake_subprocess` fixtures (records calls, scriptable returncode/stdout/stderr, supports exception injection for `FileNotFoundError`/`TimeoutExpired` paths).
- Legacy `tests/test_disc_id.py` and `tests/test_pairing.py` import from the deprecated `cd_archivist` package; ignored via `addopts=--ignore-glob=tests/test_*.py` so collection stays clean. They will be removed when Wave 1 lands their replacements under `tests/pipeline/`.
- Verified: `pip install -e .` succeeds; `pytest --collect-only` collects 0 tests with no errors; `ruff check archivist tests` returns 0.
- `.gitignore`: added `*.egg-info/`, `build/`, `dist/`.
- Unblocks all of Wave 1 (drivers + pipeline tests).

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
