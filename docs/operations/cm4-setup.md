# Raspberry Pi CM4 Setup

The CM4 is the entire archival station. It owns the optical drive, the camera, the LED, the manifest, the library, and the review UI.

## Hardware inventory

| Item | Where | Notes |
|---|---|---|
| Pi CM4 (4 GB) | host `piUSBcam2` | Debian 13 trixie, kernel 6.12.75, Python 3.13, 476 GB NVMe at `/` |
| USB CD-ROM | `/dev/sr0` (`/dev/cdrom`) | DVD-capable; tray + software eject |
| USB webcam | `/dev/video0` | Microdia Vitade AF (UVC, idVendor 0c45:6366); 1280×720 MJPEG, 30 fps |
| LED panel | mains via Tasmota smart plug @ `192.168.5.186` | bright white, paper diffuser |
| Network | LAN, same subnet as Tasmota | host reachable as `cm4` |

Access: `ssh cm4` (passwordless sudo available).

## Coexistence with the existing CD player

The CM4 is already running a working CD player (separate from this project):

- `cdplay.service` — `mpv --no-video cdda:///dev/sr0` (audio-only, IPC socket at `/tmp/mpvsock`)
- `cdweb.service` — small Python HTTP server on `:8090` that drives mpv

These services hold `/dev/sr0` while running. The archivist must not race them. Per the Option C decision (see `high-level-design.md`), the long-term plan is for the player to read from ripped FLAC files only, so contention disappears. Until that landing:

- The archivist stops `cdplay.service` before claiming the drive.
- The archivist restarts it (or its replacement) after eject.
- `cdweb` on `:8090` keeps running independently; the archivist FastAPI serves on a different port.

## Camera

### Capture command (reference)

```bash
ffmpeg -hide_banner -loglevel error \
  -f v4l2 -video_size 1280x720 -i /dev/video0 \
  -frames:v 15 -y /tmp/shot.jpg
```

We capture 10–15 frames and keep the last so the AF has time to lock. The first 1–5 frames after `streamon` are often hunting.

### Webcam quirks

- **Fixed-firmware autofocus.** Despite the "AF" name, the cam exposes no V4L2 focus controls. Distance and lighting are the only knobs.
- **VIDIOC_STREAMON occasionally errors** after long idle periods or rapid re-opens. Recovery in order of escalation:
  1. Wait 1–2 s and retry.
  2. USB sysfs unbind/rebind:
     ```bash
     echo "1-1.2.2" | sudo tee /sys/bus/usb/drivers/usb/unbind
     sleep 2
     echo "1-1.2.2" | sudo tee /sys/bus/usb/drivers/usb/bind
     ```
  3. Physical unplug/replug (the Pi can't power-cycle the port from software).
- **MJPEG is the right pixel format** — YUYV at 1280×720 maxes out at 10 fps and isn't worth it for stills.

### Camera placement convention

- Cam is positioned so a disc placed **label-side up with text reading toward the back of the tray** comes out upright in the frame.
- No software rotation is applied.
- Frames are captured at 1280×720 landscape and center-cropped to 720×720 square in the pipeline (the disc is round; tall portrait wastes pixels).
- Mount must be rigid — camera drift between captures has been the largest source of framing variance during prototyping.

## LED panel + Tasmota

### Endpoint

```
http://192.168.5.186/cm?cmnd=Power      # query state
http://192.168.5.186/cm?cmnd=Power%20On
http://192.168.5.186/cm?cmnd=Power%20Off
```

Tasmota responds with JSON like `{"POWER":"ON"}`. Relay polarity is normal (not inverted); `PowerOnState=3` (restore last state on boot).

### Why we use it

The LED's value is **white-balance and contrast consistency across ambient lighting**, not raw brightness. Auto-exposure on the cam masks most of the brightness contribution, but the LED dominates the white balance and produces a neutral-white disc surface regardless of room conditions. This matters for OCR because consistent contrast across discs is more useful than slightly higher contrast on any one disc.

In dim ambient (mean luminance < 140/255) the LED contribution is visually obvious. In bright ambient it's subtle but still measurable.

### Capture pipeline LED dance

```
1. ledOff
2. wait 500 ms                  (let AE/AWB settle on ambient)
3. capture ambient burst        → captures/disc_front_ambient_NNN.jpg
4. ledOn
5. wait 500 ms                  (let AE/AWB settle on LED)
6. capture lit burst            → captures/disc_front_lit_NNN.jpg
7. ledOff                       (restore)
```

Both bursts are preserved per disc. ~600 KB total extra per disc vs single burst, which is trivial next to ~30–100 MB of FLAC audio.

### Failure mode

If Tasmota is unreachable at any step, log a warning and fall through to capturing only the ambient set. Never block ripping on a smart plug.

## Storage layout

**Sprint-4 / D-music-pipeline-paths.** cd-archivist hands ripped discs
off to a separate music-pipeline importer (Beets → Navidrome) via the
filesystem. Three paths are env-driven:

| Env var               | Default                          | Purpose                                                        |
| --------------------- | -------------------------------- | -------------------------------------------------------------- |
| `MUSIC_INBOX_DIR`     | `~/music-pipeline/inbox`         | Discs land here only AFTER `READY` is written (atomic handoff) |
| `MUSIC_WORKING_DIR`   | `~/music-pipeline/.ripping`      | Per-disc scratch; folder moves to inbox on success             |
| `MUSIC_FAILED_DIR`    | `~/music-pipeline/failed`        | Failed rips move here with a `FAILED` marker                   |

**Legacy alias:** `ARCHIVIST_DISCS_ROOT` (sprint-1 through sprint-3)
still works — it's silently treated as `MUSIC_INBOX_DIR` with a
deprecation warning logged at startup. New deployments should set the
three vars above.

**Dogfood-rig override** (current CM4 at 192.168.6.38):
```text
/srv/music/inbox        ← MUSIC_INBOX_DIR=/srv/music/inbox
/srv/music/.ripping     ← MUSIC_WORKING_DIR=/srv/music/.ripping
/srv/music/failed       ← MUSIC_FAILED_DIR=/srv/music/failed
```
(matches `/srv/cd-music-stack/.env::MUSIC_ROOT=/srv/music`).

**Per-disc folder shape (new):** `YYYY-MM-DD_HHMM_disc-NNNNNN/` with
`source.json` (schema v1), `rip.log`, `disc-photo.jpg`,
`NN Track.flac` files, and a `READY` marker once everything is in
place. Per D-folder-naming-migration, legacy `CD_NNNN/` folders are
NOT auto-migrated — the library UI surfaces both via
`read_disc_summary` (the legacy adapter).

**Logs + LED + camera** continue at:
```text
/srv/cd-archivist/
  logs/                 service logs (ARCHIVIST_LOG_PATH)
```

### Other env knobs (sprint-4)

| Env var                          | Default                                          | Purpose                                                |
| -------------------------------- | ------------------------------------------------ | ------------------------------------------------------ |
| `ARCHIVIST_MODE`                 | `auto`                                           | `manual` makes the loop wait for `/api/control/*` triggers (D-manual-mode) |
| `ARCHIVIST_KEEP_WAVS`            | unset (delete)                                   | `1`/`true`/`yes` to keep WAVs post-FLAC (D-wav-cleanup) |
| `ARCHIVIST_PROCESS_READY_HOOK`   | `/srv/cd-music-stack/bin/process-ready-auto`     | Fire-and-forget command after each READY rename. Empty string disables (D-process-ready-trigger). |
| `ARCHIVIST_LOG_PATH`             | `/srv/cd-archivist/logs/archivist.log`           | Pipeline log destination                                |
| `ARCHIVIST_PORT`                 | `8228`                                           | FastAPI status surface                                  |
| `ARCHIVIST_DEVICE`               | `/dev/sr0`                                       | CD-ROM device                                           |
| `ARCHIVIST_LED_BASE`             | `http://192.168.5.186`                           | Tasmota LED panel endpoint                              |
| `ARCHIVIST_VIDEO_DEVICE`         | `/dev/video0`                                    | v4l2 device for captures                                |


## Required system packages

```bash
sudo apt install -y \
  cdparanoia \
  flac \
  ffmpeg \
  v4l-utils \
  eject
```

Optional:
- `cdrdao` — only if we add cue-sheet generation
- `whipper` — alternate ripper backend (deferred)

## Sample captures

Reference frames from initial bring-up live in `docs/operations/sample-captures/`. The pair worth comparing:

- `2026-05-14_dim-off.jpg` — ambient only, dim room
- `2026-05-14_dim-on.jpg` — LED on, same scene
- `2026-05-14_frame-09.jpg` — final accepted framing (no rotation, square crop applied)

These are committed to the repo as a calibration baseline; the actual archive captures live under `/srv/cd-archivist/discs/`.

## NOPASSWD sudo fragment

The archivist runs as an unprivileged user but needs a narrow set of
root-only operations: stopping/starting the `cdplay.service` unit
around drive-claim windows, and rebinding the camera's USB device when
ffmpeg hits a `VIDIOC_STREAMON` failure. Install this fragment by hand
on the CM4 the first time you wire up the rig — it is **not** managed
by the pipeline.

Install command:

```sh
sudo visudo -f /etc/sudoers.d/cd-archivist
```

Paste the following (replace `cdarchivist` with the user the service
runs as):

```sudoers
# /etc/sudoers.d/cd-archivist
# Narrowly scoped NOPASSWD rules for the archivist runtime.

# (a) Stop/start the cdplay.service unit around CD-claim windows.
#     The archivist must own /dev/sr0 exclusively while ripping, and
#     restart cdplay afterwards so headphone playback resumes.
cdarchivist ALL=(root) NOPASSWD: /bin/systemctl stop cdplay.service
cdarchivist ALL=(root) NOPASSWD: /bin/systemctl start cdplay.service

# (b) USB unbind/rebind for the webcam recovery path.
#     ffmpeg can hit VIDIOC_STREAMON after a kernel quirk; the
#     recovery wrapper writes the bus path (e.g. "1-1.2.2") to the
#     usb driver's unbind/bind sysfs files to reset the device.
cdarchivist ALL=(root) NOPASSWD: /usr/bin/tee /sys/bus/usb/drivers/usb/unbind
cdarchivist ALL=(root) NOPASSWD: /usr/bin/tee /sys/bus/usb/drivers/usb/bind
```

Verify after install:

```sh
sudo -l -U cdarchivist | grep -E "systemctl|tee"
```

Each line should appear with `(root) NOPASSWD:`. If `visudo` rejects
the file, the syntax is wrong — fix the file before saving (visudo
refuses to install a broken sudoers fragment).

