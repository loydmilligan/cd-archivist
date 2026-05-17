# cd-archivist — handoff package

This is everything Claude Code needs to implement the cd-archivist UI on the
Mash Co. design system.

## What's in this folder

```
cd-archivist/
├── README.md                  ← you are here
├── handoff/
│   └── Build prompt.md        ← paste this into Claude Code
├── brand/
│   ├── cd-a-favicon-{32,64,180,256,512,1024}x*.png   ← favicon family
│   ├── cd-a-maskable-512.png                          ← Android adaptive icon
│   ├── cd-a-apple-touch-180.png                       ← iOS home screen
│   ├── cd-a-on-bone-512.png                           ← light-mode variant
│   ├── manifest.webmanifest                           ← PWA manifest
│   └── cd-a-mark.html                                 ← mark renderer (regen source)
├── colors_and_type.css        ← TOKEN SOURCE OF TRUTH — copy to static/css/
├── cda-styles.css             ← component CSS — copy to static/css/
└── reference/
    ├── Cd Archivist.html      ← the working prototype, open in browser
    ├── cda-data.jsx           ← mock data
    ├── cda-chrome.jsx         ← header, drawer, log, atoms
    ├── cda-components.jsx     ← cards, columns, expanded body
    └── tweaks-panel.jsx       ← tweaks framework (you don't need this in prod)
```

## Where each file goes in your cd-archivist repo

Assuming a FastAPI layout with `static/`:

| From here | To your repo |
|---|---|
| `colors_and_type.css` | `static/css/tokens.css` (import this FIRST) |
| `cda-styles.css` | `static/css/cda.css` (import after tokens) |
| `brand/cd-a-favicon-*.png` | `static/img/brand/` |
| `brand/cd-a-maskable-512.png` | `static/img/brand/` |
| `brand/cd-a-apple-touch-180.png` | `static/img/brand/` |
| `brand/manifest.webmanifest` | `static/manifest.webmanifest` |
| `reference/*` | `docs/reference/` or `_design/` — keep as reference; do not serve |

## What to do

1. Drop these files into your cd-archivist repo following the table above
2. Open `reference/Cd Archivist.html` in a browser to see the working prototype
3. Paste the contents of `handoff/Build prompt.md` into Claude Code, along with
   "read the files in /static/css/, /static/img/brand/, and docs/reference/
   before you start"
4. Let Claude Code build the FastAPI/HTMX (or whatever stack) version

The prompt was written defensively — every anti-pattern the previous Claude
Code agent on a sibling project hit is called out in "Things to AVOID" so it
doesn't repeat them.
