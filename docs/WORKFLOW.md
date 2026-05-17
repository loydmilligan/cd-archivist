# WORKFLOW.md

> How work flows through the cd-archivist repo. This document is the
> companion to `CLAUDE.md`: where `CLAUDE.md` governs **how agents
> behave** while doing work, `WORKFLOW.md` governs **how work moves
> through the repo** — what we commit, how we ship to the rig, how
> documentation stays honest, and where backlog items live.

## 1. Purpose & relationship to CLAUDE.md

`CLAUDE.md` is the agent-behavior contract: coding style, side-effect
discipline, "do not do" rules, hardware assumptions. It tells an agent
*how to think while writing code in this project*.

`WORKFLOW.md` is the process contract: commit conventions, branching,
deployment, doc-update cadence, escalation paths, decision logs, sprint
lifecycle, and the add/triage flows for the two backlogs
(`ROADMAP.md` and `ISSUES.md`). It tells anyone — human or agent — *how
to move work through this repo without breaking anything else*.

When the two conflict, `CLAUDE.md` wins on **what code looks like**;
`WORKFLOW.md` wins on **what happens to that code next** (commit
shape, deployment, doc updates).

---

## 2. Git commit conventions

We follow [Conventional Commits](https://www.conventionalcommits.org/)
with a small project-specific scope vocabulary.

### Shape

```
<type>(<scope>): <one-line subject in present tense, lowercase>

<optional body — what + why, never just what>

Co-Authored-By: <agent or human> <noreply@…>
```

### Types

| Type        | When                                                          |
| ----------- | ------------------------------------------------------------- |
| `feat`      | New behavior visible to the operator or another subsystem.    |
| `fix`       | Bug fix. Must reference what broke and why this resolves it.  |
| `docs`      | Documentation, decision log, planning doc edits.              |
| `chore`     | Repo hygiene, dependency bumps, tooling, sanitization.        |
| `refactor`  | Internal restructure with no behavior change.                 |
| `test`      | Adding or changing tests — including Wave-1 failing tests.    |

### Scopes

- **`sprint-N`** — any commit that lands work from `docs/coordination/sprint-N.md`.
  Examples: `feat(sprint-7): impl-candidates-endpoint`, `test(sprint-6.5): test-bottom-drawer`.
- **Subsystem name** — for hotfixes / out-of-band work not tied to a
  sprint plan: `drivers`, `pipeline`, `service`, `state_machine`,
  `models`, `tests`. Example: `fix(drivers): retry usb rebind once on VIDIOC_STREAMON`.
- **`repo`** — for repo-wide changes (gitignore, top-level files,
  build config).

### Body conventions

- State the **what** in the subject; explain the **why** in the body.
  A commit body that only repeats the diff is worse than no body.
- Reference the decision log when the commit lands a `D-…` choice:
  `Per D-candidates-source-priority: …`.
- Reference the sprint task ID when a commit closes a Wave 1 / Wave 2
  task: `Closes test-rig-stats-endpoint.`
- For multi-file commits, lead with the load-bearing file or change.

### Atomic-commit rule

One commit = one logical change. A Wave-1 failing test is its own
commit; the Wave-2 impl that makes it pass is a separate commit. The
exception is a single bundle that names everything inside it
explicitly via brace-syntax in the subject — e.g.
`test(sprint-6.5): test-{logs-tail-endpoint,drive-status-endpoint}` —
when two tests are genuinely paired and shipping together avoids
double-ticking the same plan row.

### Co-Authored-By footer

Every agent-authored commit ends with a `Co-Authored-By:` line. The
human operator's commits don't need one; agent-authored commits do
(this is how we know which subsystem changes came from which agent
context).

---

## 3. Branching strategy

We are pre-v1, dogfooding on one machine, with a tiny pool of
contributors (one human + a small fleet of agents). **Default
branch is `master`. Default workflow is trunk-based.**

### When `master` is fine

- Single-file changes
- Sprint plans where every commit is small and atomic (most of our work)
- Doc edits, decision-log additions, ROADMAP/ISSUES updates
- Test-only commits

### When a short-lived branch is warranted

Any change that meets at least one of:

- Touches **more than 5 files** in a single logical step (large
  refactor, file reorg, sanitization sweep)
- Crosses **3 or more subsystems** (e.g. drivers + pipeline + service
  in one commit graph)
- Introduces an API contract change that has to be tested against
  multiple call sites before flipping

In those cases:

1. `git checkout -b <type>/<short-slug>` (e.g. `chore/repo-sanitize`)
2. Land the work as small commits on the branch
3. Open a PR; review; squash-or-rebase merge to `master`
4. Delete the branch after merge

Per `D-trunk-based-default` (sprint-8), this is the rule until v1.0
ships. We revisit branching policy at the v1 milestone.

---

## 4. Deployment to the CM4

The production target is the CM4 mounted in the rig
(`192.168.6.38:8228` / `cda.mattmariani.com`). Everything ships there
via `git pull`.

### Standard deploy sequence

```bash
ssh cm4
cd ~/Projects/cd-archivist
git pull --ff-only origin master
pip install -e '.[dev]'
systemctl --user restart cd-archivist
```

`pip install -e '.[dev]'` re-runs whenever `pyproject.toml` changed
this commit; safe to run every time.

### When to run it

After **every merged commit** that touches:

- `archivist/` — production code
- `pyproject.toml` — dependencies or entrypoints
- `archivist/service/static/` — vendored assets, CSS, fonts (the
  systemd-managed FastAPI uvicorn picks these up on restart)

Pure documentation commits (`docs/`, top-level `*.md`, decision-log
edits) do **not** require a deploy.

### Cache-busting after CSS changes

Browsers cache `static/css/cda.css` and `static/css/tokens.css`. After
a sprint-7-style CSS touch, hit the kanban with a hard refresh
(`Ctrl+Shift+R` / `Cmd+Shift+R`) on first visit, or append `?v=N` to
force-revalidate during smoke.

### Roll back

```bash
ssh cm4
cd ~/Projects/cd-archivist
git fetch origin
git reset --hard <known-good-sha>
pip install -e '.[dev]'
systemctl --user restart cd-archivist
```

Never `git reset --hard` without first running `git log --oneline -10`
to confirm the target SHA. Never force-push to `master`.

---

## 5. Documentation review/update cycle

### Per-sprint (every sprint closes with)

- **README.md** spot-check against current architecture; rewrite if
  retired hardware / subsystems are still described.
- **`docs/ARCHITECTURE.md`** updated for any new component, schema
  change, or major contract shift this sprint.
- **`docs/project-overview.md`** spot-check; the one-screen pitch
  must still be accurate.
- **CHANGELOG.md** — new `[Unreleased]` entries for everything that
  shipped this sprint.
- **ROADMAP.md** — anything from the closing sprint's "Sprint-N+1
  Candidates" list gets promoted to the right horizon.
- **ISSUES.md** — re-triage all `Open` issues; close any that landed
  fix commits this sprint.

### Quarterly

A full **doc-vs-code reality audit**: walk every doc, verify it still
matches the code. Stale paragraphs get marked or removed. This is
also when the architecture diagram gets compared against the actual
file tree.

### Pre-release (when bumping the `pyproject.toml` version)

- `[Unreleased]` block in CHANGELOG becomes the new version section
  with a date.
- `[Unreleased]` block is recreated empty above it.
- Tag the release: `git tag -a v0.X.Y -m "…"` and `git push --tags`.

---

## 6. Version control / versioning

We use [Semantic Versioning](https://semver.org/) on `pyproject.toml`.
While we are pre-feature-complete, we live in `0.x.y`.

| Bump  | When                                                                |
| ----- | ------------------------------------------------------------------- |
| MAJOR | API-or-data-model break. Pre-1.0 we use MINOR for these.            |
| MINOR | Backward-compatible feature addition. Most sprints land a MINOR.    |
| PATCH | Bug fix, doc-only, hotfix. Same-day reactive bumps.                 |

### `[Unreleased]` flow

Every change lands under the `[Unreleased]` section of `CHANGELOG.md`
in the appropriate subsection (`Added` / `Changed` / `Deprecated` /
`Removed` / `Fixed` / `Security`). When we tag a release:

1. Rename `[Unreleased]` to `[0.X.Y] — YYYY-MM-DD`.
2. Recreate an empty `[Unreleased]` block above it.
3. Bump `pyproject.toml` to match.
4. Commit `chore(repo): bump to 0.X.Y` and tag.

---

## 7. When to report to orc-tower

cd-archivist is one of several projects orchestrated by **orc-tower**
(meta-coordinator). The line:

- **Stays in `cd-archivist`** — any bug, missing feature, design
  question, or sprint planning issue scoped to this project. File as
  ISSUES.md entry or ROADMAP.md proposal.
- **Escalates to orc-tower** — issues that affect agent harnesses,
  the tmax workspace itself, multi-project workflows, the coord-doc
  parser, the dashboard, or any infrastructure that spans projects.
  These get filed under the `orc-tower` repo, NOT here.

Agents on cd-archivist tasks should never silently work around an
orc-tower-class bug. Flag, escalate, then continue.

---

## 8. Decision-log conventions

The coord doc for each sprint carries a `## Decision Log` section.
Decisions are addressable, durable, and machine-greppable.

### ID format

`D-<kebab-id>` — short, descriptive, unique within the project.
Examples:
`D-housekeeping-no-code-changes`, `D-candidates-source-priority`,
`D-inline-css-whitelist`.

### Entry shape

```
### YYYY-MM-DD — D-<id> — <one-line summary>

<one or two paragraphs of context + the chosen path. Optionally a
list of rejected alternatives.>
```

### When to add a decision

Any **non-obvious choice that future work might re-question**:

- Choosing between two viable approaches
- Choosing to defer something to a later sprint
- Choosing a specific magic number / threshold / TTL
- Choosing not to do something the spec suggested
- Anything where a reasonable agent on the next sprint might re-open
  the question without context

Trivia, formatting tweaks, and obvious mechanical choices don't get
their own `D-…` entry.

### OPEN vs SETTLED

- **OPEN** decisions carry the suffix `— **OPEN** (<owner> confirms
  during <task-id>)`. They're tracked in the planning phase, resolved
  during impl by the named lane.
- **SETTLED** decisions have no suffix and are immutable once
  ratified (or once landed if no ratification is needed).

### Ratification

Some decisions need explicit human-operator approval before they're
final (anything irreversible, anything that changes a contract the
operator depends on). Ratified entries move from `## Decision Log` to
the `## Ratification Log` at the bottom of the coord doc.

---

## 9. Sprint-doc lifecycle

Each sprint has exactly one `docs/coordination/sprint-N.md` file. It
moves through three states:

1. **Draft** — `status: draft` in the frontmatter. The plan is being
   written; tasks are being slotted; the Decision Log is accumulating.
2. **In-progress** — execution underway. Agents tick `[ ]` → `[x]`
   per task on the same commit as the task body lands. Activity Log
   entries accumulate newest-first.
3. **Closed** — all tasks ticked; the sprint's outcome is summarized
   in the final Activity Log entry. Carry-forwards live in the
   `## Sprint-N+1 Candidates` section.

### Don'ts

- **Don't rebase old sprint docs.** Once closed, the history is
  load-bearing for future archeology. Add corrections as new Activity
  Log entries with the current date, not by rewriting old ones.
- **Don't move tasks between sprints mid-flight.** If something has
  to be deferred, mark it closed with a "deferred to sprint-N+1"
  Activity Log entry, and add the matching item to the next plan.
- **Don't tick the box without the actual commit.** Tick-and-commit
  happen together; ticks-only commits are an anti-pattern unless
  they're consolidating an Activity Log entry at end-of-phase.

### Carry-forwards

Anything that didn't ship goes into the closing sprint's `##
Sprint-N+1 Candidates` section. The next planner pulls from there
when drafting the next sprint plan.

---

## 10. Adding to ROADMAP

`ROADMAP.md` lives at repo root and carries the **forward-looking
backlog**: things we'd like to build, sorted by horizon.

### Three horizons

| Section            | Meaning                                                         |
| ------------------ | --------------------------------------------------------------- |
| `## Next sprint`   | Earmarked for the immediately upcoming sprint plan.             |
| `## Next milestone`| Medium-term thematic groups; not the next sprint, but soon.     |
| `## Someday / maybe`| Long-tail ideas we'd revisit only if priorities flip.          |

### Item shape

```markdown
### <one-line title>

2–3 line description of what + why. Reference design docs or sprint
coord docs if relevant.

Add date: YYYY-MM-DD
```

### Add process

1. Write the entry under the most appropriate horizon section.
2. Add the date.
3. Commit: `docs(repo): roadmap — add <slug>`.
4. orc-tower picks it up at next planning cycle.

### Triage / promotion

- At each sprint-planning kick-off, the orc-tower planner reviews
  `## Next sprint` and pulls items into the new plan.
- Items demoted from `## Next sprint` (didn't make the cut) move to
  `## Next milestone`.
- Items in `## Someday / maybe` only move up when explicitly
  re-prioritized.

### Resolve

When the item ships (Activity Log of the closing sprint records it),
remove the entry from ROADMAP. The CHANGELOG holds the historical
record.

---

## 11. Adding to ISSUES

`ISSUES.md` lives at repo root and carries the **defect-focused
backlog** — bugs, regressions, known gaps, hardware faults.

### Severity tags

| Severity   | Meaning                                                            |
| ---------- | ------------------------------------------------------------------ |
| `blocker`  | Pipeline can't run, or a release can't ship.                       |
| `major`    | Significant feature broken or significantly degraded.              |
| `minor`    | Annoying but workable; data loss / risk minimal.                   |
| `cosmetic` | Visual / wording / log-noise; no functional impact.                |

### Entry shape

```markdown
### <one-line title>

- Severity: blocker / major / minor / cosmetic
- Owner: operator / drivers / pipeline / service / state-machine / tbd
- Repro: <steps OR "n/a — observed in <context>">
- Notes: <optional — link to sprint coord doc, design doc, decision log>

Add date: YYYY-MM-DD
```

### Triage rule

- **`blocker` or `major`** — pulled into the **active sprint**. If
  the sprint is locked, escalate to orc-tower and the operator
  immediately.
- **`minor` or `cosmetic`** — queued for the **next sprint** unless
  the current sprint has slack.

### Add process

1. Write the entry under `## Open` in severity order
   (blocker > major > minor > cosmetic).
2. Tag severity, owner, repro.
3. Commit: `docs(repo): issues — add <slug>`.

### Resolve

When a fix commit lands:

1. Move the issue from `## Open` to `## Resolved`.
2. Append the resolving commit SHA to the entry:
   `Resolved by <SHA>.`
3. Commit: `docs(repo): issues — close <slug>`.

The Resolved section is a permanent record; we don't garbage-collect
it.

---

## Appendix: Quick reference

| Question                                  | Where to look                                  |
| ----------------------------------------- | ---------------------------------------------- |
| How should I structure this commit?       | §2                                             |
| Branch or just push to master?            | §3                                             |
| How do I ship this to the rig?            | §4                                             |
| What docs do I need to touch this sprint? | §5                                             |
| Should I bump the version?                | §6                                             |
| Is this a cd-archivist issue or orc-tower?| §7                                             |
| Do I need a decision-log entry?           | §8                                             |
| What state is this sprint in?             | §9 + the sprint doc's frontmatter              |
| Where does this future-idea live?         | §10 (ROADMAP) or §11 (ISSUES)                  |
| Where does this defect live?              | §11                                            |
