---
title: cd-archivist — project overview
updated: 2026-05-16
status: living-doc
---

# cd-archivist

## Purpose

Get every CD in the sleeve into Navidrome, without operator drudgery. One CM4 owns the optical drive, the camera, the LED, storage, and the FastAPI surface. Insert a disc → it rips, photographs the label, fingerprints the audio, queries MusicBrainz, and either auto-applies into the library or parks in a review bucket with enough context for a one-click manual rescue.

The CD itself is the metadata artifact: TOC hash via libdiscid, AcoustID audio fingerprint, label photo, OCR text, and operator-supplied hints (Various Artists / Burned CD / album / per-track titles for mix CDs) all travel together in `source.json` next to the flacs.

## Pipeline

Four stages, left-to-right. Every disc is a card that transits through them.

1. **Capture** — cdparanoia rips audio to flac; pi camera shoots the disc label; ripper streams progress + sector errors per track.
2. **Beets ID** — automated. Fingerprint + disc-id lookup runs against MusicBrainz / AcoustID. Monitoring step; no operator input expected.
3. **Review** — beets couldn't auto-apply. Card surfaces a "why" (no match / weak match / no tags) and the operator drives a manual rescue: pick a beets candidate, paste an MBID, override with hints, or mark to skip.
4. **In Library** — clean import. Navidrome scans hourly; Jellyfin shares the same library.

Damaged or partial-rip discs stay in **Capture** with a red-shadow visual treatment and three actions: **process partial as-is**, **redo entire capture**, **pick tracks to (re-)rip**.

## UI

Single web surface at `cda.mattmariani.com`. Operator-facing only.

- **4-column kanban** with the pipeline stages. Each column scrolls independently; card-count badge in the column header.
- **Cards** carry title, per-track segment bar (green/empty/red/blue), one-line status, disc-photo thumbnail (replaced by album art once metadata confirms), and chips for VA / Burned / Mix / Partial / track count. **Cards evolve visually as they advance:** track segments gain an outline once beets identifies the track; artist/album chips glow when system-confirmed; operator-entered values render with a dashed border so you can tell asserted from confirmed at a glance.
- **Click a card** to inline-expand it (one at a time). Expanded body holds actionable controls in labeled sections: **Hints · Manual Steps · Damaged-Disc Actions**. Spacebar toggles expand when a card is focused; `?` tooltip surfaces keyboard nav.
- **Right-side drawer** is the heavy-detail surface. When no card is selected, it shows the live drive status: current track, sector, retries, photo-capture state, elapsed time. When a card is clicked, it swaps to the rip-log tail + full `source.json` + disc photo.
- **Bottom drawer** carries the daemon tail log. Collapsed by default; expand on demand. Sprint-7 will add per-rip and per-card log filters.
- **Header bar** is sparse: wordmark left, compact rig stats center (discs ripped / in review / partial), drawer-toggle + nav buttons right (navidrome, beets web UI).
- **Live updates** poll `/api/kanban` adaptively — 1s during an active rip, 5s when idle. Keeps the CM4 quiet while staying responsive at the moments that matter (eject prompts, photo capture).
- **Mobile** collapses to a single column with bucket tabs. Phone access is a "spot-check the rig" use case, not a primary surface.

## Design style

- **Dark mode by default**, Mash Co. Design System tokens (`--ink`, `--ok`, `--warn`, `--info`, `--meat-red`). Console-leaning aesthetic — terse, dense, honest about being a CM4 sidecar.
- **Pipeline-as-mental-model.** The kanban isn't a board of tasks; it's a visualization of where each disc is in the ingestion flow. Layout, sort defaults, and card-state evolution all reinforce left-to-right progress.
- **One-surface principle.** Everything an operator needs lives here. No ssh-ing to tail logs, no separate beets terminal, no jumping to Navidrome for status. Deep links out to navidrome / beets web UI when the operator wants more.
- **Confirmation gates are explicit.** Destructive actions (redo, rerip, delete) require a confirmation step. Auto-apply happens only when beets is confident; everything else waits in review for the operator.
- **Operator hints are first-class data.** VA / Burned / Artist / Album / per-track entries persist in `source.json` and feed downstream beets searches (sprint-7+). The UI distinguishes operator-asserted from system-confirmed at every level.

## Stack

- **Daemon:** Python 3.13, FastAPI, uvicorn. Runs as a systemd user service on the CM4 (`cd-archivist.service`).
- **Ripping:** `cdparanoia` + `flac`. Disc-id via `libdiscid` (`discid` Python pkg).
- **Tagging:** `beets` in a Docker container alongside `cd_navidrome` + `cd_jellyfin` on the same CM4. `musicbrainzngs` for direct MB queries; AcoustID for fingerprinting.
- **Storage:** flat directory layout under `/srv/music/{inbox,review,library,archive,failed}/` — disk is the canonical source of truth; the kanban derives state by walking it.
- **Access:** local network (`192.168.6.38:8228`) + Cloudflare tunnel (`cda.mattmariani.com`) for remote check-ins.

## Out of scope

Multi-drive rigs · containerized cd-archivist itself · live cam preview · AcoustID fingerprint submission · editable per-track metadata in the UI · multi-user auth.
