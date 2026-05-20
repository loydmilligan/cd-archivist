---
project: cd-archivist
sprint: sprint-5
created: 2026-05-15T00:00:00.000Z
updated: 2026-05-19T00:00:00.000Z
status: closed
---

# cd-archivist — coordination doc (sprint-5)

> Strict template per Session O2=B / seed §12 Phase 8. The dashboard
> reads this as the canonical substrate (seed §3.7); orc emits
> `coord-doc-stale` cards when drift is detected (§3.8 / O7=A).
>
> Section headings are load-bearing — keep them as-is so the parser can
> find them. Section bodies are markdown-flexible.

## Plan Source

- Type: inline
- Path: this document (`## Active Sprint Plan` section)
- Active unit: sprint-5

## Sprint Goals

- **Close the review loop in the UI.** Per
  `docs/design/2026-05-16-in-ui-beets-review.md`, ship Option B — a
  full MusicBrainz candidate-selection flow as web pages on the
  existing FastAPI app. After sprint-5, an operator can drive a
  `/srv/music/review/<folder>` from a phone or laptop browser without
  ssh-ing into the CM4 to run `docker exec -it cd_beets beet import`.
- **Cut the review pile by capturing `musicbrainz_disc_id` at rip
  time.** The sprint-4 stretch slipped; sprint-5 lands it. CDDB-style
  TOC lookup (track count + track lengths via libdiscid) matches
  burned copies of commercial pressings that AcoustID's audio
  fingerprint check rejects — verified against the AFI + STP rips.
  The majority of "review" backlog cases auto-resolve once the
  identifier is present in `source.json`.
- **Land five real-rig polish items proven during the sprint-4
  smoke.** WAV cleanup didn't actually run for STP (#1); the
  `/library/<disc>` thumbnail prefers the rough disc-photo even when
  beets has fetched real cover art (#2); `process-ready-auto` leaves
  a `PROCESSING` marker behind in the moved folder (#3, optional);
  the Mash Co. README still doesn't list cd-archivist (#4,
  cross-repo); and the `archivist.service` systemd unit decision
  carried from sprint-2 (`D-systemd-defer`) needs to either land or
  formally close (#5).
- **Preserve the music-pipeline contract.** No schema bump. No
  changes to `READY` / `FAILED` semantics. No changes to the disc
  folder shape. `source.json.identifiers.musicbrainz_disc_id` is
  ALREADY part of schema v1 (sprint-4 `D-source-json-v1` reserved it
  as nullable); sprint-5 just populates it.
- **TDD discipline preserved.** Wave 1 = failing tests
  (parallel-safe); Wave 2 = impls (depends-gated). Wave 0 = operator
  setup that gates Wave 1 (musicbrainzngs install on the CM4
  venv). No Wave 3 pytest — operator-driven smoke against the
  dogfood rig per the sprint-4 cadence.

> **Scope-hierarchy reminder.** Bucket B (in-UI beets review) is the
> load-bearing scope this sprint — without it, every weak-match disc
> still requires a terminal. Bucket A (disc-id capture) is small but
> high-leverage: it shrinks the Bucket B input set. Bucket C is
> visible polish; any single item can slip to sprint-6 without
> compromising the goals.

## Active Initiatives

- _None — sprint-5 plan below is the substrate._

## Active Sprint Plan

<!-- What ships in sprint-6+ (out of scope here):
     - Album art uploads via the UI (the deferred sprint-4 spec at
       `docs/design/2026-05-15-manual-capture-and-album-art.md`).
       The manifest-schema-bump-required portions stay deferred —
       the on-rig "take a review photo" button (sprint-3
       `D-review-recapture-mvp`) covers the immediate need.
     - Live cam-preview overlay (countdown-only UX is good enough).
     - AcoustID fingerprint SUBMISSION back to AcoustID DB.
     - Batch operations across multiple review folders.
     - Editable metadata corrections (rename track titles by hand
       in the UI). v1 review is "pick a MusicBrainz release";
       v1.5 may add per-field edits.
     - Containerization / Docker for cd-archivist itself (the
       music stack on CM4 in Docker is fine; cd-archivist
       containerization is sprint-7+).
     - `archivist.service` reconsidered: sprint-5 RESOLVES the
       deferral one way or the other (see Bucket C #5). Carrying
       it forward yet again is not the plan. -->

### Wave 0 — Operator-driven setup (gates Wave 1)

> **`install-musicbrainzngs-in-archivist` must complete before
> Wave 1 starts** — the Bucket B test tasks import the lib in
> their fixtures (mocked, but the import itself runs). The other
> two Wave 0 tasks are sprint-scope adjacent: they don't gate
> Wave 1 but should land before sprint-5 closes.

- [x] {agent: operator, id: install-musicbrainzngs-in-archivist}
  **Operator-owned — human-driven, not an agent task.** Add
  `musicbrainzngs` to the cd-archivist runtime venv on the CM4 so
  Bucket B's MB client can import it. Two steps:
  1. Add `"musicbrainzngs>=0.7"` to the `[project].dependencies`
     list in `pyproject.toml` (the pipeline agent does this as
     part of `impl-mb-client` — operator does NOT edit code; this
     bullet is a heads-up that the pip install lands on the CM4
     after the impl commit).
  2. After `impl-mb-client` lands, on the CM4: `cd
     /srv/cd-archivist && source .venv/bin/activate && pip
     install -e '.[dev]'` (or whatever the production install
     command is — `cm4-setup.md` documents it). Verify with
     `python -c "import musicbrainzngs; print(musicbrainzngs.
     __version__)"`.
  - **Acceptance:** `python -c "import musicbrainzngs"` returns
    cleanly on the CM4 venv; the cd-archivist process restarts
    without import errors; the new `/api/review/*` endpoints
    return 200 (not 500 from a missing-dep import error) for a
    smoke-test query.

- [x] {agent: operator, id: install-libdiscid-on-cm4}
  **Operator-owned — human-driven, not an agent task.** The
  `discid` Python package shells to libdiscid (a small C library
  that reads CD-TOCs and computes the MusicBrainz disc-id hash).
  Install the apt package on the CM4: `sudo apt-get install -y
  libdiscid0`. Then add `"discid>=1.2"` to
  `pyproject.toml::[project].dependencies` (the drivers agent
  does the pyproject edit as part of `impl-disc-id-capture`;
  the operator runs the apt install + pip reinstall after that
  commit lands). Document the apt dep in
  `docs/operations/cm4-setup.md` § "Runtime apt dependencies"
  alongside `eject` (the drivers agent folds the docs edit into
  `impl-disc-id-capture` — operator just executes the shell
  commands).
  - **Acceptance:** `dpkg -l libdiscid0` shows the package
    installed on the CM4; `python -c "import discid; d =
    discid.read('/dev/sr0'); print(d.id)"` returns a non-empty
    string when an audio CD is in the drive (use any of the
    handy commercial discs on the rig — the AFI rip is a known
    burned-CD case where this still works). Does NOT gate
    Wave 1; install any time after `impl-disc-id-capture`
    lands.

- [x] {agent: operator, id: install-archivist-systemd-unit}
  **Operator-owned — human-driven, not an agent task.** Resolve
  the long-running `D-systemd-defer` (sprint-2) decision: install
  cd-archivist as a systemd user service on the CM4 so it
  survives reboots without the operator having to re-launch
  tmux. The service unit drafted inline below; copy-paste,
  enable, verify. Lives outside the cd-archivist code repo (it's
  a deployment artifact); sprint-5's
  `D-systemd-resolve-land-it` decision-log entry captures the
  rationale and supersedes `D-systemd-defer`.

  **`~/.config/systemd/user/cd-archivist.service`:**

  ```ini
  [Unit]
  Description=cd-archivist — automated CD ripping + capture loop
  After=docker.service network-online.target
  Wants=network-online.target

  [Service]
  Type=simple
  WorkingDirectory=/srv/cd-archivist
  Environment="MUSIC_INBOX_DIR=/srv/music/inbox"
  Environment="MUSIC_WORKING_DIR=/srv/music/.ripping"
  Environment="MUSIC_FAILED_DIR=/srv/music/failed"
  Environment="ARCHIVIST_PROCESS_READY_HOOK=/srv/cd-music-stack/bin/process-ready-auto"
  Environment="ARCHIVIST_MODE=auto"
  ExecStart=/srv/cd-archivist/.venv/bin/python -m archivist
  Restart=on-failure
  RestartSec=5

  [Install]
  WantedBy=default.target
  ```

  Install:

  ```sh
  mkdir -p ~/.config/systemd/user
  # paste the unit above into ~/.config/systemd/user/cd-archivist.service
  systemctl --user daemon-reload
  systemctl --user enable --now cd-archivist.service
  loginctl enable-linger $USER   # so the unit survives logout
  ```

  - **Acceptance:** `systemctl --user status cd-archivist`
    shows `active (running)`; rebooting the CM4 brings
    cd-archivist back up automatically (operator confirms via
    `ssh cm4 'systemctl --user status cd-archivist'` after a
    reboot); the previous tmux-launched process is stopped to
    avoid double-binding `/dev/sr0`. Does NOT gate Wave 1.

- [x] {agent: operator, id: update-mash-co-readme-products-in-scope}
  **Operator-owned — human-driven, cross-repo task.** Mash Co.
  Design System's `README.md` "Products in scope" section still
  doesn't mention cd-archivist (sprint-3 + sprint-4 both used
  Mash Co. tokens for the library + manual-mode UIs; sprint-5's
  in-UI review surface uses them again). Add a one-line entry to
  `/home/loydmilligan/Projects/Mash Co. Design System/
  README.md` under the products list: `cd-archivist
  (FastAPI library + review UI on the CM4 dogfood rig)` or
  whatever phrasing matches the existing entries. Touches a
  different repo; agents in this sprint do NOT modify it.
  - **Acceptance:** `git -C "/home/loydmilligan/Projects/Mash
    Co. Design System" log --oneline -5` shows a "docs(readme):
    add cd-archivist" commit; the README's products list
    includes the new entry. Does NOT gate Wave 1.

### Wave 1 — Failing tests (parallel-safe)

#### Bucket A — MusicBrainz disc-id capture at rip time

- [x] {agent: drivers, id: test-disc-id-capture} Failing tests for
  the new `archivist/drivers/disc_id.py::read_disc_id(device:
  Path) -> str | None`. The function wraps `libdiscid` via the
  `discid` Python package: open the drive, read the TOC, return
  the MusicBrainz disc-id (a base64-ish string) or `None` when
  the drive has no disc / the read fails. Tests in
  `tests/drivers/test_disc_id.py` (new file) using `monkeypatch`
  to stub the `discid` module: (a) audio CD present → returns
  the stubbed disc-id string; (b) drive empty (`discid.read`
  raises `discid.DiscError`) → returns `None`, logs at INFO; (c)
  underlying `OSError` (e.g. drive busy) → swallowed, returns
  `None`, logs at WARNING with the exception message + device
  path; (d) `ImportError` on the `discid` module itself (not
  installed) → returns `None`, logs once at WARNING with a
  remediation hint pointing at `cm4-setup.md`; (e)
  **never-raises invariant** — no input or library outcome
  causes the function to raise (the rip path must not be poisoned
  by a missing libdiscid).
  - **Acceptance:** New file `tests/drivers/test_disc_id.py`.
    Five cases. Fails until `impl-disc-id-capture`. Helper lives
    in `archivist/drivers/disc_id.py` (new file) — sibling to
    `drive.py`.

- [x] {agent: pipeline, id: test-source-json-identifiers} Failing
  tests extending `tests/pipeline/test_source_json_builder.py`.
  When `read_disc_id()` returns a non-`None` string at rip
  start, `build_source_json(...)` populates
  `source.identifiers.musicbrainz_disc_id` with that value;
  when `read_disc_id()` returns `None`, the field stays null
  (matching sprint-4's all-null default). The disc-id is read
  ONCE at rip start (before tray-open / EJECT); the read result
  is passed through the cycle bookkeeping into the builder, NOT
  re-read at HANDOFF time. Tests: (a) builder called with
  `disc_id="abc123base64..."` → `source.identifiers.
  musicbrainz_disc_id == "abc123base64..."`; (b) builder called
  with `disc_id=None` → field stays null (regression — existing
  sprint-4 cases still pass); (c) builder called with a
  whitespace-only or empty string → treated as `None` (defense
  against libdiscid emitting an empty result on a marginal
  read).
  - **Acceptance:** Three new cases appended to
    `tests/pipeline/test_source_json_builder.py`. Existing six
    sprint-4 cases still pass. Fails until
    `impl-source-json-identifiers`.

#### Bucket B — In-UI beets review (per `docs/design/2026-05-16-in-ui-beets-review.md`)

- [x] {agent: pipeline, id: test-review-folder-list} Failing tests
  for `GET /api/review/folders`. The endpoint aggregates folders
  needing operator review from TWO sources per
  `D-review-folder-discovery`: (i) every direct child of
  `MUSIC_REVIEW_DIR` (default `/srv/music/review`) — these are
  beets-quiet-mode weak-match dropouts; (ii) every direct child
  of `MUSIC_INBOX_DIR` containing a `READY` marker but NO
  `PROCESSING` marker — these are pre-beets backlog (the import
  hook hasn't picked them up yet, OR the importer renamed
  READY→PROCESSING and crashed). Dedupe by folder name (a name
  collision shouldn't happen but defend); sort by mtime
  descending. Tests in
  `tests/service/test_review_endpoints.py` (new file) using
  `tmp_path` for both roots: (a) empty review + empty inbox →
  returns `{"folders": []}`; (b) review with one folder → one
  entry with name + audio file count + total duration (use a
  fixture FLAC OR mock `audio.total_duration_seconds` derivation
  via the same ffprobe helper sprint-4 introduced); (c) inbox
  with READY + no PROCESSING → folder included; (d) inbox with
  READY + PROCESSING → folder EXCLUDED (importer has it); (e)
  inbox without READY → folder EXCLUDED (rip in progress); (f)
  per-entry shape: `{name, source: "review"|"inbox-stuck",
  audio_count, total_seconds, source_json: {...} | null}` —
  asserts `source_json` is the loaded dict when
  `<folder>/source.json` exists, null otherwise (legacy `CD_NNNN`
  folders without source.json still surface but with null).
  - **Acceptance:** New file
    `tests/service/test_review_endpoints.py`. Six cases. Fails
    until `impl-review-routes`.

- [x] {agent: pipeline, id: test-review-candidates-search} Failing
  tests for `GET /api/review/<folder>/candidates?search=...` —
  the MusicBrainz text-search path. Tests stub the
  `musicbrainzngs` module (the singleton from
  `archivist/service/mb_client.py`) and verify the call shape +
  response transformation: (a) `?search=afi+sing+the+sorrow` →
  `mb.search_releases` called with the query string + per-page
  limit (5, matching beets' default); (b) empty result → returns
  `{"candidates": []}` with HTTP 200; (c) populated result →
  each candidate transformed into the documented shape:
  `{mbid, score, artist, title, year, label, catalog_no,
  track_count, tracks: [{position, title, length_seconds}]}`;
  (d) candidate response includes a track-by-track diff
  computed against the folder's audio files: `tracks_diff:
  [{file, proposed_title, proposed_length_seconds,
  delta_seconds, delta_warning: bool}]` — `delta_warning` true
  when `abs(delta_seconds) > 5`; (e) folder doesn't exist (no
  match in either review or inbox roots) → 404; (f) `mb` raises
  `musicbrainzngs.WebServiceError` → 502 with a clear "MusicBrainz
  unavailable" body.
  - **Acceptance:** Six cases in `tests/service/test_review_
    endpoints.py`. Fails until `impl-review-routes`.

- [x] {agent: pipeline, id: test-review-candidates-mbid} Failing
  tests for `GET /api/review/<folder>/candidates?mbid=...` —
  the direct-lookup path. Tests stub the same
  `musicbrainzngs` module: (a) `?mbid=<valid-mbid>` →
  `mb.get_release_by_id` called with `includes=
  ["recordings","artist-credits","labels","release-groups"]`
  (matching beets' MB plugin default); response transformed
  into a single-entry candidate list with the same shape as the
  search path (so the UI can render either with one component);
  (b) `mbid` validated against UUID format; bad shape → 400; (c)
  unknown MBID → MB raises `WebServiceError` with HTTP 404
  context → 404 returned; (d) `?search=...&mbid=...` both set →
  400 (the two are mutually exclusive — UI either searches or
  fetches by ID).
  - **Acceptance:** Four cases in `tests/service/test_review_
    endpoints.py`. Fails until `impl-review-routes`.

- [x] {agent: pipeline, id: test-review-apply} Failing tests for
  `POST /api/review/<folder>/apply` body `{"mbid": "..."}`. The
  endpoint shells to `subprocess.run(["docker","exec",
  "cd_beets","beet","import","-q","--search-id",mbid,
  f"/downloads/{folder}"], capture_output=True, text=True,
  timeout=120)` and reports the result. Tests use
  `fake_subprocess` from `conftest.py`: (a) happy path
  (returncode 0) → returns `{"status":"applied", "mbid":..., "
  library_path": <derived from beets stdout>}` HTTP 200; (b)
  beets nonzero returncode → 500 with `{"status":"failed",
  "stdout":..., "stderr":...}` (operator forensics); (c)
  `subprocess.TimeoutExpired` → 504 with a clear "beets import
  exceeded 120s" message; (d) `LoopState.phase in {"rip",
  "eject","capture"}` for ANY folder (this folder OR another
  in-flight rip) → 409 with `{"status":"busy","phase":...}`
  (per sprint-3 / `D-review-recapture-mvp` race-condition
  pattern — beets must not fight a live ripper for the same
  filesystem); (e) folder doesn't exist → 404; (f) request
  body missing `mbid` or invalid UUID → 400; (g) argv
  inspection — `fake_subprocess` records the call; assert on
  the EXACT argv list to lock the contract (regression check
  against accidental `shell=True` or wrong container name).
  - **Acceptance:** Seven cases in `tests/service/test_review_
    endpoints.py`. Fails until `impl-review-routes`.

- [x] {agent: pipeline, id: test-review-use-as-is} Failing tests
  for `POST /api/review/<folder>/use-as-is`. Body empty.
  Endpoint shells to `subprocess.run(["docker","exec",
  "cd_beets","beet","import","-A", f"/downloads/{folder}"],
  ...)` — `-A` is beets' "do not autotag" flag, files land
  in the library with directory-name-as-album. Same argv +
  timeout + 409-while-ripping handling as `apply`. Tests in
  `tests/service/test_review_endpoints.py`: (a) happy path
  → 200 + library path; (b) beets failure → 500 with stderr;
  (c) state mismatch (live ripper) → 409; (d) folder
  doesn't exist → 404; (e) argv inspection — assert exact
  argv list including `-A` flag (regression check).
  - **Acceptance:** Five cases in `tests/service/test_review_
    endpoints.py`. Fails until `impl-review-routes`.

- [x] {agent: pipeline, id: test-review-ui-list} Failing tests
  for `GET /review` HTML page (sibling to `/library`). Mash Co.
  dressed: dark theme, sentence case throughout, eyebrow
  pattern at the top of the page, grid of cards. Tests in
  `tests/service/test_review_pages.py` (new file) using the
  FastAPI `TestClient`: (a) empty review + empty inbox → page
  renders with an empty-state message ("nothing to review")
  using `--ink-3` muted color; (b) two review folders → grid
  contains two `<article class="card">` elements with the
  folder name, audio count, "review now" CTA link to
  `/review/<folder>`; (c) Mash Co. invariant assertions:
  `data-theme="dark"` on the body, sentence-case headings (no
  Title Case in the rendered HTML — assert via a regex on
  `<h1>` / `<h2>` content), eyebrow class present
  (`<p class="eyebrow">`), the CTA button uses
  `class="btn btn--accent"`; (d) the review and inbox-stuck
  cards visually distinguish the source (e.g. an
  `data-source="inbox-stuck"` attribute or a small chip) so
  the operator knows which pile each came from; (e) link
  back to `/library` present in nav.
  - **Acceptance:** New file `tests/service/test_review_pages.
    py`. Five cases. Fails until `impl-review-pages`.

- [x] {agent: pipeline, id: test-review-ui-detail} Failing tests
  for `GET /review/<folder>` HTML page. Header with folder
  name + audio summary; search controls (text + "search MB"
  button, MBID input + "fetch by ID" button); empty candidate
  list initially (the page loads the candidate list via a
  same-page form submission — `<form method="get"
  action="/review/<folder>">` — keeps the no-JS contract from
  sprint-3); when a search is in the query string, candidate
  cards render with confidence as a horizontal `<progress>`
  bar, artist - album, year + label + catalog #, MBID, an
  expandable track-diff table (clicking a candidate row
  toggles the row open via `<details>` / `<summary>` — no JS),
  and Apply / Use-as-is `<form method="post">` buttons. Tests
  in `tests/service/test_review_pages.py`: (a) empty query →
  renders page shell with empty candidate list; (b) `?search=
  afi` (with the MB lib stubbed to return one candidate) →
  candidate card rendered with all expected fields; (c) Mash
  Co. invariants asserted (dark, sentence case, eyebrow, Apply
  button uses `--accent`, Use-as-is uses `--ink-3` quieter
  styling, candidate cards live on `--surface` with
  `--line` borders); (d) track-diff table uses `<code>` /
  monospace styling for the filename column; rows where
  `delta_warning` is true carry a `class="row--warn"` (which
  CSS colors with `--amber` per Mash Co.); (e) folder doesn't
  exist → 404; (f) the audio preview uses the existing
  sprint-3 `<audio controls>` mechanism so the operator can
  scrub a track before committing — assert one
  `<audio controls>` per file in the folder.
  - **Acceptance:** Six cases in `tests/service/test_review_
    pages.py`. Fails until `impl-review-pages`.

#### Bucket C — Polish + bug fixes

- [x] {agent: pipeline, id: test-wav-cleanup-integration} Failing
  REGRESSION test for the sprint-4 `impl-wav-cleanup` bug. The
  STP rip on the dogfood rig left `.wav` files alongside
  `.flac` files in the imported library, which means the
  cleanup helper either (a) wasn't called from the right place
  in the pipeline, (b) ran with `ARCHIVIST_KEEP_WAVS` defaulting
  to truthy, or (c) interleaved with the post-rip hook in a way
  that the music pipeline saw both. The test must reproduce
  the actual failure mode, not just re-cover the unit-level
  cleanup helper. Test in `tests/state_machine/test_loop.py`:
  (a) full happy-path rip cycle through `_from_rip` (using fake
  ripper + fake flac stub that materializes both `.wav` and
  `.flac` per track) → after `_from_rip` returns, the
  working-dir folder contains ONLY `.flac` files (no `.wav`
  siblings); (b) same scenario with `ARCHIVIST_KEEP_WAVS=1` set
  → both `.wav` and `.flac` present (regression of the env-
  override path); (c) call-site assertion — the cleanup helper
  is called WITH the correct `audio_dir` (the working-dir
  folder, not a stale path) and BEFORE the
  `os.replace(working/folder → inbox/folder)` handoff in
  `_from_capture` (so the inbox / music-pipeline-importer
  never sees the WAVs). The author roots out which of (a)-(c)
  was the actual cause during impl and documents the finding
  in `D-wav-cleanup-real-fix`.
  - **Acceptance:** Three cases added to
    `tests/state_machine/test_loop.py` (or split into a new
    `tests/state_machine/test_wav_cleanup_integration.py` if
    crowding becomes an issue — author's call). Fails until
    `impl-wav-cleanup-fix`.

- [x] {agent: pipeline, id: test-library-prefer-beets-cover} Failing
  tests for the `/library/<disc>` thumbnail-preference change.
  Sprint-4 ALREADY writes `source.json.detected_metadata.
  {album_artist,album,year}` after beets tagging (via the
  post-rip hook → process-ready-auto → beets → source.json
  update path). The library detail page must use those fields
  to derive the expected library album dir
  (`/srv/music/library/<album_artist>/<album>/`) and prefer
  `cover.{jpg,png,jpeg,webp}` from there as the thumbnail when
  it exists; when the library dir doesn't exist yet (rip
  happened but beets hasn't imported, OR a review-pile folder
  that was never imported), fall back to the existing
  `disc-photo.jpg`. Tests in `tests/service/test_library.py`:
  (a) folder with `source.json` + `detected_metadata.album` set
  + a library cover at the derived path → thumbnail URL points
  at the library cover (assert via the rendered `<img src=...>`);
  (b) same folder but library dir absent → thumbnail falls
  back to `disc-photo.jpg`; (c) folder with `source.json` +
  null `detected_metadata` → `disc-photo.jpg` (no derivation
  attempted); (d) legacy `CD_NNNN/manifest.json` folder →
  `disc-photo.jpg` (no library lookup — legacy manifest
  doesn't carry `detected_metadata`); (e) library cover present
  but ALSO disc-photo.jpg present → library cover wins (the
  preference order); (f) the detail page renders BOTH images
  in distinct sections — library cover at the top labeled
  "album art" + disc-photo lower labeled "physical disc"
  (sprint-3 review-recapture buttons stay attached to the
  disc-photo section). The new endpoint
  `GET /library/<disc>/album-cover` serves the library cover
  (path-traversal guarded, same as sprint-3
  `/library/<disc>/photo`); the `<img src>` points at this
  endpoint when applicable.
  - **Acceptance:** Six cases in `tests/service/test_library.py`
    (or a new `test_library_covers.py` if crowding — author's
    call). Fails until `impl-library-prefer-beets-cover`.

### Wave 2 — Implementations

#### Bucket A — MusicBrainz disc-id capture at rip time

- [x] {agent: drivers, depends: test-disc-id-capture, id: impl-disc-id-capture}
  Implement `archivist/drivers/disc_id.py::read_disc_id(device:
  Path) -> str | None`. Lazy-import `discid` at function entry
  (so the module loads even on dev machines without libdiscid);
  catch `ImportError`, `discid.DiscError`, `OSError` per the
  test contract. Add `"discid>=1.2"` to `pyproject.toml::
  [project].dependencies`. Update
  `docs/operations/cm4-setup.md` § "Runtime apt dependencies"
  with `libdiscid0` (the C library the `discid` Python pkg
  shells to). Module docstring documents the
  burned-CD-vs-AcoustID rationale: the disc-id is a CDDB-style
  TOC hash, robust to audio-fingerprint mismatch on burned
  copies of commercial pressings. Helper is called by pipeline
  via `impl-source-json-identifiers`; this task delivers only
  the drivers-side reader.
  - **Acceptance:** `tests/drivers/test_disc_id.py` passes.
    `pyproject.toml` updated. `cm4-setup.md` updated with the
    apt dep line. `ruff check` clean. The lazy-import means the
    suite passes on CI even when libdiscid isn't installed.

- [x] {agent: pipeline, depends: test-source-json-identifiers,
  depends: impl-disc-id-capture, id: impl-source-json-identifiers}
  Wire `read_disc_id` into the rip pipeline. Two changes:
  (1) `archivist/state_machine/loop.py::_from_stabilize` (or
  `_from_rip` — author's call; the constraint is "before tray
  open / EJECT, while the disc is still in the drive") calls
  `read_disc_id(device)` once and stashes the result on the
  `Cycle` dataclass as `disc_id_mb: str | None`; (2)
  `archivist/pipeline/source_json.py::build_source_json(...)`
  accepts a new keyword arg `mb_disc_id: str | None = None`
  and populates `source.identifiers.musicbrainz_disc_id` when
  truthy (whitespace-only treated as None per the test
  contract). The state machine passes `cycle.disc_id_mb`
  through at HANDOFF time. Logged via `RipLogWriter` as a
  `Disc-id captured: <value>` event (or `Disc-id read returned
  None` for the empty path) so the operator gets per-disc
  forensics in `rip.log`.
  - **Acceptance:** `tests/pipeline/test_source_json_builder.
    py` all cases pass (sprint-4 + new sprint-5). State
    machine tests still pass (the new field is additive — no
    breakage). Manual sanity deferred to operator real-rig
    run after sprint-5 closes (a fresh AFI rip should write
    `source.identifiers.musicbrainz_disc_id` populated; the
    music-pipeline importer can then resolve via that ID even
    when AcoustID misses).

#### Bucket B — In-UI beets review

- [x] {agent: pipeline, depends: install-musicbrainzngs-in-archivist,
  id: impl-mb-client} Implement
  `archivist/service/mb_client.py` — a singleton wrapper around
  `musicbrainzngs` with built-in throttling + UA. Module exposes
  `get_mb_client() -> MBClient` (lazy-singleton); the
  `MBClient` holds a threading lock + a "last request" wallclock
  to enforce the 1-req/sec MusicBrainz rate limit (wraps each
  `search_releases` / `get_release_by_id` call in a sleep-up-to
  block holding the lock, so concurrent FastAPI requests
  serialize through the limiter rather than getting throttled by
  MB's server side). `set_useragent("cd-archivist", archivist.
  __version__, "https://github.com/<owner>/cd-archivist")`
  called once at singleton construction. **Throttling scope is
  intentionally minimal:** simple monotonic-clock gate (≥ 1.0s
  between calls), no retry-with-backoff, no caching. If MB
  raises `WebServiceError`, propagate — the route handler turns
  it into a 502. Add `"musicbrainzngs>=0.7"` to `pyproject.toml::
  [project].dependencies` (the operator runs the pip install
  per Wave 0 `install-musicbrainzngs-in-archivist`).
  - **Acceptance:** Module imports cleanly; `get_mb_client()`
    returns the same instance across calls; the throttle is
    exercised by the route tests via the stubbed
    `musicbrainzngs` module (the lock + sleep is a thin pass-
    through and the stub bypasses the real network). No
    standalone unit test file for `mb_client.py` — the
    behavior is fully covered by the
    `test-review-candidates-*` suites.

- [x] {agent: pipeline, depends: impl-mb-client,
  depends: test-review-folder-list,
  depends: test-review-candidates-search,
  depends: test-review-candidates-mbid,
  depends: test-review-apply,
  depends: test-review-use-as-is, id: impl-review-routes}
  Implement the `/api/review/*` endpoint family in
  `archivist/service/app.py` (route registrations) backed by a
  new `archivist/service/beets_review.py` module (handlers +
  helpers — keeps `app.py` thin per the sprint-4 library
  pattern). New env var `MUSIC_REVIEW_DIR` (default
  `~/music-pipeline/review` to match the
  `MUSIC_*_DIR` family from sprint-4; `/srv/music/review` on
  the dogfood rig) consumed at startup alongside the existing
  three. Handler outline:
  - `GET /api/review/folders` aggregates per
    `D-review-folder-discovery` — direct children of
    `MUSIC_REVIEW_DIR` (source `"review"`) + READY-no-PROCESSING
    children of `MUSIC_INBOX_DIR` (source `"inbox-stuck"`).
  - `GET /api/review/<folder>/candidates` resolves the folder
    against both roots, dispatches on `?search` vs `?mbid` (400
    if both), invokes `get_mb_client()` accordingly, transforms
    the response into the documented shape, computes the
    track-by-track diff against the folder's audio files using
    the same ffprobe helper sprint-4 introduced.
  - `POST /api/review/<folder>/apply` and
    `POST /api/review/<folder>/use-as-is` shell out to
    `docker exec cd_beets beet import ...` per the test
    contracts; both gate on `LoopState.phase` not being in
    `{"rip","eject","capture"}` (per sprint-3 race-condition
    pattern), 409 otherwise.
  Library-path derivation from beets stdout: parse the
  `Tagging:` and `-> <library_path>` lines beets emits in
  quiet mode (regex against the captured stdout). If the
  derivation fails, return the library path as `null` rather
  than 500 — the import succeeded; the operator can find the
  album via `/library`.
  - **Acceptance:** All cases in
    `tests/service/test_review_endpoints.py` pass. `app.py`
    route registrations stay terse; the handler bodies live in
    `beets_review.py`. `ruff check` clean.

- [x] {agent: pipeline, depends: impl-review-routes,
  depends: test-review-ui-list,
  depends: test-review-ui-detail, id: impl-review-pages}
  Implement the `/review` and `/review/<folder>` HTML pages in
  `archivist/service/app.py` (route registration) with the
  rendering logic in `beets_review.py` (or a sibling
  `archivist/service/templates/` if the operator decides to
  introduce a template engine — sprint-4 stayed with inline
  HTML strings via small render helpers; sprint-5 follows the
  same pattern unless it gets unwieldy, which is the planner's
  judgment call captured below). Mash Co. dressing per the
  design spec § UI:
  - `/review` is a card grid (mirrors `/library`'s grid).
    Empty state uses `--ink-3` muted color + sentence-case
    copy. Inbox-stuck cards carry a small chip distinguishing
    them from review-pile cards (per the test contract).
  - `/review/<folder>` is a single-column page: header,
    search controls (`<form method="get">` for the no-JS
    contract), candidate list, audio preview row.
  - Candidate cards: confidence as `<progress max="100"
    value="...">` styled via Mash Co. tokens; track diff in a
    `<details>` block (no JS); apply / use-as-is as separate
    `<form method="post">` blocks per candidate (Apply uses
    `--accent`, Use-as-is uses `--ink-3` quieter styling).
  - Track-diff table: filename column wrapped in `<code>`
    (monospace via Mash Co.); rows with `delta_warning` get
    `class="row--warn"` for `--amber` highlight.
  - Audio preview: one `<audio controls>` per file in the
    folder (reuse sprint-3's library asset-serving for the
    actual stream — the existing `/library/<disc>/audio/<file>`
    endpoint works against any folder under inbox; the review
    page can reuse the same URL pattern for review-pile
    folders by adding a sibling `/api/review/<folder>/audio/
    <file>` if the existing endpoint is too tightly scoped to
    inbox — author's call, but keep the path-traversal guard
    that sprint-3 introduced).
  **Decision (planner judgment, see §Judgment calls below):**
  ship `impl-review-pages` as ONE task, not split list-vs-
  detail. The two pages share the Mash Co. styling helpers,
  the empty-state vs populated-state dispatch, and the same
  inline-HTML render style. Splitting just adds task overhead;
  the test contracts stay separate so the work is verifiable
  page-by-page.
  - **Acceptance:** Both `tests/service/test_review_pages.py`
    suites pass. Manual sanity by the operator on the dogfood
    rig: browse to `http://192.168.6.38:8337/review` →
    candidate selection works against the actual STP rip
    sitting in `/srv/music/review/`; an "Apply" with the
    correct MBID lands the album in `/srv/music/library/...`
    and the card disappears from `/review` on next page load.

#### Bucket C — Polish + bug fixes

- [x] {agent: pipeline, depends: test-wav-cleanup-integration,
  id: impl-wav-cleanup-fix} Trace and fix the WAV-cleanup bug
  surfaced by the STP rip. Investigation order:
  (1) Confirm the env default — `ARCHIVIST_KEEP_WAVS` is
  documented as defaulting to `False`; verify the code matches
  (look for case-sensitivity bugs in the truthy check, or a
  wrong default in `pipeline/rip.py`'s `cleanup_wavs(audio_dir,
  *, keep=False)` signature); (2) Confirm the call site —
  `cleanup_wavs(...)` MUST be called inside `_from_rip` (after
  the per-track flac conversion loop completes successfully)
  AND with the working-dir folder path, NOT a stale legacy
  path; (3) Confirm the timing — cleanup must run BEFORE the
  `os.replace(working_dir/folder → inbox_dir/folder)` handoff
  in `_from_capture`, so the music-pipeline importer never
  sees the `.wav` files. Once the root cause is identified,
  fix it AND record the finding in
  `D-wav-cleanup-real-fix` — sprint-5's only "bug-hunt"
  decision-log entry. The fix must NOT change the public
  `cleanup_wavs` signature (drivers + state-machine call
  sites both depend on it). On the dogfood rig, the operator
  runs a manual cleanup pass on the STP folder to remove the
  already-leaked `.wav` files (one-off `find /srv/music/library
  -name '*.wav' -delete` documented inline in
  `D-wav-cleanup-real-fix`).
  - **Acceptance:** `tests/state_machine/test_loop.py`
    wav-cleanup-integration cases pass. The unit-level
    `tests/drivers/test_ripper.py` cases (sprint-4) still
    pass. Manual sanity: a fresh test rip on the dogfood rig
    writes only `.flac` files to the inbox folder and to the
    eventual library path.

- [x] {agent: pipeline, depends: test-library-prefer-beets-cover,
  id: impl-library-prefer-beets-cover} Implement the
  thumbnail-preference change in
  `archivist/service/library.py` (the adapter from sprint-4)
  + `app.py` (the new `/library/<disc>/album-cover` endpoint).
  Adapter changes:
  - `DiscSummary` gains an optional `library_cover_path: Path
    | None` field.
  - `read_disc_summary(disc_dir)` derives the library album
    dir from `source.json.detected_metadata.{album_artist,
    album}` when both are populated; checks
    `MUSIC_LIBRARY_DIR` (new env var, default
    `~/music-pipeline/library`, `/srv/music/library` on the
    dogfood rig) for `<album_artist>/<album>/cover.{jpg,png,
    jpeg,webp}` and stores the first matching path on the
    summary.
  - The `/library` grid thumbnail src points at
    `/library/<disc>/album-cover` when
    `library_cover_path` is set, else the existing
    `/library/<disc>/photo` (disc-photo.jpg).
  - The `/library/<disc>` detail page renders BOTH images in
    distinct sections per the test contract (album art at
    top, physical disc lower with the existing sprint-3
    review-recapture buttons attached to the physical-disc
    section). Sentence-case section headings ("album art" /
    "physical disc"), Mash Co. dressed.
  - The new `GET /library/<disc>/album-cover` endpoint serves
    the file with the same path-traversal guard sprint-3
    introduced for `/photo` — derive the safe path inside
    `MUSIC_LIBRARY_DIR` and refuse anything that resolves
    outside.
  Add `MUSIC_LIBRARY_DIR` to `cm4-setup.md` § env vars
  alongside the sprint-4 trio. **Decision locked:** legacy
  `CD_NNNN/manifest.json` folders never get the library
  cover (their manifest doesn't carry `detected_metadata`)
  — they keep showing `disc-photo.jpg` as the thumbnail.
  Captured in `D-library-cover-preference`.
  - **Acceptance:** `tests/service/test_library.py`
    (or new `test_library_covers.py`) cases pass. Existing
    sprint-4 library tests still pass.

#### Stretch (only if Wave 2 finishes early)

- [x] {agent: pipeline, id: impl-process-ready-strip-marker}
  _Stretch — Bucket C #3._ The `process-ready-auto` script in
  `/srv/cd-music-stack/bin/` renames `READY → PROCESSING` to
  claim a folder, then moves the folder to `review/` or
  `archive/`. The `PROCESSING` marker gets carried along inside
  the moved folder. It's harmless but cluttered. Two possible
  fixes:
  - **A (preferred, lower coupling):** the cd-archivist
    review-folder-list endpoint already filters out folders
    with PROCESSING from the inbox-stuck source; extend it to
    ALSO ignore the PROCESSING marker file when computing
    audio counts and rendering the review-folder UI for the
    MUSIC_REVIEW_DIR source (so a moved-with-PROCESSING
    folder doesn't show "audio count: 13 + 1 marker file" in
    the UI).
  - **B (cleaner, cross-repo):** add `rm PROCESSING` to the
    `process-ready-auto` script in `/srv/cd-music-stack/`
    after the move. Operator-owned (touches a different
    repo).
  This stretch task implements (A) — small, in-repo, no
  cross-repo coordination required. (B) can land any time as
  an operator one-off. Drop the stretch entirely if Wave 2
  runs long; the clutter is cosmetic.
  - **Acceptance:** A new test case in
    `tests/service/test_review_endpoints.py` asserting that
    a folder containing `track01.flac` + `PROCESSING` reports
    `audio_count: 1` (the marker is ignored). Documented in
    `D-processing-marker-cosmetic` (only landed if the
    stretch ships).

## Agent Roster

| Agent | Owns | Does not touch |
|---|---|---|
| drivers | `archivist/drivers/{drive,led,camera,ripper,systemctl,usb_discovery,rip_log,disc_id}.py`, `archivist/models/manifest.py`, `tests/drivers/` | `archivist/pipeline/`, `archivist/state_machine/`, `archivist/service/`, `archivist/__main__.py`, `archivist/models/source.py` |
| pipeline | `archivist/pipeline/{disc_id,folder,folder_name,pairing,capture,rip,rip_progress,review_capture,source_json,post_rip_hook}.py`, `archivist/state_machine/`, `archivist/service/` (incl. `archivist/service/static/`, `archivist/service/library.py`, the new `archivist/service/mb_client.py`, the new `archivist/service/beets_review.py`, and the new `/api/review/*` + `/review/*` + `/library/<disc>/album-cover` route registrations in `app.py`), `archivist/models/source.py`, `archivist/__main__.py`, `tests/pipeline/`, `tests/state_machine/`, `tests/service/` (incl. new `tests/service/test_review_endpoints.py` and `tests/service/test_review_pages.py`), `tests/models/`, `tests/test_main_logging.py`, `tests/test_main_music_paths.py`, `tests/__init__.py`, `tests/conftest.py`, `pyproject.toml`, `ruff.toml`, `docs/operations/cm4-setup.md`, `docs/operations/sprint-2-smoke.md`, `docs/coordination/sprint-5.md` | `archivist/drivers/` internals (consumes their public interfaces) |

Same two agents as sprints 1-4. Drivers' sprint-5 footprint is the
single new file `archivist/drivers/disc_id.py` (Bucket A) — the
ripper itself is unchanged this sprint. Pipeline owns everything
else: the new `mb_client.py` singleton, the `beets_review.py`
handlers, the `/api/review/*` + `/review/*` route surface, the
`source.json` builder extension for `musicbrainz_disc_id`, the
state-machine wire-in for `read_disc_id`, the WAV-cleanup
investigation + fix, and the library cover-art preference change.

**New cross-agent meeting point:** `read_disc_id(device)` is owned
by drivers; pipeline's state machine calls it once per cycle in
`_from_stabilize` (or `_from_rip` — author's call) and stashes the
result on the `Cycle` dataclass for the `build_source_json`
consumer at HANDOFF time. Captured under Contract Changes.

**External read-only dependency:** the docker stack at
`/srv/cd-music-stack/`. Bucket B's `apply` / `use-as-is`
endpoints shell into the `cd_beets` container (`docker exec
cd_beets beet import ...`) — operator-side configuration the
container name + image must match cd-archivist's expectations,
which is documented in `cm4-setup.md` § "Music-pipeline integration".

## Decision Log

> The entries below are **proposed** by the planner. They become
> ratified at the sprint-5 kickoff session via `decision-card-flow` /
> `ratify`. Same `### {{date}} — {{decision-id}} — {{summary}}`
> shape from sprint-4.

### 2026-05-15 — D-disc-id-libdiscid — capture `musicbrainz_disc_id` at rip time via libdiscid (`discid` Python pkg)

**Proposed.** Real-rig finding from sprint-4 + the AFI / STP rips:
beets quiet-mode skips burned CDs because AcoustID's audio
fingerprint check rejects burned copies of commercial pressings
(the audio stream identity differs even though the album content
is identical). MusicBrainz's separate "disc id" mechanism is a
CDDB-style hash of (track count, track lengths) read off the
disc TOC; it matches any rip whose TOC matches a known
commercial release — including burned copies. Resolution: at rip
start (before tray open / EJECT, while the disc is still in the
drive), cd-archivist reads the disc-id via `libdiscid` (wrapped
by the Python `discid` package) and populates
`source.json.identifiers.musicbrainz_disc_id`. The
music-pipeline importer can then resolve the release via the
disc-id even when AcoustID misses, dramatically shrinking the
review-pile input set.

**Dependencies:** `libdiscid0` apt package on the CM4
(`sudo apt-get install -y libdiscid0`); `discid>=1.2` Python
package added to `pyproject.toml::[project].dependencies`. Both
documented in `cm4-setup.md` § "Runtime apt dependencies" and
the env-var matrix.

**Failure mode:** missing libdiscid / no disc / OSError on read
all return `None` — never raises. Sprint-4's `D-source-json-v1`
already reserved the field as nullable, so a `None` result is a
no-op for downstream consumers (the importer falls back to the
existing AcoustID + manual review path). This is a pure-additive
change to the rip pipeline.

### 2026-05-15 — D-beets-review-ui-mode — adopt Option B (web candidate selection), reject A and C

**Proposed.** Per `docs/design/2026-05-16-in-ui-beets-review.md`.
Three options were considered: (A) one-shot "apply suggested
match" + "use as-is" buttons with no candidate selection — too
coarse, doesn't replace the operator workflow; (B) a full
MusicBrainz candidate-selection flow rendered as web pages — the
"goldilocks" option, ships in sprint-5; (C) xterm.js piping the
real `beet import` interactive session into the browser — too
much infra, ties the UI to terminal-emulation lifecycle bugs and
to beets' interactive prompt format. Option B matches the
operator's actual review workflow (search MB → pick a release →
apply) without terminal emulation, and stays mobile-friendly.

**No JS contract preserved:** the search controls are
`<form method="get">`, the apply / use-as-is buttons are
`<form method="post">`, the candidate track-diff expansion uses
`<details>` / `<summary>`. Same anchor-link / form-post pattern as
the sprint-4 library `?status=` filter and manual-mode buttons.

### 2026-05-15 — D-mb-query-direct-not-beets — `musicbrainzngs` for queries; `beet import` for moves

**Proposed.** Two paths into MusicBrainz from cd-archivist:
candidate queries (read-only) and final imports (file moves +
DB writes). Resolution: use `musicbrainzngs` directly for
candidate queries — faster (no subprocess + no terminal-prompt
parsing), pagination-friendly, bypasses beets' interactive
prompt format. Shell out to `docker exec cd_beets beet import
-q --search-id <mbid>` ONLY for the actual file moves — beets
owns the file move + DB write semantics and we should not
reimplement that in Python.

**Implication:** new singleton `archivist/service/mb_client.py`
wraps `musicbrainzngs` with built-in throttling (≥ 1 req/sec
per MB's terms of service) + UA setting. Throttle is intentionally
minimal — monotonic-clock gate, no retry-with-backoff, no caching.
If MB raises, propagate; the route handler turns it into a 502.
Caching can land in sprint-6 if a real workload demands it; v1
favors simplicity.

### 2026-05-15 — D-review-folder-discovery — `/review` aggregates `MUSIC_REVIEW_DIR` + READY-no-PROCESSING in `MUSIC_INBOX_DIR`

**Proposed.** Two distinct populations of folders need operator
review: (i) beets-quiet-mode weak-match dropouts, which
`process-ready-auto` moves to `/srv/music/review/`; (ii) inbox
folders the importer hasn't processed yet (READY marker present
but no PROCESSING marker — either the hook hasn't fired or the
importer crashed mid-claim). Resolution: `GET /api/review/folders`
returns BOTH, with a per-entry `source: "review" | "inbox-stuck"`
field so the UI can distinguish them visually (small chip on
the card). New env var `MUSIC_REVIEW_DIR` (default
`~/music-pipeline/review`, `/srv/music/review` on the dogfood
rig). The two sources cover both failure modes — "beets gave
up" and "beets hasn't run yet" — without requiring a third
"stuck rips" surface elsewhere in the UI.

**Why both in one endpoint:** an operator sitting down to
"clear the review pile" cares about all folders waiting on
human attention, regardless of which pile they came from.
Splitting into `/review` and `/stuck` would force the operator
to check two surfaces.

### 2026-05-15 — D-systemd-resolve-land-it — install `cd-archivist.service` user unit on the CM4 (supersedes `D-systemd-defer`)

**Proposed.** Long-running deferral from sprint-2
(`D-systemd-defer`) and sprint-3 carryover finally resolved.
Sprint-5 lands the systemd user unit on the CM4 so cd-archivist
survives reboots without operator intervention. Unit file
drafted inline in `install-archivist-systemd-unit` (Wave 0).
`After=docker.service network-online.target` so the post-rip
hook's `docker exec cd_beets ...` call has a running container
to exec into. `Restart=on-failure` with a 5s `RestartSec` so
transient driver hiccups don't leave the rig dead. User unit
(not system unit) so the operator owns the install without
sudo; `loginctl enable-linger` keeps the unit running across
logout. Operator-owned execution; no agent runs the install.

**Why now and not sprint-7:** the manual-mode UI (sprint-4) +
the in-UI review (sprint-5) make cd-archivist a service the
operator interacts with from a phone browser, not a
foreground tmux process. Reboot-survival becomes important
once the operator stops being co-located with the rig.

### 2026-05-15 — D-wav-cleanup-real-fix — root cause + fix for the STP rip's leaked WAVs

**Ratified.** Root cause identified during `impl-wav-cleanup-fix`:
**(b) wrong call site — the helper was never invoked from the
state machine at all.** Sprint-4's `cleanup_wavs(audio_dir, *,
keep=False)` shipped with green unit tests, but no caller in
`archivist/state_machine/loop.py` ever invoked it. The
state-machine's `_from_rip_sprint4` wrote `rip.log` and routed
success/failure to EJECT or the failed-marker path, but skipped
the cleanup step entirely. So every successful rip on the
dogfood rig left both `track*.cdda.wav` and `track*.cdda.flac`
in `<working>/<folder>/audio/`, and the subsequent
`os.replace(working/folder → inbox/folder)` carried both kinds
forward — beets then imported both into the library.

Failure modes (a) [env-var truthy bug] and (c) [post-handoff
timing] were ruled out by inspection during impl: the env-var
check would still have a default-False path that ran cleanup;
the cleanup-after-handoff variant would still have left a
single failed rip's worth of WAVs at most, not the steady-state
behaviour seen on every rip.

**Fix:** call `cleanup_wavs(disc_dir / "audio", keep=...)`
inside `_from_rip_sprint4` on the success path, BEFORE
`_set_state(State.EJECT, ...)`. This guarantees the cleanup
runs before the CAPTURE-phase `os.replace` handoff, so the
inbox-stuck importer never sees `.wav`. New tiny helper
`_env_truthy("1" | "true" | "yes" | "on", case-insensitive)`
reads `ARCHIVIST_KEEP_WAVS`; exceptions during cleanup are
logged and swallowed (rip succeeded; missing audio dir or stat
failures must not poison the state machine).

**Lesson:** unit tests for a helper aren't enough when the
helper has zero callers — the sprint-4 `tests/pipeline/test_
wav_cleanup.py` cases all passed because they invoked
`cleanup_wavs` directly. The sprint-5 integration test exercises
the full state-machine path and catches the missing-caller bug
at the right layer. Going forward, any new "pure helper" that
ships should include at least one integration test asserting
the caller actually runs it.

**One-off operator cleanup:** `find /srv/music/library -name
'*.wav' -delete` removes the already-leaked WAVs from the STP
import (and any others); documented inline here so the
operator doesn't have to derive it.

### 2026-05-15 — D-library-cover-preference — beets-fetched cover wins over disc-photo as the library thumbnail

**Proposed.** `/library/<disc>` currently shows `disc-photo.jpg`
(the canonical webcam capture) as both the grid thumbnail and
the detail-page hero. Once beets has imported the album, the
library directory at `/srv/music/library/<artist>/<album>/`
contains a real `cover.{jpg,png}` (fetched from MusicBrainz /
fanart.tv via beets' fetchart plugin). The library UI should
prefer the beets cover when available — that's the actual
"album art" the operator wants to see. The disc-photo stays
available as the "physical disc" view (sprint-3
review-recapture buttons attach to that section); the canonical
thumbnail just changes preference order.

**Derivation:** sprint-4 ALREADY writes
`source.json.detected_metadata.{album_artist,album,year}` after
beets tagging (via the post-rip hook → process-ready-auto →
beets → source.json update path). The library adapter reads
those fields, derives the library album dir, and checks for a
cover file. New env var `MUSIC_LIBRARY_DIR` (default
`~/music-pipeline/library`, `/srv/music/library` on the
dogfood rig). New endpoint
`GET /library/<disc>/album-cover` serves the file with the
same path-traversal guard as the existing
`/library/<disc>/photo`.

**Legacy folders:** `CD_NNNN/manifest.json` doesn't carry
`detected_metadata`, so legacy folders never get the library
cover — they keep showing `disc-photo.jpg` as the thumbnail.
This is fine; the legacy folders were ripped before beets
integration and aren't in the library anyway.

### 2026-05-16 — D-processing-marker-cosmetic — review-folder UI ignores the PROCESSING marker file

**Locked.** `process-ready-auto` claims an inbox folder by
renaming `READY → PROCESSING`, then moves the folder into
`MUSIC_REVIEW_DIR` or `archive/` if beets falls back. The
`PROCESSING` marker travels along with the folder, which is
harmless but cluttery: a moved-with-marker folder could otherwise
render as "N+1 tracks" in the review UI. Sprint-5 stretch shipped
Option A (in-repo): the review-folder list and detail views count
audio strictly via the `*.flac` glob, and that contract is now
pinned by `test_folder_list_review_folder_ignores_processing_marker`.
Option B (`rm PROCESSING` inside `process-ready-auto` at
`/srv/cd-music-stack/`) remains available as an operator-side
cleanup; it doesn't require cd-archivist coordination and can
land any time.

## Ratification Log

<!-- Same shape as Decision Log; entries land here when a
     ratification-needed card resolves with kind "ratified". -->

_No ratifications yet._

## Contract Changes

<!-- API / schema / coord-doc-template changes that other agents must
     respect. Each entry: `### {{date}} — {{summary}}` + body listing
     before/after. The dashboard surfaces unprocessed entries as
     "contract changes since you last looked." -->

### 2026-05-15 — `source.json.identifiers.musicbrainz_disc_id` populated when libdiscid is available

- **Before:** All `source.json.identifiers.*` fields were always
  null (sprint-4 `D-source-json-v1`). The schema reserved the
  fields as nullable; nothing populated them.
- **After:** `source.json.identifiers.musicbrainz_disc_id` is
  populated by `archivist/drivers/disc_id.py::read_disc_id` when
  libdiscid is installed, the disc is in the drive, and the
  read succeeds. All other `identifiers.*` fields stay null
  (their populators land in sprint-6+). Schema unchanged — the
  field was already declared nullable.
- **Consumers:** the music-pipeline importer
  (`/srv/cd-music-stack/bin/process-ready-auto` → beets) can
  use the disc-id to resolve releases via MB's `discid`
  endpoint when AcoustID misses; no cd-archivist-side
  consumer (the field is read-only output for the importer).

### 2026-05-15 — new `/api/review/*` endpoint family + `/review/*` HTML pages

- **Before:** No `/api/review/*` namespace. Operators reviewed
  weak-match folders by ssh-ing into the CM4 and running
  `docker exec -it cd_beets beet import --quiet-fallback=ask
  /downloads/<folder>`.
- **After:**
  - `GET /api/review/folders` — JSON list of folders needing
    review, aggregated from `MUSIC_REVIEW_DIR` + `MUSIC_INBOX_
    DIR`-with-READY-no-PROCESSING per `D-review-folder-discovery`.
    Per-entry shape: `{name, source: "review" | "inbox-stuck",
    audio_count, total_seconds, source_json: {...} | null}`.
  - `GET /api/review/<folder>/candidates?search=` — MB text
    search via `musicbrainzngs.search_releases`. Up to 5
    candidates with confidence + tracks + computed track-by-
    track diff.
  - `GET /api/review/<folder>/candidates?mbid=` — direct MB
    lookup via `musicbrainzngs.get_release_by_id`. Single-entry
    candidate list (same shape as the search path).
  - `POST /api/review/<folder>/apply` body `{"mbid":"..."}` —
    shells to `docker exec cd_beets beet import -q --search-id
    <mbid> /downloads/<folder>`. 200 / 500 / 504 / 409
    semantics per the test contract.
  - `POST /api/review/<folder>/use-as-is` — shells to
    `docker exec cd_beets beet import -A /downloads/<folder>`
    (no autotag).
  - `GET /review` — HTML grid of review-pile cards.
  - `GET /review/<folder>` — HTML candidate-selection page
    with search controls + candidate list + audio preview +
    apply / use-as-is forms.
- **Consumers:** the FastAPI app picks up the new routes;
  operator browses to `http://192.168.6.38:8337/review` to
  drive the workflow. No agent depends on the new endpoints
  programmatically.

### 2026-05-15 — new env vars `MUSIC_REVIEW_DIR` + `MUSIC_LIBRARY_DIR`

- **Before:** sprint-4 introduced
  `MUSIC_INBOX_DIR` / `MUSIC_WORKING_DIR` / `MUSIC_FAILED_DIR`.
  The review pile lived implicitly at
  `<MUSIC_*_parent>/review` and the library at
  `<MUSIC_*_parent>/library`; cd-archivist didn't read either
  path.
- **After:** Two new env vars in the same family —
  `MUSIC_REVIEW_DIR` (default `~/music-pipeline/review`) and
  `MUSIC_LIBRARY_DIR` (default `~/music-pipeline/library`).
  Both consumed at startup; `MUSIC_REVIEW_DIR` powers the
  `/review` aggregation; `MUSIC_LIBRARY_DIR` powers the
  beets-cover-art preference in the library UI. Documented
  in `cm4-setup.md` alongside the sprint-4 trio. On the
  dogfood rig: `MUSIC_REVIEW_DIR=/srv/music/review`,
  `MUSIC_LIBRARY_DIR=/srv/music/library`.
- **Consumers:**
  `archivist/__main__.py::main` (reads env, passes through);
  `archivist/service/beets_review.py` (consumes
  `MUSIC_REVIEW_DIR`); `archivist/service/library.py`
  (consumes `MUSIC_LIBRARY_DIR`).

### 2026-05-15 — new `/library/<disc>/album-cover` endpoint + `DiscSummary.library_cover_path`

- **Before:** Each disc folder in `/library` showed
  `disc-photo.jpg` (via `/library/<disc>/photo`) as both the
  grid thumbnail and the detail-page hero. The
  `DiscSummary` dataclass had no field for an external cover.
- **After:** `DiscSummary.library_cover_path: Path | None`
  derived from `source.json.detected_metadata.{album_artist,
  album}` against `MUSIC_LIBRARY_DIR`. When set, the grid
  thumbnail and the detail-page "album art" section point at
  a new `GET /library/<disc>/album-cover` endpoint (same
  path-traversal guard as `/photo`). When unset (no
  `detected_metadata`, or no cover file in the library
  album dir, or a legacy `CD_NNNN` folder), the existing
  `disc-photo.jpg` continues to be used.
- **Consumers:** `archivist/service/library.py::
  read_disc_summary` (derives the path); `archivist/service/
  app.py` (registers the new endpoint); the library grid +
  detail-page render helpers (consume the field).

## Blockers

<!-- One bullet per active blocker. Format:
     `- [<agent>] <one-line blocker> — <link or reference>`. Resolved
     blockers move to the Activity Log. -->

- _None._

## Sprint-6 Candidates

<!-- Items captured mid-sprint-5 that should be picked up at sprint-6 planning. -->

- **Candidate-disc kanban status page** — replace single-line status surface
  with a card-per-disc kanban (Capture → Beets ID → ??? → Review / Library),
  per-track bar (green/empty/red/blue), and a Review screen explaining why
  each card is in review. Design brief:
  `docs/design/2026-05-16-candidate-disc-kanban-status.md`. Owner: pipeline.
- **`cdplay.service` missing on CM4** — state machine calls `systemctl
  start/stop cdplay.service` pre- and post-rip; both fail with `exit 5:
  Unit cdplay.service not found`. Observed STP rip (2026-05-15) and RATM
  rip (2026-05-16). Either install the unit or remove the dependency.
  Owner: operator + pipeline.
- **Beets interactive traceback-spam on tag-less flacs (UI blocker)** —
  observed 2026-05-16 attempting `docker exec -it cd_beets beet import
  --singletons /review/<folder>/` on the burned-mix-CD rip. chroma's
  AcoustID lookup returns "No matching recordings found" → beets falls
  back to MB metadata search → flacs have no tags → empty query → MB
  returns HTTP 400 → full traceback printed per track in an infinite
  loop, burying the `[S]kip, Use as-is, Enter search, ...` prompt. Even
  abort (`b`) gets eaten by the noise. Hard blocker for sprint-6's
  in-UI review v2 (web wrapper for beets candidate selection): the
  underlying CLI substrate must produce a clean prompt before any UI
  can wrap it. Mitigation paths: (a) suppress MB-search fallback when
  source.json indicates no embedded tags; (b) bypass beets' interactive
  path entirely — query MusicBrainz directly via `musicbrainzngs` (per
  `D-mb-query-direct-not-beets`) and only invoke `beet import` once a
  human picks an MBID. Owner: pipeline.

- **Damaged-disc UI options (first-class sprint-6 scope)** — when a
  rip fails or is stopped mid-flight, the disc card must offer three
  explicit actions: (1) **process partial as-is** (route the
  cleanly-ripped tracks through the rest of the pipeline with
  `source.json.status.partial=True`), (2) **redo entire capture**
  (discard + restart), (3) **pick tracks to (re-)rip** (checkbox list
  of every track from the TOC, pre-selected by success/failure state;
  cdparanoia re-runs against the selected range and merges with
  existing successful flacs). Full spec in the kanban brief's
  "Damaged-disc handling" section. Subsumes generic "partial-rip data
  loss" framing.

- **Damaged-disc detection (engine side)** — RATM (2026-05-16) failed twice in a row:
  first rip stalled on track 8 for ~25 min then bailed; second attempt
  same disc failed at track 6. Both times the partial output (clean
  tracks 1–N-1) was discarded and the operator got no actionable
  surface. An "elegant" path covers:
  1. **Fail-fast detection.** When cdparanoia retries the same sector
     >N times, stop the rip immediately instead of grinding for 25 min.
     Threshold candidates: 3 retries on a single sector, or any
     "Target hardware fault" sense code.
  2. **Preserve partial output.** Whatever flacs ripped cleanly land in
     `failed/<disc-folder>/` with `rip.log`, `source.json` (marked
     `status.rip_success=False`, `status.partial=True`, list of
     successful track indices), and the disc photo. Nothing is
     auto-deleted.
  3. **Operator surface.** Failed-disc card in the kanban (Review or a
     new "Damaged" bucket) shows: which tracks succeeded, which failed,
     where the partial files live, and three actions — **retry full
     disc**, **import partial as-is** (route the clean tracks through
     beets and accept the gap), or **abandon**.
  4. **Retry hints.** Surface read-speed reduction option ("retry at
     4x") and prompt to clean the disc before retry.
  5. **No `cdplay.service` dependency.** Today the post-rip handler
     calls `systemctl start cdplay.service` which doesn't exist on the
     CM4 — eject and recovery should work without that unit.

  Subsumes the prior "partial-rip data loss" line. Builds on the
  kanban brief (`docs/design/2026-05-16-candidate-disc-kanban-status.md`
  Q3) and the cdplay.service item above. Owner: drivers + pipeline.

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

### 2026-05-19 — orc — sprint-5 closed

- Bookkeeping pass during cross-sprint review.
- 23/23 Active Sprint Plan tasks ticked. Frontmatter `status` field was never set; flipped now for dashboard correctness.

### 2026-05-16 — operator — Wave 0 + Bucket C #4 landed (3 tasks ticked)

- `install-musicbrainzngs-in-archivist`: pip install -e '.[dev]' on
  the CM4 venv at `/home/mmariani/Projects/cd-archivist/.venv`; verified
  `import musicbrainzngs` returns cleanly. Path note: the systemd-unit's
  aspirational `/srv/cd-archivist` path does not yet exist; current
  venv lives under `/home/mmariani/Projects/cd-archivist/`.
- `install-libdiscid-on-cm4`: `sudo apt-get install -y libdiscid0` →
  `libdiscid 0.6.4` reports cleanly via
  `discid.LIBDISCID_VERSION_STRING`. Unblocks `read_disc_id` (sprint-5
  `efd3fba`) at runtime on the real rig.
- `update-mash-co-readme-products-in-scope`: added a `cd-archivist`
  row to the Products in scope table in
  `~/Projects/Mash Co. Design System/README.md` between the Orc Tower
  and SRMPW rows; "Active consumer" status reflects sprint-3/4/5 use
  of Mash Co. tokens in library + manual-mode + in-UI review pages.
- `install-archivist-systemd-unit`: killed the tmux-launched archivist
  (PID 536124); wrote `~/.config/systemd/user/cd-archivist.service`
  with paths adjusted from the sprint-5 draft to match the actual
  runtime (`WorkingDirectory=/home/mmariani/Projects/cd-archivist`,
  `ExecStart=/home/mmariani/Projects/cd-archivist/.venv/bin/python -m
  archivist` — the draft's `/srv/cd-archivist` is aspirational and
  doesn't exist yet). Added `MUSIC_REVIEW_DIR` + `MUSIC_LIBRARY_DIR`
  env vars (sprint-5 contract additions). `systemctl --user
  daemon-reload && enable --now` succeeded; `loginctl enable-linger`
  set so the unit survives logout. Status: `active (running)` since
  14:05:01, PID 754050. **All four operator tasks now ticked.**

### 2026-05-16 — finding — beets interactive import unusable on tag-less flacs

- Attempted manual `docker exec -it cd_beets beet import --singletons
  /review/2026-05-16_1344_disc-000001_20260516-135755/` on the
  17-track burned mix CD.
- chroma's AcoustID lookup returned "No matching recordings found"
  for every track (tracks are likely from sources not in AcoustID's
  DB, common for burned mix CDs with DJ edits / fades).
- Beets then fell back to MusicBrainz metadata search; because the
  flacs have **zero embedded tags** (cdparanoia + flac --best writes
  no tag fields), the search query was empty (`query=&`) and MB
  returned HTTP 400 per track.
- Per-track HTTPError tracebacks printed in an infinite loop, burying
  the interactive `[S]kip, Use as-is, Enter search, ...` prompt. Even
  `b` (aBort) couldn't be reached. Required SIGINT.
- **Impact:** sprint-6 in-UI review v2 (web wrapper for beets
  candidate selection) is blocked on this; the underlying CLI substrate
  must produce a clean prompt before a UI can wrap it.
- Captured in Sprint-6 Candidates above (mitigation paths: suppress
  empty-tag MB fallback in chroma config, or bypass beets' interactive
  path entirely and use `musicbrainzngs` direct queries per
  `D-mb-query-direct-not-beets`).

### 2026-05-16 — pipeline — stretch impl-process-ready-strip-marker landed (Option A, 310/310 green)

Locked the cosmetic-marker contract for the review source. The
existing `*.flac` glob in `_audio_count_and_duration` already
excluded the `PROCESSING` marker file naturally, so no production
code needed to change — but the behavior was implicit, undocumented,
and one glob-widening away from regressing. Added a regression test
(`test_folder_list_review_folder_ignores_processing_marker`) that
seeds `track01.flac + PROCESSING` in `MUSIC_REVIEW_DIR` and asserts
`audio_count == 1` and `source == "review"`. Test passes; pipeline
suite now 310/310 (drivers' 5 disc-id failures remain in drivers'
lane). Decision captured under `D-processing-marker-cosmetic`
(Option A shipped; Option B — `rm PROCESSING` inside
`process-ready-auto` — remains an operator-side cleanup that can
land any time without coupling to cd-archivist).

### 2026-05-16 — pipeline — Wave 2 impls landed (6 tasks, 6 commits, 309/309 green)

All 6 pipeline-owned Wave 2 impls shipped as atomic commits in
dependency-respecting order. Final pipeline test count: 309 passed,
0 failed (the 5 remaining failures are drivers' disc-id tests in
drivers' lane).

**Bucket A — disc-id integration (1):**
- `02eeb57` impl-source-json-identifiers — `build_source_json`
  gains `mb_disc_id: str | None = None` kwarg; empty/whitespace
  normalised to None. State machine reads disc-id once at rip
  start (`_from_stabilize`) via a lazy-imported wrapper around
  `archivist.drivers.disc_id.read_disc_id` so missing libdiscid
  doesn't break the loop. Threaded through cycle bookkeeping
  into the builder at HANDOFF time.

**Bucket B — in-UI beets review (3):**
- `c065988` impl-mb-client — `archivist/service/mb_client.py`
  with the singleton `MBClient`. User-Agent set at construction;
  threading.Lock + monotonic-clock gate enforces ≥1.0s between
  calls so concurrent FastAPI requests serialise instead of
  getting throttled by MB's server side. No retry/backoff, no
  caching — WebServiceError propagates for route handlers to
  surface as 502.
- `157da30` impl-review-routes — new `archivist/service/beets_
  review.py` owns folder discovery + MB candidate transform +
  beets-import subprocess wrappers. Four endpoints registered
  in `app.py`:
  - GET /api/review/folders — aggregates MUSIC_REVIEW_DIR +
    READY-no-PROCESSING children of MUSIC_INBOX_DIR per
    D-review-folder-discovery; sorted by mtime descending.
  - GET /api/review/<folder>/candidates — dispatches on ?search
    vs ?mbid (400 if both, 400 on invalid UUID); calls the
    stubbable singleton; transforms responses with tracks_diff
    computed against the folder's FLAC sizes.
  - POST /api/review/<folder>/apply — body {mbid} → exact argv
    [docker, exec, cd_beets, beet, import, -q, --search-id,
    mbid, /downloads/<folder>], shell=False, timeout=120,
    409 when LoopState in {RIP, EJECT, CAPTURE}.
  - POST /api/review/<folder>/use-as-is — same argv shape with
    -A flag.
  All 30 endpoint cases green.
- `7a2536e` impl-review-pages — `/review` list + `/review/
  <folder>` detail HTML in the same module. Mash Co.-dressed:
  dark theme, sentence case, eyebrow ≤2 words, no decorative
  emoji. Candidate cards render confidence as `<progress>` bar;
  Apply uses `btn--accent`; Use-as-is uses `btn--secondary`
  (--ink-3 quieter). Track-diff table wraps filenames in
  `<code>` (monospace) with `class="row--warn"` on >5s deltas
  (--amber colored). Audio preview per FLAC via new
  `GET /api/review/<folder>/audio/<filename>` (path-traversal
  guarded; .flac only). No-JS — search uses same-page
  `<form method="get">` per the sprint-3/4 contract. All 11
  page-render cases green.

**Bucket C — polish (2):**
- `aec8150` impl-wav-cleanup-fix — root cause documented inline
  in D-wav-cleanup-real-fix: the helper was never called from
  the state machine. Sprint-4's `cleanup_wavs` had unit-level
  coverage but zero production callers. Fixed by calling
  `cleanup_wavs(disc_dir / "audio", keep=_env_truthy(
  ARCHIVIST_KEEP_WAVS))` inside `_from_rip_sprint4` on the
  success path, BEFORE `_set_state(EJECT)` so cleanup
  guaranteed runs before the CAPTURE-phase working→inbox
  handoff. Cleanup exceptions logged and swallowed. Lesson
  captured: pure-helper unit tests aren't enough when the
  helper has zero callers; ship an integration test asserting
  the caller actually runs it.
- `012779c` impl-library-prefer-beets-cover — `DiscSummary`
  gains `library_cover_path`; adapter derives the expected
  `<library_root>/<artist>/<album>/cover.{jpg,jpeg,png,webp}`
  path from source.json detected_metadata. Grid thumbnails
  prefer the library cover via new
  `GET /library/<disc>/album-cover` (path-traversal guarded);
  detail page renders two distinct sections (ALBUM ART +
  PHYSICAL DISC) with sprint-3 review-recapture buttons
  preserved on the physical-disc section. Legacy CD_NNNN
  folders never look up a library cover (manifest has no
  detected_metadata). Also the detail rendering now handles
  BOTH source.json and manifest.json folders — sprint-5's
  new-shape folders no longer 500 on the detail page.

**Footprint:**
  - 3 new modules (`archivist/service/mb_client.py`,
    `archivist/service/beets_review.py`, plus changes to
    existing `library.py`).
  - 6 new routes (`/api/review/folders`,
    `/api/review/<folder>/{candidates,apply,use-as-is,audio/<filename>}`,
    `/library/<disc>/album-cover`).
  - 2 new HTML pages (/review, /review/<folder>) Mash Co.
    dressed per the SKILL.md voice contract.
  - 1 state-machine bug fix (cleanup_wavs call site).
  - 1 ratified Decision Log entry (D-wav-cleanup-real-fix)
    with the root cause + lesson recorded inline.

`create_app` grew two new optional kwargs: `review_root` and
`library_root` (both `Path | None = None`). Both are wired in
`__main__.py` from new env vars `MUSIC_REVIEW_DIR` and
`MUSIC_LIBRARY_DIR` — wiring lands separately (operator-
adjacent, not on the Wave 2 pipeline list).

### 2026-05-16 — pipeline — Wave 1 failing tests landed (10 tasks, 10 commits)

All 10 pipeline-owned Wave 1 tests shipped as atomic commits. Each
file is in the documented red state; impl phase will turn each green.

**Bucket A (1):**
- `e1801a3` test-source-json-identifiers — 3 cases appended to
  `tests/pipeline/test_source_json_builder.py`. New `mb_disc_id`
  kwarg on `build_source_json`; populates
  `identifiers.musicbrainz_disc_id`. Blank/whitespace strings map
  to None (defends against libdiscid emitting empty on marginal
  reads). Sprint-4's 6 cases continue to pass.

**Bucket B — review endpoints (1 file, 28 cases):**
- `ce7e7b4` `tests/service/test_review_endpoints.py` bundles five
  test tasks:
  - test-review-folder-list (6): empty roots; review folder
    surfaces with source='review'; inbox READY-no-PROCESSING with
    source='inbox-stuck'; READY+PROCESSING excluded; no-READY
    excluded; legacy folder with null source_json.
  - test-review-candidates-search (6): search_releases called with
    query + limit=5; empty list; response transformation;
    tracks_diff with delta_warning; unknown folder 404;
    WebServiceError → 502.
  - test-review-candidates-mbid (4): get_release_by_id with the
    correct `includes`; UUID validation; ResponseError → 404;
    search+mbid mutually exclusive → 400.
  - test-review-apply (7): happy path, exact argv lock,
    beets nonzero → 500, TimeoutExpired → 504, busy-state
    parametrized 409, unknown folder 404, missing/invalid mbid 400.
  - test-review-use-as-is (5): happy path, -A flag argv,
    failure, busy 409, unknown 404.

**Bucket B — review UI (1 file, 11 cases):**
- `b1dde3a` `tests/service/test_review_pages.py`:
  - test-review-ui-list (5): empty-state with --ink-3, two-card
    grid, Mash Co. invariants (data-theme=dark, eyebrow class,
    no emoji, no ALL-CAPS, --accent CTA), inbox-stuck
    distinction, nav-back-to-library link.
  - test-review-ui-detail (6): page-shell render with no
    candidates, candidate card rendered on ?search=, Mash Co.
    invariants, monospace filename column + row--warn class,
    unknown-folder 404, one <audio controls> per FLAC.

**Bucket C (2):**
- `79631f8` test-wav-cleanup-integration — 3 cases in new file
  `tests/state_machine/test_wav_cleanup_integration.py` that
  reproduce the STP failure mode end-to-end through the state
  machine (FakeRipper materializes BOTH track*.cdda.wav AND
  track*.cdda.flac). Default cycle MUST land only .flac in
  inbox; ARCHIVIST_KEEP_WAVS=1 preserves both; tick-by-tick
  invariant: inbox never holds a .wav at ANY tick (cleanup
  must run BEFORE the working→inbox handoff). Root cause
  documentation lands in `D-wav-cleanup-real-fix` during impl.
- `2483189` test-library-prefer-beets-cover — 6 cases in new
  file `tests/service/test_library_covers.py`. New
  `library_root` kwarg on create_app; `/library/<disc>/album-
  cover` endpoint; thumbnail prefers beets cover when
  available; legacy CD_NNNN never resolves a library cover;
  detail page renders both "album art" and "physical disc"
  sections.

**Footprint:** 10 new failing test files + edits to one existing
file. No production code touched. New deps consumed: the test
files import `musicbrainzngs` (already installed in the local
venv as part of Wave 0 prep). Mash Co. invariants asserted in the
review-UI assertions match the SKILL.md voice rules (sentence
case, eyebrow ≤2 words, dark-first, no decorative emoji, --accent
for primary CTAs, --ink-3 for secondary, --amber for warning rows).

### 2026-05-16 — drivers — Wave 2 impl-disc-id-capture landed

Single drivers task; closes drivers' sprint-5 scope.

- **impl-disc-id-capture** (this commit) — new module
  `archivist/drivers/disc_id.py` exposing
  `read_disc_id(device: Path) -> str | None`. Lazy-imports `discid`
  at function entry so the module loads even on dev boxes without
  libdiscid. Catches (in order): `ImportError` on the package itself
  → `None` + WARNING with a remediation hint naming
  `libdiscid0` / `cm4-setup.md`; `discid.DiscError` (no disc in drive)
  → `None` + INFO log; `OSError` (drive busy etc.) → `None` + WARNING
  with exception + device path; broad-except guard catches anything
  else the runtime might surface (RuntimeError, ValueError,
  MemoryError, …) → `None` + WARNING. Never raises — the rip path
  can't be poisoned by a flaky libdiscid. Returns
  `getattr(disc, "id", None)` on success.
- `pyproject.toml` — `discid>=1.2` added to
  `[project].dependencies` (alongside pydantic / requests / fastapi /
  uvicorn).
- `docs/operations/cm4-setup.md` § "Runtime apt dependencies":
  `libdiscid0` added to the single `sudo apt install -y …` block;
  new row in the per-binary breakdown table noting the C library
  paired with the `discid>=1.2` Python package, the
  `D-disc-id-libdiscid` rationale (burned CDs vs AcoustID), and the
  `None`-on-failure graceful-degradation posture.

Verified: `pytest tests/drivers/test_disc_id.py` → 5/5 PASS; full
drivers suite 77/77 PASS; `ruff check archivist/drivers/disc_id.py
tests/drivers/test_disc_id.py` clean. (Two pre-existing ruff errors
in pipeline-owned files — `service/beets_review.py:418` and
`state_machine/loop.py:607` — are not in this commit's scope.)

Unblocks: pipeline's `impl-source-json-identifiers` (wires
`read_disc_id` into `_from_stabilize`/`_from_rip`, stashes the result
on the `Cycle` dataclass, threads it through to
`build_source_json(mb_disc_id=...)`).

### 2026-05-15 — drivers — Wave 1 failing tests landed (1 task, 1 commit)

Light sprint for drivers — single test task closed.

- **test-disc-id-capture** (`3fdaa02`) — new file
  `tests/drivers/test_disc_id.py` with 5 failing tests for
  `archivist.drivers.disc_id.read_disc_id(device) -> str | None` per
  `D-disc-id-libdiscid`. Covers the happy path (libdiscid reads TOC →
  returns the disc-id string), `discid.DiscError` (empty drive) →
  `None` + INFO log, `OSError` (drive busy) → `None` + WARNING with
  exception + device path, `ImportError` on the `discid` package
  itself → `None` + WARNING with a remediation hint pointing at
  `cm4-setup.md` / `libdiscid`, and the never-raises invariant under
  RuntimeError / ValueError / MemoryError. A `_install_fake_discid`
  helper installs a synthetic `discid` module in `sys.modules` so the
  impl's lazy-import resolves to it. Target function is imported
  lazily inside `_read_disc_id()` so the test module collects cleanly
  (5/5 fail as `ModuleNotFoundError`).

Existing 72 sprint-1..4 driver tests still PASS. `ruff check
tests/drivers/test_disc_id.py` clean.

Wave 2 queue: `impl-disc-id-capture` (1 task — lazy-import
discid, add `discid>=1.2` to `pyproject.toml`, document
`libdiscid0` in `cm4-setup.md` § "Runtime apt dependencies").

### 2026-05-15 — planner — sprint-5 plan drafted

Three buckets per the sprint scope decision:
- **Bucket A (disc-id capture):** 2 Wave 1 tests + 2 Wave 2
  impls + 1 Wave 0 operator setup. Sprint-4 stretch slip
  finally lands; the field is already reserved in the
  schema.
- **Bucket B (in-UI beets review):** 7 Wave 1 tests + 3 Wave
  2 impls (mb_client, routes, pages) + 1 Wave 0 operator
  setup. Per `docs/design/2026-05-16-in-ui-beets-review.md`,
  Option B selected (full candidate selection web UI) over
  Option A (too coarse) and Option C (xterm.js too much
  infra).
- **Bucket C (polish + bugs):** 2 Wave 1 tests + 2 Wave 2
  impls + 2 Wave 0 operator tasks (systemd unit; Mash Co.
  README cross-repo edit). 1 stretch task.

**Wave totals:**
- Wave 0 (operator-driven): 4 tasks
  (`install-musicbrainzngs-in-archivist`,
  `install-libdiscid-on-cm4`,
  `install-archivist-systemd-unit`,
  `update-mash-co-readme-products-in-scope`)
- Wave 1 failing tests: 2 (Bucket A) + 7 (Bucket B) + 2 (Bucket C)
  = **11 tests**
- Wave 2 impls: 2 (Bucket A) + 3 (Bucket B) + 2 (Bucket C)
  = **7 impls**
- Stretch: 1
- **Total: 23 tasks**

**Decision Log entries proposed: 7**
- `D-disc-id-libdiscid` (Bucket A)
- `D-beets-review-ui-mode` (Bucket B)
- `D-mb-query-direct-not-beets` (Bucket B)
- `D-review-folder-discovery` (Bucket B)
- `D-systemd-resolve-land-it` (Bucket C — supersedes
  sprint-2's `D-systemd-defer`)
- `D-wav-cleanup-real-fix` (Bucket C — body filled at impl
  time once the root cause is identified)
- `D-library-cover-preference` (Bucket C)

**Judgment calls (planner):**
- **`mb_client` throttling scope:** intentionally minimal —
  monotonic-clock gate (≥ 1.0s between calls), threading
  lock so concurrent FastAPI requests serialize. NO
  retry-with-backoff, NO response caching. Rationale: v1
  workload is one operator clicking through review folders;
  the 1-req/sec gate is fine. Caching adds complexity
  (invalidation, on-disk vs in-memory, cross-restart
  persistence) for no real benefit at this workload. If a
  real workload ever demands caching, sprint-6+ adds it.
- **`impl-review-pages` is ONE task, not split.** The
  list page and the detail page share Mash Co. styling
  helpers, the empty-state vs populated-state dispatch, and
  the same inline-HTML render style. Splitting just adds
  task overhead. The test contracts are split
  (`test-review-ui-list` vs `test-review-ui-detail`) so
  the work stays verifiable page-by-page; the impl bundles
  them.
- **Systemd unit task gates nothing.** It's Wave 0 by
  category (operator-owned setup) but does NOT block Wave
  1 — sprint-5's code-side work runs the same in tmux or
  under systemd. The unit install is a sprint-5 close-out
  item; if the operator slips it to sprint-6, the
  decision-log entry `D-systemd-resolve-land-it` still
  ratifies the direction (land it, not defer further).
- **`install-libdiscid-on-cm4` doesn't gate Wave 1 either.**
  The drivers tests stub the `discid` module so they pass
  on any machine; the apt install is needed only at
  runtime on the CM4 to actually populate the field. If
  the operator slips the install, `read_disc_id` returns
  `None` (per the lazy-import + `ImportError` swallow
  contract) — graceful degradation, not a runtime
  failure.
- **`install-musicbrainzngs-in-archivist` DOES gate Wave 1**
  for Bucket B. The route tests import the lib via the
  `mb_client` singleton (mocked in the tests, but the
  module-level import runs). If the lib isn't available
  in the venv, the route tests fail at collection time.
  Operator runs the pip install on the CM4 venv before
  Bucket B tests start.

**Open questions the planner couldn't resolve from context:**
- Does the existing `/library/<disc>/audio/<file>` endpoint
  scope to `MUSIC_INBOX_DIR` only, or does it work against
  any folder under cd-archivist's known roots? If it's
  inbox-only, the review-detail page needs a sibling
  `/api/review/<folder>/audio/<file>` endpoint to stream
  audio from `MUSIC_REVIEW_DIR` folders. The
  `impl-review-pages` task notes this as an author's-call
  issue; the impl agent verifies the existing endpoint's
  scope and either reuses it or adds the sibling.
- How does `process-ready-auto` derive the library path
  beets writes to? The `apply` route handler parses beets'
  stdout to surface the path back to the operator; the
  exact regex depends on beets' quiet-mode output format.
  The impl agent verifies against a real `docker exec`
  invocation during Wave 2.
- The `D-wav-cleanup-real-fix` decision-log body is
  intentionally left incomplete at planning time — the
  impl agent fills in the actual root cause during Wave
  2. This is unusual but appropriate: the test reproduces
  the symptom; the entry documents the cause once known.
