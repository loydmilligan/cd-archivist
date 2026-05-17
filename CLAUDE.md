# CLAUDE.md

This file gives Claude Code project-specific instructions.

For workflow rules — commits, deployment, documentation cycle, version
control, escalation paths, backlog processes — see
[docs/WORKFLOW.md](docs/WORKFLOW.md). WORKFLOW.md governs HOW work
flows; CLAUDE.md governs HOW agents behave.

## Project summary

CD Archivist is a Raspberry Pi + Power Mac G4 archival system for ripping old CDs and preserving visual/physical metadata from burned mix CDs.

The system should:

1. Capture photos of each disc in the G4 tray.
2. Rip the CD using the G4.
3. Sync ripped audio to the Pi.
4. Pair photos and audio by timestamp/session.
5. Generate metadata using OCR/AI where available.
6. Preserve each disc as a durable archival object.
7. Serve cleaned music through a local music server such as Navidrome.

## Development priorities

Prioritize reliability and recoverability over elegance.

The pipeline should tolerate:

- Unknown discs
- Bad metadata
- Failed rips
- Ambiguous OCR
- User interruptions
- Multiple retries
- Network hiccups between G4 and Pi

## Architectural rules

- The G4 is a ripper, not the brain.
- The Pi owns camera, metadata, review, and library management.
- Do not require perfect metadata before continuing.
- Store raw captures and raw rips before any destructive transformation.
- Keep all generated metadata in editable plain-text or JSON sidecar files.
- Every disc gets a stable `disc_id`.
- Every automated decision should be traceable in logs or manifest fields.

## Preferred language and tooling

Use Python 3.11+ for Pi-side services and scripts.

Suggested libraries:

- `pydantic` for manifest models
- `watchdog` for filesystem events
- `opencv-python` for tray/disc detection
- `Pillow` for image processing
- `FastAPI` for local review UI/API
- `pytest` for tests
- `ruff` for linting

## Data model expectations

Every disc should eventually have a folder like:

```text
CD_0001/
  manifest.json
  captures/
  audio/
  logs/
  review/
```

The manifest should include:

- `disc_id`
- capture timestamps
- rip timestamps
- audio file list
- OCR text
- AI visual description
- physical description
- review status
- confidence
- source machine
- error history

## Coding style

- Favor small modules.
- Keep side effects explicit.
- Use typed functions.
- Log important file moves and decisions.
- Avoid hidden global state.
- Prefer idempotent operations.
- Never delete source media automatically.
- Use dry-run support for destructive operations.

## Testing expectations

Create tests for:

- Disc ID generation
- Manifest read/write
- Pairing capture sessions with rips
- File organization
- Review queue behavior
- Error handling

## Do not do

- Do not assume commercial album metadata exists.
- Do not assume burned CDs have readable titles.
- Do not overwrite existing disc folders.
- Do not delete raw captures.
- Do not delete raw rips.
- Do not require cloud AI to run the base pipeline.
- Do not require hardware hacks into the G4 front panel.

## Claude Code workflow

When making changes:

1. Inspect existing docs and code first.
2. Update design docs when changing architecture.
3. Add or update tests for logic changes.
4. Keep hardware assumptions documented.
5. Prefer simple working scripts before complex services.
