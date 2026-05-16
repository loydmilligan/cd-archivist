---
title: Candidate-disc kanban status page
status: draft
sprint-target: sprint-6
owner: pipeline
created: 2026-05-16
source: user conversation 2026-05-16 (orc orchestration session)
related:
  - docs/design/2026-05-16-in-ui-beets-review.md
  - sprint-5 D-beets-review-ui-mode (Option B web candidate selection)
---

# Candidate-disc kanban status page

Replaces the current single-line `GET /` status surface with a card-per-disc
kanban that tracks every candidate disc through its lifecycle.

## Terminology

- **Candidate disc**: a CD that has just been inserted into the drive. The
  pipeline creates a card the moment a disc is detected; the card accretes
  detail as each stage produces it.

## Card — collapsed view

Minimum content visible without expanding:

1. **Current status** (which kanban bucket it's in + sub-state if any).
2. **Process progress bar** — a percentage bar for the *current* stage
   (e.g. "rip 65%", "fingerprinting 30%").
3. **Per-track bar** — one segment per track. State colors:
   - **empty / grey** — not started
   - **blue** — in progress
   - **green** — completed successfully
   - **red** — failed (e.g. unreadable sector — see RATM rip, 2026-05-16)
4. **Visual** where available: disc-photo thumbnail once captured; cover art
   once beets resolves it.

Expand the card for: full metadata, rip log tail, source.json contents,
beets candidate list (when applicable), error detail.

## Kanban buckets (left → right)

1. **Capture** — rip (cdparanoia → flac) + photo (camera). Card lives here
   from disc-detect until both finish. Per-track bar drives the visual.
2. **Beets ID** — fingerprinting + MusicBrainz lookup runs. Card shows the
   top candidate's score as it lands.
3. **(TBD intermediate)** — placeholder. Likely either "Tagging / write" or
   "Awaiting confirm". User flagged uncertainty here; resolve at planning.
4. **Review** — terminal-for-now: beets couldn't auto-apply. Card pops out
   to the Review screen (next section).
5. **In Library** — terminal-success: album landed in `/music/` and is in
   the beets DB. Card stays visible (collapsed) for some recency window
   (TBD — last N or last hour?).

A card moves left-to-right only. Failures inside a bucket stay in that
bucket with red state; the operator chooses whether to retry or send to
review.

## Review screen (separate page)

Triggered by clicking a card in the Review bucket. v1 scope:

- List the cards currently in Review.
- For each card: surface *why* it landed there (e.g. "beets top score
  0.28 — below auto-apply threshold", "fingerprint returned no match",
  "duration mismatch on N tracks").
- Explain *what to do manually* to resolve: which beets command to run,
  which MusicBrainz URL to consult, where the files live on disk.
- No interactive beets controls in v1 — display + instructions only.

**v2 (out of scope for sprint-6):** in-browser beets candidate selection.
Most of the substrate already exists at `/api/review/*` and `/review/*`
(sprint-5 work — see `docs/design/2026-05-16-in-ui-beets-review.md`).
v2 wires the new kanban Review bucket into that existing review-folder UI.

## Damaged-disc handling (first-class UI scope)

Surfaced from the RATM rig (2026-05-16): two attempts in a row failed at
tracks 7–8 and 6 respectively, both on the same disc. The operator UI
must give a clean exit out of this state with three explicit actions —
all of them anchored to the same disc card.

When the rip stops (either fail-fast threshold hit or operator cancels
mid-rip via a "stop" button on the card), the card moves into a
**Damaged / Partial** sub-state inside Capture (or its own bucket — TBD
during plan-phase). The card surface offers three actions:

1. **Process partial as-is.** Take the cleanly-ripped tracks (1..N-1),
   skip the failed/remaining tracks, and route the partial album through
   the rest of the pipeline (Beets ID → Review or Library). The
   `source.json` is flagged `status.partial=True` with the included
   track indices so beets and downstream review know it's incomplete.
2. **Redo entire capture.** Discard all rip output, re-eject + re-insert
   prompt, and restart from track 1. Useful if the operator wants to
   clean / reseat the disc and try again.
3. **Pick tracks to (re-)rip.** Show a checkbox list of every track on
   the disc (from the TOC), pre-selected based on success/failure state.
   The operator can:
   - include/exclude the failed track(s) (e.g. include track 6 to retry
     it; exclude if known unreadable);
   - include tracks *after* the failure point (everything from track 7
     to end) for a partial-retry-and-merge flow;
   - any arbitrary subset.
   Submit re-rips only the selected tracks (cdparanoia takes track
   ranges) and merges with previously-successful tracks. `source.json`
   gets a per-track provenance trail showing which attempt each track
   came from.

Acceptance for damaged-disc UI:

- The three buttons exist on a damaged-state card and route to the
  three flows above.
- The checkbox-pick-tracks flow correctly invokes `cdparanoia -d ...
  <track-spec>` and writes the resulting flacs into the same disc
  folder as the prior successful tracks.
- `source.json` schema gains `status.partial` + per-track provenance
  fields; the manifest model is updated accordingly.
- Tests cover: (a) partial-as-is flow writes `status.partial=True` and
  hands off to beets; (b) redo flow clears the disc folder before
  restarting; (c) pick-tracks flow merges new + existing flacs and
  records provenance.

## Open questions for planning

1. **Bucket 3 identity.** What stage sits between "beets ID" and the
   terminal buckets? Candidates: tagging-write, awaiting-operator-confirm,
   embedart/replaygain post-processing.
2. **Card retention in "In Library".** Show forever, last N, or last
   time-window?
3. **Failed-rip handling.** Today (per 2026-05-16 RATM rip) a track-N
   read failure discards the whole rip — partial flacs (1..N-1) are
   deleted. Does a "rip failed" card land in Review with the partial set
   preserved, or stay in Capture as red until manually dismissed?
4. **Live update transport.** SSE on `/api/status/stream`, or polling
   `/api/status` at 1–2s cadence?
5. **Data source.** Today `LoopState` holds only one rip's worth of
   state. Card-per-disc requires either expanding LoopState to a list or
   reading from disk (inbox / review / library directories) + the active
   rip's in-memory state.

## Cross-references

- **Existing routes to extend:** `app.py::api_status` (line 115);
  `app.py::/review` family (lines 166–209).
- **Per-track failure detection:** `archivist/drivers/ripper.py` —
  cdparanoia stderr is already parsed for sector errors; needs to map
  sector ranges to track indices for the red-state visualisation.
- **Photo capture:** `archivist/drivers/camera.py` — disc-photo path
  lands in `source.json` (already present); card visual just needs the
  URL.
- **Beets candidate score:** lands via `archivist/service/beets_review.py`
  and `archivist/service/mb_client.py`; surface the top-score number on
  the Beets-ID bucket cards.

## Acceptance (sprint-6 framing — to refine during plan-phase)

- A test asserting the kanban renders correct buckets for a synthetic
  set of disc states (one in capture, one in beets-id, one in review,
  one in library).
- A test asserting per-track bar colors map correctly from rip log /
  source.json states.
- The Review screen lists every card in the Review bucket with the
  "why" explanation rendered.
- No regressions in `/api/status` consumers (keep backward-compatible
  fields if anything reads them; otherwise document the break).
