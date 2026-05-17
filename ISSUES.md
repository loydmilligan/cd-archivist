# ISSUES.md

> Defect-focused backlog for **cd-archivist** — bugs, regressions,
> known gaps, hardware faults. Forward-looking feature backlog lives
> in [ROADMAP.md](ROADMAP.md); per-sprint historical outcomes live in
> [CHANGELOG.md](CHANGELOG.md).

## Add / triage / resolve process

Anyone (operator or agent) can file an issue under `## Open` in
severity order (blocker > major > minor > cosmetic). Tag severity,
owner, repro. Commit as `docs(repo): issues — add <slug>`.

**Triage rule.** `blocker` and `major` issues get pulled into the
**active sprint**. If the active sprint is locked, escalate to
orc-tower and the operator immediately. `minor` and `cosmetic`
queue for the next sprint unless the current sprint has slack.

**Resolve flow.** When a fix commit lands: move the issue from
`## Open` to `## Resolved`, append the fix SHA, and commit as
`docs(repo): issues — close <slug>`. `## Resolved` is a permanent
record (we don't garbage-collect it). See
[docs/WORKFLOW.md §11](docs/WORKFLOW.md) for the full process.

---

## Open

Sorted by severity: blocker > major > minor > cosmetic.

### Drive hardware failure — PLDS DVD-RW DA8A6SH no longer reads TOCs

- Severity: blocker
- Owner: operator
- Repro: insert any audio CD; cdparanoia + libdiscid both fail to
  read the table-of-contents. Observed 2026-05-17 on the production
  rig. RMA in progress; replacement drive expected.
- Notes: this is the trigger for sprint-8 being a housekeeping
  sprint (see `D-housekeeping-no-code-changes` in
  `docs/coordination/sprint-8.md`). All real-rig validation is
  paused until the replacement arrives.

Add date: 2026-05-17

### Operator-hints not yet wired into beets search

- Severity: minor
- Owner: pipeline
- Repro: edit operator hints (artist, album, VA, burned) on a
  review-bucket card; observe that the next beets import does not
  yet consume them. The hints persist to `source.json` correctly;
  only the downstream beets call ignores them.
- Notes: carried from sprint-6's sprint-7 candidates. Sprint-7's
  direct-musicbrainzngs candidates endpoint (`D-mb-query-direct-not-
  beets`) reads the hints for the candidates UI flow; the beets
  import path still doesn't. Also tracked as a ROADMAP item.

Add date: 2026-05-17

### Track-identification data source is stubbed

- Severity: minor
- Owner: pipeline
- Repro: any post-beets-id card; the `.track-cell--identified`
  1px-white-inset outline never appears.
- Notes: sprint-7's `archivist/service/track_identification.py::
  identified_tracks()` returns `set()` per
  `D-track-identification-source` (the OPEN decision lane-2 was
  unable to pick a clean data source for mid-impl). Tracked as a
  ROADMAP item with three resolution options.

Add date: 2026-05-17

### Beets CLI traceback-spam on tag-less flacs in interactive import

- Severity: minor
- Owner: pipeline / operator
- Repro: `beet import` over a folder of flacs that have no embedded
  tags (which is what burned CDs typically produce). Beets'
  interactive MB fallback emits Python tracebacks even when the
  import ultimately succeeds.
- Notes: sprint-5 finding. Sprint-7's direct-musicbrainzngs
  candidates endpoint sidesteps the beets CLI for the UI flow, so
  the operator-facing surface is clean — but the underlying beets
  CLI path still has the issue when a manual `beet import` is run.

Add date: 2026-05-17

### `cdplay.service` install deferral — known and intentional

- Severity: minor
- Owner: operator
- Repro: `systemctl --user status cdplay.service` on the CM4
  shows an exit-5 warning on each rip cycle.
- Notes: sprint-6 settled `D-cdplay-decouple-not-install` — the
  state machine no longer claims/releases `cdplay.service` around
  drive operations. The exit-5 warning is harmless. Documented here
  so the issue isn't re-raised by a future agent or operator
  spot-check; revisit only if the eject path fails in the wild.

Add date: 2026-05-17

---

## Resolved

Newest first. Each entry retains its full prior body plus a
`Resolved by: <SHA>` footer (and is allowed to grow as we land
follow-ups against the same root cause).

_None yet — sprint-8 is the first sprint with this file._
