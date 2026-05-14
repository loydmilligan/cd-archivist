# Ripping Session Runbook

The archivist is hands-free. Insert a disc, walk away, come back when it ejects, swap. Repeat.

## One-time / start-of-session checks

1. CM4 is up: `ssh cm4 'uptime'`.
2. Drive present: `ssh cm4 'ls /dev/sr0'`.
3. Camera present: `ssh cm4 'ls /dev/video0'`.
4. Tasmota reachable: `curl -s http://192.168.5.186/cm?cmnd=Power` returns `{"POWER":"ON"}` or `"OFF"`.
5. Existing CD player (`cdplay.service`) is stopped or in "library mode" — the archivist needs sole ownership of `/dev/sr0`.
6. Storage has room: `ssh cm4 'df -h /srv/cd-archivist /srv/music'`.
7. Archivist service is running and reports `IDLE` on its status endpoint.

## For each disc

1. **Place the disc label-side up, with text reading toward the back of the tray** (camera-up convention — keeps OCR upright).
2. Push the tray closed.
3. Walk away.

The archivist will:
- Detect the disc via `CDROM_DRIVE_STATUS` polling.
- Wait ~2 s for the drive to settle.
- Capture the ambient burst (LED off).
- Capture the lit burst (LED on, then off).
- Rip CDDA tracks via `cdparanoia`, encode to FLAC.
- Write the manifest into `CD_NNNN/`.
- Software-eject the disc.

Check the status endpoint or logs if you want to watch progress live.

## After session

1. Check the review queue: any disc whose status is `needs_review` should be looked at while the session is fresh.
2. Confirm rips landed: `ls /srv/cd-archivist/discs/` and spot-check the most recent folder.
3. Confirm captures exist for each rip (both ambient and lit sets).
4. Back up `/srv/cd-archivist/` (NVMe is not a backup).

## Recovery

| Symptom | Action |
|---|---|
| Disc detected but no capture | Camera USB hung — `sudo` unbind/rebind the USB port (see `cm4-setup.md`). The rip still proceeded; manifest will be flagged. |
| Disc detected but rip fails immediately | Likely `cdplay.service` or `mpv` is holding the drive. Stop the player and re-insert. |
| Tasmota timeouts | Captures continue with ambient-only. Investigate the smart plug separately; do not block the session. |
| Drive won't eject | A process still holds the device — `lsof` (if installed) or `fuser /dev/sr0` to find the holder. |
| Disc identified as `needs_review` | Open the review queue once the session is done. Don't try to fix mid-session. |

## Conventions

- **Never delete raw captures or raw rips manually.** The archivist keeps them as the source of truth; the music library under `/srv/music` is downstream.
- **One disc per insert.** The pipeline assumes a single capture+rip per disc cycle. If you swap discs without an eject in between, you'll get one disc's photos paired with another's audio — the manifest will be wrong.
- **Keep the LED panel area clear.** A diffuser on the panel matters; check it before each session.
