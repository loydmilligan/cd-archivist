# Build prompt — Library Manager (top-level shell + menu)

You're adding the **Library Manager** surface to cd-archivist — the FastAPI
operator UI you previously built from the cd-archivist handoff package. It
is a second top-level surface, separate from the existing rip kanban, but
visually of-a-piece with it. Same brand, same tokens, same voice, same
right-drawer / bottom-log idioms — different mental model.

The rip kanban is a *pipeline view* (one disc moves left-to-right). The
Library Manager is a *control panel view* of the post-rip side of the
whole CM4 music stack — queues, disk, scheduled jobs, library browse.

This pass scopes the **shell** only. Per-panel UX comes in follow-up
briefs.

A working visual reference lives at
`reference/Cd Archivist - Library Manager.html`. Open it in a browser
before you start. Three artboards: the landing state, a panel-selected
state, and the breadcrumb switcher in isolation with its dropdown open.

---

## 0. Read these first

| File | Why |
|---|---|
| `reference/Cd Archivist - Library Manager.html` | Open in a browser — the visual target |
| `reference/cda-library.jsx` | React reference for the shell. Translate to your stack. |
| `reference/cda-library-styles.css` | All new CSS (`.cda-lib-*`, `.cda-switcher-*`). Lift wholesale. |
| `reference/cda-styles.css` | Already in your repo. Make sure it matches — this prompt does not add anything to it. |
| `colors_and_type.css` | Already in your repo. No new tokens added. |

---

## 1. Files to drop into the cd-archivist repo

| From (this folder) | To (your repo) |
|---|---|
| `reference/cda-library-styles.css` | `static/css/library.css` — load AFTER `cda.css` |
| `reference/cda-library.jsx` | reference only — translate to FastAPI templates / your stack |
| `reference/*` (everything else) | `docs/reference/mashco-design-system/cd-archivist-library/` |

The new CSS is self-contained — it only references Mash Co. tokens already
in your `tokens.css`.

---

## 2. Non-negotiable decisions

### Surface switcher — brand-lockup breadcrumb

The `cd/a` brand mark becomes the navigation primitive. Recipe:

```
[cd/a]  ·  rip ▾   |   cda-pi · 192.168.6.38:8228   |   live chip   |   rig stats   |   nav buttons
```

Click the `rip ▾` button opens a small dropdown listing every surface
(currently `rip` and `library`). Each row carries a one-line telemetry
hint (e.g. `4 ripping · 2 review` for rip, `3 inbox · 1 download` for
library). Active surface shows a moss check.

This recipe is final. The header's other clusters (live chip, rig stats,
nav buttons) are unchanged across both surfaces. No left rail. No
header tabs.

### Rig stats — identical across surfaces

The five rig-stats cells (`Ripped · In review · Partial · Storage ·
Uptime`) stay identical on both surfaces. They're chassis-level telemetry,
not rip-specific. Don't swap cells out when Library is active. Per-surface
counters belong in the panel menu rows inside Library (e.g. `Inbox · 3`,
`Downloads · 1 queued · 1 error`).

### Library shell — left sidebar + viewport

The Library surface is a two-column shell inside the main content area:

```
┌──────────────────────────────────────────────────────────────┐
│ Header (breadcrumb switcher · rig stats · nav)               │
├──────────┬──────────────────────────┬───────────────────────┤
│ Library  │ Library viewport         │ Right drawer (340px)  │
│ sidebar  │ (landing grid OR panel)  │ idle: "Select an item │
│ (220px)  │                          │ to see details"       │
├──────────┴──────────────────────────┴───────────────────────┤
│ Bottom daemon log strip (shared with kanban)                 │
└──────────────────────────────────────────────────────────────┘
```

### Landing state on entry

When the operator enters Library and no panel is selected, the viewport
renders a **landing card grid** showing all 7 panels. Each card has:

- Eyebrow (e.g. "Downloads · spooty queue")
- Title (e.g. "Spotify → YouTube")
- One-sentence sub
- A small preview shape that hints at the panel content (per-track pip
  strip for Downloads; album rows with READY pip for Inbox; three
  horizontal usage bars for Disk; recent-imports list for Library; three
  blurred lines for v2 ghosts)

After the first click, the sidebar drives. To return to the grid, click
the "Library" entry in the breadcrumb dropdown — `/library` (no panel
selected) renders the grid.

### Sidebar — grouped panel list, all 7 always visible

```
QUEUES
  ↓  Downloads      [1]   ← v1 primary
  ▣  Inbox          [3]   ← v1 primary

HEALTH
  ◧  Disk                 ← v1 primary

BROWSE
  ♪  Library              ← v1 primary

COMING · v2
  ?  Review         soon  ← v2 ghosted, not clickable
  ≡  Recent imports soon  ← v2 ghosted, not clickable
  ⏱  Cron/scheduler soon  ← v2 ghosted, not clickable
```

v2 entries render at 42% opacity, are non-interactive (`cursor:
not-allowed`), and carry a small `soon` chip on the right.

---

## 3. Panel inventory + decided labels

| ID | Label in UI | Sub-line | Group | Status |
|----|-------------|----------|-------|--------|
| `downloads` | **Downloads** | `spooty queue` | Queues | v1 primary |
| `inbox` | **Inbox** | `cd rips · downloads` | Queues | v1 primary |
| `disk` | **Disk** | `usage` | Health | v1 primary |
| `library` | **Library** | `browse + jump` | Browse | v1 primary |
| `review` | **Review** | `soon` | Coming · v2 | v2 ghost |
| `recent` | **Recent imports** | `soon` | Coming · v2 | v2 ghost |
| `cron` | **Cron / scheduler** | `soon` | Coming · v2 | v2 ghost |

**Decided open questions from the brief:**

- **Spooty panel label is "Downloads"** — operator-task language up
  front. The "via spooty" tag goes in the sub-line, not the primary label.
- **Disk panel at-a-glance shape**: three stat cells with horizontal
  usage bars. One per mount (`/`, `/mnt/seagate`, `/mnt/archive`). No
  treemap, no sparkline. Bar color follows percent: pulp under 60%,
  amber 60–85%, ember above 85%.
- **Library panel scope**: thin teaser only — `Search · 10 most-recent
  imports · big "Open Navidrome ↗" CTA`. Don't try to reimplement
  Navidrome.
- **v2 ghost ordering**: grouped, not prioritized. Review and Recent are
  read-only viewers; Cron is health. Group them under "Coming · v2."

---

## 4. Panel header + placeholder pattern (this pass)

When a panel is selected in the sidebar, the viewport renders:

1. **Panel header** — eyebrow + h1 + sub + (optional) right-aligned
   stat cells matching the rig-stats group style
2. **Honest placeholder** — a dashed-border card with 3 ghost rows and
   an "in design" tag explaining that per-panel UX is deferred to a
   per-panel brief

This shape is the same for all 4 primary panels in this pass. The
per-panel briefs will replace the placeholder body with real panel UX
later, but the header pattern stays.

```html
<div class="cda-lib-panel">
  <header class="cda-lib-panel-head">…</header>
  <div class="cda-lib-panel-empty">
    <!-- 3 ghost rows -->
    <div class="cda-lib-panel-empty-foot">
      <span class="tag">in design</span>
      <span>UX is intentionally undecided in this pass…</span>
    </div>
  </div>
</div>
```

---

## 5. Right drawer + bottom log — reserved, shared

The right drawer (340px, sticky) renders an **idle state** for every
Library panel in this pass:

> "Select an item to see details."

Per-panel drawer modes (similar to the kanban's drive-status / card-detail
modes) come in follow-up briefs.

The bottom daemon log is **shared globally** with the rip kanban — same
DOM element, same data source, same collapsed-by-default 36px → 240px
expand behavior. Do not duplicate it per surface. Mount it at the app
level, beneath both `<main>` regions.

---

## 6. URL structure

```
/                                     → redirects to /rip
/rip                                  → existing kanban
/library                              → Library Manager, landing card grid
/library/downloads                    → Downloads panel
/library/inbox                        → Inbox panel
/library/disk                         → Disk panel
/library/library                      → Library browse panel (yes, the name is unfortunate but the URL is honest)
```

The breadcrumb switcher targets `/rip` and `/library` (root) directly.
The Library sidebar updates the URL to `/library/{panelId}` on click.
Browser back/forward should swap the active panel.

---

## 7. Things to AVOID (specific to this surface)

- **Don't render the Library as a second kanban.** Pipeline-as-mental-model
  belongs to /rip. Library is a control panel — cards, lists, stat blocks.
  Never columns scrolling vertically.
- **Don't add a fifth semantic color.** Disk at 90%+ uses `--ember`. Disk
  60–85% uses `--amber`. Anything genuinely needing a new state is a
  conversation, not a unilateral choice.
- **Don't relocate the daemon log or rig stats.** They're chassis-level
  and shared.
- **Don't auto-design the per-panel UX.** The brief explicitly defers
  this. Ghost it cleanly and stop.
- **Don't put navidrome / beets / spooty branding in the panel labels.**
  Operator-task language — "Downloads", "Inbox", "Disk", "Library".
  Implementation detail goes in the sub-line.
- **Don't fight the rip kanban's column scroll.** No left rail. The
  breadcrumb switcher costs zero horizontal real estate; preserve that.

---

## 8. Open for follow-up briefs

These are deliberately undecided in this pass — flag them in your build
notes so they can be picked up in the per-panel briefs:

- **Downloads panel UX** — list density, per-track expand state, retry
  affordances, submit-playlist flow, error recovery
- **Inbox panel UX** — row density, READY marker semantics, import-now
  trigger, multi-select for batch import
- **Disk panel UX** — beyond the three stat cells: drilldown breakdowns
  (inbox vs library vs archive vs spooty per-mount), trend over time,
  cleanup affordances
- **Library browse UX** — search input behavior, recent-imports tail
  density, "Open Navidrome" deep-link parameters
- **Right drawer modes per panel** — what details surface when a row is
  selected in each panel
- **Multi-select + batch actions** — universal pattern across queue-style
  panels (Downloads, Inbox, Review)
- **Refresh cadence** — adaptive polling per panel (Downloads: 1s during
  an active download? Inbox: 5s steady? Disk: 30s?)
- **v2 panel order + grouping** — should Cron move under Health when it
  ships? Should Review/Recent group with the import flow?

---

## 9. Definition of done

- [ ] `/library` route renders the Library Manager shell inside the cda
  app (same header, same bottom log, same right drawer slot)
- [ ] The brand-lockup breadcrumb switcher works: click `cd/a · rip ▾`
  opens the dropdown, picking a surface navigates
- [ ] Header rig stats stay identical across `/rip` and `/library`
- [ ] Library sidebar lists all 7 panels in the grouped order (Queues /
  Health / Browse / Coming · v2)
- [ ] v2 entries are visibly ghosted (42% opacity, `soon` chip, not
  clickable)
- [ ] `/library` (no panel) renders the landing card grid with previews
  matching the reference HTML
- [ ] `/library/{panelId}` renders the panel header + "in design"
  placeholder for each of the 4 primary panels
- [ ] Right drawer renders the idle state on every Library route
- [ ] Bottom daemon log is the same element on both surfaces, not
  duplicated
- [ ] Browser back/forward swaps the active panel without re-rendering
  the full shell
- [ ] No console errors. No raw hex literals.

When you're done, open `reference/Cd Archivist - Library Manager.html`
side-by-side with your build and visually compare each artboard.
