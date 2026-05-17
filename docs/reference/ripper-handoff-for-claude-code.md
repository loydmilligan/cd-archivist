# CD Ripper Handoff Spec for Claude Code

You are helping build or modify a local CD-ripping application so it integrates cleanly with an existing Docker-based post-rip music stack.

The post-rip stack already exists and expects the ripper to write completed disc folders into an intake directory. The stack then uses Beets to identify/tag/import music, Navidrome to serve the final library, and Jellyfin optionally for broader media-device support.

Your job is **only the ripper-side integration**: make sure the ripper creates the correct folder structure, writes the required sidecar files, captures the disc photo at the right time, and marks the disc folder as ready only when everything is complete.

---

## System Overview

The post-rip pipeline expects this flow:

```text
CD inserted
  ↓
Ripper detects disc
  ↓
Ripper extracts audio securely
  ↓
Ripper collects available disc metadata
  ↓
Ripper ejects tray or waits for eject event
  ↓
Ripper captures physical disc photo
  ↓
Ripper writes source.json, rip.log, disc-photo.jpg
  ↓
Ripper creates READY marker
  ↓
Beets import process picks up the folder
  ↓
Clean music appears in Navidrome/Jellyfin
```

The ripper **must not** write directly to the final music library. It only writes to the intake folder.

---

## Existing Docker Stack Assumptions

The scaffolded stack uses these host folders by default:

```text
~/music-pipeline/inbox      raw completed rips from the CD-ripping app
~/music-pipeline/review     uncertain albums requiring human review
~/music-pipeline/library    clean tagged music library
~/music-pipeline/archive    raw successful rips after import
~/music-pipeline/logs       import logs
~/music-pipeline/photos     optional extra photo storage
~/music-pipeline/backups    optional backup staging
```

The Docker Compose stack maps:

```text
Host: ~/music-pipeline/inbox    → Beets container: /downloads
Host: ~/music-pipeline/library  → Beets container: /music
Host: ~/music-pipeline/review   → Beets container: /review
Host: ~/music-pipeline/archive  → Beets container: /archive
Host: ~/music-pipeline/logs     → Beets container: /logs
```

The ripper should write to:

```text
~/music-pipeline/inbox
```

Allow this to be configured with an environment variable or config setting:

```bash
MUSIC_INBOX_DIR="$HOME/music-pipeline/inbox"
```

Do not hard-code only one path. Use the default above, but make it overrideable.

---

## Required Per-Disc Folder Layout

For each disc, create one unique folder inside the inbox.

Example:

```text
~/music-pipeline/inbox/2026-05-14_1832_disc-000421/
  01 Track.flac
  02 Track.flac
  03 Track.flac
  disc-photo.jpg
  source.json
  rip.log
  READY
```

### Folder Naming

Use a stable, sortable, collision-resistant name:

```text
YYYY-MM-DD_HHMM_disc-NNNNNN
```

Example:

```text
2026-05-14_1832_disc-000421
```

Requirements:

- Use local time.
- Use 24-hour time.
- Include a monotonic disc counter or UUID suffix to avoid collisions.
- Avoid spaces and special shell characters.
- Use only safe path characters: letters, numbers, dots, dashes, underscores.

Acceptable alternatives:

```text
2026-05-14_1832_disc-000421
2026-05-14_1832_8f2a7c91
20260514-183211-disc-000421
```

---

## Completion Marker Contract

The `READY` file is the contract between the ripper and the Beets import process.

The ripper must create `READY` **only after all required work is complete**:

1. Audio extraction has finished.
2. Audio files have been fully flushed to disk.
3. `rip.log` has been written.
4. `source.json` has been written.
5. `disc-photo.jpg` has been saved, or the photo failure has been explicitly recorded in `source.json`.
6. The folder is no longer being modified.

The importer ignores folders that do not contain `READY`.

### Important atomicity rule

Do not create `READY` early.

Recommended behavior:

```text
Create folder
Write files
fsync/flush important files where practical
Write READY.tmp
Rename READY.tmp → READY
```

The final marker should be an atomic rename.

Example shell equivalent:

```bash
echo "ready_at=$(date -Iseconds)" > READY.tmp
mv READY.tmp READY
```

---

## Use a Temporary Working Folder

To avoid the importer seeing half-written files, use either of these approaches.

### Preferred approach

Write to a temporary folder outside the inbox, then move the completed folder into the inbox and create `READY`.

```text
~/music-pipeline/.ripping/2026-05-14_1832_disc-000421/
  ...work in progress...
```

Then, when complete:

```text
mv ~/music-pipeline/.ripping/2026-05-14_1832_disc-000421 \
   ~/music-pipeline/inbox/2026-05-14_1832_disc-000421
```

Then create:

```text
~/music-pipeline/inbox/2026-05-14_1832_disc-000421/READY
```

### Acceptable approach

Write directly inside inbox, but do not create `READY` until done:

```text
~/music-pipeline/inbox/2026-05-14_1832_disc-000421/
  ...work in progress...
```

This is acceptable only if `READY` is guaranteed to be last.

---

## Required Files

Each completed disc folder should contain the following.

### 1. Audio files

Preferred format:

```text
FLAC
```

File naming before Beets import does not need to be perfect, but should be stable and track-numbered:

```text
01 Track.flac
02 Track.flac
03 Track.flac
```

Better if metadata is known:

```text
01 - So What.flac
02 - Freddie Freeloader.flac
```

Requirements:

- Use zero-padded track numbers.
- Preserve track order.
- Do not overwrite existing files.
- Prefer secure ripping where available.
- Keep pre-gap/hidden-track info in the log if detected.

Optional but useful:

```text
album.cue
accuraterip.log
```

### 2. `disc-photo.jpg`

This is the physical disc photo captured when the disc is ejected or immediately after the tray opens.

Requirements:

- Filename should be exactly:

```text
disc-photo.jpg
```

- Use JPEG unless there is a strong reason to use PNG.
- Capture the disc face/label as clearly as possible.
- Do not overwrite with a lower-quality image later.
- If photo capture fails, record the failure in `source.json`.

Optional additional photos are allowed:

```text
disc-photo-raw.jpg
disc-photo-cropped.jpg
disc-photo-enhanced.jpg
```

But `disc-photo.jpg` should be the canonical one.

### 3. `source.json`

This is the main metadata handoff file. It preserves everything the ripper knows before Beets touches the album.

The importer preserves this file beside the imported album using Beets' extrafiles behavior.

Use this schema as the target.

```json
{
  "schema_version": 1,
  "ripper": {
    "name": "YOUR_RIPPER_APP_NAME",
    "version": "0.1.0",
    "host": "hostname-or-device-name"
  },
  "disc": {
    "folder_name": "2026-05-14_1832_disc-000421",
    "disc_counter": 421,
    "inserted_at": "2026-05-14T18:28:03-07:00",
    "rip_started_at": "2026-05-14T18:28:11-07:00",
    "rip_finished_at": "2026-05-14T18:34:44-07:00",
    "ejected_at": "2026-05-14T18:35:02-07:00",
    "ready_at": "2026-05-14T18:35:18-07:00",
    "timezone": "America/Los_Angeles"
  },
  "drive": {
    "device": "/dev/sr0",
    "model": "PIONEER BD-RW BDR-XD07",
    "serial": null,
    "read_offset": null
  },
  "audio": {
    "format": "flac",
    "sample_rate_hz": 44100,
    "bits_per_sample": 16,
    "channels": 2,
    "track_count": 12,
    "total_duration_seconds": 3184,
    "secure_rip": true,
    "accuraterip_verified": null
  },
  "identifiers": {
    "musicbrainz_disc_id": null,
    "freedb_disc_id": null,
    "cd_toc": null,
    "upc": null,
    "isrcs": []
  },
  "detected_metadata": {
    "album_artist": null,
    "album": null,
    "year": null,
    "label": null,
    "catalog_number": null,
    "tracks": [
      {
        "track": 1,
        "title": null,
        "artist": null,
        "duration_seconds": 241,
        "isrc": null,
        "filename": "01 Track.flac"
      }
    ]
  },
  "physical_disc": {
    "photo": "disc-photo.jpg",
    "photo_captured": true,
    "photo_captured_at": "2026-05-14T18:35:12-07:00",
    "photo_device": "camera-name-or-id",
    "photo_notes": null,
    "label_text_guess": null,
    "appears_burned": null,
    "handwritten": null
  },
  "files": [
    {
      "path": "01 Track.flac",
      "kind": "audio",
      "size_bytes": 25123456,
      "sha256": "optional-sha256-here"
    },
    {
      "path": "disc-photo.jpg",
      "kind": "photo",
      "size_bytes": 1048576,
      "sha256": "optional-sha256-here"
    },
    {
      "path": "rip.log",
      "kind": "log",
      "size_bytes": 12345,
      "sha256": "optional-sha256-here"
    }
  ],
  "status": {
    "rip_success": true,
    "photo_success": true,
    "ready": true,
    "warnings": [],
    "errors": []
  }
}
```

### 4. `rip.log`

This should be a plain-text log of the rip.

Include:

- Start/end time.
- Drive used.
- Ripping command/tool used.
- Track list.
- Read errors/retries.
- Secure-rip or AccurateRip results if available.
- Any metadata found during ripping.
- Photo capture result.
- Final ready marker creation.

Example:

```text
[2026-05-14T18:28:03-07:00] Disc inserted: /dev/sr0
[2026-05-14T18:28:11-07:00] Rip started
[2026-05-14T18:34:44-07:00] Rip finished: 12 tracks, format=FLAC
[2026-05-14T18:35:02-07:00] Tray ejected
[2026-05-14T18:35:12-07:00] Disc photo captured: disc-photo.jpg
[2026-05-14T18:35:18-07:00] READY marker written
```

### 5. `READY`

Marker file. Contents can be minimal.

Example:

```text
ready_at=2026-05-14T18:35:18-07:00
schema_version=1
```

---

## Failure Behavior

Do not mark a failed rip as `READY` unless the failure is intentionally meant for review.

### Audio rip failure

If audio extraction fails, do this:

```text
~/music-pipeline/failed/2026-05-14_1832_disc-000421/
```

or leave it in a non-ready state:

```text
~/music-pipeline/inbox/2026-05-14_1832_disc-000421/
  rip.log
  source.json
  FAILED
```

Do not create `READY` for failed audio extraction.

### Photo failure

Photo failure should not necessarily block the rip from being imported.

If audio rip succeeds but photo capture fails:

- Write `source.json` with `photo_success: false`.
- Add the error to `status.warnings` or `status.errors`.
- Create `READY` if the audio files are otherwise valid.

Example `source.json` section:

```json
{
  "physical_disc": {
    "photo": null,
    "photo_captured": false,
    "photo_captured_at": null,
    "photo_device": "camera-name-or-id",
    "photo_notes": "Camera timeout after eject"
  },
  "status": {
    "rip_success": true,
    "photo_success": false,
    "ready": true,
    "warnings": ["Disc photo capture failed: camera timeout"],
    "errors": []
  }
}
```

### Unknown metadata

Unknown album or track metadata is fine.

Do not invent metadata.

Use `null` for unknown values and let Beets/Picard/manual review handle identification later.

---

## Burned CD Handling

Burned CDs are expected and should be preserved accurately.

For burned CDs:

- Do not force them to match a commercial album.
- Preserve the physical-disc photo.
- Preserve any handwritten label guess if OCR or manual entry is available.
- Set `physical_disc.appears_burned` to `true` if the app can detect this reliably.
- Set `physical_disc.handwritten` to `true` only if known or strongly detected.

Example:

```json
{
  "physical_disc": {
    "photo": "disc-photo.jpg",
    "photo_captured": true,
    "label_text_guess": "Matt Summer Mix 2003",
    "appears_burned": true,
    "handwritten": true
  },
  "detected_metadata": {
    "album_artist": "Various Artists",
    "album": "Matt Summer Mix 2003",
    "year": 2003,
    "tracks": []
  }
}
```

For unknown burned CDs, a good default album title is based on the folder name or label text:

```text
Unknown Burned CD 2026-05-14 18:32
```

---

## Photo Capture Requirements

The existing user requirement is:

> The app takes a picture of the CD when the CD-ROM is ejected.

Implement this carefully.

Recommended behavior:

1. Complete the audio rip.
2. Eject or open the tray.
3. Wait a short configurable delay for the tray to settle.
4. Capture image from configured camera.
5. Save image as `disc-photo.jpg`.
6. Optionally create a lower-resolution preview or crop.
7. Record photo metadata in `source.json`.
8. Only then write `READY`.

Config options to support:

```bash
DISC_PHOTO_ENABLED=true
DISC_PHOTO_CAMERA=/dev/video0
DISC_PHOTO_DELAY_SECONDS=2
DISC_PHOTO_OUTPUT=disc-photo.jpg
```

If the user already has a working photo mechanism, preserve it, but make sure it saves into the per-disc folder before `READY` is created.

---

## Suggested Config File

Add or support a config file similar to:

```yaml
music_pipeline:
  inbox_dir: "~/music-pipeline/inbox"
  working_dir: "~/music-pipeline/.ripping"
  failed_dir: "~/music-pipeline/failed"

ripping:
  output_format: "flac"
  secure_mode: true
  create_cue: true
  create_log: true
  eject_after_rip: true

photo:
  enabled: true
  camera_device: "/dev/video0"
  delay_after_eject_seconds: 2
  output_filename: "disc-photo.jpg"
  fail_rip_if_photo_fails: false

ready_marker:
  filename: "READY"
  write_last: true
```

Environment variables should be able to override these values:

```bash
MUSIC_INBOX_DIR
MUSIC_WORKING_DIR
MUSIC_FAILED_DIR
DISC_PHOTO_ENABLED
DISC_PHOTO_CAMERA
DISC_PHOTO_DELAY_SECONDS
```

---

## Implementation Tasks for Claude Code

Please modify or create the ripper code so that it satisfies the following checklist.

### Path handling

- [ ] Add configurable `inbox_dir`, defaulting to `~/music-pipeline/inbox`.
- [ ] Add configurable `working_dir`, defaulting to `~/music-pipeline/.ripping`.
- [ ] Add configurable `failed_dir`, defaulting to `~/music-pipeline/failed`.
- [ ] Expand `~` correctly.
- [ ] Create missing directories at startup.
- [ ] Validate write permissions before ripping starts.

### Disc session creation

- [ ] Generate a unique per-disc folder name.
- [ ] Create the working folder before ripping.
- [ ] Store all output for a disc inside that one folder.
- [ ] Never reuse an existing folder.
- [ ] Avoid unsafe path characters.

### Audio ripping

- [ ] Rip audio as FLAC by default.
- [ ] Preserve track order with zero-padded filenames.
- [ ] Write or capture a `rip.log`.
- [ ] Capture available disc identifiers, TOC, ISRC, UPC, CD-Text, or MusicBrainz disc ID if available.
- [ ] Record rip success/failure in `source.json`.

### Eject and photo capture

- [ ] Eject the disc or detect the eject event after the rip completes.
- [ ] Wait a configurable delay before taking the photo.
- [ ] Save the physical disc photo as `disc-photo.jpg`.
- [ ] Record photo success/failure in `source.json`.
- [ ] Do not let a photo failure destroy a successful audio rip unless explicitly configured.

### Source metadata

- [ ] Write `source.json` using schema version `1`.
- [ ] Include ripper name/version.
- [ ] Include timestamps with timezone offsets.
- [ ] Include drive/device info where available.
- [ ] Include audio summary and track count.
- [ ] Include available identifiers.
- [ ] Include detected metadata or `null` values.
- [ ] Include file list with paths and sizes.
- [ ] Include warnings/errors.

### Ready marker

- [ ] Write `READY` only after all other files are complete.
- [ ] Write `READY.tmp` first, then atomically rename to `READY`.
- [ ] Never write `READY` for failed audio rips.
- [ ] If audio succeeded but metadata is unknown, still write `READY`.
- [ ] If audio succeeded but photo failed, write `READY` and record a warning unless configured otherwise.

### Move into inbox

- [ ] Prefer writing in `working_dir` first.
- [ ] Move completed folder into `inbox_dir` only after ripping and photo capture are complete.
- [ ] Create `READY` after the folder is in the inbox, or ensure the final state appears atomically to the importer.

### Logging

- [ ] Log all major events.
- [ ] Include timestamps.
- [ ] Include command failures and retries.
- [ ] Include final output folder path.

---

## Acceptance Tests

After implementation, these cases should pass.

### Test 1: Successful commercial CD

Given a normal commercial CD:

- Ripper creates a unique folder.
- Audio files are FLAC.
- `rip.log` exists.
- `source.json` exists and is valid JSON.
- `disc-photo.jpg` exists.
- `READY` exists and was written last.
- Folder appears under `~/music-pipeline/inbox`.

Expected example:

```text
~/music-pipeline/inbox/2026-05-14_1832_disc-000421/
  01 Track.flac
  02 Track.flac
  disc-photo.jpg
  source.json
  rip.log
  READY
```

### Test 2: Burned CD with handwritten label

Given a burned CD:

- Audio files are still ripped.
- Disc photo is preserved.
- `source.json` does not invent commercial album metadata.
- `physical_disc.appears_burned` is `true` if detectable.
- `physical_disc.label_text_guess` is set only if OCR/manual input exists.
- `READY` exists if audio succeeded.

### Test 3: Unknown metadata

Given a CD with no metadata:

- Audio rip still succeeds.
- Unknown metadata fields are `null`.
- Folder is still marked `READY`.
- Beets can later decide whether to import or move to review.

### Test 4: Photo failure

Given a successful audio rip but camera failure:

- Audio files are preserved.
- `source.json` records `photo_success: false`.
- `status.warnings` includes the photo failure.
- `READY` exists unless `fail_rip_if_photo_fails` is configured true.

### Test 5: Audio rip failure

Given an unreadable CD:

- No `READY` file is created.
- Failure is recorded in `rip.log` and/or `source.json`.
- Folder is moved to `failed_dir` or left with a `FAILED` marker.
- No partial failed rip is presented as complete.

### Test 6: Importer compatibility

After a successful rip, run from the Docker stack directory:

```bash
./bin/process-ready-auto
```

Expected result:

- If Beets identifies the album confidently, music is copied into `~/music-pipeline/library`.
- Raw rip folder moves to `~/music-pipeline/archive`.
- If Beets cannot identify it, raw rip folder moves to `~/music-pipeline/review`.
- `disc-photo.jpg`, `source.json`, and `rip.log` are preserved with imported albums when possible.

---

## Do Not Do These Things

- Do not write directly to `~/music-pipeline/library`.
- Do not create `READY` before the photo and metadata sidecars are handled.
- Do not delete the raw rip after import; the Beets process handles archiving/review.
- Do not invent album metadata just to avoid nulls.
- Do not overwrite existing disc folders.
- Do not store all discs in one shared folder.
- Do not use filenames that depend on untrusted album metadata without sanitization.
- Do not require internet access for basic ripping.
- Do not make photo failure destroy a successful audio rip by default.

---

## Helpful Optional Enhancements

These are useful but not required for the first pass.

- Compute SHA-256 hashes for each output file and include them in `source.json`.
- Save CD TOC in a machine-readable form.
- Save MusicBrainz Disc ID if available.
- Save ISRCs per track if available.
- Save UPC/EAN if available.
- Save a CUE sheet.
- Save AccurateRip verification results.
- Add OCR of the disc label into `physical_disc.label_text_guess`.
- Add a small `manifest.txt` for human debugging.
- Add a `FAILED` marker for failed rips.
- Add retry behavior for camera capture.
- Add a dry-run mode.
- Add a command like `ripper doctor` to verify drive, camera, and folder permissions.

---

## Minimal Example Output

This is a valid completed disc folder:

```text
~/music-pipeline/inbox/2026-05-14_1832_disc-000421/
  01 Track.flac
  02 Track.flac
  03 Track.flac
  disc-photo.jpg
  source.json
  rip.log
  READY
```

Minimal valid `READY`:

```text
ready_at=2026-05-14T18:35:18-07:00
schema_version=1
```

Minimal valid `source.json`:

```json
{
  "schema_version": 1,
  "ripper": {
    "name": "YOUR_RIPPER_APP_NAME",
    "version": "0.1.0",
    "host": "ripper-host"
  },
  "disc": {
    "folder_name": "2026-05-14_1832_disc-000421",
    "inserted_at": "2026-05-14T18:28:03-07:00",
    "rip_started_at": "2026-05-14T18:28:11-07:00",
    "rip_finished_at": "2026-05-14T18:34:44-07:00",
    "ejected_at": "2026-05-14T18:35:02-07:00",
    "ready_at": "2026-05-14T18:35:18-07:00",
    "timezone": "America/Los_Angeles"
  },
  "audio": {
    "format": "flac",
    "track_count": 3,
    "secure_rip": true
  },
  "physical_disc": {
    "photo": "disc-photo.jpg",
    "photo_captured": true,
    "photo_captured_at": "2026-05-14T18:35:12-07:00"
  },
  "status": {
    "rip_success": true,
    "photo_success": true,
    "ready": true,
    "warnings": [],
    "errors": []
  }
}
```

---

## Final Goal

At the end of the ripper run, the only thing the post-rip stack needs is this:

```text
A complete per-disc folder inside ~/music-pipeline/inbox
with audio files, disc-photo.jpg, source.json, rip.log, and READY.
```

Once that exists, the user can run:

```bash
cd ~/cd-music-stack
./bin/process-ready-auto
```

The rest of the pipeline will handle tagging, organizing, review, and serving the music.
