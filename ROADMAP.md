# ROADMAP.md

> Forward-looking backlog for **cd-archivist**. Sorted by horizon:
> what we'd build next, what we'd build soon, and what we'd revisit
> someday. Defect-shaped work lives in [ISSUES.md](ISSUES.md); historical
> per-sprint outcomes live in [CHANGELOG.md](CHANGELOG.md).

## Add / triage / resolve process

Anyone (operator or agent) can add an entry under the most appropriate
horizon section. Add the date. Commit as
`docs(repo): roadmap — add <slug>`.

At each sprint-planning kick-off, the orc-tower planner reviews
`## Next sprint` first and pulls items into the new plan; items not
pulled drop to `## Next milestone`. `## Someday / maybe` is the
long-tail bucket — items move up only when explicitly re-prioritized.

When an item ships, it's removed from this file (the CHANGELOG holds
the historical record). See [docs/WORKFLOW.md §10](docs/WORKFLOW.md)
for the full process.

---

## Next sprint

Items earmarked for the upcoming sprint plan (sprint-9, pending drive
RMA — see [ISSUES.md](ISSUES.md) drive-hardware-failure).

### Real-rig validation against sprint-7 UI

Once the RMA drive replacement arrives, run the deferred Wave-3 visual
smoke from sprint-7 against `cda.mattmariani.com`: every card state,
the brand mark, beets-candidates Apply end-to-end, header live-status
+ rig-stats with real numbers, drawer mode toggles, destructive
gates, polling cadence flip. Also: sprint-5's outstanding
`musicbrainz_disc_id` real-rig populate test.

Add date: 2026-05-17

### Track-identification data source

Sprint-7 stubbed `archivist/service/track_identification.py::
identified_tracks()` to return `set()` per
`D-track-identification-source` (lane-2 was unable to pick a clean
source mid-impl). Pick one of (a) parse `beets-import.log` for
per-track identified lines, (b) query the beets web API
(`http://cm4:8337/item/<id>`), or (c) re-derive from the candidates
endpoint results. Wire it, drop the stub, confirm the
`.track-cell--identified` outline appears post-Beets-ID.

Add date: 2026-05-17

### Tail-log filter UI

Backend `/api/logs/tail` already accepts (and ignores) per-rip /
per-card query params. Add the UI controls (filter chips in the
bottom-drawer head row) and the matching backend filtering. Carried
from sprint-6.5.

Add date: 2026-05-17

### Wire `operator_hints` into beets search

Album-level + per-track hints feed `beet import --set` or per-track
`musicbrainzngs` search + tag-write before `--singletons` import.
Carried from sprint-6's sprint-7 candidates → sprint-7's sprint-8
candidates → here. Closes the loop the sprint-7 candidates endpoint
opens.

Add date: 2026-05-17

### Force re-run beets ID action

Button on Beets-ID-bucket cards to nudge a re-import (e.g. after an
operator edits hints, the operator should be able to immediately
re-trigger the beets identification pass without waiting for any
state-machine retry window).

Add date: 2026-05-17

---

## Next milestone

Medium-term thematic groups; not the next sprint, but soon.

### Cloudflare Access + spooty service-token wiring

Sprint-11 shipped `/settings` unauthenticated (per `D-settings-unauth-v1`); spooty's own REST API has no auth (audited 2026-05-20 — stock `raiper34/spooty` with zero `@UseGuards`). Once the operator stands up Cloudflare Access in front of `cda.mattmariani.com` + `spooty.mattmariani.com`, the cda → spooty call needs `CF-Access-Client-Id` + `CF-Access-Client-Secret` headers (per `~/Projects/spooty-curator/CLOUDFLARE_ACCESS_SETUP.md`). Add `spooty_cf_client_id` + `spooty_cf_client_secret` to the `Config` dataclass + settings page; have `spooty_client.py` send the headers when set. Deferred until the operator finishes the Cloudflare Access setup — current testing is intentionally LAN-friendly.

Add date: 2026-05-20

### Review v2 — in-UI candidate selection

Sprint-6.5 deferred the in-UI beets candidate picker because of
`beets-CLI traceback-spam on tag-less flacs`. Sprint-7's
`/api/disc/<folder>/candidates` endpoint side-steps the beets CLI
entirely by going direct to musicbrainzngs — this unlocks a proper
Review v2 UI: in-card pickers per album candidate, per-track override
panel, MBID-paste fallback.

Add date: 2026-05-17

### `cdplay.service` decision revisited

Sprint-6 landed `D-cdplay-decouple-not-install`: the state machine
no longer touches the system's `cdplay.service`. Eject still works
end-to-end. Revisit only if the eject path fails in the wild — keep
the option on the radar but don't pre-emptively re-install the
dependency.

Add date: 2026-05-17

### Edit-by-hand library metadata

Library-bucket cards currently render the beets-imported metadata
read-only. Add per-field edits (album, artist, year) that round-trip
to a beets-modify shell-out + Navidrome rescan trigger. Carried from
sprint-6.5.

Add date: 2026-05-17

### Sort / filter controls per column

Kanban columns ship with sensible defaults today (review priority
desc, etc.). Add explicit operator-visible sort + filter controls
per column — useful as the library hits the hundreds.

Add date: 2026-05-17

### Cache `build_kanban_state` disk-walk

The `build_kanban_state` walk currently re-scans the music tree on
every `/api/kanban` poll. Once the library reaches hundreds of
discs, switch to inotify-driven invalidation (or fall back to mtime
polling).

Add date: 2026-05-17

### Alert / notification strip in header

H-C variant from the sprint-6.5 K1.2 sub-brainstorm. A horizontal
strip below the header for transient operator-visible alerts (drive
failure, beets backlog, MB rate-limit). Deferred each sprint so
far; revisit when the operator hits a moment where they'd actually
want it.

Add date: 2026-05-17

### Empty-tag MB-fallback suppression in beets

Beets' interactive import path generates traceback spam on tag-less
flacs even though sprint-7's direct musicbrainzngs candidates flow
sidesteps it for the UI. Either bypass the beets interactive path
entirely, or patch the empty-tag MB-fallback to fail closed. Carried
from sprint-5.

Add date: 2026-05-17

---

## Someday / maybe

Long-tail ideas we'd revisit only if priorities flip.

### Multi-drive support

Today the rig is single-CM4 / single-USB-drive. Multi-drive parallel
ripping would shrink the ingest tail on the backlog, at the cost of
state-machine + UI work. Out of scope through v1.

Add date: 2026-05-17

### Containerize cd-archivist itself

The beets + navidrome + jellyfin music stack is already in docker
on the CM4 (sprint-4 migration). cd-archivist itself stays
bare-metal-with-systemd-user-service because it needs USB device
access. Containerizing would require resolving the device-passthrough
story; deferred indefinitely.

Add date: 2026-05-17

### Live cam preview

Streaming the pi-camera feed into the UI when a disc is in the tray.
Useful for spot-checking dim labels. Out of scope today because the
camera fights the rip for USB bandwidth.

Add date: 2026-05-17

### AcoustID fingerprint submission

We *consume* AcoustID fingerprints in the candidates endpoint (stubbed
in sprint-7); contributing fingerprints back to the AcoustID corpus
would be a longer-tail contribution to the ecosystem.

Add date: 2026-05-17

### Light-mode theme

Status quo dark per K1.9 of the sprint-6.5 brainstorm. A light-mode
variant would require auditing every semantic-color decision against
WCAG contrast — non-trivial.

Add date: 2026-05-17

### Full voice pass

Every visible string reviewed against the design-system voice rules.
Sprint-7 did targeted; the full sweep has been deferred each
subsequent sprint as "not housekeeping-shaped." Worth doing when
the next operator-facing UI sprint surfaces.

Add date: 2026-05-17
