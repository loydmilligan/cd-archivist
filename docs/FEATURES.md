# FEATURES.md

> Current-state feature inventory as of sprint-8 (2026-05-17).
> One entry per feature, grouped by subsystem.
> States: **shipped** (in production, tests green) / **partial** (code exists, gaps noted) / **planned** (backlog).
> File pointers are module-level; see `docs/ARCHITECTURE.md` for detail.

---

## Drivers

| Feature | State | Sprint | File |
| ------- | ----- | ------ | ---- |
| CD drive status polling (ioctl CDROM_DRIVE_STATUS) | shipped | 1 | `archivist/drivers/drive.py` |
| USB webcam capture via ffmpeg (burst mode) | shipped | 1 | `archivist/drivers/camera.py` |
| Tasmota LED panel control (power on/off/status) | shipped | 1 | `archivist/drivers/led.py` |
| cdparanoia rip + flac encoding (RipResult) | shipped | 1 | `archivist/drivers/ripper.py` |
| libdiscid TOC hash → MusicBrainz disc ID | shipped | 5 | `archivist/drivers/disc_id.py` |
| cdparanoia stderr progress parser | shipped | 3 | `archivist/drivers/rip_log.py`, `archivist/pipeline/rip_progress.py` |
| USB camera device auto-discovery at startup | shipped | 2 | `archivist/drivers/usb_discovery.py` |
| systemd unit stop/start adapter (future use) | partial | 2 | `archivist/drivers/systemctl.py` |
| Drive hardware recovery (USB rebind on VIDIOC_STREAMON fail) | planned | — | `archivist/drivers/drive.py` |

---

## Pipeline

| Feature | State | Sprint | File |
| ------- | ----- | ------ | ---- |
| LED dance + burst capture (ambient + lit frames) | shipped | 1 | `archivist/pipeline/capture.py` |
| Canonical photo selection (prefer lit_002) | shipped | 4 | `archivist/pipeline/capture.py` |
| cdparanoia rip orchestration → RipRecord | shipped | 1 | `archivist/pipeline/rip.py` |
| WAV cleanup after FLAC encoding | shipped | 4 | `archivist/pipeline/rip.py` |
| Track rename to canonical (NN Track.flac) | shipped | 4 | `archivist/pipeline/rip.py` |
| Partial-rip preservation (failed_tracks list) | shipped | 6 | `archivist/pipeline/rip.py` |
| Per-rip-attempt provenance records | shipped | 6 | `archivist/pipeline/source_json.py` |
| Disc ID reservation (lockfile-guarded, collision-safe) | shipped | 4 | `archivist/pipeline/disc_id.py` |
| Disc folder naming (YYYY-MM-DD_HHMM_disc-NNNNNN) | shipped | 4 | `archivist/pipeline/folder_name.py` |
| Disc folder scaffold (audio/ captures/ logs/ review/) | shipped | 1 | `archivist/pipeline/folder.py` |
| Capture-session pairing to rip session | shipped | 1 | `archivist/pipeline/pairing.py` |
| source.json assembly from disc context | shipped | 4 | `archivist/pipeline/source_json.py` |
| Post-rip beets hook (docker exec beet import) | shipped | 5 | `archivist/pipeline/post_rip_hook.py` |
| Post-import recapture (retake disc photo mid-review) | shipped | 3 | `archivist/pipeline/review_capture.py` |
| Capture fires post-eject (disc face visible) | shipped | 3 | `archivist/pipeline/capture.py` |

---

## Service / UI

| Feature | State | Sprint | File |
| ------- | ----- | ------ | ---- |
| FastAPI daemon (uvicorn on port 8228) | shipped | 2 | `archivist/service/app.py` |
| systemd user service (`cd-archivist.service`) | shipped | 5 | — (operator-installed) |
| Cloudflare tunnel (`cda.mattmariani.com`) | shipped | 5 | — (operator-configured) |
| Static file mount (`/static` for CSS, fonts, icons) | shipped | 7 | `archivist/service/app.py` |
| 4-column kanban page (Capture / Beets ID / Review / In Library) | shipped | 6 | `archivist/service/kanban_page.py` |
| `GET /api/kanban` — board state JSON | shipped | 6 | `archivist/service/app.py`, `disc_card_builder.py` |
| Adaptive kanban polling (1s ripping / 5s idle) | shipped | 6.5 | `archivist/service/kanban_page.py` |
| Per-track segment bar (state-colored per disc) | shipped | 6 | `archivist/service/disc_card_builder.py` |
| Card inline-expand (one at a time; spacebar toggles) | shipped | 6 | `archivist/service/kanban_page.py` |
| Right-side drawer (drive status / rip-log tail / source.json) | shipped | 6.5 | `archivist/service/kanban_page.py` |
| Bottom drawer (daemon tail log) | shipped | 6.5 | `archivist/service/kanban_page.py` |
| Header: rig-stats group (ripped / in review / partial / storage / uptime) | shipped | 7 | `archivist/service/app.py` |
| Header: live-status chip (pulsing "ripping · DISC-XXXX" vs "idle") | shipped | 7 | `archivist/service/kanban_page.py` |
| `GET /api/rig/stats` — stats JSON | shipped | 7 | `archivist/service/app.py` |
| `GET /api/drive/status` — DriveStatus JSON | shipped | 6.5 | `archivist/service/app.py` |
| `GET /api/logs/tail` — structured log tail | shipped | 6.5 | `archivist/service/app.py` |
| `GET /api/disc/{folder}/candidates` — MB candidates | shipped | 7 | `archivist/service/app.py`, `mb_client.py` |
| `POST /api/disc/{folder}/accept-top-candidate` | shipped | 7 | `archivist/service/app.py` |
| `GET /api/disc/{folder}/log/tail` — per-disc log | shipped | 7 | `archivist/service/app.py` |
| Mash Co. design system (tokens.css + cda.css + brand fonts) | shipped | 7 | `archivist/service/static/` |
| cd/a brand mark (chunky-extruded, 3 size variants) | shipped | 7 | `archivist/service/static/img/brand/` |
| source.json syntax highlight in drawer | shipped | 7 | `archivist/service/json_highlight.py` |
| Operator hints form (VA / Burned / Artist / Album / per-track) | shipped | 6 | `archivist/service/operator_hints.py` |
| Review explainer ("why it's in review" human-readable string) | shipped | 6 | `archivist/service/review_explainer.py` |
| Destructive-action confirmation gate (second-click confirms) | shipped | 7 | `archivist/service/damaged_disc.py` |
| Card-enter / card-leave CSS transitions (200ms) | shipped | 7 | `archivist/service/static/css/cda.css` |
| Damaged-disc actions (process-partial / redo / rerip-tracks) | shipped | 6 | `archivist/service/damaged_disc.py` |
| Library view (`/library`, `/library/{disc_id}`) | shipped | 3 | `archivist/service/library.py` |
| Library post-import recapture (`POST /api/library/{disc_id}/recapture`) | shipped | 3 | `archivist/service/app.py` |
| Review page v1 (`/review`, `/review/{folder}`) | shipped | 3 | `archivist/service/review_page_v1.py` |
| Mobile single-column layout (bucket tabs) | partial | 7 | `archivist/service/static/css/cda.css` |
| PWA manifest + favicon family + apple-touch icon | shipped | 7 | `archivist/service/static/` |
| Operator hints wired into beets search | planned | — | (sprint-8 open issue) |
| Per-rip / per-card log-tail filter UI | planned | — | `/api/logs/tail` has stub params |
| Sort / filter controls per kanban column | planned | — | — |
| Alert / notification strip in header | planned | — | — |
| Force-re-run beets ID action | planned | — | — |
| Edit-by-hand library metadata in UI | planned | — | — |
| Track identification data source (real data) | partial | 7 | `archivist/service/track_identification.py` |

---

## Operations

| Feature | State | Sprint | File |
| ------- | ----- | ------ | ---- |
| `source.json` atomic read/write (`.tmp` + `os.replace`) | shipped | 4 | `archivist/models/source.py` |
| `manifest.json` legacy reader (CD_NNNN backwards compat) | shipped | 1 | `archivist/models/manifest.py` |
| Disc bucket directories (`inbox/ review/ library/ archive/ failed/`) | shipped | 5 | `archivist/__main__.py` env vars |
| ARCHIVIST_* env-var config (device, discs_root, log_path, port, led_base) | shipped | 2 | `archivist/__main__.py` |
| SIGTERM / SIGINT graceful shutdown | shipped | 2 | `archivist/__main__.py` |
| Disc-wall disk-usage in rig stats | shipped | 7 | `archivist/service/app.py` |
| Process uptime in rig stats | shipped | 7 | `archivist/service/app.py` |
| CM4 deploy runbook | shipped | 8 | `docs/WORKFLOW.md` §4 |
| Wave-3 visual smoke (end-to-end on real rig) | partial | 7 | `docs/coordination/sprint-7.md` — deferred; drive RMA pending |
| Multi-drive support | planned | — | — |
| Containerized cd-archivist daemon | planned | — | — |
| AcoustID fingerprint submission | planned | — | — |
| Live cam preview in UI | planned | — | — |
| `cache build_kanban_state` disk-walk with fs-event invalidation | planned | — | `archivist/service/disc_card_builder.py` |
