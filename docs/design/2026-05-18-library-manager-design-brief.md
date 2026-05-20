# Design brief — Library Manager (top-level shell + menu)

**Audience:** claude-design (Mash Co. design tool).
**Purpose:** Produce a top-level screen + navigation shell for a new **Library Manager** surface inside cd-archivist. All slices visible in the menu; only the shell + ghosted panels are built in this pass. Per-panel UX comes in follow-up briefs, one at a time.
**Companion doc (read first):** [`docs/LIBRARY-MANAGER-PROPOSAL.md`](../LIBRARY-MANAGER-PROPOSAL.md) — full problem framing, pipeline diagram, file layout, spooty API, auth notes.
**Predecessor handoff (style + tokens are inherited from here, do not redo):** [`docs/reference/mashco-design-system/cd-archivist/handoff/Build prompt.md`](../reference/mashco-design-system/cd-archivist/handoff/Build%20prompt.md)

---

## What we're asking for

A **second top-level surface** for cd-archivist called **Library Manager**, separate from the existing rip kanban but visually of-a-piece with it. Same brand, same tokens, same voice, same drawer/log idioms — different mental model.

The rip kanban is a *pipeline view* (one disc moves left→right through four columns). The Library Manager is a *control panel view* of the post-rip side of the whole CM4 music stack: queues, disk, scheduled jobs, library browse. It is **not** another kanban. It should feel like a sibling surface, not a re-skin.

In this first pass we want:

1. The navigation shape that gets you between the two surfaces.
2. The Library Manager **shell** — header context, panel layout, the menu listing every planned panel.
3. Ghosted/empty states for every panel so the operator (and we) can see the full intended scope at a glance, even though nothing is wired.

Per-panel interaction design (drill-in actions, list densities, expand-states) comes in follow-up briefs after we discuss each one. Don't over-spec the panels here — just establish their place, label, and ghost shape.

---

## Constraints inherited from the existing system

Hard inheritances from the cd-archivist build prompt — claude-design has already established these and they must not be re-litigated:

- **Tokens:** `colors_and_type.css` is the single source. Same `--ink-*`, `--mash-pulp`, `--moss/amber/ember/sky`, same fonts (Bricolage Grotesque display, Inter Tight body, JetBrains Mono).
- **Brand mark:** the chunky extruded `cd/a`. Do not flatten. Header lockup recipe is established.
- **Voice:** sentence case in source, mono shorthand for time/bytes, no emoji, no marketing language, operator-specific vocabulary (`inbox`, `review`, `library`, `archive`, `failed`, `beets`, `mbid`, `acoustid`).
- **Semantic colors:** four, no more. `--moss` success · `--amber` warn · `--ember` error · `--sky` info. If a panel needs a fifth state, raise it as an open question — don't invent.
- **Operator-asserted vs system-confirmed:** dashed border for asserted, solid + glow for confirmed. Applies wherever the Library Manager surfaces editable values.
- **Bottom daemon log:** the same collapsed-by-default 36px → 240px log strip runs across the bottom of *both* surfaces. It is global to cda, not per-surface.
- **No stock Tailwind palette colors.** Same anti-patterns as before.

---

## Top-level navigation — what we need from you

We want this as a **separate screen** from the rip kanban, with the same visual DNA but a clear "you're somewhere else now" signal. Open on the *shape* of the nav — propose what fits the system. Two starter options to react to, plus invitation to do better:

- **Option A — Header tabs**: two tabs in the header bar between the brand lockup and the rig stats: `Rip` (current kanban) and `Library` (new surface). Active tab uses pulp accent.
- **Option B — Left rail**: thin persistent rail on the left edge with icon-labels for each surface. Rip kanban becomes one rail entry alongside Library; rail also hosts a slot for whatever surfaces we add later (settings, archive).
- **Option C — Your shape**: if neither fits the operator-console aesthetic, show us. The constraint is: surface-switching must be one click, visible at all times, and the rig stats / live-status chip / brand lockup must remain in the header on both surfaces.

When the Library Manager is active, the header's center cluster (Ripped · In review · Partial · Storage · Uptime) should stay — it's rig-level state, not rip-specific. We may want to swap one cell for a Library-relevant counter; flag that and propose what.

---

## The Library Manager shell

Inside the Library surface, we need:

- A **panel menu** — operator's index into every panel. Open on whether this is a left sidebar, a top sub-nav, a grid of cards on a landing screen, or something else. The operator should be able to see *all* planned panels at once, including ghosted/coming-soon ones, so the surface advertises its own scope.
- A **panel viewport** — where the active panel renders. Use the same surface-2 (`--ink-2`) card treatment as the kanban cards. Density should match the kanban: dense, mono-friendly, comfortable on a 14" laptop but legible at arm's length on a wall-mounted Pi screen.
- **Right drawer** — same 340px sticky drawer as the kanban surface. Mode pattern is per-panel (TBD in follow-up briefs); for now just reserve the slot and show an idle state ("Select an item to see details").
- **Bottom daemon log** — shared with kanban. Do not duplicate.

---

## Panel inventory — what goes in the menu

From `LIBRARY-MANAGER-PROPOSAL.md`. v1 scope (primary, visible, ghost-shapes designed) and v2 scope (ghosted "coming" entries — muted, not interactive, but **visible in the menu so the operator sees the full intended surface**).

### v1 — primary panels (design ghost shapes for these)

1. **Spooty queue** — Spotify→YouTube downloader. Per-playlist rows with per-track sub-state. Source: spooty REST at `:3003/api`. Actions later: submit playlist, retry track, delete, retry whole playlist.
2. **Inbox queue** — `/srv/music/inbox/` (CD rips) + `/srv/music/inbox/spooty/` (spooty downloads). One row per album folder; show file count, size, last-modified, READY marker. Actions later: import now, mark READY.
3. **Disk usage** — `/`, `/mnt/seagate`, `/mnt/archive`. Per-surface breakdown (inbox vs library vs archive vs spooty). Informational. The 1 TB Seagate was just added; the operator needs to *see* where bytes live.
4. **Library browse** — read-only Subsonic API into Navidrome. Search, view album, deep-link out to Navidrome for playback. Read-only — edits go through beets, not here.

### v2 — ghosted "coming" entries (show in menu, muted)

5. **Review queue** — `/srv/music/review/` walks. Beets couldn't auto-apply.
6. **Recent imports** — tail of `/srv/music/logs/beets-import.log` + beets sqlite.
7. **Cron / scheduler health** — spooty cron next-run + last-run status + errors.

Ghost treatment: same row/card silhouette as a primary panel entry, opacity reduced, no hover state, and a small `soon` eyebrow or analogous marker — propose what fits the system. The operator should be able to read the label and understand what it will be without it competing for attention.

---

## What we want claude-design to produce

In the handoff packet:

1. **Updated header / nav recipe** — exact HTML/CSS for the surface switcher, whichever shape you pick, plus rationale for why.
2. **Library Manager shell** — a working static page (matching the cd-archivist prototype's React+Babel-in-HTML style) showing the panel menu, an active-but-empty viewport, the reserved drawer, and the shared log strip.
3. **Ghost shapes** for all 7 panels in the menu — v1 primary entries clickable (open into an empty viewport with the panel's header + an honest "not built yet — see brief" placeholder), v2 ghosted entries non-interactive.
4. **Updated `Build prompt.md`-style handoff doc** — same flavor as the existing one. Tells the implementing agent which files to copy, which existing files are now superseded (if any), what's non-negotiable about the nav recipe, anti-patterns specific to this surface.
5. **An "open for follow-up" section** — call out which per-panel decisions you deliberately did *not* make in this pass, so we know what to brief next.

---

## Things to AVOID

- **Don't make this a second kanban.** Pipeline-as-mental-model belongs to the rip surface. The Library Manager is a control panel; force a different layout idiom.
- **Don't introduce a sidebar pattern that fights the rip kanban's column-scroll.** If you choose a left rail, the rip surface keeps its four-column layout to the right of the rail unchanged.
- **Don't add a fifth semantic color.** If a panel (e.g., disk usage at 90% full) needs a "critical" treatment, use `--ember`. If you genuinely need a new state, raise it as an open question.
- **Don't auto-decide the per-panel UX.** The point of this brief is the shell. Resist the urge to fully design Spooty Queue. Ghost it, note your instincts in the open-follow-ups section, and move on.
- **Don't put navidrome/beets/spooty branding into the menu.** These are operator-implementation details. The panel labels should be operator-task language: "Inbox", "Library", "Disk", "Downloads" (or whatever reads cleanest for spooty — propose).
- **Don't relocate the daemon log or rig stats.** They're cda-global.

---

## Open questions to surface in your packet

- Spooty queue is operator-facing but the word "spooty" is internal. Should the panel label be "Spooty" (honest) or "Downloads" (operator-task)? Recommend a direction.
- Library browse is read-only here but Navidrome's own UI is a click away. Is the in-cda browse worth the surface area, or should this panel be a thin "jump to Navidrome" + recent-additions teaser?
- Disk panel — minimum at-a-glance shape: bar chart, sparkline, stat cells, or a small treemap? Operator looks at this maybe weekly, not continuously.
- The v2 ghosted entries — should they be ordered by priority (operator's likely next ask) or grouped (queues / health / browse)?

---

## Deliverable expectations

Same shape as the existing handoff:

- A `handoff/` directory inside `docs/reference/mashco-design-system/cd-archivist/` (or a sibling dir if you'd rather isolate this slice — propose).
- A working `.html` prototype demonstrating the nav switch and the Library shell with all menu entries visible.
- Any new tokens or CSS additions live next to the existing `cda-styles.css` — don't fork; extend.
- A `Build prompt.md` (or equivalently named) covering definition-of-done, files to copy, and per-panel TODOs.

---

## When this is done

We come back to this brief, take your handoff, implement the shell + ghosted panels in the FastAPI app, and then start the per-panel cycle: brainstorm Spooty Queue → brief → handoff → implement; repeat for Inbox, Disk, Library Browse, then the v2 set.
