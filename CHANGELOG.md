# Changelog

All notable changes to **cd-archivist** are documented here. Format
follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/);
this project adheres to [Semantic Versioning](https://semver.org/).
See [docs/WORKFLOW.md](docs/WORKFLOW.md) §6 for the versioning and
release-flow conventions.

Each historical entry below is back-filled from the corresponding
`docs/coordination/sprint-N.md` Activity Log; for full per-task
provenance, walk that source. Dates reflect each sprint's final
`updated:` field.

## [Unreleased]

### Added

### Changed

### Deprecated

### Removed

### Fixed

### Security

---

## [sprint-11] — 2026-05-20

The "edit URLs and creds from the browser" sprint. Two-lane parallel
execution stood up a JSON config store, refactored the four sprint-10
service-clients to read through it, and shipped a `/settings` page so
operators can edit Spooty / Navidrome URLs + creds + music dirs
without ssh.

### Added
- `archivist/service/config.py` — config store with FILE > ENV >
  DEFAULT precedence (D-config-precedence). Frozen `Config`
  dataclass (10 knobs), `get_config()` (cached), `reload_config()`
  (clears the cache), `save_config(updates)` (sparse merge, atomic
  write via `os.open(O_CREAT, 0o600)` + `os.replace`, auto-reload,
  rejects unknown keys with `UnknownConfigKey` before any disk
  write). Exposes `SECRET_FIELDS` so API layers can mask
  `navidrome_pass` / `spooty_api_token`. File path is
  `$ARCHIVIST_CONFIG_PATH` or `~/.config/cd-archivist/config.json`.
- `GET /api/config` — returns the resolved config with secrets
  masked to `●●●●●●●●` (or `null` when unset). Non-secret fields
  returned verbatim.
- `POST /api/config` — sparse `{key: value, ...}` update. Per-field
  validation: `*_url` must be `http(s)://`, `*_dir` must be
  absolute, non-secret strings must be non-empty. Empty-string in a
  secret field is silently dropped (don't overwrite stored
  password). `null` clears a key. Unknown keys → 400.
- `GET /settings` — single-column form bound to `/api/config`. Ten
  inputs across three sections (Spooty / Navidrome / Music paths).
  Password fields never carry a `value=` attribute (no leak via
  View Source); placeholder `●●●●●●●●` signals a stored value.
  Inline JS posts JSON, shows a moss "Saved at HH:MM" banner on 200
  or an ember error banner on 4xx.
- Brand-lockup breadcrumb switcher gains a `settings` row with
  `<N> knobs · saved <T> ago` telemetry, sourced from
  `get_config_summary()` (read-only helper in `config.py`). Rendered
  on every chassis surface (rip / library / settings).
- New env var: `ARCHIVIST_CONFIG_PATH` (override for the config
  file path).

### Changed
- The four sprint-10 service-clients (`disk_client`, `inbox_client`,
  `spooty_client`, `subsonic_client`) now read URLs / creds / dirs
  via `config.get_config()` at call time instead of
  `os.environ.get(...)`. Backward compat preserved: env vars still
  flow through as the precedence-tier-2 fallback. The Settings page
  becomes authoritative for any key the operator saves; untouched
  keys continue to resolve from systemd `Environment=` lines.
- Client test fixtures switch from `monkeypatch.setenv(...)` to a
  per-test isolated config-store path with `save_config(...)`.

### Security
- `/settings` and `/api/config` ship **unauthenticated** for v1
  (D-settings-unauth-v1). cda.mattmariani.com is publicly reachable
  via the Cloudflare tunnel, so an unauthenticated `POST /api/config`
  is a real risk. Operator-facing mitigations (LAN-restrict or
  stand up Cloudflare Access) are documented in
  `docs/operations/cm4-setup.md` §Library Manager config. A follow-up
  sprint should wire Cloudflare Access service tokens or a
  per-request token check.

### Notes
- Test suite: 857 (848 baseline + 9 net new — lane-2's
  config-runtime-wiring kept existing client tests at the same count
  while moving them onto the new fixture pattern; lane-1 added 50
  new tests across config_store + settings_api + settings_page;
  lane-2 added the switcher telemetry tests).
- Live smoke against `cda.mattmariani.com` (CM4) on 2026-05-20:
  `/settings` returns 200, `GET /api/config` shows the merged
  file+env state, `POST /api/config` writes
  `~/.config/cd-archivist/config.json` (verified mode 0600), and
  `GET /api/library/browse/recent` returns live Navidrome data
  confirming the subsonic_client is reading creds through the
  config_store end-to-end.

---

## [sprint-10] — 2026-05-20

The "Library Manager v1 panels" sprint. Two-lane parallel execution
replaced the four sprint-9 "in design" placeholders with live data
and real operator actions. The Library Manager moves from honest
shell to working control panel for the whole CM4 music stack.

### Added
- Service-clients package (`archivist/service/clients/`) with a
  README defining the contract: one module per external surface,
  typed dataclass returns, typed `*Unavailable` exceptions on
  transport failure, env-var-driven config read at call time, 5s
  HTTP timeouts. Four clients ship under it: `disk_client`,
  `inbox_client`, `spooty_client`, `subsonic_client`.
- `library_panels.py` dispatcher — `render_panel(panel_id)` resolves
  the per-panel module via a static map and falls back to the
  sprint-9 placeholder when the per-panel module is absent. Keeps
  lane-1 and lane-2 off each other's files for the rest of the
  sprint.
- Per-panel polling dispatcher in `chassis_js.py` — reads
  `<meta name="library-poll-ms">` + `<meta name="library-poll-endpoint">`,
  fires fetch on interval, pauses on `visibilitychange`. Cadences
  per panel: Disk 30s, Inbox 5s, Downloads 1s active / 5s idle,
  Library none.
- **Disk panel** end-to-end (`/library/disk` + `/api/library/disk`).
  `get_disk_usage()` returns a `DiskUsageSnapshot` of `MountUsage`
  rows for `/`, `/mnt/seagate`, `/mnt/archive` with per-surface
  byte breakdown (inbox / library / archive / spooty, attributed by
  longest-prefix mount, disjoint walks). Panel renders three
  usage-bar rows (threshold classes `is-pulp` / `is-amber` /
  `is-ember` from build-prompt §3) + per-surface drilldown table.
  Missing mounts degrade to "not mounted".
- **Inbox panel** end-to-end (`/library/inbox` + `/api/library/inbox`
  + `POST /api/library/inbox/import-now`). Walks `$MUSIC_INBOX_DIR`
  + `$MUSIC_INBOX_DIR/spooty/`, returns frozen `InboxFolder` rows
  sorted newest-first. `import-now` POST spawns the matching
  importer via `subprocess.Popen` (fire-and-forget; argv form;
  mirrors `post_rip_hook.py`'s pattern).
- **Downloads panel** end-to-end (`/library/downloads` + the
  `/api/library/downloads/*` surface). Thin proxy over the spooty
  REST API at `$SPOOTY_API_URL` — read methods (list_playlists,
  list_tracks) + mutating methods (submit_playlist, retry_track,
  delete_track, retry_playlist). Panel renders per-playlist rows
  with per-track pip strips (green=ok, pulp=active, ember=error,
  empty=pending) + submit form + retry/delete affordances.
- **Library/browse panel** end-to-end (`/library/library` +
  `/api/library/browse?q=` + `/api/library/browse/recent`). Read-only
  Subsonic client against Navidrome (`search3.view`,
  `getAlbumList2.view?type=newest`) with fresh-salt-per-call auth.
  Panel renders a debounced search input + 10 most-recent imports
  + a prominent "Open Navidrome ↗" CTA that works even when the
  API is down.
- New env vars (all read at call time; see
  `docs/operations/cm4-setup.md` §Library Manager env knobs):
  `MUSIC_LIBRARY_DIR`, `MUSIC_ARCHIVE_DIR`, `MUSIC_SPOOTY_DIR`,
  `SPOOTY_API_URL`, `SPOOTY_API_TOKEN`, `NAVIDROME_URL`,
  `NAVIDROME_USER`, `NAVIDROME_PASS`.

### Changed
- `library_panels.py` refactored from monolithic placeholder into a
  thin dispatcher. The placeholder remains as the fallback for
  unimplemented panels (v2 ghosts).
- Sprint-9 placeholder tests in `test_library_panels.py` re-pointed
  from `disk` / `inbox` (which now have real panel modules) to the
  v2 `review` id, which still exercises the placeholder via the
  dispatcher.

### Notes
- Test suite: 798 (677 baseline + 22 disk + 17 library/browse +
  inbox + downloads + chassis-poll tests).
- Live smoke against `cda.mattmariani.com` (CM4) on 2026-05-20:
  all four panel routes return 200; disk + inbox return live data;
  downloads + library degrade cleanly when their backends are
  unconfigured/unreachable (spooty `/playlists` 404 upstream;
  Navidrome creds not yet set on the operator's systemd unit).
  Operator action to fully light up the Library panel: append
  `NAVIDROME_URL` / `NAVIDROME_USER` / `NAVIDROME_PASS` to the
  systemd user unit.

---

## [sprint-7] — 2026-05-16

The "Mash Co. design system" sprint. Three-lane parallel execution
re-skinned the operator UI against the vendored design system,
refactored card anatomy, and added the beets-candidates surface
that closes the manual-review loop end-to-end.

### Added
- FastAPI `/static` mount serving the vendored Mash Co.
  `tokens.css` + `cda.css`, the full favicon family, the apple-touch
  icon, the PWA `manifest.webmanifest`, and Google Fonts wiring for
  Bricolage Grotesque + Inter Tight + JetBrains Mono.
- `cd/a` brand-mark recipe (chunky-extruded, three size variants:
  header / splash / marketing).
- `GET /api/disc/<folder>/candidates` — MusicBrainz-backed ranked
  candidate list (disc-id → fingerprint → operator-hints priority
  per `D-candidates-source-priority`; 5-minute in-memory cache keyed
  by folder per `D-candidates-cache-ttl`).
- `GET /api/rig/stats` — storage + uptime for the header rig-stats
  group (mono-shorthand human strings).
- Beets-candidates section in the expanded card body (`.score-chip`
  + `.candidate-meta` + `.apply-btn` rows; top row `.candidate--top`
  with amber tint).
- `archivist/service/json_highlight.py::highlight(obj)` — hand-rolled
  JSON syntax highlighter (`.k` / `.s` / `.n` / `.b` spans) for the
  right-drawer card-detail `source.json` view.
- CSS disc-photo placeholder (`.thumb--placeholder` with
  conic-gradient glow; larger `--lg` variant for the drive-mode
  drawer body).
- 8px column "headlamp" stage dots; header live-status chip with
  pulsing-moss dot when active; 5-cell bordered rig-stats group;
  drawer mode toggles (drive / card).
- Card anatomy refactor: 56×56 thumbnail + slug eyebrow + title +
  artist; mono status-line with the project's operator-voice
  templates; chip row with `.chip--asserted` / `.chip--confirmed`
  contracts; per-column left-border accent (pulp / sky / amber /
  ember / moss); 1px white-inset outline on identified track cells.
- Destructive-action second-click confirmation gate with build-prompt
  hint text; card-entering / card-leaving / flash-moss CSS animations
  for poll-to-poll diffs.

### Changed
- `POST /api/disc/<folder>/accept-top-candidate` accepts an optional
  `{mbid: str}` JSON body in addition to the legacy no-body call
  (additive; backward-compat preserved).
- Kanban CSS migrated off the inline `<style>` block in
  `kanban_page.py` and onto the imported `tokens.css` + `cda.css`.
  Only the CSS-custom-property-as-data inline pattern remains
  (`style="--progress: …%"`, `style="--track-count: …"`).
- Column label "In Library" → "In library" (targeted voice pass;
  sentence case in source — eyebrows are CSS-uppercased).

### Fixed
- Targeted voice-pass polish on status lines, button labels, and
  error templates per the build-prompt operator-voice rules; no
  emoji, no smart quotes, project-vocabulary verbatim.

---

## [sprint-6.5] — 2026-05-16

Kanban usability pass. Filled the gap between sprint-6's basic
kanban surface and sprint-7's design-system overhaul: expand
mechanic, drawers, adaptive polling, mobile fallback.

### Added
- Click-to-expand / spacebar-toggle card mechanic with one-at-a-time
  guard and three labeled body sections (Hints / Manual steps /
  Damaged-disc actions).
- Right slide-out drawer with two modes — drive-status by default,
  card-detail when a card is focused.
- Bottom drawer (daemon log tail) with localStorage-persisted
  collapsed/expanded state.
- High-leverage collapsed-card buttons (process-partial, redo,
  accept-top-match) gated by per-card state.
- Column count badges + sticky column headers + independent column
  scrolling.
- Mobile bucket-tabs (single-column with segmented control) at the
  `D-mobile-breakpoint-v1` width.
- Adaptive polling cadence (1s active rip / 5s idle) driven by
  `active_rip` flag on the `/api/kanban` payload.
- `GET /api/logs/tail?limit=N` and `GET /api/drive/status` endpoints.
- `DriveStatus` dataclass on `LoopState` populated by the drivers
  ripper + state-machine threads (thread-safe via internal RLock).
- Card visual-evolution rules: track-cell identification, asserted-
  vs-confirmed chip styling, damaged-card red-shadow accent.

### Fixed
- `build_kanban_state` phantom-`audio` bug: stopped routing
  bucket-empty folders that had a stray `audio/` subdir into a
  fake card.

---

## [sprint-6] — 2026-05-16

Replaced the single-line status surface with a candidate-disc
kanban and landed first-class damaged-disc handling. Removed the
`cdplay.service` runtime dependency via `D-cdplay-decouple-not-install`.

### Added
- Kanban API + page render: four-stage pipeline view (Capture /
  Beets ID / Review / In library) driven by a disk-walking
  `build_kanban_state` function over `/srv/music/{inbox,review,
  library,archive,failed}/`.
- Operator-hints API + per-card UI (`various_artists`, `burned_cd`,
  artist, album, per-track hints) persisted to `source.json`.
- Damaged-disc actions: `process-partial`, `redo`, `rerip-tracks`
  POST endpoints with explicit-confirm semantics.
- Engine-side fail-fast: cdparanoia halts on N unrecoverable sectors
  per track (configurable), preserving partial output.

### Changed
- State machine no longer stops/starts `cdplay.service` around drive
  claims (decoupled, not installed — per `D-cdplay-decouple-not-
  install`).

---

## [sprint-5] — 2026-05-15

Closed the review loop in the UI and started capturing
`musicbrainz_disc_id` at rip time to cut the manual-review pile.

### Added
- Review surface in the FastAPI app: per-folder explainer copy
  surfaced as a "why in review" panel; manual-steps shell snippet
  copy-paste flow.
- `/api/review/*` endpoints (folder list, per-folder detail,
  candidate search by metadata and by MBID).
- `source.json.identifiers.musicbrainz_disc_id` populated at rip
  time via `libdiscid` (`discid` Python package).
- `mb_client.MBClient` singleton wrapping `musicbrainzngs` with a
  rate-limit gate + User-Agent header.
- Five real-rig polish items from the sprint-4 smoke session.

---

## [sprint-4] — 2026-05-15

Music-pipeline contract conformance. Folder shape, track naming,
and per-disc sidecar JSON all moved to the canonical shape
documented in the music-stack handoff.

### Added
- New disc folder shape: `YYYY-MM-DD_HHMM_disc-NNNNNN` (legacy
  `CD_NNNN/` remains readable).
- `source.json` per-disc sidecar (replaces `manifest.json` for new
  rips; legacy folders still read via the old shape).
- Atomic `READY` marker on rip completion + a `process-ready` hook
  (shell-out invoked after the rename; backed by a systemd backup
  timer per `D-process-ready-trigger`).
- Manual-mode gating on the state-machine loop (`mode: "manual"`
  waits on `/api/control/*` triggers).

### Changed
- Music-root storage layout standardized to `/srv/music/{inbox,
  review,library,archive,failed}/` per the migration plan.

---

## [sprint-3] — 2026-05-14

Polish from the sprint-2 hardware bring-up and a redesigned
eject-time capture flow. Read-only `/library` browser landed.

### Added
- Eject-time camera capture: photo fires after the rip completes
  (drive-tray-open phase), not during cdparanoia (which fought the
  drive's spin).
- `/library` read-only browser surfacing per-disc metadata + the
  captured photo.
- `last_tick_at` heartbeat field on `LoopState` (advances every
  tick; `state_entered_at` now only advances on transitions).
- Live `rip_progress` label parsed from cdparanoia stderr.
- Drive-status `drive-missing` path: state machine treats
  `/dev/sr0` absent as "wait, retry" rather than crash.

### Fixed
- Seven concrete fixes from sprint-2 smoke: systemctl scope flag,
  log-fallback path, rip-stderr streaming, rip-error recovery, plus
  the live-progress display in the status UI.

---

## [sprint-2] — 2026-05-14

End-to-end pipeline on the real CM4. State-machine glue, FastAPI
status surface, webcam recovery, and the Mash Co. design system's
second consumer (cd-archivist).

### Added
- State machine: `IDLE → STABILIZE → CAPTURE → RIP → EJECT → IDLE`
  loop with timer-bounded transitions and clean shutdown.
- FastAPI status surface on port 8228 (`/`, `/api/status`,
  `/api/log`) with the Mash Co. tokens dressing the page.
- USB sysfs unbind/rebind webcam recovery on `VIDIOC_STREAMON`
  errors, with auto-discovery of the camera USB bus path from
  `/sys/class/video4linux/*` (env-var override remains).
- `cdplay.service` cooperative pause/resume around drive claims
  (later removed in sprint-6).
- `tests/conftest.py` shared `fake_completed_process` helper and
  the `tests/__init__.py` packaging fix.
- Vendored Mash Co. design tokens into `archivist/service/static/`.

---

## [sprint-1] — 2026-05-13

Hardware-facing driver primitives + manifest schema + disc archival
skeleton. TDD discipline on every primitive; no real `/dev/sr0`,
Tasmota, or webcam touched yet — fakes only.

### Added
- `archivist/drivers/` driver primitives: `read_drive_status` (ioctl-
  backed), `LEDPanel` (Tasmota HTTP client), `capture_frame` (ffmpeg
  burst), `CDAudioRipper` (`cdparanoia` → `flac`).
- `archivist/models/Manifest` pydantic model (`schema_version="0.2"`)
  with atomic `read_manifest` / `write_manifest`.
- `archivist/pipeline/` disc-folder helpers: `next_disc_id`
  (lockfile-atomic), `prepare_disc_folder` (idempotent),
  `make_pairing` / `attach_pairing`.
- `tests/conftest.py` with `tmp_disc_root` + `fake_subprocess`
  fixtures.
- `pyproject.toml` (Python 3.11+ initial pin; later relaxed),
  `ruff.toml`, pytest config.

---

[Unreleased]: https://github.com/loydmilligan/cd-archivist/compare/master...HEAD
