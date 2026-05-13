# CD Archivist

Automated archival pipeline for old commercial CDs, burned mix CDs, and unknown CD-Rs.

The project uses:

- A Power Mac G4 as the optical-drive ripping machine.
- A Raspberry Pi as the camera, metadata, storage, review, and music-server machine.
- A Pi camera or USB webcam aimed at the G4 CD tray.
- Optional AI/OCR to capture handwritten CD labels and physical descriptions.
- A structured library suitable for Navidrome or another self-hosted music server.

## Core idea

The CD itself is treated as a metadata artifact.

For each disc, the system captures:

- Disc photos
- OCR text
- AI-generated physical description
- Rip metadata
- Track files
- Logs
- Human review status

Example disc folder:

```text
CD_0042/
  manifest.json
  captures/
    disc_front_001.jpg
    disc_front_002.jpg
  audio/
    01 Track 01.m4a
    02 Track 02.m4a
  logs/
    rip.log
  review/
    notes.md
```

## High-level flow

```text
Disc placed in G4 tray
        ↓
Pi detects tray/disc or receives trigger
        ↓
Pi captures burst of photos
        ↓
G4 rips CD and ejects
        ↓
Audio syncs to Pi
        ↓
Pi pairs newest rip with newest capture session
        ↓
AI/OCR creates metadata
        ↓
Disc lands in library or review queue
```

## Current status

Scaffold only.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

Lint:

```bash
ruff check .
```

## Important design principle

Do not block ripping on perfect metadata.

The system should preserve context first, then allow cleanup later.

```text
Rip first.
Capture visual evidence.
Tag later.
Review only exceptions.
```

## Safety

This project should not require modifying or electrically tapping into the Power Mac G4. Prefer external sensing:

- Pi camera tray detection
- Limit switch
- Magnetic reed switch
- Manual capture button

The G4 should primarily do:

```text
read CD → rip audio → eject → sync files
```
