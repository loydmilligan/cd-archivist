# Music-stack migration — laptop → CM4

**When:** sprint-4 Wave 0, before any cd-archivist code touches the music-pipeline contract.
**Why:** the music-pipeline handoff doc (`docs/ripper-handoff-for-claude-code.md`) assumes ripper and importer share a filesystem. cd-archivist runs on the CM4; the beets/Navidrome/Jellyfin stack currently runs on the laptop. Co-locate them on the CM4 to honor the contract as-written, eliminate mount/sync glue, and match the always-on duty cycle.

## Pre-flight

Verify on the CM4:
```sh
ssh cm4 'which docker && docker compose version && id && df -h /srv'
```

Expected:
- `docker` present (29.4.0 or newer)
- `docker compose version` returns v2.x or v5.x
- `id` shows uid=1000(mmariani), member of `docker` group
- `/srv` (or `/`) has at least 5GB free for the stack itself; library growth budget on top

## Step 1 — Stop containers on the laptop

On the laptop:
```sh
cd /srv/cd-music-stack
docker compose down
docker ps   # confirm cd_navidrome / cd_jellyfin / cd_beets are gone
```

## Step 2 — Create target dirs on the CM4

```sh
ssh cm4 'sudo mkdir -p /srv/cd-music-stack /srv/music && sudo chown -R mmariani:mmariani /srv/cd-music-stack /srv/music'
```

## Step 3 — Sync the stack config

```sh
rsync -avh --progress /srv/cd-music-stack/ cm4:/srv/cd-music-stack/
```

This carries `docker-compose.yml`, `.env`, `bin/`, `config/{navidrome,jellyfin,beets}/`, `cache/`, and `README.md`. It will overwrite anything already at the target — there shouldn't be anything there.

## Step 4 — Sync the music tree

```sh
rsync -avh --progress /srv/music/ cm4:/srv/music/
```

Carries `inbox/` (which currently holds CD_0004 + CD_0018 from the dogfood rips), plus the empty `library/`, `review/`, `archive/`, `logs/`, `photos/`, `backups/` skeleton.

## Step 5 — Verify the .env is right for the CM4

```sh
ssh cm4 'cat /srv/cd-music-stack/.env'
```

Expected (already correct because mmariani is also UID 1000):
```
PUID=1000
PGID=1000
TZ=America/Los_Angeles   # adjust if CM4 is on a different timezone
MUSIC_ROOT=/srv/music
NAVIDROME_PORT=4533
JELLYFIN_PORT=8096
BEETS_PORT=8337
```

If the CM4 timezone differs from the laptop, fix `TZ=` here before bringing up.

## Step 6 — Bring up the stack on the CM4

```sh
ssh cm4 'cd /srv/cd-music-stack && docker compose up -d'
```

Wait ~30s for containers to settle, then:
```sh
ssh cm4 'docker ps'
```

All three (`cd_navidrome`, `cd_jellyfin`, `cd_beets`) should be `Up` with `(healthy)` for jellyfin.

## Step 7 — Smoke-test from the laptop / phone

From any device on the LAN:
- Navidrome: `http://192.168.6.38:4533/` — should show the empty library
- Jellyfin: `http://192.168.6.38:8096/` — should land on the setup wizard if first run, OR the existing config carried over
- Beets WebUI: `http://192.168.6.38:8337/` — should show the empty database (or the CD_0004/CD_0018 if you'd already imported them on the laptop)

## Step 8 — Re-test the beets import flow

```sh
ssh cm4 'docker exec -it cd_beets beet import /downloads/CD_0018/'
```

(`/downloads/` inside the container = `/srv/music/inbox/` on the CM4.) Walk through the MusicBrainz match prompt for the AFI disc.

## Step 9 — Update cd-archivist's output target (this is sprint-4 work proper)

Once the stack is live on the CM4, sprint-4's contract-conformance tasks can write directly to `/srv/music/inbox/` instead of `/home/mmariani/cd-archivist-data/discs/`. The cd-archivist also runs on the CM4 → same filesystem → atomic moves work as the handoff doc describes.

Set in cd-archivist's runtime env (entrypoint or systemd unit when sprint-4 lands it):
```
MUSIC_INBOX_DIR=/srv/music/inbox
MUSIC_WORKING_DIR=/srv/music/.ripping
MUSIC_FAILED_DIR=/srv/music/failed
```

## Step 10 — Clean up the laptop

After confirmed working on the CM4 for at least one full rip cycle:
```sh
# Optional: keep as backup for a few days, then remove
sudo rm -rf /srv/cd-music-stack /srv/music
```

Or leave them in place as a cold backup until you're confident.

## Rollback

If something on the CM4 goes wrong:
```sh
ssh cm4 'cd /srv/cd-music-stack && docker compose down'
# Bring the laptop stack back up:
cd /srv/cd-music-stack && docker compose up -d
```

The two never need to be running simultaneously; they bind the same ports on different hosts and consume the same `/srv/music/` dataset (which we just rsync'd, so both have it). `rsync` again before bringing the laptop back up if any data landed on the CM4 in the interim.

## Known gotchas

- **Power management:** the CM4 should stay powered on indefinitely. If it loses power mid-import, beets' SQLite DB at `/srv/cd-music-stack/config/beets/library.db` may need a `.recover` or you may have a half-imported album in `library/` that beets thinks doesn't exist. Recovery: `docker exec -it cd_beets beet update`.
- **Config-file ownership:** if any container ran as root on the laptop and wrote root-owned files, the CM4 containers (running as PUID=1000) will throw permission errors. Fix: `ssh cm4 'sudo chown -R 1000:1000 /srv/cd-music-stack/config /srv/music'`.
- **USB drive eject:** if you decide to put `/srv/music/library/` on the Seagate Expansion, you need a stable mount (label-based or UUID-based in `/etc/fstab`, NOT `/dev/sda1` which can change). Skipping for now — the NVMe has 332GB free, plenty for a starter library.
