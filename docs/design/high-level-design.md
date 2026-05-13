# High-Level Design

## Problem

A collection of old CDs includes both commercial albums and burned mix CDs. Many burned discs have little or no digital metadata. Some have handwritten labels or visual clues that are historically meaningful.

Manual metadata entry would be tedious and would slow the ripping process.

## Goal

Create a semi-automated archival station that:

- Rips CDs using an old Power Mac G4.
- Captures photos of each physical disc using a Raspberry Pi camera.
- Extracts visible text and physical descriptions.
- Pairs image metadata with ripped audio.
- Preserves each disc as an archival object.
- Makes the resulting library usable through a music server.

## Non-goals

- Perfect automatic metadata for every disc.
- Electrical modification of the G4.
- Blocking rips until metadata is corrected.
- Replacing human review entirely.
- Deleting source files after processing.

## System components

### Power Mac G4

Role:

- Optical drive host
- CD ripper
- Auto-eject machine
- Audio sync source

The G4 should run the simplest reliable ripping setup available, such as iTunes or XLD.

### Raspberry Pi

Role:

- Camera host
- Capture controller
- Metadata processor
- Pairing engine
- Review queue
- Music library host
- Optional Navidrome host

### Camera

Role:

- Capture label-side images of naked discs while they sit in the tray.

Could be:

- Pi Camera Module
- USB webcam

### Storage

The Pi should maintain durable archival storage.

Recommended structure:

```text
/srv/cd-archivist/
  captures/
  incoming-rips/
  discs/
  review/
  logs/

/srv/music/
  Albums/
  Mix CDs/
  Unknown/
```

## Pipeline

### 1. Disc capture

Trigger options:

- Camera-based tray detection
- Limit switch
- Magnetic reed switch
- Manual capture button
- G4 sends SSH trigger

Initial recommendation:

Start with a manual Pi-side capture command or button, then add tray detection later.

### 2. Rip

The G4 imports the CD and ejects it.

The ripper should prefer:

- ALAC or FLAC for archival quality
- Error correction enabled if using iTunes
- Rip logs if using XLD

### 3. Sync

The G4 copies completed rips to the Pi.

Possible mechanisms:

- `rsync` from G4 to Pi
- Pi pulls from G4
- Shared network folder

### 4. Pairing

The Pi pairs the newest capture session with the newest completed rip session.

Primary pairing method:

- Timestamp proximity

Other possible signals:

- G4 event messages
- Track count
- Rip duration
- User button/session ID

### 5. Metadata

The metadata process should create structured fields:

- Visible text
- OCR confidence
- Physical description
- Disc type
- Marker color
- Brand markings
- Condition
- Human-readable title guess
- Review needed flag

### 6. Review

Uncertain discs go to a review queue.

Review should show:

- Disc photos
- AI/OCR guess
- Track list
- Audio preview links if available
- Edit controls

### 7. Library publication

Reviewed or accepted discs are moved/copied into a music library.

Commercial albums may be organized by artist/album.

Mix CDs should preserve disc identity and track order.

## Disc folder layout

```text
CD_0001/
  manifest.json
  captures/
    disc_front_001.jpg
    disc_front_002.jpg
  audio/
    01 Track 01.m4a
  logs/
    capture.log
    rip.log
    metadata.log
  review/
    notes.md
```

## Manifest sketch

```json
{
  "schema_version": "0.1",
  "disc_id": "CD_0001",
  "created_at": "2026-05-12T12:00:00-07:00",
  "status": "needs_review",
  "captures": [],
  "rips": [],
  "metadata": {
    "visible_text": [],
    "physical_description": "",
    "probable_title": "",
    "confidence": "low"
  },
  "errors": []
}
```

## Failure handling

The system must handle:

- Capture but no rip
- Rip but no capture
- Multiple captures before one rip
- Multiple rips near one capture
- Failed AI/OCR
- Partial file sync
- Duplicate disc IDs
- User restarts

All such cases should land in review rather than being discarded.

## Guiding principle

Do not optimize for perfect automation.

Optimize for:

```text
low-friction capture
durable preservation
later correction
```
