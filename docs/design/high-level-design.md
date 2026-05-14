# High-Level Design

## Problem

A collection of old CDs includes both commercial albums and burned mix CDs. Many burned discs have little or no digital metadata. Some have handwritten labels or visual clues that are historically meaningful.

Manual metadata entry would be tedious and would slow the ripping process.

## Goal

Create a semi-automated archival station that:

- Rips CDs using a USB optical drive on a Raspberry Pi CM4.
- Captures photos of each physical disc using a USB webcam.
- Extracts visible text and physical descriptions (later phase).
- Pairs image metadata with ripped audio.
- Preserves each disc as a durable archival object.
- Exposes the resulting library through a music server.

## Non-goals

- Perfect automatic metadata for every disc.
- Blocking rips until metadata is corrected.
- Replacing human review entirely.
- Deleting source files after processing.
- Real-time playback of unripped discs (see "Player split" below).

## Architecture summary

A single Raspberry Pi CM4 owns the entire pipeline:

- USB CD-ROM drive (`/dev/sr0`)
- USB webcam (`/dev/video0`)
- LED panel (white, paper-diffused) controlled via Tasmota smart plug over HTTP
- Local storage on NVMe
- FastAPI service for status + future review UI
- Music library directory served by a separate music server (e.g. Navidrome)

The earlier two-machine design (Power Mac G4 ripper + Pi brain) has been retired. See `docs/operations/g4-setup.md` (deprecated) for historical context.

## Player split (Option C)

The CD player and the archivist are intentionally separated:

- **Archivist owns the optical drive.** It detects discs, captures photos, rips audio, ejects.
- **The player only plays already-ripped files** from the music library. It never reads `/dev/sr0`.

This eliminates drive contention (no fight between mpv and the ripper) and matches the project's archival mission: the disc is the source artifact, the library is the listening surface.

Tradeoff: a freshly inserted disc cannot be played until it has been ripped (~5–8 min for a 50-minute CD).

A standalone proof-of-concept CD player (`cdweb` + `mpv`) currently runs on the CM4 on port 8090. It will keep running independently for now and will eventually be replaced or retrofitted to play from ripped files.

## System components

### Raspberry Pi CM4

Role:
- Camera host, capture controller
- LED orchestrator (Tasmota HTTP)
- Drive state poller
- Ripper host (`cdparanoia` + `flac` for v1)
- Manifest writer
- Pairing engine (trivial: single-process timestamps)
- Review queue host (later phase)
- Music library host

### USB CD-ROM drive

Role: read CDs (and DVDs — see "Future: DVD support"), report state via `CDROM_DRIVE_STATUS` ioctl, accept software eject.

### USB webcam

Currently a Microdia "Vitade AF" UVC camera at `/dev/video0`. Notable traits:
- 1280×720 MJPEG at 30 fps
- Fixed-firmware autofocus (no V4L2 focus controls)
- VIDIOC_STREAMON occasionally errors after long idle periods; recoverable by USB unbind/rebind.

### LED panel + Tasmota

A bright white LED panel powered through a Tasmota-flashed smart plug at `192.168.5.186`. Paper diffuser on the panel. Controlled via simple HTTP:

```
curl http://192.168.5.186/cm?cmnd=Power%20On
curl http://192.168.5.186/cm?cmnd=Power%20Off
curl http://192.168.5.186/cm?cmnd=Power
```

The LED makes captures **consistent across ambient lighting**, not dramatically brighter — auto-exposure compensates for ambient. With LED-on, disc surface white-balances to neutral and contrast against the marker text is reliable regardless of room conditions.

### Storage

```text
/srv/cd-archivist/
  discs/                CD_NNNN/ archival objects (canonical)
  incoming-rips/        scratch space during rip (moved to discs/ on success)
  review/               manifests flagged for human review
  logs/                 service logs

/srv/music/             library — published reviewed/accepted discs
```

## Pipeline

### 1. Drive state polling loop

Poll `/dev/sr0` via `CDROM_DRIVE_STATUS` ioctl every ~2 s. State machine:

```
IDLE
  └── tray opened or no disc        → WAITING
WAITING
  ├── DISC_OK                       → STABILIZE (~2s)
  └── (no transition)               → keep polling
STABILIZE
  └── timer                         → CAPTURE → RIP → EJECT → IDLE
```

No udev events, no physical button, no external triggers needed. Software eject after rip; user inserts the next disc when ready.

### 2. Capture

For each disc, two bursts are captured under different lighting:

```
LED off  → wait 500ms (AE/AWB settle)  → ambient burst → captures/disc_front_ambient_NNN.jpg
LED on   → wait 500ms (AE/AWB settle)  → lit burst     → captures/disc_front_lit_NNN.jpg
LED off
```

Both sets are preserved. Downstream OCR/AI defaults to the lit set (better contrast); the ambient set is archival reference and OCR fallback.

Camera convention: webcam is positioned so that **a disc placed label-side up with text reading toward the back of the tray comes out upright in the frame**. No software rotation. Frames are center-cropped to a 720×720 square in the pipeline (disc is round; tall portrait wastes pixels).

Capture is best-effort. Tasmota unreachable → log warning, capture proceeds with whatever ambient light exists. Camera errored → log error, but rip still proceeds (disc audio is the irreplaceable part).

### 3. Rip

`cdparanoia` reads CDDA tracks; output piped through `flac` for archival encoding.

```text
cdparanoia -B -d /dev/sr0 -- "1-" /tmp/rip-NNNN/
flac --best /tmp/rip-NNNN/track*.wav
```

Rip failure modes (read errors, scratched discs, mixed-mode discs) are logged and the disc lands in review with whatever audio was successfully extracted. **Source media is never re-ejected on failure** — the user decides whether to retry.

### 4. Pairing

Trivially a no-op in v1 — capture and rip happen in the same process for the same disc. The `PairingRecord` is still written to the manifest with `method: "single_session"` so the schema is forward-compatible with future detached-capture workflows.

### 5. Metadata (later phase)

OCR + AI metadata extraction is deferred. The manifest schema reserves fields for it.

### 6. Review (later phase)

Discs flagged uncertain land in `/srv/cd-archivist/review/`. The FastAPI service will expose a UI later.

### 7. Library publication (later phase)

Reviewed/accepted discs are copied to `/srv/music/` in a structure compatible with Navidrome.

## Pluggable ripper interface

To leave the door open for DVD ingest and other media types, the ripping step is mediated by a small interface:

```python
class Ripper(Protocol):
    media_types: set[str]              # e.g. {"audio_cd"}
    def detect(self, device: Path) -> str | None  # returns media_type or None
    def rip(self, device: Path, out_dir: Path) -> RipResult
```

v1 ships one implementation: `CDAudioRipper`. Future implementations:

- `DataDiscRipper` — `dd` / `genisoimage --image` for data CDs/DVDs
- `DVDVideoRipper` — `HandBrake` or `MakeMKV` for video DVDs (CSS-encrypted ones need `libdvdcss`)

Disc detection picks the right backend based on `CDROM_DISC_STATUS`. Manifest gains a `media_type` field.

## Disc folder layout

```text
CD_0001/
  manifest.json
  captures/
    disc_front_ambient_001.jpg
    disc_front_ambient_002.jpg
    disc_front_lit_001.jpg
    disc_front_lit_002.jpg
  audio/
    01 Track 01.flac
    02 Track 02.flac
    ...
  logs/
    capture.log
    rip.log
  review/
    notes.md
```

## Manifest sketch

```json
{
  "schema_version": "0.2",
  "disc_id": "CD_0001",
  "media_type": "audio_cd",
  "created_at": "2026-05-14T12:00:00-07:00",
  "status": "ripped",
  "captures": [
    {"capture_id": "...", "lighting": "ambient", "image_paths": ["..."]},
    {"capture_id": "...", "lighting": "lit",     "image_paths": ["..."]}
  ],
  "rips": [],
  "pairings": [{"method": "single_session", "confidence": "high"}],
  "metadata": {},
  "errors": []
}
```

## Failure handling

The system must handle:

- Capture but no rip (camera worked, drive failed)
- Rip but no capture (cam unplugged, rip succeeded)
- LED unreachable (Tasmota offline)
- Camera unreachable (USB hung)
- Drive read errors mid-rip
- User pulls disc during rip (drive door sense changes)
- Process restart mid-pipeline

All such cases land in review rather than being discarded. Source media (raw captures + raw audio that *was* extracted) is never automatically deleted.

## Future: DVD support

DVDs are deliberately out of scope for v1 but designed-for. Adding DVD support means:

1. New `Ripper` implementations (`DataDiscRipper`, `DVDVideoRipper`).
2. Disc detection extended to `CDS_DATA_*` and DVD types.
3. `media_type` enum extended.
4. Library publishing learns about non-audio outputs.

The capture/manifest/library/review halves of the system already work identically for any disc.

## Guiding principle

Do not optimize for perfect automation.

Optimize for:

```text
low-friction capture
durable preservation
later correction
```
