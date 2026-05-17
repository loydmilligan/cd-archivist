# Build prompt — cd-archivist UI on the Mash Co. design system

You're building the operator-facing web UI for **cd-archivist**, a Python/FastAPI
daemon running on a CM4 that rips a backlog of CDs into Navidrome. The project
overview is the source of truth for what the surface does; this document is the
source of truth for **how it should look and feel**.

A working prototype lives at `Cd Archivist.html` in the design-system project.
Read it, the supporting JSX (`cd-archivist/cda-*.jsx`), and the styles
(`cd-archivist/cda-styles.css`) before you start. The prototype is React + Babel;
when you translate to your stack (FastAPI templates? HTMX? Svelte? Vue?) keep the
component shapes and CSS structure intact and reuse the token CSS verbatim.

---

## Files to pull from this project into the cd-archivist repo

Copy these into the FastAPI project (suggested layout: `static/css/` and
`static/img/brand/`):

| Source (here) | Dest (cd-archivist repo) | Why |
|---|---|---|
| `colors_and_type.css` | `static/css/tokens.css` | All CSS variables. Import this FIRST in every page. Do not redefine these tokens. |
| `cd-archivist/cda-styles.css` | `static/css/cda.css` | The kanban + card + drawer styles. Include after tokens. |
| `cd-archivist/brand/cd-a-favicon-32x32.png`<br>`cd-archivist/brand/cd-a-favicon-64x64.png`<br>`cd-archivist/brand/cd-a-favicon-180x180.png`<br>`cd-archivist/brand/cd-a-favicon-256x256.png`<br>`cd-archivist/brand/cd-a-favicon-512x512.png` | `static/img/brand/` | Favicon family. Transparent PNG, dark-first. |
| `cd-archivist/brand/cd-a-maskable-512.png` | `static/img/brand/` | PWA maskable / Android adaptive icon |
| `cd-archivist/brand/cd-a-apple-touch-180.png` | `static/img/brand/` | iOS home-screen icon |
| `cd-archivist/brand/manifest.webmanifest` | `static/manifest.webmanifest` | Wire all icon sizes |
| `Cd Archivist.html` + `cd-archivist/cda-*.jsx` | `docs/reference/` | Keep as reference; don't serve these directly |

Wire favicons into the base template:

```html
<link rel="icon" type="image/png" sizes="32x32"   href="/static/img/brand/cd-a-favicon-32x32.png">
<link rel="icon" type="image/png" sizes="64x64"   href="/static/img/brand/cd-a-favicon-64x64.png">
<link rel="icon" type="image/png" sizes="256x256" href="/static/img/brand/cd-a-favicon-256x256.png">
<link rel="apple-touch-icon" sizes="180x180" href="/static/img/brand/cd-a-apple-touch-180.png">
<link rel="manifest" href="/static/manifest.webmanifest">
<meta name="theme-color" content="#07090c">
```

---

## The cd/a brand mark — non-negotiable recipe

The brand mark is **chunky and extruded**. It is NOT a flat italic. Render it
exactly like this:

```html
<span class="cda-brand-mark">cd/a</span>
```

```css
.cda-brand-mark {
  font-family: var(--font-display); /* Bricolage Grotesque */
  font-weight: 800;
  font-style: italic;
  letter-spacing: -0.05em;
  line-height: 1;
  color: var(--mash-pulp);          /* #ff5b2e */
  -webkit-text-stroke: 1.5px var(--mash-pulp-edge);  /* #8a2d15 */
  paint-order: stroke fill;
  text-shadow:
    0 1px 0 var(--mash-pulp-edge),
    0 2px 0 var(--mash-pulp-edge),
    0 3px 0 var(--mash-pulp-edge),
    0 4px 0 var(--mash-pulp-edge),
    0 5px 0 var(--mash-pulp-edge),
    0 7px 10px rgba(0,0,0,0.5);
}
```

Six size variants (font-size + stroke + extrude depth):

| Where | Font size | Stroke | Extrude | Drop blur |
|---|---|---|---|---|
| Header | 22px  | 1.5px | 5 layers × 1px | 0/7/10 |
| Splash hero | 84px  | 2px   | 6 layers × 1px | 0/24/24 |
| Marketing hero | 240px | 2.5px | 6 layers × 4px | 0/30/36 |

For the actual favicon, use the PNGs that ship with this project. Do **not**
re-render the mark in CSS at favicon sizes — the PNGs were generated from a
captured real-Bricolage render and the bounding box was centered with consistent
padding. Anti-aliasing matters at 32×32.

Bricolage Grotesque + Inter Tight + JetBrains Mono load from Google Fonts via
`tokens.css`. Don't substitute. If the import fails, fix the import — don't
fall back to a system stack.

---

## The kanban — what to build

Four columns, left-to-right, equal width, scrolling independently. The columns
ARE the pipeline; their order encodes the mental model and must not be
reordered. Each column's stage indicator is a 8px colored "headlamp" dot, never
a colored card background, never a colored column background:

| Stage | Column label | Headlamp color | Card accent |
|---|---|---|---|
| 1 | Capture | `--mash-pulp` | left-border 3px pulp when ripping; red glow + `--ember` left-border when damaged |
| 2 | Beets ID | `--sky` | left-border 3px sky (monitoring) |
| 3 | Review | `--amber` | left-border 3px amber (weak match) or `--ember` (no match) |
| 4 | In library | `--moss` | left-border 3px moss |

**Card anatomy** (from top to bottom, in this order — do not reorder):

1. **Header row**: 56×56 disc photo thumbnail (left) + slug eyebrow + title + artist line
2. **Track segment bar**: one segment per CD track; height 8px (14px when card is expanded)
3. **Status line**: mono, muted, one line; e.g. `ripping track 7 · sector 24,318 · 1 retry · 04:12 elapsed`
4. **Chip row**: 0–4 chips (VA, BURNED, MIX, WEAK MATCH · 0.42, MUSICBRAINZ · 0.97, etc.)
5. **Expanded body** (only when expanded): see below

**Track segment colors** (per project overview):

| Status | Segment color | Token |
|---|---|---|
| ripped clean | green | `--moss` |
| ripped with recovered errors | blue | `--sky` |
| unrecoverable errors | red | `--ember` |
| not yet ripped / skipped | dark gray | `--ink-3` |
| currently ripping | dark gray base + pulp animated fill at progress% | `--ink-3` + `--mash-pulp` |

When beets identifies a track, the segment gets a **1px white outline (inset
2px)**. This is the "card evolves visually as it advances" rule.

**Operator-asserted vs system-confirmed visual contract**:

| Kind | Visual |
|---|---|
| System-confirmed value | solid chip with semantic color (e.g. `--moss-soft` background) |
| Operator-asserted value | **dashed border** on the chip, OR **dashed underline** on inline text |
| Glow on system-confirmation | small box-shadow halo in the matching semantic color |

Do not invent new visual states. These three carry every status in the system.

---

## Expanded card body

Spacebar toggles expand. Only one card expanded at a time. Inside the expanded
body, three labeled sections, in this fixed order:

1. **Beets candidates** (only when there are candidates) — list of up to 5
   ranked candidates with score chip on the left, release + mbid in the middle,
   "Apply" button on the right. Top candidate has an amber-tinted background.
2. **Hints · operator-asserted** — 4-up toggle grid (Various artists, Burned cd,
   Mix cd, Demo / unreleased), then Album + Artist input rows. Toggles use the
   pulp accent when on.
3. **Manual steps** — flat row of buttons: Paste mbid → re-id (primary), Run
   beets search, Edit source.json, Skip · move to failed.
4. **Damaged-disc actions** — only when the disc is in Capture and damaged OR
   when `disc.column === "capture"`. Three buttons all using the `--ember`
   surface treatment: Process partial as-is, Redo entire capture, Pick tracks to
   re-rip…

Destructive actions (redo, rerip, skip, delete) **require a second click to
confirm**. Render the gate hint below them: *"Destructive actions require a
second click to confirm. The partial flac files stay on disk until you choose."*

---

## Right drawer

340px fixed width, sticky head, scrollable body. Two modes, swapped by the
header nav buttons:

| Mode | When | Contents |
|---|---|---|
| `drive` | No card focused | Disc-photo placeholder at top + Drive · Active rip · Cache · Poll cadence sections |
| `card` | A card is focused | Same photo + Disc · Rip log (tail, max 200px height) · `source.json` (syntax-highlighted) |

The disc photo placeholder is a CSS-drawn circle with a conic-gradient glow —
this is a placeholder for the real Pi-camera photo. Replace with `<img
src="/photos/{slug}.jpg">` when wired up.

`source.json` is rendered as preformatted text inside a `pre.cda-json` with
inline syntax-highlight spans (`.k` keys, `.s` strings, `.n` numbers, `.b`
booleans). Don't use a code-highlighting library; the schema is small and
stable.

---

## Bottom drawer (daemon log)

Collapsed by default — 36px tall strip across the bottom with a `≡ daemon log`
toggle, total entry count, and warn/error counts colored amber/ember. Expanded
height: 240px max, scrollable. Each log line is a grid: timestamp · level
(warn/error/info, colored, all-lowercase, mono, letter-spaced) · message.

Sprint-7 will add filters; reserve the right portion of the head row for them.

---

## Header bar

56px tall. Layout, left to right:

1. **Brand lockup**: `cd/a` mark + `cd-archivist` slug (mono, weight 700) + `cda-pi · 192.168.6.38:8228` host line (mono, quiet)
2. **Live status chip**: pulsing green dot + "ripping · DISC-A4F2" when active, "idle" otherwise. Use the same chip recipe even when idle (different colors).
3. **Rig stats group** (centered, auto-margin both sides): 5 stat cells in a single bordered group — Ripped · In review · Partial · Storage · Uptime. The numbers are mono, weight 700; the labels are eyebrows.
4. **Header nav** (right): navidrome ↗, beets ↗, daemon log toggle, drive/card-detail mode toggles.

The brand lockup uses `transform: translateY(-2px)` on the mark to keep the
extrude shadow from kissing the bottom border.

---

## Live updates — polling cadence

Per the project overview: `1s during an active rip, 5s when idle`. Implement
adaptive polling:

```js
// in the kanban controller
let pollMs = 5000;
function setCadence(state) {
  pollMs = state === "ripping" ? 1000 : 5000;
}
```

When you swap polling intervals, don't slide content around. Cards entering a
new column should fade-in (200ms `--ease-out`). Cards leaving fade out then
remove. Track segments fill smoothly — no "step animation" on the segment
progress.

When something is "live updating", flash a 200ms `var(--moss)` border, then
fade. Don't slide.

---

## Voice — copy guidelines

This is operator UI. Voice rules from the design system apply hard:

- **Sentence case everywhere** in source. Eyebrows are CSS-uppercased.
- **No emoji**. Unicode glyphs (▸ ▾ ↵ ↑ ↓ ↗ ↻) only.
- **No marketing language**. "Stored". "Ripped". "Awaiting beets." "Halted ·
  3 unrecoverable sectors."
- **Be specific in error states**. Not "Something went wrong" — "track 4 ·
  sector 12,044 · gave up after 8 retries".
- **Use the project's vocabulary** verbatim: `disc`, `slug`, `source.json`,
  `inbox`, `review`, `library`, `failed`, `archive`, `beets`, `mbid`, `acoustid`,
  `disc-id`, `cdparanoia`, `Various Artists`, `Burned CD`, `Mix CD`.
- **Mono shorthand for time + bytes**: `04:12 elapsed`, `26.4 MB`, `1d 22h`.

---

## Tokens you'll actually use

From `colors_and_type.css`:

```css
/* Brand */
--mash-pulp        #ff5b2e   /* primary accent — ripping, primary CTA, brand */
--mash-pulp-deep   #d94c23   /* pressed / hover */
--mash-pulp-edge   #8a2d15   /* mark extrude, stroke */
--mash-pulp-soft   #ff5b2e22 /* tinted fill */
--bone             #faf7f2

/* Neutrals — dark scale */
--ink-0  #07090c       /* page bg */
--ink-1  #0d1116       /* surface */
--ink-2  #141921       /* surface-2 / card */
--ink-3  #1c232c       /* hover / input */
--ink-4  #283039       /* line */
--ink-5  #3a4451       /* line-strong */
--ink-6..9             /* fg scale */

/* Semantic — four states, each with a `-soft` surface */
--moss   #3ec27a   --moss-soft  #1d3a2a   /* success · library · clean rip */
--amber  #e8a83a   --amber-soft #3a2e15   /* warn · review · weak match */
--ember  #e6566c   --ember-soft #3b1a22   /* error · damaged · no match */
--sky    #5aa3ff   --sky-soft   #16263f   /* info · beets-id · monitoring */

/* Type */
--font-display "Bricolage Grotesque", ui-sans-serif, system-ui, sans-serif
--font-body    "Inter Tight", ui-sans-serif, system-ui, sans-serif
--font-mono    "JetBrains Mono", ui-monospace, monospace
```

---

## Things to AVOID (specific anti-patterns)

These are mistakes the previous agent on a sibling project made. Don't repeat
them.

- **Don't** render the brand mark as flat italic. The extrusion is the mark.
- **Don't** use stock Tailwind palette colors (`bg-purple-*`, `bg-blue-*`,
  `bg-green-*`, `bg-amber-400`, `bg-red-*`). Use the semantic tokens above.
- **Don't** make a "rounded card with only a colored left-border" without the
  rest of the border existing too. The 1px slate border on all four sides
  always exists; the colored left-border (3–4px) is layered on top.
- **Don't** add purple, indigo, magenta, or any gradient hero. The brand has
  one accent + four semantic states. That's it.
- **Don't** use mesh gradients, abstract geometric backgrounds, or AI-style
  hero illustrations.
- **Don't** add emoji to the UI. Real CD ripping is dry work; the bot doesn't
  cheer.
- **Don't** invent semantic colors. There are four. If you need a fifth, that's
  a conversation, not a unilateral choice.
- **Don't** fall back the display font stack to `serif`. Bricolage is sans.
- **Don't** truncate the status line on cards. The operator needs to read
  "sector 24,318 · 1 retry" without hovering. Wrap if you must.

---

## Definition of done

- The kanban renders four columns with the correct stage ordering and column
  headlamp colors
- Cards in every state (ripping, damaged, monitoring, weak-match, no-match,
  confirmed-in-library) render with the correct left-border accent + chips
- Track segment bars render with the right colors per status AND get an outline
  once `track.identified === true`
- Dashed border on operator-asserted chips; solid on system-confirmed
- The `cd/a` mark in the header renders chunky + extruded, not flat
- Favicons resolve at all sizes; the PWA manifest is wired
- Right drawer swaps modes correctly between drive-status and card-detail
- Bottom log collapses to 36px and expands to 240px max
- Polling cadence flips 1s ↔ 5s based on active-rip state
- Console is clean. No `bg-blue-*` / `bg-purple-*` / stock Tailwind colors in
  the codebase. `--font-display` fallback is sans.
- The voice of every status line matches the operator-voice examples in the
  prototype

When you're done, read `Cd Archivist.html` side-by-side with your build and
sanity-check every card state.
