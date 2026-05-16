# In-UI beets review — design spec

**Status:** sprint-5 candidate
**Drafted:** 2026-05-16
**Source:** user request during sprint-4 smoke (Stone Temple Pilots rip landed in `/srv/music/review/` after beets quiet-skipped a no-AcoustID-match album; operator wanted to drive the review from the FastAPI UI instead of `docker exec -it cd_beets beet import`)

## Why

Sprint-4 closed the rip → READY → beets → library loop, but beets-in-quiet-mode skips any album it can't auto-match with high confidence. For burned CDs (the project's primary use case) this is the modal outcome: the audio fingerprint doesn't match the commercial pressing, beets gives up, and the folder lands in `/srv/music/review/` waiting for a human.

Today the only way to resolve a review is `ssh cm4 && docker exec -it cd_beets beet import --quiet-fallback=ask /review/<folder>/` — interactive terminal, requires SSH, no mobile-friendly path. Operator wants to drive review from the same FastAPI UI that shows the library.

## Scope (v1 — sprint-5)

Aim for **Option B — the full candidate-selection flow as a web UI** (per the 2026-05-16 conversation tradeoff). Smaller "Apply as-is" button is too coarse to be useful for actual reviews; xterm.js piping is more infra than the value justifies.

### Backend

- New `archivist/service/beets_review.py` module.
- New routes on the existing FastAPI app:
  - `GET /api/review/folders` → list of folders currently in `/srv/music/review/` (and `/srv/music/inbox/<>/ ` with READY markers that haven't been processed yet). For each: folder name, audio file count, total duration, current `source.json` if present.
  - `GET /api/review/<folder>/candidates?search=&mbid=` → query MusicBrainz for candidate releases. With no params: AcoustID auto-match (re-do beets' default). With `search`: MB text search. With `mbid`: direct release lookup. Returns ranked list with confidence scores, track-by-track diffs (filename → proposed title + duration delta).
  - `POST /api/review/<folder>/apply` body `{ "mbid": "..." }` → invoke `beet import -q --search-id <mbid> /downloads/<folder>/`. beets does the actual tag + copy. Returns final library path.
  - `POST /api/review/<folder>/use-as-is` → invoke `beet import -A /downloads/<folder>/` (no autotag, files land in library/ with directory-name-as-album). Last-resort.
- Implementation note: use the `musicbrainzngs` Python library directly for `GET /api/review/<folder>/candidates` (faster, no subprocess; beets' MB query path uses the same lib internally). For the actual import (`apply`, `use-as-is`), shell out to `docker exec cd_beets beet import ...` so beets owns the file move + DB write. Don't try to reimplement beets in Python.

### UI

- New tab / nav entry: `/review` (sibling to `/library`).
- Page shape (Mash Co. dressed):
  - List of review folders as cards (same card pattern as `/library`). Each card: folder name, audio count, "review now" button.
  - On click → `/review/<folder>` detail page:
    - Header: folder name + audio summary
    - **Search controls:** text input ("artist + album" hint) + "search MB" button, OR MBID input + "fetch by ID" button. Each fires the candidate-fetch endpoint.
    - **Candidate list:** top 5 (matching beets' default). For each: confidence %, artist - album, release year + label + catalog #, MBID, "Apply" button.
    - **Track diff:** clicking a candidate expands it to show filename → proposed-title + duration delta per track. Same layout beets shows in its terminal prompt. Highlights duration mismatches > 5s in `--amber`.
    - **Apply button** per candidate → fires `POST /api/review/<folder>/apply` with that MBID. Page shows the import progress (poll `/api/log?lines=20` for live beets output for ~15s).
    - **"Use as-is, no metadata" footer button** for truly unidentifiable discs.
  - On successful apply: card disappears from `/review`, new entry appears in `/library/<artist>/<album>/` (the existing library page already auto-picks up new files).

### Decision Log entries to land at sprint-5 plan time

- `D-beets-review-ui-mode` — adopt Option B (web candidate selection), reject Option A (one-shot buttons too coarse) and Option C (xterm.js too much infra). Justification: matches the operator's actual workflow + stays mobile-friendly without terminal emulation.
- `D-mb-query-direct-not-beets` — use `musicbrainzngs` directly for candidate queries; shell out to `beet import` only for the actual file operations. Beets' own MB plugin uses the same library; bypassing it for queries gives us faster responses + cleaner pagination + no terminal-prompt awkwardness.
- `D-review-folder-discovery` — `/review` aggregates folders from both `/srv/music/review/` (post-beets weak matches) and `/srv/music/inbox/<>/` with READY but no PROCESSING marker (pre-beets backlog). The two sources cover the "beets gave up" and "beets hasn't run yet" cases without a separate "stuck in inbox" surface.

## Out of scope for v1 (sprint-6+)

- Editable metadata: title / track-name corrections by hand. v1 is "pick a MusicBrainz release"; v1.5 might add "edit fields before applying."
- AcoustID fingerprint submission back to AcoustID DB (so the next burned-CD ripper on the same fingerprint gets a hit).
- Cover art upload during review.
- Batch operations across multiple folders.

## Important alignment with the disc-id capture work

This UI is **complementary** to capturing `musicbrainz_disc_id` at rip time (sprint-4 stretch, slipped). Disc-id matching is the *correct* answer for ripped audio CDs — even burned ones — as long as the track ORDER matches a known release. AcoustID only fails on the audio-stream-identity check; the disc-id is a CDDB-style lookup of (track count, track lengths) which is much more permissive.

Sprint-5 should land BOTH:
1. Disc-id capture at rip time (small, drivers-side) — high-confidence auto-matches go through without review.
2. This UI for the residual "truly unique mix CDs" that disc-id can't match either.

If we only land #1, the project is mostly self-driving but operator-blocked for genuine mix CDs. If we only land #2, every disc requires manual review even when MusicBrainz already knows it. Together, the system is automatic for known-album rips and ergonomic for everything else.

## Implementation notes

- Same race-condition pattern as the sprint-3 review-recapture endpoint: if `state in {RIP, EJECT, CAPTURE}`, 409 the import request — beets shouldn't fight the live ripper for the same folder.
- The post-rip hook (sprint-4) ALREADY fires `process-ready-auto` immediately. The "review" pile fills up because beets quiet-mode skips weak matches. We don't need to change the hook — we just need a path to act on what beets left for review.
- Mash Co. dressing: candidate list as cards with confidence % rendered as a horizontal progress bar (use existing `--ink-*` tokens). Apply button is `--accent` primary CTA. "Use as-is" is a quieter `--ink-3` secondary. Track-diff table uses `--mono` for filename column.
- Browser FLAC playback ALREADY works in `/library/<disc>/audio/<file>` (sprint-3 impl-library-asset-serving). Review page can reuse the same `<audio controls>` to let the operator preview a track before committing.
- The `musicbrainzngs` lib needs a User-Agent string and rate-limit awareness (MB throttles aggressively at 1 req/sec). Wrap in a `MBClient` class with built-in throttling.
