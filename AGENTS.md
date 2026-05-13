# AGENTS.md

Project agent roles and responsibilities.

## 1. Archivist Agent

Purpose:

- Protect source material.
- Ensure every disc gets a durable identity.
- Preserve photos, rips, logs, and metadata together.

Responsibilities:

- Create stable disc IDs.
- Maintain manifest files.
- Track review status.
- Avoid destructive changes.

## 2. Camera Agent

Purpose:

- Capture usable images of naked CDs in the G4 tray.

Responsibilities:

- Detect tray open/closed state.
- Capture image bursts.
- Store raw images.
- Pick representative images.
- Record lighting/camera metadata where available.

Future capabilities:

- Detect glare.
- Request recapture.
- Crop disc area.
- Detect blank/unlabeled discs.

## 3. Rip Ingest Agent

Purpose:

- Receive ripped audio from the G4.

Responsibilities:

- Watch incoming rip folder.
- Detect rip completion.
- Avoid importing partial rips.
- Move/copy audio into the correct disc folder.
- Keep raw imports intact.

## 4. Pairing Agent

Purpose:

- Match visual capture sessions with ripped audio sessions.

Responsibilities:

- Pair by timestamp.
- Handle ambiguous matches.
- Mark uncertain matches for review.
- Never guess silently.

## 5. Metadata Agent

Purpose:

- Extract metadata from images and audio.

Responsibilities:

- OCR visible text.
- Generate physical disc descriptions.
- Identify likely disc type.
- Store confidence levels.
- Mark uncertain results for review.

The metadata agent must never block the core archival flow.

## 6. Review Agent

Purpose:

- Help the human quickly approve or fix uncertain discs.

Responsibilities:

- Expose a local web UI or structured review files.
- Show disc photos and track list together.
- Allow title/status edits.
- Track accepted/rejected/needs-review states.

## 7. Music Library Agent

Purpose:

- Move reviewed or accepted discs into the listening library.

Responsibilities:

- Organize files for Navidrome or similar.
- Preserve mix-CD ordering.
- Keep unknown discs findable.
- Avoid flattening mixes into unrelated album metadata prematurely.

## Guiding principle

The system should be an archival assistant, not a gatekeeper.

It should capture and preserve first, then invite cleanup later.
