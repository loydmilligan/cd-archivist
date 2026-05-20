# Library Manager — handoff package

This package adds the **Library Manager** surface to cd-archivist — a
second top-level surface alongside the existing rip kanban.

This pass scopes the **shell** only:
- Top-level navigation between Rip and Library (brand-lockup breadcrumb)
- Library left sidebar listing all 7 planned panels
- Landing card grid for the no-panel-selected state
- Per-panel header + honest "in design" placeholder

**Per-panel UX is deliberately deferred.** Follow-up briefs (one per panel)
will replace the placeholder body. The shell, switcher, and panel
inventory are settled.

## What's in this folder

```
library-manager-handoff/
├── README.md                          ← you are here
├── handoff/
│   └── Build prompt.md                ← paste this into Claude Code
└── reference/
    ├── Cd Archivist - Library Manager.html   ← open in browser — visual target
    ├── cda-library.jsx                  ← React reference for the shell
    ├── cda-library-styles.css           ← NEW CSS (.cda-lib-*, .cda-switcher-*) — copy into your repo
    ├── cda-styles.css                   ← already in your repo from cd-archivist build
    ├── cda-chrome.jsx                   ← reference for header / drawer / log atoms
    ├── cda-components.jsx               ← reference for column / card atoms
    ├── cda-data.jsx                     ← RIG / DAEMON_LOG fixture
    └── colors_and_type.css              ← Mash Co. tokens (already in your repo)
```

## Where each file goes in your repo

| From here | To your repo |
|---|---|
| `reference/cda-library-styles.css` | `static/css/library.css` — load AFTER `cda.css` |
| `reference/*` (everything else) | `docs/reference/mashco-design-system/cd-archivist-library/` — keep as reference, do not serve |

## Decided open questions (from brief)

- **Spooty panel label** = **Downloads** (operator-task language). "via
  spooty" goes in the sub-line, not the primary label.
- **Library browse scope** = thin teaser only (search + recent + jump
  to Navidrome CTA). Don't try to reimplement Navidrome.
- **Disk panel shape** = three stat cells with horizontal bars per
  mount. No treemap, no sparkline.
- **v2 ordering** = grouped (Coming · v2 group at the bottom of the
  sidebar), not prioritized.

## What to do

1. Drop the files in (table above)
2. Open `reference/Cd Archivist - Library Manager.html` in a browser
   and explore the three artboards
3. Paste the contents of `handoff/Build prompt.md` into Claude Code,
   along with: *"read the files in docs/reference/mashco-design-system/cd-archivist-library/
   before you start — especially the .css file and the .jsx file."*

## Notes for Claude Code

- The new CSS lives in **one file** — `cda-library-styles.css`. It does
  not modify `cda-styles.css` from the prior build. Load order matters:
  base tokens → cda → library.
- The breadcrumb switcher replaces the brand-mark slot in the header.
  Keep the `cd/a` mark visually intact (extruded recipe).
- The bottom daemon log is **shared**, not duplicated. Mount it once at
  the app level.
- Per-panel UX is intentionally undecided. Don't unilaterally design
  Downloads / Inbox / Disk / Library — they get per-panel briefs.

## What's coming next

The brief explicitly defers per-panel UX. Expect follow-up briefs for:

1. **Downloads** (spooty queue) — drill-in, retry, submit, error recovery
2. **Inbox** — album-folder rows, READY semantics, import-now flow
3. **Disk** — drilldown breakdowns, cleanup affordances
4. **Library browse** — search + recent + jump

Then the v2 set (Review, Recent imports, Cron / scheduler).
