# CD Archivist

Get every disc in the sleeve into Navidrome, without operator drudgery. One CM4 owns the optical drive, the USB webcam, the LED light panel, storage, and the FastAPI review surface. Insert a disc — it rips, photographs the label, fingerprints the audio, queries MusicBrainz, and either auto-applies the result into the library or parks the disc in a review bucket with enough context for a one-click manual rescue.

## How it works

Four stages. Every disc is a card that transits left-to-right:

1. **Capture** — cdparanoia rips audio to FLAC; the webcam shoots the disc label under LED illumination; ripper streams progress per track.
2. **Beets ID** — automated fingerprint (AcoustID) + disc-id (libdiscid) lookup against MusicBrainz. No operator input expected.
3. **Review** — beets couldn't auto-apply. Card surfaces the reason and the operator picks a beets candidate, pastes an MBID, supplies hints (Various Artists / Burned / per-track titles), or marks to skip.
4. **In Library** — clean import. Navidrome scans hourly; Jellyfin shares the same mount.

Damaged discs stay in Capture with three rescue actions: process partial as-is, redo entire capture, or pick individual tracks to re-rip.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full component map, state machine, and API surface.

## Quick start

**Requirements:** CM4 with `cdparanoia`, `flac`, `libdiscid0`, `ffmpeg` installed; Docker running `beets` + `navidrome`; Tasmota LED panel reachable at `http://192.168.5.186`.

```bash
git clone <repo>
cd cd-archivist
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

**Run tests:**

```bash
pytest
```

**Run the daemon (development):**

```bash
python -m archivist
```

**Deploy to the rig (CM4):**

```bash
ssh cm4
cd ~/Projects/cd-archivist
git pull --ff-only origin master
pip install -e '.[dev]'
systemctl --user restart cd-archivist
```

**Access the UI:** `http://192.168.6.38:8228` on the local network, or `https://cda.mattmariani.com` via Cloudflare tunnel.

## Repo layout

See [`docs/FILE-LAYOUT.md`](docs/FILE-LAYOUT.md) for the full canonical tree schema — what belongs where, what doesn't belong tracked, and legacy areas to audit.

```
archivist/          production code (drivers / pipeline / state_machine / service / models)
tests/              pytest suite mirroring archivist/ subsystem-for-subsystem
docs/               architecture, workflow, features, design, runbooks, sprint coordination
CHANGELOG.md        release history (Keep-a-Changelog)
ROADMAP.md          three-horizon backlog
ISSUES.md           defect backlog
```

## Workflow & contributions

See [`docs/WORKFLOW.md`](docs/WORKFLOW.md) for commit conventions, branching strategy, CM4 deployment sequence, documentation cadence, versioning, and the add/triage flows for ROADMAP and ISSUES.

Short version: trunk-based on `master`; Conventional Commits (`feat/fix/docs/chore`); one commit per logical change; atomic commits with `Co-Authored-By` footer for agent work.

## Status

**Working today:**

- Full rip pipeline: cdparanoia → FLAC → disc-id + AcoustID fingerprint → MusicBrainz lookup → beets auto-apply or review queue
- 4-column kanban UI at `cda.mattmariani.com` with live polling, card-expand drawer, per-track segment bars, and operator-hints support
- Damaged-disc rescue actions (process-partial, redo, rerip-tracks)
- MusicBrainz candidates panel in the review UI (sprint-7)
- Library view with album art, captures, and audio playback
- systemd user service (`cd-archivist.service`) on the CM4

**Pending / known gaps:** drive hardware failure (PLDS DVD-RW DA8A6SH — RMA in progress); operator-hints not yet wired into beets search; track-identification data source stubbed.

See [`ROADMAP.md`](ROADMAP.md) for the forward backlog and [`ISSUES.md`](ISSUES.md) for the defect list.
