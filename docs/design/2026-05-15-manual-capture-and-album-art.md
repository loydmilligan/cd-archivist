# Manual capture + album art upload — design spec

**Status:** sprint-4 candidate
**Drafted:** 2026-05-15
**Source:** user request during sprint-2 hardware bring-up + sprint-3 in-flight

## Why

Sprint-2's auto-capture (LED-dance + ffmpeg burst) covers the "every disc gets a basic photo record" baseline. But the operator workflow has gaps:

1. **Auto-captures are ambient/lit pairs of the disc face only.** Real archival quality means album art too — front cover, back cover, inside the case, liner notes if present.
2. **The auto-capture only fires once per ingest cycle.** If lighting was bad, the disc was misaligned, or the camera flaked — there's no retry without re-ingesting the disc (which generates a new `CD_NNNN/`, splitting the record).
3. **Album art lives outside the CD itself.** A burned mix CD's case, j-card, or scribbled label is part of the artifact. Today nothing in the pipeline knows about it.

This spec adds two surfaces to the existing `/library/CD_NNNN` detail page (sprint-3 read-only baseline): a **manual capture trigger** and an **upload endpoint for supplemental images**.

## Scope (v1 — sprint-4)

### Manual capture trigger
- Button on `/library/CD_NNNN`: "Take a new photo with the webcam"
- LED-mode toggle (radio): **off** (ambient only) | **on** (lit only) | **both** (full ambient+lit dance like auto-capture)
- Click → 3-2-1 countdown rendered client-side so the operator can position the tray/disc/case
- POST `/api/library/CD_NNNN/recapture?led=off|on|both` to fire the burst
- Burst writes JPGs into `captures/` with a `manual_` filename prefix (e.g. `manual_lit_20260515T1430Z_001.jpg`) so they're distinguishable from auto-captures
- Manifest's `captures[]` gets a new entry; each `CaptureRecord` extends with `source: "auto" | "manual"`
- **Race condition handling:** if the state-machine loop is currently using the camera (CAPTURE state), return 409 with a clear "the loop is using the cam right now, try again in a few seconds" message

### Album art / supplemental image upload
- Same detail page: drag-and-drop or file-picker upload area
- Accepts JPEG / PNG (validate magic bytes, not just extension)
- Category dropdown per upload: `front_cover` | `back_cover` | `inside_tray` (behind the disc) | `liner_notes` | `other`
- POST `/api/library/CD_NNNN/upload` (multipart/form-data with `category` + `file`)
- Files saved into a NEW `art/` subdirectory under `CD_NNNN/` (parallel to `captures/audio/logs/review/`) — keeps webcam captures separate from operator-uploaded images
- Filename: `art/{category}_{ISO_TS}.{ext}` (so reuploading "front_cover" doesn't overwrite, and timestamps preserve which is most recent)
- Manifest gets a new `art: list[ArtRecord]` field with `{filename, category, source: "uploaded", uploaded_at}`
- File-size cap (default 20MB per upload; `ARCHIVIST_MAX_UPLOAD_MB` env override)

### Manifest schema bump

Goes from `0.2` → `0.3`:
- `CaptureRecord` gains `source: Literal["auto","manual"]` (existing records auto-migrate to `"auto"`)
- New top-level `art: list[ArtRecord]` field (default `[]`)
- New `ArtRecord` model: `filename: str`, `category: Literal[...]`, `source: Literal["uploaded"]`, `uploaded_at: datetime`

`read_manifest` keeps accepting `0.2` (read-only — auto-fills `source="auto"` and `art=[]`); `write_manifest` always writes `0.3` once a disc is touched by sprint-4 code.

## Out of scope for v1 (sprint-5+)

### Live alignment overlay
The "ideal" UX is a live MJPEG preview from the webcam with a CD-shaped outline overlaid so the operator can position the disc precisely before clicking. Doable but adds:
- A new `GET /api/camera/preview` streaming endpoint (FastAPI `StreamingResponse` + a continuous ffmpeg MJPEG pipe)
- Browser-side canvas overlay sized to CD dimensions
- Lifecycle management (the preview stream blocks `/dev/video0`, so it has to release cleanly when the user clicks capture or navigates away)
- Probable USB bandwidth contention with the auto-capture path

Defer until v1 ships and we know whether the countdown alone is enough. If the overlay turns out to be needed, it's its own ~half-sprint of work.

### Editable manifest fields
Sprint-4 adds **adding** content (uploads, manual captures). It does NOT add **editing** — no track renaming, no metadata correction, no deleting old captures. That's the natural sprint-5 expansion alongside OCR/Discogs lookup landing.

## Implementation notes for whoever picks this up

- **Lockfile around the camera:** the manual capture path needs a non-blocking lock check against the auto-capture path. `/dev/video0` busy → 409. The state machine's existing CAPTURE / EJECT-CAPTURE phases should hold the lock for their burst windows.
- **Mash Co. dressing:** the upload area is a bordered drop-zone using `--surface` background + `--line` dashed border, hover state to `--surface-hover`. Capture button uses `--accent` (pulp orange) primary CTA. Countdown is big numerals in the display font.
- **No auth this sprint** — same as sprint-2's status surface: LAN-only, no credentials. If exposing via the postponed Cloudflare-tunnel work, auth becomes blocking.
- **Tests:** TestClient for the routes; fakes for the camera + manifest. The 409 race case is load-bearing (tests must verify a real lock is held, not just a "we checked a flag" approximation).
- **Browser FLAC playback note from sprint-3 still applies** — image rendering is a non-issue, browsers handle JPEG/PNG natively.

## Decision log entries to land at sprint-4 plan time

- `D-manifest-v0.3` — bump schema for `source` field + `art` list; backward-compatible read; write-time migration only
- `D-manual-capture-led-modes` — three LED modes (off/on/both) match the auto-capture taxonomy; could simplify to off/on but the dual-burst is the design's signature
- `D-art-subdir` — `art/` is parallel to `captures/`, not nested under it (operator-supplied vs camera-supplied is a meaningful distinction)
- `D-upload-no-overwrite` — uploads are timestamp-suffixed; reuploading `front_cover` keeps both versions; deletion is sprint-5's editable-review concern
- `D-overlay-deferred` — alignment overlay deferred to sprint-5+ pending v1 feedback on countdown-only UX
