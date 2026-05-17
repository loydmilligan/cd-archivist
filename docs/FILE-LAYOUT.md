# FILE-LAYOUT.md

> Canonical "where things go" schema for the cd-archivist repo.
> Phase B-1 of sprint-8 (lane-1, repo sanitizer) consumes this as
> its categorization spec. The intended layout below is the
> SOURCE OF TRUTH; the violations list at the bottom catalogues
> what's currently out of place but NOT YET MOVED.

## Top-level files

Tracked files at the repo root are limited to:

| File              | Role                                                              |
| ----------------- | ----------------------------------------------------------------- |
| `README.md`       | First-touch project intro. Quick start + pointers.                |
| `CHANGELOG.md`    | Keep-a-Changelog release history (per `D-keep-a-changelog-format`). |
| `ROADMAP.md`      | Three-horizon forward backlog.                                    |
| `ISSUES.md`       | Defect-focused backlog.                                           |
| `CLAUDE.md`       | Agent-behavior contract.                                          |
| `AGENTS.md`       | Multi-agent roster (legacy).                                      |
| `pyproject.toml`  | Build + dependency config; package set lives here.                |
| `ruff.toml`       | Lint config.                                                      |
| `.gitignore`      | Tracked-vs-not-tracked policy.                                    |
| `.env.example`    | Documented env-var template (no secrets).                         |

Nothing else lives at repo root. Scratch artifacts, design archives,
JPGs from manual testing, screenshots — all go under `docs/` or
get `.gitignore`d (see below).

## `archivist/` — production code

Sole source of importable code. Five subsystems, each a Python
subpackage:

| Subdir                  | Role                                                       |
| ----------------------- | ---------------------------------------------------------- |
| `archivist/drivers/`    | Hardware-facing primitives (drive, camera, LED, ripper).   |
| `archivist/pipeline/`   | Pipeline orchestration (capture, rip, disc-folder ops).    |
| `archivist/state_machine/` | IDLE → CAPTURE → RIP → EJECT loop + DriveStatus snapshot. |
| `archivist/service/`    | FastAPI surface (kanban, endpoints, static, templates).    |
| `archivist/models/`     | Pydantic schemas (Manifest, source.json shape).            |

`archivist/__main__.py` is the daemon entrypoint (`python -m archivist`).

## `tests/` — pytest tree

Mirrors `archivist/` subsystem-for-subsystem:

| Subdir                  | Mirrors                  |
| ----------------------- | ------------------------ |
| `tests/drivers/`        | `archivist/drivers/`     |
| `tests/pipeline/`       | `archivist/pipeline/`    |
| `tests/state_machine/`  | `archivist/state_machine/` |
| `tests/service/`        | `archivist/service/`     |
| `tests/models/`         | `archivist/models/`      |

Plus `tests/conftest.py` (shared fixtures) and `tests/__init__.py`.
Top-level `tests/test_*.py` files are reserved for cross-cutting
integration tests (e.g. `tests/test_main_logging.py`).

Test data, fixtures, and reference media live under
`tests/<subdir>/fixtures/`. **Screenshots do not belong in `tests/`** —
they go under `docs/screenshots/` (see below).

## `docs/` subdirectories

| Subdir                    | Role                                                          |
| ------------------------- | ------------------------------------------------------------- |
| `docs/coordination/`      | One `sprint-N.md` per sprint. Frozen on sprint close.         |
| `docs/design/`            | Design briefs (one file per topic; date-prefixed).            |
| `docs/operations/`        | Operator runbooks for setup, migration, and one-off ops.      |
| `docs/runbooks/`          | Recurring operator procedures (ripping sessions, etc.).       |
| `docs/research/`          | Vendored ecosystem research; open questions.                  |
| `docs/reference/`         | Vendored external references (handoffs, third-party docs).    |
| `docs/screenshots/` (NEW) | UI screenshots from review sessions (operator-captured).       |
| `docs/`                   | Plus top-level cross-cutting docs: `project-overview.md`,     |
|                           | `WORKFLOW.md`, `FILE-LAYOUT.md`, `ARCHITECTURE.md`,           |
|                           | `WORKFLOW-DIAGRAM.md`, `FEATURES.md`.                         |

## What goes at repo root vs nested

**Root.** Stays minimal: only the files in the top-level table above.
Anything operator-facing-but-temporary (screenshots, scratch
docs) belongs under `docs/`. Anything code-shaped belongs under
`archivist/` or `tests/`.

**`docs/`.** Anything documentation-shaped. New cross-cutting docs
land here directly (`docs/FOO.md`); domain-specific docs land under
the matching subdir.

**`archivist/`.** Only production code. No scratch scripts, no
generated assets (except vendored CSS / fonts / icons under
`archivist/service/static/`, which IS production payload).

## What does NOT belong tracked

The following patterns should be `.gitignore`d or removed; if
present in the working tree they're sanitizer-pass-1 targets:

- `*.zip` design-system / vendor archive bundles at any path
- `.playwright-mcp/` — Playwright MCP scratch dir (gitignore)
- `mbid-*.jpg`, `*-cover.jpg`, MB-scraped cover-art JPGs from manual
  testing
- `.DS_Store` (already covered by `.gitignore`)
- `__pycache__/`, `*.pyc`, `*.pyo` (already covered)
- `.pytest_cache/`, `.ruff_cache/` (already covered indirectly via
  patterns; verify)
- `cd_archivist.egg-info/` (build artifact; covered by `*.egg-info/`)
- `.orc-tower/` (already gitignored)

If an artifact is reference-worthy long-term, it moves under
`docs/reference/` and gets tracked; otherwise it's gone.

## Legacy areas to audit

These exist in the tree but predate the current architecture; the
sanitizer should flag each for keep/move/delete:

- **`src/cd_archivist/`** — pre-sprint-1 package layout. Today
  `pyproject.toml` explicitly excludes `src/*` from packaging and
  `pytest`'s `norecursedirs`. Almost certainly delete-or-archive,
  but verify nothing in `docs/` still references it before
  removing.
- **`hardware/`** — physical-rig wiring docs + mount STLs. Keep;
  move under `docs/hardware/` if it makes the top-level tighter.
- **`scripts/`** — two pre-sprint-1 utility scripts (`capture_stub.py`,
  `init_disc.py`). Audit whether either is still referenced by any
  runbook before deletion.
- **`config/`** — single `default.yaml`. Verify it's the canonical
  runtime config; if so, keep; if stale, delete.

## Current violations (to be sanitized by lane-1)

As of 2026-05-17, the following items do not match the schema above
and are the sanitizer's work order:

| Item                                                       | Disposition                                       |
| ---------------------------------------------------------- | ------------------------------------------------- |
| `docs/Mash Co. Design System.zip` (untracked)              | Either extract to `docs/reference/` or `.gitignore`. |
| `docs/mashco-design-system-handoff/` (untracked dir)       | Move to `docs/reference/mashco-design-system/`.    |
| `docs/mbid-a359ebe6-…-19375630765.jpg` (untracked)         | Delete (MB cover-art testing artifact) OR move to `docs/research/` if reference-worthy. |
| `docs/ripper-handoff-for-claude-code.md` (untracked)       | Review then move to `docs/reference/` or delete if superseded. |
| `tests/cd-arhcivist-screen.png` (untracked; note typo)     | Move to `docs/screenshots/cd-archivist-screen.png` (fix typo). |
| Any other `*.png` strays at repo root                      | Move to `docs/screenshots/`.                       |
| `.playwright-mcp/`                                         | Add to `.gitignore` if absent.                     |
| `cd_archivist.egg-info/` (currently tracked-or-present)    | Confirm `.gitignore` covers it; remove if tracked. |

After sanitization, `git status` should be clean: no untracked files
left, no tracked files out of place. The pytest suite must remain
green throughout (per `D-housekeeping-no-code-changes`).
