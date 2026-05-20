# Library Manager — Feature Proposal

**Status:** Discussion draft. Originated from a side conversation with another agent that has full context on the CM4 music pipeline but no cda context. This doc is the handoff brief for the cda-side agent who will turn it into a real proposal (ROADMAP entry + design doc + ADR if needed).

---

## TL;DR

cda already owns the rip workflow (Capture → Beets ID → Review → In Library). The CM4 now also runs a second ingest source — **spooty** (Spotify-playlist → YouTube downloader) — plus beets and Navidrome. There is no operator surface for the post-rip side of any of this: the inbox queue, the review bucket, spooty's download state, disk usage on the new external drive, etc. Today it's all CLI + log files.

Proposal: add a **Library** screen to cda that surfaces the operational state of the whole music pipeline, not just discs. Same FastAPI, same kanban-style UI, same Cloudflare tunnel, same auth. No new service.

---

## Why this is needed

The CM4 has accumulated a multi-source music ingest pipeline that cda's rip flow is just one piece of:

```
┌────────────────────┐
│ CD rip (cda)       │──┐
└────────────────────┘  │
                        ├──→ /srv/music/inbox/<album>      ──┐
┌────────────────────┐  │                                    │
│ spooty (Spotify    │──┘                                    │
│   playlist DL)     │     /srv/music/inbox/spooty/<album>  ─┤
└────────────────────┘                                       │
                                                             ▼
                                                     beets (cd_beets)
                                                  autotag + copy + write
                                                             │
                                                             ▼
                                              /srv/music/library/...
                                              /srv/music/library/spooty/...
                                                             │
                                                             ▼
                                                 Navidrome + Jellyfin
```

What's missing is the **operator's view across all of that**. Today:

- **No queue visibility.** Inbox folders sit on disk; you only know what's there by `ls`. Same for `review/` (uncertain beets matches) and `archive/` (successful rips moved aside).
- **No way to act.** "Import this folder now," "retry this album with different hints," "move from review back to inbox," "delete this failed download" — all require sshing into the CM4 and running docker/beet commands.
- **No spooty surface.** Spooty has its own minimal UI for submitting playlists, but no way to see "this track failed to download," "retry," "kill this whole playlist," etc., without poking at its REST API directly.
- **No disk awareness.** A 1 TB Seagate was just added at `/mnt/seagate`, bind-mounted under `/srv/music/library/spooty/` and `/srv/music/inbox/spooty/`, so spooty content lives on spinning disk while CD rips stay on the SD card. The operator should see disk usage per surface, not have to remember the layout.
- **No unified log view.** Beets writes to `/srv/music/logs/beets-import.log`; the new spooty cron writes to `/srv/music/logs/spooty-cron.log`; navidrome's scan log is inside its container. Spread across three places.

cda is already the natural home for this because:

1. It owns a polished FastAPI + kanban UI the operator already uses.
2. It already touches the same beets DB and `/srv/music/` tree.
3. It already publishes through Cloudflare at `cda.mattmariani.com`.
4. The 4-column kanban pattern maps directly onto the inbox→review→library flow.
5. Building a separate "music dashboard" would duplicate auth, deployment, tunnel, and UI conventions.

The alternative considered — Homepage / Glances / Beets web UI / Navidrome plugins — were all rejected: those are listener-facing or generic-dashboard tools, not workflow surfaces.

---

## What the screen would do

Sketched as panels. Each maps to an existing API or filesystem read; no new persistence layer required at first.

| Panel | Source of truth | Actions |
|---|---|---|
| **Spooty queue** | Spooty REST: `GET /api/playlist`, `GET /api/track/playlist/:id` | Submit playlist URL (`POST /api/playlist`), retry track (`GET /api/track/retry/:id`), delete (`DELETE /api/track/:id`), retry whole playlist (`GET /api/playlist/retry/:id`) |
| **Inbox queue** | Filesystem walk of `/srv/music/inbox/` (CD rips) and `/srv/music/inbox/spooty/` | "Import now" (invokes appropriate beets path), mark READY (for cda's existing auto-import script), show file count + total size + last-modified |
| **Review queue** | Filesystem walk of `/srv/music/review/` | Retry interactive import, send back to inbox, delete, view beets-import.log tail for the album |
| **Recent imports** | Tail of `/srv/music/logs/beets-import.log` + beets sqlite db (`/srv/cd-music-stack/config/beets/library.db`) | Click an import to see what tags were applied, jump to navidrome to play |
| **Library browse** | Navidrome's Subsonic API (read-only) | Search, view album, deep-link into Navidrome for playback. **Read-only** — actual edits go through beets. |
| **Disk usage** | `shutil.disk_usage` on `/`, `/mnt/seagate`, `/mnt/archive` | None; informational. Show breakdown per surface (inbox vs library vs archive vs spooty). |
| **Cron / scheduler health** | `crontab -l` parse + log tail | Show next-run time for the spooty cron, last run status, errors. |

The visual idiom: each row in a panel is a card, same drawer-expand pattern as the existing rip kanban.

---

## Pipeline context the cda-side agent needs

This is the operational reality the Library screen has to wrap. None of this is in cda's existing docs — it's all on the CM4.

### File layout on the CM4

```
/srv/music/                       (on SD card — CD rips and core dirs)
  inbox/                          CD rip drop zone (album folders with READY marker)
  inbox/spooty/                   → bind mount to /mnt/seagate/spooty/inbox
  library/                        the library Navidrome and Jellyfin serve
  library/spooty/                 → bind mount to /mnt/seagate/spooty/library
  review/                         beets couldn't auto-apply; needs operator
  archive/                        successful rips, raw form, post-import
  logs/                           beets-import.log, spooty-cron.log
  backups/  failed/  photos/

/mnt/seagate/spooty/              (on 1 TB Seagate — added 2026-05-18)
  inbox/                          where spooty writes raw downloads
  library/                        spooty content after beets import, under spooty/ prefix

/srv/cd-music-stack/              docker-compose stack: navidrome, jellyfin, beets
  docker-compose.yml
  .env                            MUSIC_ROOT, PUID, PGID, ports
  config/navidrome/navidrome.toml
  config/beets/config.yaml        main beets config (used for CD rips)
  config/beets/spooty.yaml        overlay config used by spooty imports — adds spooty/ path prefix
  bin/process-ready-auto          existing auto-import for CD rips with READY marker
  bin/import-inbox-interactive    operator-driven full inbox import
  bin/import-review-interactive   operator-driven review-bucket import

/home/mmariani/docker/spooty/     spooty docker-compose stack
  docker-compose.yml
  Dockerfile                      custom image extending raiper34/spooty:latest
                                  (adds sqlite3, yt-dlp symlinks)
  data/                           sqlite db persistence

/usr/local/bin/spooty-import.sh   cron-driven wrapper:
                                  1. mutagen pre-tag (album = folder name)
                                  2. beet -c /config/spooty.yaml import -qI --quiet-fallback=asis
```

### Spooty REST API (unauthenticated, NestJS at port 3003)

Base: `http://192.168.6.38:3003/api` or `https://spooty.mattmariani.com/api`

```
GET    /api
GET    /api/playlist
POST   /api/playlist
PUT    /api/playlist/:id
DELETE /api/playlist/:id
GET    /api/playlist/retry/:id
GET    /api/track/playlist/:id
GET    /api/track/download/:id
GET    /api/track/retry/:id
DELETE /api/track/:id
```

There is **no auth on spooty currently** — see Auth section below.

### Containers in play

```
spooty                  custom image, port 3003 → public
cd_navidrome            port 4533 → public
cd_jellyfin             port 8096 → LAN
cd_beets                port 8337 → LAN (web UI minimal)
cloudflared             tunnels spooty + cda + navidrome publicly
```

### Beets configuration nuances

- Main config writes to `/srv/music/library/...` with path template `$albumartist/[$year] $album/$track - $title`.
- Spooty overlay config (`spooty.yaml`) prefixes every path with `spooty/`, so spooty imports land in `/srv/music/library/spooty/...` — which is bind-mounted to the Seagate.
- Beets runs as `abc` (UID 1000) inside `cd_beets`. Spooty writes files as root (UID 0) inside its container. This caused permission failures when the wrapper tried to pre-tag — fix was `docker exec -u root cd_beets python3 -i ...` for the tag step.
- `cd_beets` is **always running** with its own SQLite handle on `library.db`. Spawning a second beets via `docker compose run --rm` causes SQLite write conflicts where edits silently disappear. **Rule: always use `docker exec` against the running cd_beets container, never `compose run`.**
- Mount-namespace gotcha: when host bind mounts are added under a path that's already bind-mounted into a container, the container's view doesn't refresh. Containers must be restarted after host fstab changes that affect their mount points. This bit both `cd_beets` and `cd_navidrome` during the Seagate migration.

### Known recent fragility

- Spooty image upstream (`raiper34/spooty:latest`) ships without sqlite3 AND without yt-dlp. The custom Dockerfile in `/home/mmariani/docker/spooty/` patches both. Rebuild takes ~10 min on the Pi (sqlite3 builds from source).
- `ytdlp-nodejs` (the node wrapper inside spooty) looks for yt-dlp/ffmpeg in `<package-root>/bin/`, not `$PATH`. Dockerfile symlinks `/usr/bin/yt-dlp → /spooty/node_modules/ytdlp-nodejs/bin/yt-dlp`. Same for ffmpeg/ffprobe.
- Spooty only embeds `title` + `artist` in downloaded mp3s. No album/year/track #. The pre-tag step in the spooty wrapper sets `album = folder name` and `albumartist = most common artist` before beets sees the files — without that, beets imports land at `Artist/[0000]/00 - Title.mp3` with no album in the path.
- A beets plugin (likely `chroma` or `replaygain`) occasionally throws `NotFoundError: No matching Item found` mid-import. Non-fatal but noisy. If it becomes a problem, drop `chroma` from the spooty config's plugin list.

---

## Auth

Spooty and Navidrome are both publicly reachable today through Cloudflare tunnel. cda has the same setup at `cda.mattmariani.com`.

A separate doc was drafted for adding **Cloudflare Access** in front of spooty: `/home/loydmilligan/Projects/spooty-curator/CLOUDFLARE_ACCESS_SETUP.md`. Same approach should apply to the cda Library screen — it'll inherit cda's existing tunnel auth, but cross-service API calls (cda → spooty) will need a **Service Token** so the backend can call spooty's API without going through the login wall.

If the Library screen ships before Access is configured, that's fine — it'll work on the LAN regardless. But before exposing actions like "delete this playlist" publicly, Access is the recommended gate.

---

## Where this came from

Pre-history (none of this is in cda yet — it all happened on the CM4 in the last day):

- Got spooty actually running (image was broken on arm64 — patched sqlite3 + yt-dlp + ffmpeg into a custom image).
- Wired spooty's downloads through `/srv/music/inbox/spooty/` into beets via a 15-min cron.
- Added album-pretag step so spooty imports don't lose the album name.
- Mounted a 1 TB Seagate (`/dev/sda` → `/mnt/seagate`, ext4, in fstab) and bind-mounted spooty's inbox + library subtrees onto it. CD rips stay on the SD card; spooty content lives on the Seagate. Both visible at the same paths the containers expect.
- Triggered a Navidrome full rescan; it picked up `/music/spooty/...` and even detected the moved files rather than dedupe-ing.

After all of that the operator surface gap became obvious: every action took an SSH + docker exec. Hence this proposal.

---

## What the cda-side agent should do next

In rough order:

1. **Read this doc, then read `docs/ARCHITECTURE.md` and `docs/WORKFLOW.md`** — confirm whether a Library screen fits cda's existing architecture (FastAPI service layout, kanban frontend patterns, state-machine conventions) or whether it's a separate sibling concern.
2. **Draft a ROADMAP entry** in `ROADMAP.md` for the Library Manager screen — one paragraph + acceptance criteria.
3. **Draft a design doc** in `docs/` (suggested name: `LIBRARY-MANAGER-DESIGN.md`) covering:
   - Service-layer additions (where does the spooty client live? the beets-runner abstraction?)
   - API surface (cda routes that back each panel)
   - Frontend route + components
   - Auth / Cloudflare Service Token wiring
   - Failure modes (spooty down, beets locked, navidrome offline)
4. **ADR**, if any of the above introduces a new external dependency that needs justification — e.g., adding the Subsonic API client, or persisting any state cda doesn't already own.
5. **Decide on scope-cuts for v1.** The full panel set above is overkill for a first release. A reasonable v1 might be: spooty queue + inbox queue + disk usage + library browse (read-only). Review/cron-health/log-tail can land in v2.

There's no rush. The cron + bind mounts keep new music flowing into Navidrome unattended; this screen is about reducing operator drudgery, not unblocking a broken pipeline.

---

## Open questions for the operator

(These are things this side agent didn't pin down — surface during the cda discussion.)

- Should the Library screen live at `/library` inside the existing cda UI, or as a separate top-level surface (e.g., `library.mattmariani.com`)?
- Does cda's existing kanban frontend stack have room for the additional panel types, or does this warrant a new layout pattern?
- Should beets actions go through cda's existing review-workflow primitives, or call beets directly as one-shots?
- Is there a future where cda owns the beets DB writes (and the spooty wrapper goes away), or does the spooty cron stay independent?

---

## References

- `/srv/cd-music-stack/docker-compose.yml` — main music stack (navidrome, jellyfin, beets)
- `/srv/cd-music-stack/config/beets/config.yaml` — main beets config (CD rips)
- `/srv/cd-music-stack/config/beets/spooty.yaml` — spooty overlay (path prefix)
- `/home/mmariani/docker/spooty/docker-compose.yml` — spooty stack
- `/home/mmariani/docker/spooty/Dockerfile` — custom image with sqlite3 + yt-dlp
- `/usr/local/bin/spooty-import.sh` — cron-invoked wrapper (pretag + beets)
- `/etc/fstab` — Seagate + bind mounts
- `/home/loydmilligan/Projects/spooty-curator/CLOUDFLARE_ACCESS_SETUP.md` — Access walkthrough (not yet enacted)
- Spooty upstream: `raiper34/spooty` on Docker Hub
- Navidrome plugins doc: <https://www.navidrome.org/docs/usage/features/plugins> (relevant only insofar as it confirms Navidrome's plugin system is for metadata agents/scrobblers, **not** dashboards — i.e., extending Navidrome itself is not the answer)
