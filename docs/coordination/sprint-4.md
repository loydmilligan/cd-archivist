---
project: cd-archivist
sprint: sprint-4
created: 2026-05-15T00:00:00.000Z
updated: 2026-05-15T00:00:00.000Z
---

# cd-archivist — coordination doc (sprint-4)

> Strict template per Session O2=B / seed §12 Phase 8. The dashboard
> reads this as the canonical substrate (seed §3.7); orc emits
> `coord-doc-stale` cards when drift is detected (§3.8 / O7=A).
>
> Section headings are load-bearing — keep them as-is so the parser can
> find them. Section bodies are markdown-flexible.

## Plan Source

- Type: inline
- Path: this document (`## Active Sprint Plan` section)
- Active unit: sprint-4

## Sprint Goals

- **Music-pipeline contract conformance.** Make cd-archivist's per-disc
  output conform to `docs/ripper-handoff-for-claude-code.md` so the
  existing `/srv/cd-music-stack/` Beets/Navidrome/Jellyfin pipeline can
  consume rips with zero translation: env-driven inbox/working/failed
  paths, atomic working-dir → inbox handoff, `YYYY-MM-DD_HHMM_disc-NNNNNN`
  folder naming, `NN Track.flac` track filenames, `source.json` schema v1,
  per-disc `rip.log`, atomic `READY` marker, canonical `disc-photo.jpg`,
  and a `FAILED` disposition for failed audio rips.
- **Resolve the path inconsistency.** The handoff doc defaults to
  `~/music-pipeline/`; the actual dogfood stack uses `/srv/music/`. Make
  every path env-driven (`MUSIC_INBOX_DIR`, `MUSIC_WORKING_DIR`,
  `MUSIC_FAILED_DIR`); document both layouts in `cm4-setup.md`; add a
  `/srv/music/` override note inside the handoff doc itself.
- **Land three sprint-3 polish items proven by the CD_0018 real-rig
  rip.** (#13 the cdparanoia stderr parser regex doesn't match the
  real format and `LoopState.rip_progress` never populates; #12 WAVs
  are kept alongside FLACs and double per-disc disk usage; #11 the
  library page has no rip-status filter so failed rips clutter the
  default view.)
- **Legacy-readable, new-writable.** The 18 existing `CD_NNNN/` folders
  on the dogfood rig stay in place, untouched, in their v0.2-manifest
  shape. New rips write the new `YYYY-MM-DD_HHMM_disc-NNNNNN/` shape +
  `source.json`. The library UI reads BOTH manifests and prefers
  `source.json` when present — one small adapter, no migration script.
- **TDD discipline preserved.** Wave 1 = failing tests (parallel-safe);
  Wave 2 = impls (depends-gated). No Wave 3 pytest — real-rig
  validation is operator-driven; the existing
  `docs/operations/sprint-2-smoke.md` gets a contract-conformance
  appendix.

> **Scope-hierarchy reminder.** Bucket A (contract conformance) is the
> load-bearing scope this sprint — without it, the handoff to the
> music pipeline is a manual translation step. Bucket B (3 sprint-3
> polish items) is the visible-polish scope; if any one item slips it
> can ship in sprint-5 without breaking the contract. Stretch items
> (SHA-256 hashes in `source.json.files[]`, libdiscid /
> MusicBrainz disc id) ship only if Wave 2 finishes early.

## Active Initiatives

- _None — sprint-4 plan below is the substrate._

## Active Sprint Plan

<!-- What ships in sprint-5+ (out of scope here):
     - Manual capture / countdown / LED-mode toggle (the now-demoted
       `docs/design/2026-05-15-manual-capture-and-album-art.md`)
     - Album art uploads (front/back/inside/liner-notes, multipart
       upload, magic-byte validation)
     - Live alignment overlay
     - OCR of disc label (populates `physical_disc.label_text_guess`)
     - AccurateRip verification (populates `audio.accuraterip_verified`)
     - ISRC / UPC / TOC capture (populates `identifiers.{isrcs,upc,
       cd_toc}`)
     - CUE sheet generation (`album.cue`)
     - `archivist.service` systemd unit (still postponed per
       `D-systemd-defer`)
     - Containerization / Docker (still postponed per
       `D-docker-postpone`)
     - Editable review UI (rename tracks, fix metadata)
     - Navidrome / Beets / Jellyfin integration — the music-pipeline
       stack handles these; cd-archivist only writes into the inbox
     - Migration script for existing 18 `CD_NNNN/` folders — they stay
       legacy-as-is per `D-folder-naming-migration` -->

### Wave 0 — Operator-driven infrastructure migration (gates Wave 1)

> **This wave must complete before Wave 1 starts.** All Bucket A
> contract-conformance work assumes the music-pipeline inbox is on the
> same filesystem as the cd-archivist process (so `os.replace(working_
> dir, inbox_dir)` is a true atomic rename, not a cross-host copy). The
> migration below moves the music stack onto the CM4 alongside
> cd-archivist, eliminating the cross-machine transport question
> entirely.

- [x] {agent: operator, id: migrate-music-stack} **Operator-owned —
  human-driven, not an agent task.** Follow the procedure in
  `docs/operations/2026-05-15-music-stack-migration.md` to relocate the
  music-pipeline stack (Navidrome + Jellyfin + beets) from the laptop
  (`/srv/cd-music-stack` and `/srv/music`) onto the CM4. After
  migration, cd-archivist-on-CM4 writes directly into the same-
  filesystem inbox per the music-pipeline contract — co-locating
  ripper and importer, eliminating the cross-machine transport
  question. The operator owns execution; no agent runs this task.
  - **Acceptance:** After migration, all three containers are `Up` on
    the CM4 (`ssh cm4 'docker ps' | grep cd_`); the URLs
    `http://192.168.6.38:4533/`, `http://192.168.6.38:8096/`, and
    `http://192.168.6.38:8337/` are reachable from the LAN; the
    existing `CD_0004` and `CD_0018` folders are visible at
    `ssh cm4 'ls /srv/music/inbox/'`; and a test
    `docker exec -it cd_beets beet import /downloads/CD_0018/` works.

### Wave 1 — Failing tests (parallel-safe)

#### Bucket A — music-pipeline contract conformance

- [ ] {agent: pipeline, id: test-music-paths} Failing tests for the new
  env-driven path configuration in `archivist/__main__.py`. Three new
  env vars consumed at startup: `MUSIC_INBOX_DIR` (default
  `~/music-pipeline/inbox`), `MUSIC_WORKING_DIR` (default
  `~/music-pipeline/.ripping`), `MUSIC_FAILED_DIR` (default
  `~/music-pipeline/failed`). The legacy `ARCHIVIST_DISCS_ROOT` env var
  is **aliased** to `MUSIC_INBOX_DIR` for backward compat (warning
  logged when only the legacy var is set). Tests: (a) all three vars
  unset → defaults expand `~` correctly; (b) all three vars set → those
  values used; (c) only `ARCHIVIST_DISCS_ROOT` set → its value used as
  inbox, deprecation warning logged; (d) parent dirs auto-created at
  startup if missing; (e) write-permission validation: a read-only
  inbox raises a clear `PermissionError` at startup with the path + env
  var name in the message.
  - **Acceptance:** New file `tests/test_main_music_paths.py` (sibling
    to `tests/test_main_logging.py`). Five cases. Fails until
    `impl-music-paths`.

- [ ] {agent: pipeline, id: test-folder-naming} Failing tests for the
  new disc folder naming scheme. New helper `next_disc_folder_name(
  inbox_root: Path, *, now: datetime | None = None) -> str` in
  `archivist/pipeline/disc_id.py` (or sibling `archivist/pipeline/
  folder_name.py` — author's call). Format:
  `YYYY-MM-DD_HHMM_disc-NNNNNN` where `NNNN..` is a monotonic
  6-digit-zero-padded counter. Tests: (a) empty inbox + injected
  `now=2026-05-14T18:32:00` → returns `2026-05-14_1832_disc-000001`;
  (b) inbox already contains
  `2026-05-13_0900_disc-000420/` → returns `..._disc-000421`; (c)
  the counter scans only folder names matching the new shape — legacy
  `CD_NNNN/` folders are ignored (do NOT contribute to the counter);
  (d) local time, 24-hour (no AM/PM, no UTC `Z` suffix); (e) safe
  characters only (no spaces, no shell metacharacters); (f) collision
  guard — if the computed name already exists (clock jump or manual
  test artifact), the counter increments until the name is free. The
  fcntl-based serialization from `next_disc_id` is preserved (rename
  the lockfile to `.disc-folder.lock` or reuse it — author's call;
  recommend reuse).
  - **Acceptance:** Tests in `tests/pipeline/test_disc_id.py` (or new
    `tests/pipeline/test_folder_name.py`). Six cases. Existing
    `next_disc_id` tests still pass — the legacy helper stays
    available for the legacy code path until everything migrates.

- [ ] {agent: pipeline, id: test-track-rename} Failing tests for the
  new post-FLAC track-rename step. After `flac` produces
  `track01.cdda.flac`, a new helper `rename_tracks_to_canonical(audio_dir:
  Path) -> list[Path]` renames each `trackNN.cdda.flac` to `NN
  Track.flac` (zero-padded NN, single space, no metadata-aware
  naming this sprint). Tests: (a) directory with `track01.cdda.flac`,
  `track02.cdda.flac`, `track12.cdda.flac` → renamed to `01 Track.flac`,
  `02 Track.flac`, `12 Track.flac`; (b) returns the new paths in track
  order; (c) idempotent — calling twice on an already-canonical
  directory is a no-op (no errors); (d) leaves non-`trackNN.cdda.flac`
  files alone (e.g. an `album.cue` if it ever lands); (e) collision
  guard — if a target name already exists, raise rather than overwrite.
  - **Acceptance:** New file `tests/pipeline/test_rip_canonical_names.py`.
    Five cases. Fails until impl. Helper lives in
    `archivist/pipeline/rip.py` next to `rip_disc`.

- [ ] {agent: pipeline, id: test-source-json-model} Failing tests for
  the new Pydantic v2 model `SourceJson` (schema v1) per the handoff
  doc §source.json. New file `archivist/models/source.py`. Top-level
  fields: `schema_version: Literal[1]`, `ripper`, `disc`, `drive`,
  `audio`, `identifiers`, `detected_metadata`, `physical_disc`,
  `files`, `status`. All sub-models use `extra="forbid"` (consistent
  with `Manifest`). Tests: (a) round-trip the minimal example from the
  handoff doc §"Minimal valid source.json" — load via
  `SourceJson.model_validate_json`, dump, load again, equality holds;
  (b) full example from the handoff doc §source.json round-trips; (c)
  schema_version mismatch raises (e.g. payload with
  `"schema_version": 2`); (d) extra fields rejected; (e) timestamps
  serialize as ISO-8601 with timezone offsets (not naive UTC, not
  trailing `Z` — local with offset per the handoff doc spec);
  (f) `status.rip_success: bool` and `status.photo_success: bool`
  required; (g) `files: list[FileEntry]` where each entry is `path`,
  `kind: Literal["audio","photo","log"]`, `size_bytes: int`, optional
  `sha256: str | None = None` (sprint-4 default `None`; stretch task
  populates).
  - **Acceptance:** New file `tests/models/test_source.py`. Seven
    cases. Fails until `impl-source-json-model`. The legacy
    `archivist/models/manifest.py` (Manifest v0.2) stays untouched —
    both models coexist.

- [ ] {agent: pipeline, id: test-source-json-write} Failing tests for
  `write_source_json(path: Path, payload: SourceJson) -> None` and
  `read_source_json(path: Path) -> SourceJson`. Tests: (a) write +
  read round-trip equals the original; (b) atomic write — `.tmp`
  sibling + `os.replace` (same shape as `write_manifest`); (c) read
  raises `ValueError` on schema_version mismatch; (d) read raises on
  malformed JSON (clear message naming the path).
  - **Acceptance:** Tests in `tests/models/test_source.py`. Four
    cases. Fails until impl.

- [ ] {agent: pipeline, id: test-working-dir-handoff} Failing tests for
  the new working-dir → inbox atomic handoff in the state machine.
  Tests in `tests/state_machine/test_loop.py`: (a) STABILIZE creates
  the disc folder under `working_dir`, NOT under `inbox_dir`; (b)
  RIP writes audio + rip.log under `working_dir`; (c) after CAPTURE
  completes (and `source.json` + `disc-photo.jpg` are written), the
  loop performs `os.replace(working_dir / folder_name, inbox_dir /
  folder_name)` and only then writes `READY`; (d) at no point does
  the inbox contain a partially-populated folder lacking `READY`; (e)
  if the working-dir → inbox move fails (e.g. `OSError`), state
  transitions to ERROR with the failure recorded; the working-dir
  folder is left intact for operator triage. Uses fakes for the
  ripper / camera / led; injects `working_dir` and `inbox_dir`
  separately into the loop construction.
  - **Acceptance:** Five new cases in `tests/state_machine/test_loop.
    py`. Fails until `impl-working-dir-handoff`. Existing capture-
    after-eject tests revised to use the new (working_dir, inbox_dir)
    constructor signature.

- [ ] {agent: pipeline, id: test-ready-marker} Failing tests for the
  atomic `READY` marker writer. New helper `write_ready_marker(
  disc_dir: Path, *, ready_at: datetime, schema_version: int = 1) ->
  Path` in `archivist/pipeline/folder.py` (or sibling). Tests: (a)
  writes `READY.tmp` first, then `os.replace`s to `READY`; (b) `READY`
  contents include `ready_at=<ISO-8601-with-offset>` and
  `schema_version=1`; (c) `READY` is absent during write — a fake
  `os.replace` that raises before renaming leaves only `READY.tmp` on
  disk, no `READY`; (d) refuses to overwrite an existing `READY`
  (raises `FileExistsError`); (e) refuses to write `READY` if any of
  these required files are missing in `disc_dir`: any `*.flac` audio
  file, `source.json`, `rip.log` — raises a clear error naming the
  missing files. (Photo is NOT required per the handoff doc — a
  failed photo capture still gets `READY` with `photo_success: false`.)
  - **Acceptance:** New file `tests/pipeline/test_ready_marker.py`.
    Five cases. Fails until impl.

- [ ] {agent: pipeline, id: test-canonical-photo} Failing tests for
  the canonical-disc-photo selection. New helper
  `select_canonical_photo(captures_dir: Path) -> Path | None`. Per
  `D-canonical-disc-photo`, picks `disc_front_lit_002.jpg` (the
  middle of the 3 lit frames) if present; falls back to any
  `disc_front_lit_*.jpg`; returns `None` if no lit captures exist.
  Then `copy_canonical_photo(disc_dir: Path) -> Path | None`: calls
  the selector, `cp`s the chosen file to `<disc_dir>/disc-photo.jpg`,
  returns the new path (or `None` if no photo to copy). Tests: (a)
  captures dir with all 6 files → `disc_front_lit_002.jpg` chosen;
  (b) captures dir with only 1 lit (`disc_front_lit_000.jpg`) → that
  one chosen; (c) captures dir with only ambient frames → returns
  `None`; (d) `copy_canonical_photo` writes
  `<disc_dir>/disc-photo.jpg` byte-equal to the source; (e) the
  supplemental 5 captures are NOT moved (left in `captures/` for the
  operator); (f) idempotent — calling twice produces the same
  `disc-photo.jpg`.
  - **Acceptance:** New file `tests/pipeline/test_canonical_photo.py`.
    Six cases. Fails until impl. Helper lives in
    `archivist/pipeline/capture.py` (next to `capture_disc`).

- [ ] {agent: pipeline, id: test-source-json-builder} Failing tests for
  `build_source_json(disc_dir: Path, *, ripper_name, ripper_version,
  hostname, drive_info, rip_record, capture_result, ready_at,
  timestamps) -> SourceJson` — the assembler that turns the
  state-machine's per-cycle bookkeeping into a populated `SourceJson`.
  Tests: (a) happy path with a successful rip + successful capture →
  `status.rip_success=True`, `status.photo_success=True`,
  `status.ready=True`, `physical_disc.photo="disc-photo.jpg"`,
  `audio.track_count` matches the FLAC count, `files[]` lists every
  audio file + the photo + `rip.log` with `size_bytes` populated and
  `sha256=None`; (b) rip success + photo failure → `photo_success=
  False`, `physical_disc.photo=None`, `status.warnings` includes the
  failure message, `status.ready=True` (per the handoff doc — photo
  failure does NOT block READY); (c) rip failure → `rip_success=
  False`, `status.ready=False`, `status.errors` populated; (d)
  `detected_metadata` is always all-nulls (no inventing — sprint-5
  populates from OCR/MB-disc-id); (e) `physical_disc.label_text_guess`
  / `appears_burned` / `handwritten` are always null in sprint-4;
  (f) timestamps include local timezone offsets (assert presence of
  `+` or `-` in the ISO string, not `Z`).
  - **Acceptance:** New file `tests/pipeline/test_source_json_builder.
    py`. Six cases. Fails until impl. Helper lives in
    `archivist/pipeline/source_json.py` (new file).

- [x] {agent: drivers, id: test-rip-log-writer} Failing tests for the
  new per-disc `rip.log` plain-text writer. New helper
  `archivist/drivers/rip_log.py::RipLogWriter` (context-manager
  style): construct with the disc-folder path, the writer opens
  `<disc_dir>/rip.log` in append mode, exposes `event(message: str)`
  which writes a `[<ISO-8601-local-with-offset>] <message>\n` line
  and flushes. Tests: (a) instantiation creates the file; (b)
  `event("Rip started")` produces a line of the documented shape
  (regex assertion on the timestamp prefix); (c) multiple events
  preserve order; (d) `__exit__` flushes + closes; (e) re-opening on
  the same path appends rather than truncates. Also: a thin
  integration shim — when `CDAudioRipper.rip(progress_callback=...)`
  is called with a `RipLogWriter.event` callback, every cdparanoia
  stderr line lands as a `rip.log` entry (assert by inspecting the
  log file after a fake-Popen rip).
  - **Acceptance:** New file `tests/drivers/test_rip_log.py`. Six
    cases (5 unit + 1 integration). Fails until impl. Lives in
    `drivers/` because it's the writer used by the ripper; the state
    machine consumes it as a callback.

- [ ] {agent: pipeline, id: test-failed-marker} Failing tests for the
  failed-disc disposition. Per `D-failed-disc-disposition`, on RIP
  failure the loop: (i) writes `<working_dir>/<folder>/FAILED` (a
  marker file with `failed_at=<ISO>` + `reason=<short string>`); (ii)
  writes `source.json` with `status.rip_success=False, ready=False`
  + the rip.log; (iii) atomically moves the folder
  `working_dir/<folder>` → `failed_dir/<folder>` (NOT into inbox);
  (iv) does NOT write a `READY` marker. Tests in
  `tests/state_machine/test_loop.py`: (a) RIP raises → folder lands
  in `failed_dir`, contains `FAILED`, `source.json`, `rip.log`, no
  `READY`; (b) `RipRecord(status="fail")` returned → same; (c)
  inbox is untouched (no folder created there for the failure); (d)
  the existing terminal `ERROR` state still entered (the operator
  recovery via `tray-open` → IDLE behavior from sprint-3 is
  preserved); (e) `cdplay` still restarts in the failure path
  (existing cdplay-paired invariant).
  - **Acceptance:** Five cases added to `tests/state_machine/test_
    loop.py`. Fails until `impl-failed-marker`.

#### Bucket B — sprint-3 polish carryovers (proven by CD_0018)

- [ ] {agent: pipeline, id: test-rip-progress-real-format} Failing
  tests for the `parse_cdparanoia_progress` regex update. The
  sprint-3 parser was written from the cdparanoia man page; the
  CD_0018 real-rig stderr format doesn't match. Author captures a
  real stderr sample (either: dump from any of the 18 existing
  `CD_NNNN/` rip logs if available, OR run a fresh test rip with
  `cdparanoia -v` against a known disc and capture stderr to a
  fixture file). New fixture file `tests/pipeline/fixtures/
  cdparanoia_stderr_real.txt` with ≥30 lines covering: per-track
  "Ripping from sector ..." headers, the smiley/percent progress
  lines, the "no errors" or "error" trailer per track, and the
  final "Done." line. Tests: (a) feeding each line through
  `parse_cdparanoia_progress` produces a non-`None` result for at
  least the per-track headers and the smiley/percent lines (assert
  ≥10 non-None results across the 30+ lines); (b) the parsed string
  shape matches `"track N/T, P%"` (regex assertion on each non-None
  result); (c) the existing 4 synthetic test cases either pass or
  are removed/updated to match the real format (author's call —
  prefer keeping synthetic cases that target edge conditions like
  "0%", "100%", "no track number yet"); (d) feeding the full fixture
  end-to-end via `CDAudioRipper.rip` with a fake Popen yielding the
  fixture lines results in `LoopState.rip_progress` being non-None
  by the end of the run. **Decision locked (2026-05-15):** fixture
  capture is part of this task — the pipeline agent does a fresh
  test rip on the CM4 during impl to capture cdparanoia's actual
  stderr. Sprint-3's streaming refactor (`impl-rip-stderr-stream`)
  means every line lands in `archivist.log` via `_logger.info`, so
  the agent greps that file post-rip to extract the fixture
  content. No need to re-instrument cdparanoia or run it standalone.
  - **Acceptance:** Updated `tests/pipeline/test_rip_progress.py` +
    new fixture file. ≥4 cases including the fixture-driven check.
    Fails until the parser regex is updated.

- [ ] {agent: pipeline, id: test-wav-cleanup} Failing tests for
  post-FLAC WAV deletion. Per `D-wav-cleanup`, after each track's
  flac conversion succeeds, the source `track01.cdda.wav` is
  deleted; an `ARCHIVIST_KEEP_WAVS=1` env var disables the cleanup
  (operator who wants AccurateRip verification artifacts). Tests in
  `tests/drivers/test_ripper.py`: (a) default behavior — after
  successful flac, the WAV is gone, the FLAC remains; (b)
  `ARCHIVIST_KEEP_WAVS=1` set → both WAV + FLAC remain; (c) flac
  conversion fails → WAV is preserved (no deletion of input on a
  failed conversion); (d) the env-var read happens at ripper
  construction time (or per-rip — author's call; tests target the
  observable behavior).
  - **Acceptance:** Four cases in `tests/drivers/test_ripper.py`.
    Fails until `impl-wav-cleanup`.

- [ ] {agent: pipeline, id: test-library-status-filter} Failing
  tests for the `?status=` query parameter on `GET /library`.
  Query param: `status` ∈ {`success`, `failed`, `all`}, default
  `success`. Tests in `tests/service/test_library.py`: (a) no
  param → only successful rips returned (status filter
  defaults to `success`); (b) `?status=failed` → only failed rips;
  (c) `?status=all` → all rips; (d) the page renders a Mash Co.
  chip group at the top of the grid with three pill-shaped chips
  (`success`, `failed`, `all`); the active chip uses `--accent`
  background, inactive chips use `--surface-2` (assert by
  substring on the rendered HTML); (e) clicking a chip is a
  same-page anchor link (`<a href="/library?status=...">`) — no
  JS required for the filter; (f) filter reads from the new
  `source.json.status.rip_success` when `source.json` exists,
  falls back to legacy `manifest.json.status == "ripped"` when
  only `manifest.json` exists (the legacy adapter — see
  `test-library-legacy-adapter` below).
  - **Acceptance:** Six cases in `tests/service/test_library.py`.
    Fails until `impl-library-filter`.

- [ ] {agent: pipeline, id: test-library-legacy-adapter} Failing
  tests for the unified library reader that handles BOTH
  `manifest.json` (legacy v0.2) and `source.json` (new v1) per
  `D-library-legacy-adapter`. New helper `read_disc_summary(disc_dir:
  Path) -> DiscSummary` (a small dataclass with the fields the
  library UI needs: `disc_id_or_folder`, `created_at`,
  `rip_success: bool`, `track_count: int`, `thumbnail: Path | None`,
  `is_legacy: bool`). Tests: (a) folder containing only legacy
  `manifest.json` → returns a summary with `is_legacy=True`,
  `rip_success` derived from `manifest.status == "ripped" and
  rips[0].status == "success"`; (b) folder containing only new
  `source.json` → `is_legacy=False`, `rip_success` from
  `source.status.rip_success`; (c) folder containing BOTH (shouldn't
  happen but defend) → prefers `source.json`, logs once; (d) folder
  containing neither → returns `None` (caller filters it out); (e)
  folder name parsed correctly for both shapes (`CD_0018` for
  legacy, `2026-05-15_1432_disc-000001` for new).
  - **Acceptance:** New file `tests/service/test_library_adapter.py`.
    Five cases. Fails until impl. Lives in
    `archivist/service/library.py` (new file extracted from
    `app.py` — keeps the route handlers thin).

#### Bucket C — real-rig fixes surfaced during post-Wave-0 smoke (2026-05-15)

> Three issues observed on the dogfood CM4 after Wave 0 completed:
> (1) `CDROMEJECT` ioctl reports success but the USB drive's tray
> doesn't physically open (firmware quirk); (2) when eject fails,
> the loop transitions back to WAITING, sees `disc-ok`, and
> immediately re-rips the same disc (CD_0019, CD_0020, ... all from
> the same physical disc tonight); (3) auto-mode timing has too
> many edge cases — operator needs an explicit "manual mode" where
> state transitions through STABILIZE/RIP/CAPTURE/EJECT are
> button-driven rather than automatic. Bucket C is **complementary
> to Bucket A** (does not block contract conformance) but lands in
> the same sprint because the underlying state-machine restructure
> in `impl-working-dir-handoff` is the natural integration point.

- [ ] {agent: drivers, id: test-eject-reliability} Failing tests for
  the new shell-based `eject(device: Path) -> bool` in
  `archivist/drivers/drive.py`. The current ioctl impl
  (`fcntl.ioctl(fd, CDROMEJECT)`) returns success on the dogfood
  USB drive but the tray never physically opens — almost certainly
  a drive-firmware quirk where `CDROMEJECT` is silently ignored.
  The shell `eject` binary uses ATAPI `START STOP UNIT` with the
  LoEj+Start bits, which is more universally honored. Tests use
  `fake_subprocess` from `conftest.py` to stub `subprocess.run`:
  (a) `returncode == 0` → returns `True`; (b) non-zero returncode
  → returns `False`, stderr captured and logged via the module
  logger (assert via caplog); (c) `FileNotFoundError` (no `eject`
  binary on PATH) → returns `False`, logs a clear error naming the
  missing binary; (d) `subprocess.TimeoutExpired` → returns
  `False`, logs the timeout (10s ceiling); (e) **never-raises
  invariant** — no input or subprocess outcome causes the function
  to raise (the state machine relies on this). Function signature
  is unchanged from the ioctl version (`eject(device: Path) ->
  bool`) so callers don't need to know about the impl change.
  - **Acceptance:** Five cases in `tests/drivers/test_drive.py`
    (or a sibling `test_eject.py` if `test_drive.py` gets
    crowded — author's call). Fails until
    `impl-eject-reliability`.

- [ ] {agent: pipeline, id: test-waiting-remove-state} Failing tests
  for the new `WAITING_REMOVE` loop state. After EJECT phase
  completes, the loop must transition to `WAITING_REMOVE` (NOT
  back to WAITING/IDLE), and stay there until the drive reports
  `tray-open` OR `no-disc` — i.e. until the operator has
  physically removed the disc. This is robust against the
  eject-firmware quirk in Bucket C #1 even after that's fixed:
  if the tray didn't physically open, the state machine sits in
  `WAITING_REMOVE` rather than auto-re-ripping. Tests in
  `tests/state_machine/test_loop.py`: (a) post-EJECT `tick()` →
  `LoopState.phase == "waiting_remove"`; (b) in `WAITING_REMOVE`
  with drive reporting `disc-ok` → stays put, no advance, no
  re-rip cycle started, `tick()` is effectively a no-op for
  forward progress; (c) in `WAITING_REMOVE` with `tray-open` →
  advances to IDLE/WAITING (ready for the next disc); (d) in
  `WAITING_REMOVE` with `no-disc` → advances to IDLE/WAITING;
  (e) `LoopState` serialization includes the new state (status
  endpoint surfaces it correctly).
  - **Acceptance:** Five cases in `tests/state_machine/test_loop.
    py`. Fails until `impl-waiting-remove-state`.

- [ ] {agent: pipeline, id: test-manual-mode-state-gating} Failing
  tests for manual-mode gating of state-machine auto-transitions.
  In manual mode, the loop still polls drive status (so it knows
  what's there) but the production-phase auto-transitions
  (STABILIZE→RIP, RIP→EJECT, EJECT→CAPTURE, CAPTURE→WAITING_REMOVE)
  do NOT fire automatically. They fire only when an explicit
  operator-trigger advances them. Tests in `tests/state_machine/
  test_loop.py`: (a) `LoopState.mode == "manual"` + `disc-ok` →
  loop transitions IDLE→STABILIZE (drive-state observation still
  happens) but does NOT auto-advance STABILIZE→RIP even after
  STABILIZE_SECONDS elapses; (b) in `manual` mode + `STABILIZE`,
  calling the explicit `advance("rip")` trigger advances to RIP
  and runs the rip; (c) in `manual` mode + `RIP` complete,
  `advance("eject")` advances to EJECT, `advance("capture")`
  advances to CAPTURE; (d) in `auto` mode (default), all
  transitions fire as today (regression check); (e) `advance()`
  with a trigger that doesn't match the current state is a
  no-op at the state-machine level (the HTTP layer surfaces 409
  — see `test-manual-mode-endpoints`); (f) `advance("reset")`
  in any mode returns the loop to IDLE without ripping, clears
  the in-flight `_cycle`, and is logged via `RipLogWriter` if a
  cycle was active.
  - **Acceptance:** Six cases in `tests/state_machine/test_loop.
    py`. Fails until `impl-manual-mode`.

- [ ] {agent: pipeline, id: test-manual-mode-endpoints} Failing
  tests for the new manual-mode HTTP control surface. New
  endpoints in `archivist/service/app.py`:
  `POST /api/control/start-rip`, `POST /api/control/eject`,
  `POST /api/control/capture`, `POST /api/control/reset`,
  `POST /api/control/mode?mode=auto|manual`. Tests in
  `tests/service/test_control_endpoints.py` (new file): (a)
  `POST /api/control/mode?mode=manual` → `200`, `LoopState.mode`
  flips to `"manual"`; (b) `POST /api/control/mode?mode=auto` →
  `200`, flips back; (c) `POST /api/control/mode?mode=garbage`
  → `400`; (d) in manual mode + `STABILIZE`, `POST
  /api/control/start-rip` → `200`, advances to RIP; (e) in
  manual mode + `IDLE`, `POST /api/control/start-rip` → `409`
  (state mismatch); (f) in `auto` mode, `POST
  /api/control/start-rip` → `403` (manual-only trigger refused);
  (g) `POST /api/control/reset` works in either mode and from
  any state (operator escape hatch — always allowed); (h)
  `/api/status` response includes `mode: "auto" | "manual"` so
  the UI knows which buttons to show.
  - **Acceptance:** Eight cases in `tests/service/test_control_
    endpoints.py`. Fails until `impl-manual-mode`.

### Wave 2 — Implementations

#### Bucket A — music-pipeline contract conformance

- [ ] {agent: pipeline, depends: test-music-paths, id: impl-music-paths}
  Implement env-driven path config in `archivist/__main__.py`. Read
  `MUSIC_INBOX_DIR`, `MUSIC_WORKING_DIR`, `MUSIC_FAILED_DIR` from env
  with the documented defaults (use `Path.expanduser()` to handle
  `~`). If only legacy `ARCHIVIST_DISCS_ROOT` is set, alias it to
  `MUSIC_INBOX_DIR` and log a deprecation warning naming both vars.
  At startup, `mkdir(parents=True, exist_ok=True)` on all three;
  validate write-permission by attempting to create a `.write_test`
  file in each (and removing it). Pass `inbox_dir`, `working_dir`,
  `failed_dir` through to the loop construction (the loop currently
  takes a single `discs_root` — that becomes `inbox_dir` for legacy
  reads, `working_dir` for in-progress writes; see
  `impl-working-dir-handoff` for how the loop consumes both).
  - **Acceptance:** `tests/test_main_music_paths.py` passes. The
    `_configure_logging` fallback path from sprint-3 still works
    (orthogonal). Manual sanity: `python -m archivist` against the
    dogfood rig (`MUSIC_INBOX_DIR=/srv/music/inbox` etc.) starts
    cleanly.

- [ ] {agent: pipeline, depends: test-folder-naming, id: impl-folder-naming}
  Implement `next_disc_folder_name(inbox_root, *, now=None) -> str`
  in `archivist/pipeline/disc_id.py` (alongside the legacy
  `next_disc_id`). Reuse the `.disc-id.lock` fcntl lockfile for
  serialization. Scan `inbox_root` for entries matching
  `^\d{4}-\d{2}-\d{2}_\d{4}_disc-(\d{6})$`; take the max counter,
  increment. `now` defaults to `datetime.now().astimezone()` (local
  with offset). Format the timestamp portion with `strftime
  ("%Y-%m-%d_%H%M")`. Materialize the folder under
  `working_dir / folder_name` (NOT the inbox — see
  `impl-working-dir-handoff`); the lockfile lives in `working_dir`
  too. Note: `next_disc_id` (the legacy `CD_NNNN` allocator) stays
  in the file but is no longer called by the production code path
  — kept available for the legacy-fixture-using tests until the
  next sprint can remove them.
  - **Acceptance:** `tests/pipeline/test_disc_id.py` (or new
    `test_folder_name.py`) all pass. Existing `next_disc_id` tests
    still pass.

- [ ] {agent: pipeline, depends: test-track-rename, id: impl-track-rename}
  Implement `rename_tracks_to_canonical(audio_dir: Path) -> list[Path]`
  in `archivist/pipeline/rip.py`. Glob `track*.cdda.flac`; for each
  matching file, parse the track number with a regex
  (`^track(\d{2})\.cdda\.flac$`), build the target name `f"{nn} Track.flac"`,
  refuse if target exists, otherwise `path.rename(target)`. Wire
  into `rip_disc` so it runs after the flac conversion loop and
  before the `RipRecord` is constructed; the `RipRecord.tracks`
  list contains the new canonical names.
  - **Acceptance:** `tests/pipeline/test_rip_canonical_names.py`
    passes. Existing `tests/pipeline/test_rip.py` updated to expect
    the new filename shape (or kept asserting the trackNN shape if
    the rename happens after the existing assertion point —
    author's call; the goal is no regressions).

- [ ] {agent: pipeline, depends: test-source-json-model,
  depends: test-source-json-write, id: impl-source-json-model}
  Implement `archivist/models/source.py` with the Pydantic v2
  `SourceJson` schema v1 per the handoff doc. All sub-models use
  `extra="forbid"`. `read_source_json` and `write_source_json`
  follow the same atomic-write shape as `manifest.py`'s
  `read_manifest` / `write_manifest`. The legacy `Manifest` (v0.2)
  is untouched — both models coexist; sprint-5 may consolidate.
  - **Acceptance:** `tests/models/test_source.py` passes. Existing
    `tests/models/test_manifest.py` (or wherever Manifest tests
    live) still passes. `ruff check` clean.

- [ ] {agent: pipeline, depends: test-source-json-builder,
  depends: impl-source-json-model, id: impl-source-json-builder}
  Implement `archivist/pipeline/source_json.py::build_source_json(...)`.
  Drive info: read from a small new helper
  `archivist/drivers/drive.py::read_drive_info(device: Path) ->
  DriveInfo` (returns `model: str | None, serial: str | None,
  read_offset: int | None`) — implemented best-effort by parsing
  `/proc/sys/dev/cdrom/info` if present, else returning all-nulls;
  this is a thin drivers-side helper that pipeline consumes.
  Hostname via `socket.gethostname()`. Ripper name/version from
  `archivist.__version__` (read from `pyproject.toml` via
  `importlib.metadata.version("cd-archivist")` if installed, else
  the literal `"0.0.0+dev"`). All `detected_metadata` fields
  null per the handoff doc (no inventing). All `physical_disc`
  fields except `photo` / `photo_captured` / `photo_captured_at`
  / `photo_device` null in sprint-4. `files[]` enumerates every
  file in `disc_dir` matching the audio glob, the photo, and the
  log; `sha256=None` (stretch task populates). **Decision locked
  (2026-05-15):** `audio.total_duration_seconds` is extracted via
  `ffprobe` (already a dependency for the camera pipeline via
  ffmpeg) — no new `mutagen` dep. Add a small
  `archivist/drivers/ffprobe.py` helper if needed, or inline the
  subprocess call in the source.json builder (author's choice; the
  hard rule is no new third-party dep).
  - **Acceptance:** `tests/pipeline/test_source_json_builder.py`
    passes. Drives helper tested in `tests/drivers/test_drive.py`
    if it's non-trivial (the `/proc` parser is — add 2 cases:
    happy-path with a known fixture, fallback when the file is
    missing).

- [ ] {agent: pipeline, depends: test-canonical-photo, id: impl-canonical-photo}
  Implement `select_canonical_photo` and `copy_canonical_photo` in
  `archivist/pipeline/capture.py`. The 5 supplemental captures stay
  in `<disc_dir>/captures/` untouched; `disc-photo.jpg` is a copy
  (NOT a symlink — keeps the inbox folder self-contained for the
  Beets pipeline). Wire into the new `_from_capture` handler (see
  `impl-working-dir-handoff`) so canonical-photo selection runs
  immediately after `capture_disc` returns.
  - **Acceptance:** `tests/pipeline/test_canonical_photo.py` passes.

- [ ] {agent: pipeline, depends: test-ready-marker, id: impl-ready-marker}
  Implement `write_ready_marker(disc_dir, *, ready_at,
  schema_version=1) -> Path` in `archivist/pipeline/folder.py`.
  Required-files check before the `os.replace` step. Idempotency
  rule: refuse to overwrite an existing `READY` (raise
  `FileExistsError`) — the loop never calls this twice for the same
  folder, and an unexpected double-call is a real bug worth
  surfacing.
  - **Acceptance:** `tests/pipeline/test_ready_marker.py` passes.

- [ ] {agent: drivers, depends: test-rip-log-writer, id: impl-rip-log-writer}
  Implement `archivist/drivers/rip_log.py::RipLogWriter`. Plain-text
  writer with `[<ISO-8601-local-with-offset>] <message>\n` line
  format. `event(message: str)` writes-and-flushes (the importer
  may pick up a partial log on a crash — flushing keeps the trailing
  events visible). `__enter__` opens; `__exit__` flushes + closes.
  Pipeline-side wiring (calling `event()` at each state transition,
  passing `event` as the `progress_callback` to the ripper) lands
  in `impl-working-dir-handoff` because the call sites are in the
  loop.
  - **Acceptance:** `tests/drivers/test_rip_log.py` passes. The
    integration case (cdparanoia stderr → rip.log entries) shares
    the fake-Popen scaffolding from sprint-3's
    `test-rip-stderr-stream`.

- [ ] {agent: pipeline, depends: impl-music-paths,
  depends: impl-folder-naming, depends: impl-track-rename,
  depends: impl-source-json-builder, depends: impl-canonical-photo,
  depends: impl-ready-marker, depends: impl-rip-log-writer,
  depends: test-working-dir-handoff, id: impl-working-dir-handoff}
  Restructure the state machine to use the working-dir → inbox
  pattern + the new file layout. Changes to
  `archivist/state_machine/loop.py`:
  1. **Construction** — accept `inbox_dir`, `working_dir`,
     `failed_dir` separately (replaces the single `discs_root`
     parameter). The `__main__.py::main` change in `impl-music-paths`
     wires these.
  2. **STABILIZE** — calls `next_disc_folder_name(inbox_dir, now=...)`
     (the counter scans the **inbox** so it stays monotonic across
     runs even if working-dir is wiped); creates
     `working_dir / folder_name`; constructs a `RipLogWriter` for
     `<working_dir>/<folder_name>/rip.log` and stashes it on the
     `Cycle` dataclass. The existing `prepare_disc_folder` is
     **not** called for the new path — the new path doesn't write
     a legacy `manifest.json`. Instead, create the canonical
     subdirs (`audio/`, `captures/`, `review/`) inline. **Decision
     locked (2026-05-15):** drop `logs/` (rip.log now lives at the
     disc-folder root); keep `captures/` for supplemental burst
     photos and `review/` because sprint-3's review-recapture
     surface writes there. Logs a `Disc inserted` event to
     rip.log.
  3. **RIP** — passes `RipLogWriter.event` as the
     `progress_callback` to `rip_disc` so cdparanoia stderr lines
     land in `rip.log` live (and `LoopState.rip_progress` updates
     via the chained callback — the closure does both: parse with
     `parse_cdparanoia_progress` AND log raw line via `event`).
     Calls `rename_tracks_to_canonical(audio_dir)` after a
     successful rip. Logs `Rip finished: N tracks, format=FLAC`.
     On failure: the failure path lands in `impl-failed-marker`.
  4. **EJECT → CAPTURE** — unchanged from sprint-3; `_from_eject`
     ejects the tray, restarts cdplay, sleeps
     `EJECT_SETTLE_SECONDS`, transitions to CAPTURE. `_from_capture`
     calls `capture_disc(disc_dir, ...)` (the disc dir is still
     under `working_dir` at this point), then
     `copy_canonical_photo(disc_dir)`, then logs photo capture
     event to rip.log.
  5. **NEW: HANDOFF (folded into `_from_capture` end)** — after
     captures are done, build the `SourceJson` via
     `build_source_json(...)`, write it to `<working>/<folder>/
     source.json`. Verify required files present (audio, source.
     json, rip.log) — `read_disc_summary` + a small helper, or
     just inline checks. Then **`os.replace(working_dir / folder,
     inbox_dir / folder)`** — the atomic move. Then write `READY`
     into `inbox_dir / folder` via `write_ready_marker(...)`. Log
     `READY marker written` to a final `rip.log` entry (the writer
     reopens the moved log file in append mode for the final
     line). Transition to IDLE; clear `_cycle`.
  6. **Legacy `manifest.json` writes — REMOVED** from the new path.
     The state machine no longer writes manifest.json for new
     rips. Existing `CD_NNNN/` folders keep their legacy manifests
     untouched (no migration). The library reader handles both
     shapes (see `impl-library-legacy-adapter`).
  - **Acceptance:** `tests/state_machine/test_loop.py` all pass
    including the new working-dir-handoff cases and the revised
    capture-after-eject cases (which now expect new folder shape +
    source.json + READY). Existing crash-recovery + cdplay-paired
    invariant tests still pass. `ruff check` clean. Manual sanity
    deferred to operator real-rig run after sprint-4 closes.

- [ ] {agent: pipeline, depends: impl-working-dir-handoff,
  depends: test-failed-marker, id: impl-failed-marker} Implement
  the failed-disc disposition in `_from_rip` (and the existing
  ERROR path). On rip failure (exception OR
  `RipRecord(status="fail")`):
  1. Build a `SourceJson` with `status.rip_success=False,
     ready=False`, errors populated; write it to
     `<working>/<folder>/source.json`.
  2. Log the failure reason to `rip.log`.
  3. Write `<working>/<folder>/FAILED` (`failed_at=<ISO>` +
     `reason=<short string>`) — atomic via `.tmp` + replace, same
     shape as the READY writer.
  4. `os.replace(working_dir / folder, failed_dir / folder)` — the
     folder lives in `failed_dir`, NOT in inbox.
  5. **NO** `READY` write (per the handoff doc).
  6. Restart cdplay (existing invariant) + transition to ERROR
     (existing sprint-3 behavior). The operator-recovery path
     (`tray-open` → IDLE) is unchanged.
  Photo failure during CAPTURE does NOT trigger this path — the
  rip succeeded, the folder still moves to inbox, `source.json`
  records `photo_success=False` + a warning, `READY` is still
  written.
  - **Acceptance:** `tests/state_machine/test_loop.py` failed-disc
    cases pass. Existing terminal-ERROR + crash-recovery tests
    still pass.

- [ ] {agent: pipeline, depends: impl-music-paths, id: impl-docs-paths}
  Update `docs/operations/cm4-setup.md` with: the three new env
  vars + their defaults; the `/srv/music/` override block for the
  dogfood rig (point at `/srv/cd-music-stack/.env`'s `MUSIC_ROOT`
  for the source of truth); the `ARCHIVIST_DISCS_ROOT` deprecation
  alias; the migration note that legacy `CD_NNNN/` folders stay
  in place and surface in `/library` via the legacy adapter.
  Append a short note to `docs/ripper-handoff-for-claude-code.md`
  itself: a "## Dogfood-rig override" sub-section near the top
  documenting that on the cd-archivist dogfood deployment,
  `MUSIC_INBOX_DIR=/srv/music/inbox` etc., not the
  `~/music-pipeline/...` defaults. Also append a
  contract-conformance appendix to
  `docs/operations/sprint-2-smoke.md` listing the new acceptance
  checks (folder shape, presence of source.json + rip.log + READY,
  atomic-handoff sanity). The smoke script itself is unchanged
  (still operator-driven).
  - **Acceptance:** Three docs updated. No code changes. Reviewed
    against the handoff doc to confirm naming consistency.

#### Bucket B — sprint-3 polish carryovers

- [ ] {agent: pipeline, depends: test-rip-progress-real-format,
  id: impl-rip-progress-real-format} Update the
  `parse_cdparanoia_progress` regex in `archivist/pipeline/
  rip_progress.py` to match the captured real-format fixture. The
  existing parser stays roughly the same shape (returns
  `"track N/T, P%"`-shaped strings); the regex(es) inside need to
  match what cdparanoia 10.2 actually emits. Author of this task
  documents the format in the helper's docstring with a 3-line
  example block (so future maintainers don't repeat the
  sprint-3 mistake of writing the parser from the man page).
  - **Acceptance:** `tests/pipeline/test_rip_progress.py` passes
    including the fixture-driven case. The end-to-end check
    (fake Popen yielding the fixture → `LoopState.rip_progress`
    populated) green.

- [ ] {agent: pipeline, depends: test-wav-cleanup,
  id: impl-wav-cleanup} Implement post-FLAC WAV deletion in
  `archivist/drivers/ripper.py` (or `archivist/pipeline/rip.py` —
  whichever owns the per-track flac conversion loop). After each
  successful flac conversion, `wav.unlink(missing_ok=True)`. Read
  `ARCHIVIST_KEEP_WAVS` env var at construction; when truthy
  (any of `1`, `true`, `yes`, case-insensitive), skip the
  unlink. Document the env var in `cm4-setup.md` (folded into
  `impl-docs-paths` if convenient). Failed flac conversion does
  NOT trigger the unlink (debugging artifact).
  - **Acceptance:** `tests/drivers/test_ripper.py` WAV-cleanup
    cases pass. Existing ripper tests pass.

- [ ] {agent: pipeline, depends: test-library-legacy-adapter,
  id: impl-library-legacy-adapter} Extract a new
  `archivist/service/library.py` module containing
  `read_disc_summary(disc_dir) -> DiscSummary | None` and the
  preference logic (`source.json` wins when both are present;
  legacy `manifest.json` falls back). The existing `/library`
  and `/library/{disc_id}` route handlers in `app.py` move to
  consume the adapter; the route-registration code stays in
  `app.py`. The detail page renders BOTH shapes correctly:
  for legacy folders, a `<pre>` of the `manifest.json` dump (as
  today); for new folders, a `<pre>` of the `source.json` dump
  + the audio file list comes from globbing the disc-folder root
  (not an `audio/` subdir — the new layout puts `NN Track.flac`
  at the root). The `disc-photo.jpg` (when present) renders as
  the hero image at the top of the detail page; `captures/`
  supplementals continue to surface as the thumbnail grid below.
  Path-traversal guard (sprint-3) preserved. **Decision locked
  (2026-05-15):** `SourceJson.disc.disc_counter` is acceptably
  missing for legacy `CD_NNNN/` folders — those folders keep their
  `manifest.json` and are NOT retro-fitted with a `source.json`.
  The adapter handles the absence gracefully (returns `None` or
  omits the field on the `DiscSummary`); no synthetic counter is
  derived from the legacy `CD_NNNN` numeric suffix.
  - **Acceptance:** `tests/service/test_library_adapter.py`
    passes. Existing `tests/service/test_library.py` passes
    (with route handlers refactored, not behavior-changed for
    legacy folders).

- [ ] {agent: pipeline, depends: impl-library-legacy-adapter,
  depends: test-library-status-filter, id: impl-library-filter}
  Implement the `?status=` filter on `GET /library`. Default
  `success`. Mash Co. chip group at the top of the grid: 3
  pill-shaped chips (`success`, `failed`, `all`); active chip
  uses `--accent` background, inactive uses `--surface-2`. Chips
  are anchor links (`<a href="/library?status=...">` — no JS).
  Filter consults `DiscSummary.rip_success` (which the adapter
  already derives correctly for both legacy + new shapes).
  - **Acceptance:** `tests/service/test_library.py` filter cases
    pass. Manual sanity: with the dogfood rig's 18 legacy
    `CD_NNNN/` folders + a fresh sprint-4 rip, browse to
    `/library` → only successful rips visible; `?status=failed`
    → just CD_0017 (or whichever was the failed one); `?status=
    all` → everything.

#### Bucket C — real-rig fixes surfaced during post-Wave-0 smoke (2026-05-15)

- [ ] {agent: drivers, depends: test-eject-reliability,
  id: impl-eject-reliability} Replace the ioctl-based `eject` in
  `archivist/drivers/drive.py` with `subprocess.run(["eject",
  str(device)], capture_output=True, text=True, timeout=10)`.
  Returncode 0 → `True`; non-zero → `False` with stderr logged via
  the module logger; `FileNotFoundError` → `False` with a clear
  log; `subprocess.TimeoutExpired` → `False` with timeout logged.
  Function signature unchanged so neither the state machine nor
  existing tests need to know about the impl change. Module
  docstring updated to document that the `CDROMEJECT` ioctl was
  tried first but didn't move the tray on the dogfood USB drive
  (cite this as a real-rig finding from the post-Wave-0 smoke on
  2026-05-15) — the shell `eject` binary uses ATAPI `START STOP
  UNIT` with LoEj+Start, which is more universally honored, and
  also handles fallback paths (LOAD/UNLOAD, etc.) we'd otherwise
  have to reimplement. Add `eject` as a runtime-binary dependency
  documented in `docs/operations/cm4-setup.md` (already standard
  on Debian, including the CM4 — folded into `impl-docs-paths` if
  convenient).
  - **Acceptance:** `tests/drivers/test_drive.py` (or
    `test_eject.py`) eject cases pass. Existing state-machine
    tests that exercise EJECT still pass (signature unchanged).

- [ ] {agent: pipeline, depends: test-waiting-remove-state,
  depends: impl-eject-reliability,
  depends: impl-working-dir-handoff,
  id: impl-waiting-remove-state} Extend the loop state enum with
  `WAITING_REMOVE`. Update the EJECT→IDLE/WAITING transition to
  EJECT→WAITING_REMOVE. Add the WAITING_REMOVE handler keyed on
  drive status: `tray-open` OR `no-disc` → IDLE/WAITING (whichever
  matches the existing post-eject convention); `disc-ok` → stay in
  WAITING_REMOVE (no advance, no re-rip). The status page
  (`archivist/service/static/` + the FastAPI status template)
  renders the new state with the Mash Co. `--amber` token (the
  "needs operator" semantic color) and a short copy line such as
  "Remove disc to continue." `LoopState` JSON serialization
  includes the new state so `/api/status` consumers see it. **No
  abort path needed** — the operator can always physically open
  the tray manually OR (once Bucket C #3 lands) hit the manual-
  mode `POST /api/control/reset` to force back to IDLE; either
  resolves the wait. Documented in the state docstring.
  - **Acceptance:** `tests/state_machine/test_loop.py`
    waiting-remove cases pass. The status page renders the new
    state correctly (manual sanity by the operator on the dogfood
    rig — no automated UI test).

- [ ] {agent: pipeline, depends: test-manual-mode-state-gating,
  depends: test-manual-mode-endpoints,
  depends: impl-waiting-remove-state,
  id: impl-manual-mode} Implement manual-mode gating + the new
  control endpoints. Changes:
  1. **`LoopState.mode: Literal["auto","manual"]`** — defaults
     from env `ARCHIVIST_MODE` (validated, defaults to `"auto"`
     when unset or invalid; invalid value logged with a warning).
     Mode is included in `LoopState.to_dict()` so `/api/status`
     surfaces it.
  2. **State-machine gating** — the existing auto-transitions
     (STABILIZE→RIP, RIP→EJECT, EJECT→CAPTURE,
     CAPTURE→WAITING_REMOVE) check `loop_state.mode`; in
     `manual` mode, they DO NOT fire automatically. Drive
     polling + state observation happens in both modes; only the
     forward production-phase transitions are gated.
  3. **`advance(trigger: Literal["rip","eject","capture",
     "reset"]) -> bool`** method on the state machine. Each
     trigger advances iff the current state matches; otherwise
     no-op (returns `False`). `reset` is always allowed and
     returns to IDLE without ripping, clearing the in-flight
     `_cycle` and logging via `RipLogWriter` if active.
  4. **New endpoints in `archivist/service/app.py`:**
     `POST /api/control/mode?mode=auto|manual` (200 / 400);
     `POST /api/control/start-rip`, `POST /api/control/eject`,
     `POST /api/control/capture` — each: 200 if `advance()`
     succeeded, 409 if the trigger doesn't match the current
     state, 403 if `loop_state.mode == "auto"` (manual-only
     triggers); `POST /api/control/reset` — 200 in either mode
     from any state.
  5. **UI** — the FastAPI status page renders a two-button mode
     toggle group at the top of the state card (Auto | Manual)
     using Mash Co. tokens (active = `--accent` background,
     inactive = `--surface-2`); when `mode == "manual"`, a
     per-state action button group renders below the state line
     showing the buttons that match the current state ("Start
     rip" in STABILIZE; "Eject now" in RIP-complete; "Capture
     now" in EJECT-complete; "Reset" always present). Buttons
     are `<form method="post" action="/api/control/...">` with
     no JS — same anchor-link pattern as the library `?status=`
     filter. **Default mode = `"auto"`** (preserves today's
     behavior for operators who don't set `ARCHIVIST_MODE`); the
     judgment call is captured in `D-manual-mode`. The new
     `?status=` filter UI from Bucket B and the manual-mode
     button group share the same Mash Co. chip/button styling.
  - **Acceptance:** `tests/state_machine/test_loop.py` gating
    cases pass; `tests/service/test_control_endpoints.py`
    passes; existing auto-mode tests still pass (regression).
    Manual sanity on the dogfood rig: flip to manual, drive a
    full disc through STABILIZE→RIP→EJECT→CAPTURE→WAITING_REMOVE
    by clicking the buttons; flip back to auto, confirm next
    disc auto-progresses.

#### Stretch (only if Wave 2 finishes early)

- [ ] {agent: pipeline, id: impl-source-json-sha256} _Stretch_ —
  populate `source.json.files[].sha256` for every file. Add a
  `compute_sha256(path: Path) -> str` helper; call it from
  `build_source_json` for each file entry. Streaming hash (read in
  chunks) so a 700 MB FLAC doesn't blow memory. Tests: round-trip
  the hash via the model + verify against an out-of-band
  `hashlib.sha256` of the same file. Drop if Wave 2 runs long.
  - **Acceptance:** Tests in `tests/pipeline/test_source_json_
    builder.py`. Mark the task `[x]` with a "stretch — done" note
    or close as `[ ]` with a "deferred to sprint-5" Activity Log
    entry.

- [ ] {agent: drivers, id: impl-musicbrainz-disc-id} _Stretch_ —
  populate `source.json.identifiers.musicbrainz_disc_id` via
  libdiscid. Add a thin wrapper around `python-discid` (a
  ctypes binding to libdiscid); call it from
  `archivist/drivers/drive.py::read_drive_info` (or a sibling)
  before the rip starts. Skip on import error so the rest of the
  pipeline isn't blocked by a missing C library. Tests: mock the
  discid module + assert the populated field. Drop if not
  needed; `null` is acceptable per the handoff doc.
  - **Acceptance:** Tests in `tests/drivers/test_drive.py`.
    `pyproject.toml` adds `python-discid` as an optional
    dependency under a `[project.optional-dependencies]` table.

## Agent Roster

| Agent | Owns | Does not touch |
|---|---|---|
| drivers | `archivist/drivers/{drive,led,camera,ripper,systemctl,usb_discovery,rip_log}.py`, `archivist/models/manifest.py`, `tests/drivers/` | `archivist/pipeline/`, `archivist/state_machine/`, `archivist/service/`, `archivist/__main__.py`, `archivist/models/source.py` |
| pipeline | `archivist/pipeline/{disc_id,folder,pairing,capture,rip,rip_progress,review_capture,source_json}.py`, `archivist/state_machine/`, `archivist/service/` (incl. `archivist/service/static/`, the new `archivist/service/library.py`, and the new manual-mode control endpoints in `app.py`), `archivist/models/source.py`, `archivist/__main__.py`, `tests/pipeline/`, `tests/state_machine/`, `tests/service/` (incl. new `tests/service/test_control_endpoints.py`), `tests/models/`, `tests/test_main_logging.py`, `tests/test_main_music_paths.py`, `tests/__init__.py`, `tests/conftest.py`, `pyproject.toml`, `ruff.toml`, `docs/operations/cm4-setup.md`, `docs/operations/sprint-2-smoke.md`, `docs/ripper-handoff-for-claude-code.md` (dogfood-rig override note only), `docs/coordination/sprint-4.md` | `archivist/drivers/` internals (consumes their public interfaces) |

Same two agents as sprints 1-3. Drivers' sprint-4 footprint is small:
the new `archivist/drivers/rip_log.py::RipLogWriter` (lives next to the
ripper because the ripper consumes it as the `progress_callback`), the
`read_drive_info` helper on `drive.py` (small `/proc` parser), the
WAV-cleanup edit in `ripper.py` (post-FLAC `wav.unlink`), and the
ioctl→shell-eject swap in `drive.py` (Bucket C — `impl-eject-
reliability`; signature unchanged). Pipeline owns everything else:
the new `source.json` model + builder, the folder-name allocator, the
working-dir → inbox handoff in the state machine, the `READY` /
`FAILED` markers, the canonical-photo selection, the library legacy
adapter, the `?status=` filter, and the Bucket C state-machine
extensions (`WAITING_REMOVE` state, `LoopState.mode` gating, the new
`/api/control/*` endpoints, and the manual-mode UI button group).

**New cross-agent meeting point:** `RipLogWriter.event` is consumed by
the state machine (`_from_*` handlers call it directly) and by the
ripper (`progress_callback` argument). The closure that pipeline
constructs in `_from_rip` does both: parse the line via
`parse_cdparanoia_progress` (pipeline's parser) AND log the raw line
via `event` (drivers' writer). Captured under Contract Changes.

**External read-only dependency:** the docker stack at
`/srv/cd-music-stack/` and the `MUSIC_ROOT=/srv/music` override it
defines. cd-archivist reads neither at runtime — both surfaces are
documented in `cm4-setup.md` as the operator-side configuration the
env vars must agree with.

## Decision Log

> The seven entries below are **proposed** by the planner. They become
> ratified at the sprint-4 kickoff session via `decision-card-flow` /
> `ratify`. The same `### {{date}} — {{decision-id}} — {{summary}}`
> shape from sprint-3 is preserved.

### 2026-05-15 — D-music-pipeline-paths — env-driven inbox/working/failed paths; document `/srv/music/` override

**Proposed.** The handoff doc defaults to `~/music-pipeline/...`; the
dogfood rig uses `/srv/music/...` (configured via
`/srv/cd-music-stack/.env::MUSIC_ROOT=/srv/music`). Resolution: every
path in cd-archivist becomes env-driven —
`MUSIC_INBOX_DIR` (default `~/music-pipeline/inbox`),
`MUSIC_WORKING_DIR` (default `~/music-pipeline/.ripping`),
`MUSIC_FAILED_DIR` (default `~/music-pipeline/failed`). The legacy
`ARCHIVIST_DISCS_ROOT` is aliased to `MUSIC_INBOX_DIR` with a
deprecation warning so the dogfood unit doesn't break mid-deploy.
Both layouts (`~/music-pipeline/` reference, `/srv/music/` dogfood)
are documented in `docs/operations/cm4-setup.md`; a "## Dogfood-rig
override" sub-section is added to the handoff doc itself so the spec
acknowledges the deployed reality.

### 2026-05-15 — D-source-json-v1 — adopt handoff-doc schema v1; legacy `manifest.json` stays readable

**Proposed.** New `SourceJson` Pydantic v2 model (schema v1) per the
handoff doc §source.json. Lives in `archivist/models/source.py`
alongside the existing `archivist/models/manifest.py` (Manifest v0.2)
— both models coexist. New disc folders write `source.json` and do NOT
write `manifest.json`. Legacy `CD_NNNN/manifest.json` stays untouched
on disk. The library UI reads both via a small adapter
(`D-library-legacy-adapter`).

**Sprint-4 fields populated:** ripper, disc, drive (model from
`/proc/sys/dev/cdrom/info` best-effort, serial/read_offset null),
audio summary, files (with size_bytes; sha256 stretch), status,
physical_disc.{photo,photo_captured,photo_captured_at,photo_device}.

**Sprint-4 fields always null:** identifiers.{musicbrainz_disc_id,
freedb_disc_id, cd_toc, upc, isrcs} (libdiscid is stretch),
detected_metadata.* (no inventing — sprint-5 brings OCR / MB
lookup), physical_disc.{label_text_guess, appears_burned,
handwritten} (sprint-5+).

### 2026-05-15 — D-folder-naming-migration — `YYYY-MM-DD_HHMM_disc-NNNNNN`; legacy `CD_NNNN/` not auto-renamed

**Proposed.** New disc folders use `YYYY-MM-DD_HHMM_disc-NNNNNN` (local
time, 24-hour, 6-digit zero-padded monotonic counter). The counter
scans the **inbox** (not the working dir) for the highest existing
`disc-(\d{6})` value and increments. Legacy `CD_NNNN/` folders are
NOT migrated — they stay in place, surface in the library UI via the
legacy adapter, and don't contribute to the new counter. A migration
script is **explicitly out of scope** for sprint-4 (and likely beyond
— the legacy folders work fine for the library UI; only the
contract-conforming new folders ship to the music-pipeline import
flow).

**Why not migrate:** (a) the legacy folders are valid as-is for
operator browsing; (b) a rename would invalidate any operator notes
that reference disc-ids in external systems; (c) the music-pipeline
import flow only cares about new rips landing in the inbox with
`READY` — it ignores the legacy folders, so no urgency.

### 2026-05-15 — D-canonical-disc-photo — middle lit frame copied to `disc-photo.jpg`; supplementals stay in `captures/`

**Proposed.** The handoff doc requires ONE canonical `disc-photo.jpg`
at the disc-folder root. cd-archivist's `capture_disc` writes 6
frames (3 ambient + 3 lit). Resolution: `select_canonical_photo`
picks `disc_front_lit_002.jpg` (the middle of the 3 lit frames —
intuitively the most likely to be settled and in-focus); fallback
to any other lit frame if the middle is missing; `None` if no lit
frames exist (then `physical_disc.photo=null` + a warning in
status.warnings, but `READY` still written per the handoff doc).
The 5 supplemental captures stay in `<disc>/captures/` for the
operator (and for any future "pick a better photo" UI). The
canonical is a **copy**, not a symlink — keeps the inbox folder
self-contained for the Beets pipeline.

### 2026-05-15 — D-failed-disc-disposition — failed rips get a `FAILED` marker AND move to `failed_dir`

**Proposed.** The handoff doc allows EITHER moving the folder to
`failed_dir` OR leaving a `FAILED` marker in the inbox folder.
Resolution: do BOTH — write the `FAILED` marker AND move to
`failed_dir`. Rationale: (a) defense in depth — if either mechanism
fails the other still keeps the bad disc out of the importer's
view; (b) the `failed_dir` location keeps `inbox` clean (the
importer doesn't even need to scan `inbox` for `FAILED` markers);
(c) the `FAILED` marker inside the failed folder gives the operator
a quick "what's broken" answer at a glance. `source.json` is still
written for failed rips (with `rip_success=False, ready=False`,
errors populated) so the operator can debug.

### 2026-05-15 — D-wav-cleanup — delete WAVs after FLAC by default; `ARCHIVIST_KEEP_WAVS=1` to keep

**Proposed.** Per the CD_0018 polish item #12: cdparanoia writes a WAV
per track, flac converts to FLAC, but the WAV is currently kept.
This roughly doubles per-disc disk usage and adds nothing for the
dogfood case (no AccurateRip verification this sprint). Resolution:
delete the WAV after a successful flac conversion by default; honor
`ARCHIVIST_KEEP_WAVS=1` (or `true` / `yes`) to skip the deletion
for operators who want the lossless originals (e.g. for
AccurateRip when it lands in sprint-5+). Failed flac conversion
preserves the WAV for debugging.

### 2026-05-15 — D-library-legacy-adapter — Library UI reads BOTH `manifest.json` + `source.json`; prefers `source.json` when both present

**Proposed.** The 18 existing `CD_NNNN/` folders use
`manifest.json` (v0.2); new `YYYY-MM-DD_HHMM_disc-NNNNNN/` folders
use `source.json` (v1). The library UI surfaces both via a new
adapter `archivist/service/library.py::read_disc_summary` that
returns a unified `DiscSummary` dataclass (the small set of fields
the UI needs: disc-id-or-folder-name, created_at, rip_success,
track_count, thumbnail, is_legacy). When both files exist in the
same folder (shouldn't happen — defense-in-depth case), prefer
`source.json` and log once. When neither exists, the folder is
filtered out of `/library`. The detail page renders the matching
schema's dump in a `<pre>` block — legacy folders show
`manifest.json`, new folders show `source.json`. The
`?status=success|failed|all` filter consults
`DiscSummary.rip_success` which the adapter derives correctly for
both shapes.

### 2026-05-15 — D-eject-via-shell — replace `CDROMEJECT` ioctl with shell `eject` binary

**Proposed.** Real-rig finding from the post-Wave-0 smoke on
2026-05-15: the CM4's USB CD drive accepts `CDROMEJECT`
(`fcntl.ioctl(fd, 0x5309)`) and returns success, but the tray
never physically opens. Almost certainly a drive-firmware quirk
where `CDROMEJECT` is silently ignored. Resolution: switch the
implementation of `archivist/drivers/drive.py::eject(device)` to
shell out to the `eject` binary via `subprocess.run(["eject",
str(device)], capture_output=True, text=True, timeout=10)`. The
`eject` binary uses ATAPI `START STOP UNIT` with the LoEj+Start
bits, which is more universally honored, and also handles
fallback paths (LOAD/UNLOAD, etc.) we'd otherwise have to
reimplement.

**Tradeoff:** the ioctl approach is correct for many drives and
adds no runtime-binary dependency, but it's unreliable across the
spectrum (this dogfood drive is the proof). `eject` is a standard
Debian package (already present on the CM4) so the dependency
cost is effectively zero. Function signature stays
`eject(device: Path) -> bool` so neither the state machine nor
existing tests need to change. Module docstring documents the
ioctl-was-tried-first history so future maintainers don't repeat
the exploration.

### 2026-05-15 — D-waiting-remove-state — new `WAITING_REMOVE` state gates re-rip on physical disc removal, not on EJECT phase completion

**Proposed.** Real-rig finding from the post-Wave-0 smoke on
2026-05-15: even with `D-eject-via-shell` fixing the eject
mechanism, there's an underlying state-machine bug. After the
EJECT phase completes, the loop transitions back to
WAITING/IDLE. If the drive STILL reports `disc-ok` (because
eject failed OR because the operator hasn't physically removed
the disc yet), the loop sees `disc-ok` and immediately starts
another rip cycle. The CM4 generated CD_0019, CD_0020, ... all
from the same physical disc tonight before the operator caught
it.

**Resolution:** introduce a new `WAITING_REMOVE` state. After
EJECT, transition to `WAITING_REMOVE` (not directly to
IDLE/WAITING). `WAITING_REMOVE` only advances when drive status
reports `tray-open` OR `no-disc` — i.e. the disc has been
physically removed. While `disc-ok` persists, the state machine
sits in `WAITING_REMOVE` and does nothing. This is robust
against the eject-firmware-quirk too: even if the tray doesn't
physically open, the machine just waits for the operator to
intervene rather than auto-re-ripping.

**No abort path needed:** the operator can always physically
open the tray manually OR use `POST /api/control/reset` (from
`D-manual-mode`) to force back to IDLE. The status-page render
uses Mash Co. `--amber` (the "needs operator" semantic color)
so the wait is visually obvious.

### 2026-05-15 — D-manual-mode — operator can drive the state machine step-by-step until auto-mode timing edge cases are polished

**Proposed.** Real-rig finding from the post-Wave-0 smoke on
2026-05-15: auto-mode timing has accumulated too many edge cases
(the sprint-2/3 polish queue + `D-eject-via-shell` +
`D-waiting-remove-state` above). Until those polish items land
and shake out, the operator needs an explicit "manual mode"
where the state machine doesn't auto-advance through STABILIZE/
RIP/CAPTURE/EJECT — instead, the operator clicks "Start rip",
"Eject now", "Capture now", "Reset" buttons in the FastAPI UI
when ready.

**Default = `auto`.** This is a judgment call: defaulting to
manual would force every existing operator workflow to change,
which violates the "preserve today's behavior unless asked"
principle. Defaulting to auto keeps the dogfood rig behaving as
before, with manual mode as an explicit opt-in (via
`ARCHIVIST_MODE=manual` env or the UI toggle). Mode persists in
`LoopState.mode` and is exposed in `/api/status` so the UI knows
which buttons to show. The mode toggle itself is a two-button
group at the top of the state card.

**Complementary, not replacement.** This is orthogonal to the
sprint-3 review-recapture button (`D-review-recapture-mvp`):
that button takes an extra photo on demand; the new manual-mode
buttons drive the state machine step by step. Both share the
same Mash Co. chip/button styling.

**Endpoints (all `POST`):** `/api/control/mode?mode=auto|manual`
(200/400); `/api/control/start-rip`, `/api/control/eject`,
`/api/control/capture` (200 / 409 state mismatch / 403 if
`mode==auto`); `/api/control/reset` (200 in any mode/state —
operator escape hatch).

## Ratification Log

<!-- Same shape as Decision Log; entries land here when a
     ratification-needed card resolves with kind "ratified". -->

_No ratifications yet._

## Contract Changes

<!-- API / schema / coord-doc-template changes that other agents must
     respect. Each entry: `### {{date}} — {{summary}}` + body listing
     before/after. The dashboard surfaces unprocessed entries as
     "contract changes since you last looked." -->

### 2026-05-15 — env-driven path config replaces `ARCHIVIST_DISCS_ROOT`

- **Before:** `ARCHIVIST_DISCS_ROOT=<path>` selected the single root
  for all disc folders. The state machine's `discs_root` constructor
  parameter received this value.
- **After:** `MUSIC_INBOX_DIR`, `MUSIC_WORKING_DIR`, `MUSIC_FAILED_DIR`
  (defaults `~/music-pipeline/inbox`, `~/music-pipeline/.ripping`,
  `~/music-pipeline/failed`). The state machine accepts three
  parameters: `inbox_dir`, `working_dir`, `failed_dir`. Legacy
  `ARCHIVIST_DISCS_ROOT` aliases to `MUSIC_INBOX_DIR` with a
  deprecation warning.
- **Consumers:** `archivist/__main__.py::main` (reads env, passes
  through); `archivist/state_machine/loop.py` (constructor signature
  change); `archivist/service/app.py::create_app` (the optional
  `discs_root` kwarg is renamed to `inbox_dir` — same shape, more
  accurate name). Tests using `create_app` with an explicit kwarg
  need a one-line rename.

### 2026-05-15 — new `archivist.models.source.SourceJson` schema v1

- **Before:** `archivist.models.manifest.Manifest` (v0.2) was the only
  per-disc metadata model. Written to `<disc>/manifest.json`.
- **After:** `archivist.models.source.SourceJson` (v1) is the new
  model per the handoff doc §source.json. Written to
  `<disc>/source.json`. The legacy `Manifest` is unchanged and
  continues to be readable; new code never writes manifest.json.
  Consumers that previously called `read_manifest(disc / "manifest.
  json")` to derive UI fields move to
  `read_disc_summary(disc) -> DiscSummary` which handles both shapes.
- **Consumers:** `archivist/state_machine/loop.py` (writes source.json
  via the new builder); `archivist/service/library.py` (reads via
  the adapter); tests in `tests/service/test_library*.py` (use
  fixtures of both shapes).

### 2026-05-15 — disc folder naming scheme changes

- **Before:** `CD_NNNN` (4-digit zero-padded counter, no timestamp,
  global across the single `discs_root`).
- **After:** `YYYY-MM-DD_HHMM_disc-NNNNNN` (local time + 24-hour +
  6-digit counter; counter scans the inbox). Legacy `CD_NNNN/`
  folders are not auto-renamed and continue to surface in the
  library UI via the legacy adapter; they do NOT contribute to the
  new counter.
- **Consumers:** `archivist/pipeline/disc_id.py` adds
  `next_disc_folder_name`; the legacy `next_disc_id` stays
  available (the production path no longer calls it but tests still
  reference it). State machine consumes the new helper.

### 2026-05-15 — per-disc rip log moves from global `archivist.log` to `<disc>/rip.log`

- **Before:** All ripping events logged to the global
  `ARCHIVIST_LOG_PATH`-configured logger (default
  `~/.local/share/archivist/archivist.log` or similar). Per-disc
  observability was "grep the global log".
- **After:** Each disc gets its own `<disc>/rip.log` written by
  `archivist/drivers/rip_log.py::RipLogWriter`. The global log
  continues to receive the same events (the writer doesn't replace
  the standard logger — both are written, the per-disc log is a
  scoped tee). Format: `[<ISO-8601-local-with-offset>] <message>\n`.
- **Consumers:** `archivist/state_machine/loop.py` constructs a
  writer per cycle, passes `event` as the `progress_callback` to the
  ripper, and calls `event` directly at state transitions.

### 2026-05-15 — `READY` and `FAILED` marker contract

- **Before:** Disc folders had a `manifest.json` with a `status`
  field (`"ripped"` / `"rip_failed"` / `"created"`). No marker
  files. Importer didn't exist (cd-archivist was end-of-pipeline).
- **After:** Successful disc folders contain a `READY` marker
  written atomically last (`READY.tmp` → `os.replace` → `READY`).
  Failed disc folders contain a `FAILED` marker AND live in
  `failed_dir` (never `inbox`). Per the handoff doc, the music
  pipeline's importer (`/srv/cd-music-stack/bin/process-ready-auto`)
  consumes folders only when `READY` is present.
- **Consumers:** `archivist/pipeline/folder.py` adds
  `write_ready_marker`; `archivist/state_machine/loop.py` calls it
  as the last step of `_from_capture`; the importer (external,
  read-only) consumes the marker.

### 2026-05-15 — `eject(device)` switches from ioctl to shell `eject` binary

- **Before:** `archivist/drivers/drive.py::eject(device)` issued
  `CDROMEJECT` (`0x5309`) via `fcntl.ioctl`. No runtime-binary
  dependency.
- **After:** Shell out to `subprocess.run(["eject", str(device)],
  capture_output=True, text=True, timeout=10)`. Signature unchanged
  (`eject(device: Path) -> bool`). Adds `eject` (Debian-standard,
  already present on the CM4) as a runtime-binary dependency.
- **Consumers:** state machine `_from_eject` calls the same
  function; no caller change. Tests in `tests/drivers/test_drive.py`
  (or sibling) update their fakes from `fake_ioctl` to
  `fake_subprocess`.

### 2026-05-15 — new `WAITING_REMOVE` state + `LoopState.mode`

- **Before:** Loop states were the existing IDLE/STABILIZE/RIP/
  EJECT/CAPTURE/WAITING/ERROR set. After EJECT the loop returned
  to WAITING/IDLE; a `disc-ok` reading there immediately started
  another rip cycle. `LoopState` had no `mode` field — auto-
  advance was always on.
- **After:** New `WAITING_REMOVE` state sits between EJECT and
  IDLE/WAITING; only `tray-open` OR `no-disc` advances it
  (prevents auto-re-rip when eject didn't physically open the
  tray). `LoopState.mode: Literal["auto","manual"]` (default
  `"auto"` from `ARCHIVIST_MODE`); in `manual` mode the
  production-phase auto-transitions are gated and require
  explicit `advance(trigger)` calls.
- **Consumers:** `archivist/state_machine/loop.py`;
  `archivist/service/app.py` (status payload + new control
  endpoints); status page renders the new state with `--amber`
  and a button group when `mode == "manual"`. Tests in
  `tests/state_machine/test_loop.py` and the new
  `tests/service/test_control_endpoints.py`.

### 2026-05-15 — new `/api/control/*` endpoints (manual mode)

- **Before:** No `/api/control/*` namespace. The only
  state-mutating endpoint was sprint-3's review-recapture trigger.
- **After:** `POST /api/control/mode?mode=auto|manual` (200 / 400);
  `POST /api/control/start-rip`, `POST /api/control/eject`,
  `POST /api/control/capture` (200 if `advance()` succeeds, 409 on
  state mismatch, 403 if `mode==auto`); `POST /api/control/reset`
  (200 in any mode/state — operator escape hatch). `/api/status`
  response includes `mode: "auto" | "manual"`.
- **Consumers:** the FastAPI status page renders the mode toggle
  + the per-state action button group; future remote-control
  surfaces (none planned this sprint) can drive the loop via the
  same endpoints.

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

### 2026-05-15 — planner — sprint-4 mid-sprint addition: Bucket C (real-rig fixes from post-Wave-0 smoke)

Three issues surfaced by the operator during the post-Wave-0 smoke on
the dogfood CM4 land in sprint-4 BEFORE agents kick off (precedent:
`D-review-recapture-mvp` from sprint-3, which also landed mid-plan
after a real-rig finding). Issues:

1. **Eject ioctl reports success but tray doesn't open.**
   `archivist/drivers/drive.py::eject` issues `CDROMEJECT` (`0x5309`)
   via `fcntl.ioctl`. On the dogfood USB CD drive the call returns
   success but the tray never physically opens — almost certainly a
   firmware quirk. Switching to shell-out to the `eject` binary
   (ATAPI `START STOP UNIT` with LoEj+Start) is more universally
   honored.
2. **Loop re-rips the same disc when eject doesn't physically work.**
   Underlying state-machine bug: after EJECT, the loop returns to
   WAITING; if the drive still reports `disc-ok`, it immediately
   starts another rip cycle. CD_0019, CD_0020, ... all generated
   from the same physical disc tonight before the operator caught
   it. Fix: new `WAITING_REMOVE` state that only advances when the
   drive reports `tray-open` OR `no-disc`.
3. **Manual mode (operator-driven state-machine advance).**
   Auto-mode timing has too many edge cases. Operator needs an
   explicit Auto | Manual toggle in the FastAPI UI; in Manual mode,
   STABILIZE/RIP/CAPTURE/EJECT transitions are button-driven via
   new `POST /api/control/{start-rip,eject,capture,reset,mode}`
   endpoints. Default remains `auto` — the new mode is opt-in via
   the UI toggle or `ARCHIVIST_MODE=manual` env.

**Tasks added (7 total — 4 Wave 1 tests + 3 Wave 2 impls):**
`test-eject-reliability`, `test-waiting-remove-state`,
`test-manual-mode-state-gating`, `test-manual-mode-endpoints`
(Wave 1); `impl-eject-reliability`,
`impl-waiting-remove-state`, `impl-manual-mode` (Wave 2). All
land in a new "Bucket C — real-rig fixes surfaced during
post-Wave-0 smoke" subsection in both Wave 1 and Wave 2; existing
Bucket A and Bucket B tasks unchanged. Bucket A (music-pipeline
contract conformance) remains the load-bearing scope; Bucket C
is complementary — `impl-waiting-remove-state` and
`impl-manual-mode` depend on `impl-working-dir-handoff` so the
state-machine restructure is the natural integration point.

**Three new decision-log entries proposed:** `D-eject-via-shell`,
`D-waiting-remove-state`, `D-manual-mode`. Total decision-log
entries proposed for sprint-4 ratification: 10 (was 7).

**Updated sprint-4 task counts:**
- Wave 0 (operator-driven): 1 task (complete)
- Wave 1 failing tests: 11 (Bucket A) + 3 (Bucket B) + 4 (Bucket C) = **18 tests**
- Wave 2 impls: 10 (Bucket A) + 1 docs (Bucket A) + 3 (Bucket B) + 3 (Bucket C) = **17 impls**
- Stretch: 2 (unchanged)
- **Total: 38 tasks** (was 31 including stretch + Wave 0; was 27 post-Wave-0 non-stretch).

### 2026-05-15 — operator — Wave 0 migration complete

Music-pipeline stack relocated from laptop (`/srv/cd-music-stack` on `mash-ubie`) to CM4 (`/srv/cd-music-stack` on `piUSBcam2` / `192.168.6.38`). All 10 steps of `docs/operations/2026-05-15-music-stack-migration.md` executed cleanly.

**End state on CM4:**
- All three containers `Up`: `cd_navidrome`, `cd_jellyfin`, `cd_beets`
- URLs reachable from LAN: `http://192.168.6.38:{4533,8096,8337}/`
- Music tree intact: `/srv/music/inbox/CD_0004` (341MB) + `/srv/music/inbox/CD_0018` (282MB) carried over
- Runtime sqlite DBs wiped on landing (clean start for navidrome / jellyfin / beets)
- `.env` correct: PUID/PGID=1000 (matches mmariani), TZ=America/Los_Angeles, MUSIC_ROOT=/srv/music

**Beets config gotchas surfaced during the smoke-test import of CD_0018** (these are sprint-4 polish for the music-stack scaffold, NOT cd-archivist code work — but worth logging here so they don't recur on the next deployment):
1. `fetchart.sources` was scaffolded in the legacy flat-string format (`filesystem coverart itunes amazon albumart`) which the current beets rejects with `UnknownPairError`. Patched in place to a YAML list of source names. Plugin loaded cleanly after container restart.
2. **The `musicbrainz` plugin was missing from `plugins:`** — `chroma` (AcoustID) explicitly warns `"musicbrainz plugin not enabled; acoustid matches will not produce candidates"` and produces zero results regardless of search method. Symptom: every import path (auto-match, text search, direct ID lookup) returned "no matching release found." Added `musicbrainz` to the plugin list, restarted container, MB queries started returning real candidates.
3. **Burned-CD AcoustID failure:** the CD_0018 rip is a burned copy; its audio fingerprint doesn't match the commercial 1999 US Nitro release in AcoustID's DB. Beets' auto-match returned weak candidates (best 32% confidence) but text search + direct MBID lookup (`5100dc6d-7191-483c-901d-cdb95bf06f88`) both work. This is the design failure mode that sprint-4's `musicbrainz_disc_id` stretch task addresses for future rips.

Wave 0 is closed. Wave 1 (failing tests) is unblocked.

### 2026-05-15 — planner — sprint-4 drafted

Drafted `docs/coordination/sprint-4.md` per the handoff brief.
Bucket A (music-pipeline contract conformance, 11 Wave 1 tests + 11
Wave 2 impls including a docs task) is the load-bearing scope.
Bucket B (3 sprint-3 polish carryovers proven by the CD_0018 real-rig
rip — `rip_progress` parser fix, WAV cleanup, library `?status=`
filter) ships alongside. Stretch tasks (SHA-256 hashes in
`source.json.files[]`, libdiscid for `musicbrainz_disc_id`) marked
optional.

Seven decision-log entries proposed (`D-music-pipeline-paths`,
`D-source-json-v1`, `D-folder-naming-migration`,
`D-canonical-disc-photo`, `D-failed-disc-disposition`,
`D-wav-cleanup`, `D-library-legacy-adapter`) — to be ratified at
sprint-4 kickoff via `decision-card-flow` / `ratify`.

Demoted scope: the manual-capture-and-album-art design doc
(`docs/design/2026-05-15-manual-capture-and-album-art.md`) is
deferred to sprint-5 candidate per the handoff brief.

Out of scope (carried to sprint-5+): manual capture / album art
upload, alignment overlay, OCR, AccurateRip verification, ISRC /
UPC / TOC, CUE sheets, `archivist.service` systemd unit (still
postponed per `D-systemd-defer`), Docker (still postponed per
`D-docker-postpone`), editable review UI, Navidrome integration.
