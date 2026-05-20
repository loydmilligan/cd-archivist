---
project: cd-archivist
sprint: sprint-11
created: 2026-05-20T00:00:00.000Z
updated: 2026-05-20T00:00:00.000Z
status: active
---

# cd-archivist — coordination doc (sprint-11)

> Strict template per Session O2=B / seed §12 Phase 8. The dashboard
> reads this as the canonical substrate (seed §3.7); orc emits
> `coord-doc-stale` cards when drift is detected (§3.8 / O7=A).
>
> Section headings are load-bearing — keep them as-is so the parser can
> find them. Section bodies are markdown-flexible.

## Plan Source

- Type: inline
- Path: this document (`## Active Sprint Plan` section)
- Active unit: sprint-11
- Trigger: operator feedback after sprint-10 deploy — "we need a settings page to setup navidrome url and spooty url". The four Library panels currently read URLs/creds from `.env` + systemd; editing them requires ssh. Sprint-11 closes that loop.

## Sprint Goals

Edit URLs and creds from the browser

Settings page with read-write JSON config + reload endpoint — no more ssh to update spooty/navidrome creds.

## Active Initiatives

- _None — sprint-11 plan below is the substrate._

## Active Sprint Plan

<!-- Inline plan parsed by orc-tower's InlineArtifactSource. -->

- [x] {agent: lane-1, id: setup-config-store} Establish the config-store pattern that the settings page reads/writes. New `archivist/service/config.py` exporting:
    - `Config` dataclass (typed fields): `spooty_api_url`, `spooty_api_token`, `navidrome_url`, `navidrome_user`, `navidrome_pass`, `music_inbox_dir`, `music_library_dir`, `music_archive_dir`, `music_spooty_dir`, `music_review_dir`. All `str | None` except dirs (default to current `MUSIC_*` defaults).
    - `get_config() -> Config` — reads `$ARCHIVIST_CONFIG_PATH` (default `~/.config/cd-archivist/config.json`); merges with env vars per precedence **FILE > ENV > DEFAULT**. Cached; reset on `reload_config()`.
    - `save_config(updates: dict)` — atomic write (`config.json.tmp` → `os.replace`) with file mode 0600. Refuses unknown keys. Auto-calls `reload_config()` after a successful write.
    - `reload_config()` — clears the cache so the next `get_config()` re-reads disk.
  Document the precedence + write semantics in `archivist/service/config.py`'s docstring.
  - **Acceptance:** `tests/service/test_config_store.py` covers (a) FILE > ENV > DEFAULT precedence; (b) atomic write — concurrent reader never sees `.tmp`; (c) file-mode 0600 on the written file; (d) `save_config` rejects unknown keys; (e) `reload_config` clears the cache. Full suite stays green.

- [x] {agent: lane-1, depends: setup-config-store, id: settings-api-endpoints} New API endpoints for the settings page. In `archivist/service/app.py`:
    - `GET /api/config` — returns the current `Config` as JSON, with **secret fields masked** (`navidrome_pass`, `spooty_api_token` → `"●●●●●●●●"` when set, `null` when unset).
    - `POST /api/config` — accepts `{key: value, …}` partial updates. Pydantic validation: URLs must be `http(s)://`, non-empty strings, paths must be absolute. **Empty-string in a password field = "no change"** (don't overwrite stored password with empty). Returns the updated masked config.
  - **Acceptance:** `tests/service/test_settings_api.py` covers GET masking (set vs unset secret), POST happy path, POST validation rejection on bad URL, POST empty-pass = no-change behavior, POST rejects unknown keys via the config_store error path. Full suite stays green.

- [ ] {agent: lane-2, depends: setup-config-store, id: config-runtime-wiring} Refactor the four service-clients to consume `config.get_config()` instead of `os.environ.get(...)`. Touch all four:
    - `archivist/service/clients/spooty_client.py` — replace `os.environ.get("SPOOTY_API_URL", DEFAULT_API_URL)` and the token lookup with `get_config().spooty_api_url` etc.
    - `archivist/service/clients/subsonic_client.py` — replace the Navidrome env reads.
    - `archivist/service/clients/inbox_client.py` — replace the `MUSIC_INBOX_DIR` env read.
    - `archivist/service/clients/disk_client.py` — replace all five `MUSIC_*` env reads.
  Each client must call `get_config()` **inside** the function body (not at module import time) so a saved config edit reflects on the next request. Update the matching test files: replace `monkeypatch.setenv(...)` setup with `save_config(...)` setup (or a small fixture that patches `get_config` to return a test `Config`).
  - **Acceptance:** All four clients pass their existing tests against the config-store source. `tests/service/test_library_disk.py`, `test_library_inbox.py`, `test_library_downloads.py`, `test_library_browse.py` updated. Full suite stays green. **Backward compat preserved**: env vars set via systemd/`.env` still flow through (because `get_config` consults env when the file key is unset).

- [ ] {agent: lane-1, depends: settings-api-endpoints, id: settings-page-render} New `/settings` route + `archivist/service/settings_page.py` renderer. The page is a single form using the existing Mash Co. design system (tokens.css + cda.css + library.css). Layout: shared chassis header (the breadcrumb switcher must include `settings` as a third row — see `settings-link-in-switcher`), then a single-column form with sections (`Spooty`, `Navidrome`, `Music paths`) each holding the relevant fields. Field types: `url`, `text`, `password` (for secrets — masked, with placeholder `●●●●●●●●` when stored value is set). Save button posts to `/api/config`. After save: in-page banner shows `Saved at <HH:MM>` (moss accent) or the validation error (ember accent). No client-side framework — vanilla `<form>` POST with `fetch` + small inline JS.
  - **Acceptance:** `tests/service/test_settings_page.py` covers route returns 200, form contains all 10 fields with correct `type` attributes, password fields have placeholder when set, save button posts to `/api/config`. Visual smoke via `bash -c 'curl -sk https://cda.mattmariani.com/settings | grep -c "<input"'` returns 10. Full suite stays green.

- [ ] {agent: lane-2, depends: setup-config-store, id: settings-link-in-switcher} Extend the brand-lockup breadcrumb switcher in `archivist/service/library_switcher.py` to include a `settings` row alongside `rip` and `library`. Telemetry hint: `<N> knobs · saved <T> ago` where N is the count of non-default values and T is the human-relative time since the last config.json mtime (or `never` if file missing). Pull both via a tiny `get_config_summary() -> dict[str, int | str]` helper in `archivist/service/config.py` (lane-2 adds this helper as part of this task — it's a read-only consumer of config_store). The switcher's `active` param now accepts `"settings"`. Update existing tests in `tests/service/test_breadcrumb_switcher.py` accordingly.
  - **Acceptance:** Switcher dropdown has three rows in order (`rip`, `library`, `settings`). On `/settings`, the `settings` row carries `is-on`. Telemetry hint format verified in tests. Full suite stays green.

- [ ] {agent: lane-1, depends: settings-api-endpoints,config-runtime-wiring,settings-page-render,settings-link-in-switcher, id: deploy-and-smoke} Final integration. Pull lane-2's commits, run full suite locally green. Deploy: `ssh cm4 → git pull → systemctl restart`. Walk `/settings` in the browser: confirm the form loads with current values (URLs filled in, passwords showing the masked placeholder), edit one URL, save, observe the success banner, hit `/library/downloads` (or whichever panel matches the edited URL), confirm the panel reflects the change. Update `docs/operations/cm4-setup.md` adding a `Library Manager config` section noting (a) `~/.config/cd-archivist/config.json` is the new source of truth, (b) env vars + systemd Environment= still work as bootstrap fallbacks, (c) the `/settings` page is the primary editing surface. **Security note:** add a clear paragraph that `/settings` is currently unauthenticated; if the cda surface is publicly reachable, operator should either restrict to LAN or stand up Cloudflare Access before sharing the URL. Update `CHANGELOG.md` with the sprint-11 entry. Update `FEATURES.md` adding the Settings surface. Mark sprint-11 `status: closed`, append the final activity log entry.
  - **Acceptance:** `/settings` route returns 200 on the deployed CM4. Editing a value via the page changes the corresponding `/library/*` panel's behavior. Docs updated. Sprint-11 marked closed. Full suite green.

## Agent Roster

| Agent | Pane | Lane | Owns |
|---|---|---|---|
| lane-1 | (workspace pane lane-1) | config-store + settings API + settings page + deploy | `archivist/service/config.py` (new), `archivist/service/app.py` (`/api/config` + `/settings` route additions only), `archivist/service/settings_page.py` (new), `tests/service/test_config_store.py`, `tests/service/test_settings_api.py`, `tests/service/test_settings_page.py`, `docs/operations/cm4-setup.md` (Library Manager config section additions only), `CHANGELOG.md` + `FEATURES.md` (sprint-11 entries only) |
| lane-2 | (workspace pane lane-2) | runtime-wiring + switcher | `archivist/service/clients/*.py` (edit only — config-store consumption), `archivist/service/library_switcher.py` (add settings row + telemetry hint), `tests/service/test_library_disk.py` + `test_library_inbox.py` + `test_library_downloads.py` + `test_library_browse.py` (edit — switch fixtures from monkeypatch.setenv to save_config), `tests/service/test_breadcrumb_switcher.py` (settings row), and the `get_config_summary` helper inside `archivist/service/config.py` (read-only consumer; lane-1 reviews) |

**Cross-lane coordination:**
- `archivist/service/config.py` is owned by lane-1 (it lands in `setup-config-store`). lane-2 adds the read-only `get_config_summary()` helper at the bottom of the same file in `settings-link-in-switcher` — quick PR-style commit on top of lane-1's foundation. Coordinate timing: lane-1 commits + pushes `setup-config-store` first, lane-2 pulls before starting `settings-link-in-switcher`.
- `archivist/service/app.py` route additions: lane-1 only this sprint. lane-2 stays out of `app.py`.
- `archivist/service/library_switcher.py` is touched by lane-2 only.
- The four service-client modules + their tests: lane-2 owns. lane-1 doesn't touch.

## Decision Log

### 2026-05-20 — D-config-precedence — FILE > ENV > DEFAULT

The config-store consults the JSON file first, env vars second, defaults third. Rationale: the whole point of the settings page is editing without ssh; if env vars won, web edits would be silently masked by systemd's Environment= lines. The trade-off is that systemd vars become bootstrap-only — once the operator first saves via the web, the file is the source of truth for that key. For keys never touched via the web, env vars remain authoritative (because the file key is null).

### 2026-05-20 — D-settings-unauth-v1 — settings page ships unauthenticated, security gap documented

Sprint-11 ships `/settings` without auth. cda.mattmariani.com is publicly reachable via Cloudflare tunnel; an unauthenticated `/api/config POST` is a real risk. Operator-facing mitigation for v1: documented in `deploy-and-smoke` (LAN-restrict or stand up Cloudflare Access before exposing publicly). A follow-up sprint can wire Cloudflare Access or a token check — out of scope here to keep the sprint shippable.

## Ratification Log

_No ratifications yet._

## Contract Changes

### 2026-05-20 — service-clients read from config_store instead of os.environ

`spooty_client`, `subsonic_client`, `inbox_client`, `disk_client` now call `get_config()` at function-call time. Env-var values still flow through (config_store reads them as fallback when file key is null), so existing systemd / `.env` deployments keep working. Tests must use the new `save_config(...)` fixture pattern instead of `monkeypatch.setenv`.

### 2026-05-20 — brand-lockup breadcrumb switcher gains `settings` row

`render_switcher(active=...)` now accepts `"settings"` as a valid value alongside `"rip"` and `"library"`. The dropdown popover shows three rows. Existing callers passing `"rip"` or `"library"` are unaffected.

## Blockers

- _None._

## Activity Log

<!-- Per-agent updates land here, newest first. Format:

     ### {{date}} — {{agent}} — {{summary}}
     - what changed
     - why
     - links: PRs, audit entries -->

### 2026-05-20 — lane-1 — settings-api-endpoints closed

- New `GET /api/config` + `POST /api/config` routes in `app.py`.
  Routes live above the existing `_mount_library_routes` block and
  do not require `music_root` — `/api/config` is always available
  (the Settings page needs to bootstrap even when no music tree is
  configured yet).
- GET returns `Config` as JSON with `SECRET_FIELDS` (`navidrome_pass`,
  `spooty_api_token`) masked to the eight-bullet glyph `●●●●●●●●`
  when set, `null` when unset. Non-secret fields are returned
  verbatim.
- POST accepts a sparse `{key: value, ...}` body. Per-field validation:
  - `*_url` fields must start with `http://` or `https://`
  - `*_dir` fields must be absolute paths
  - non-secret string fields must be non-empty
  - secret fields with an empty-string value are **silently dropped**
    from the update (the "don't overwrite stored password with empty"
    behavior — the typical edit case where the operator changes a URL
    but doesn't retype their password)
  - `null` values are allowed and clear the corresponding key
  - non-string non-null values rejected
- POST returns 400 with `{error, details}` on validation failure. The
  `UnknownConfigKey` error path from `save_config` becomes a 400 with
  the offending key in the detail. After a successful save the
  response is the freshly-masked config (so the caller sees what
  actually landed, including the mask glyph for newly-set secrets).
- `tests/service/test_settings_api.py` (15 tests). Covers GET
  masking (set vs unset secret), POST happy path + dir-field happy
  path, validation rejections (non-http URL, relative dir, empty
  non-secret, non-string, non-object body, invalid JSON), empty-pass
  no-change behavior (with + without other fields in the same
  payload), null-clears-a-field, and unknown-key rejection (whole
  payload rejected — no partial write).
- Full suite at this commit: 828/828 green (my 15 new + 813 prior).
  (Lane-2's in-progress client refactor is uncommitted and not
  included in this commit; their broken-mid-refactor state in the
  shared working tree doesn't affect what's in this commit's tree.)

### 2026-05-20 — lane-1 — setup-config-store closed

- New `archivist/service/config.py`. Frozen `Config` dataclass with
  the 10 sprint-11 knobs (5 URL/cred slots as `str | None`, 5 music
  dirs with sensible defaults). `get_config()` resolves each field
  via FILE > ENV > DEFAULT per D-config-precedence and caches the
  result; `reload_config()` clears the cache; `save_config(updates)`
  validates keys against `CONFIG_KEYS`, merges sparsely with the
  existing file, writes through `os.open(... O_CREAT, 0o600)` +
  `os.replace(tmp, real)` for atomicity, and auto-reloads. Exposes
  `SECRET_FIELDS` (frozenset of fields the API layer must mask) and
  `UnknownConfigKey` for the validation error path. File path is
  `$ARCHIVIST_CONFIG_PATH` or `~/.config/cd-archivist/config.json`.
- File-with-null falls through to env (so an operator who hand-edits
  the JSON to `null` a key restores systemd-bootstrap behavior).
  Empty env values treated as unset (matches `os.environ.get` +
  truthiness pattern used by the sprint-10 clients).
- `tests/service/test_config_store.py` (15 tests). Covers the
  sprint-11 acceptance list (a-e) plus: file-null falls through to
  env, empty env treated as unset, sparse updates preserve untouched
  keys, save_config failure cleans up the .tmp file, save_config
  auto-reloads (no manual reload needed), CONFIG_KEYS matches the
  dataclass fields. Atomic-write test verifies `os.replace` is the
  actual seam (not just an absence of `.tmp` after).
- Full suite: 813/813 green (798 baseline + 15 new).
- Next: settings-api-endpoints (lane-1) consumes this; lane-2's
  config-runtime-wiring + settings-link-in-switcher both depend on
  this commit.

### 2026-05-20 — orc — sprint-11 plan drafted (Settings page)

- Drafted in response to operator feedback after sprint-10 deploy. Two facts driving the design: (1) the four Library panels read URLs/creds from `.env` + systemd today, which requires ssh to edit — operator wants browser editing. (2) sprint-10's service-clients pattern (read env at call-time) makes the refactor cheap.
- Six tasks across two lanes. Wave 0: setup-config-store (lane-1). Wave 1: settings-api-endpoints (lane-1) + config-runtime-wiring (lane-2). Wave 2: settings-page-render (lane-1) + settings-link-in-switcher (lane-2). Wave 3: deploy-and-smoke (lane-1).
- Two decisions logged upfront: D-config-precedence (FILE > ENV > DEFAULT — settings page edits win over systemd) and D-settings-unauth-v1 (unauthenticated for v1, security gap documented in the deploy doc).
- Lane-1 critical path (4 tasks); lane-2 has 2 substantial tasks (the 4-client refactor is the chunky one).
- Sprint-10 cleanly closed earlier today including the spooty endpoint hotfix (`f7756c1`); all four Library panels live on the CM4 with real data. Sprint-11 builds directly on sprint-10's service-clients pattern.
