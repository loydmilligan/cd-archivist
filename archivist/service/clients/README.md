# archivist.service.clients

Service-clients package for the Library Manager panels (sprint-10).

Each module here is a **thin typed wrapper around one external surface**
— a filesystem walk, a REST API, a Subsonic API. Panel implementations
in `archivist/service/library_*_panel.py` import the client they need
and render its data; they never touch `requests` or `shutil` directly.

## Contract

1. **One module per external surface.** Examples:
   - `disk_client.py` — `shutil.disk_usage()` + filesystem walks
   - `inbox_client.py` — filesystem walk of `$MUSIC_INBOX_DIR`
   - `spooty_client.py` — REST API at `$SPOOTY_API_URL`
   - `subsonic_client.py` — Subsonic API against `$NAVIDROME_URL`

2. **Typed return values.** Use `dataclasses` (frozen where reasonable)
   for snapshots and rows. No bare dicts crossing the module boundary.

3. **Typed exceptions on failure.** Each client defines its own
   exception class (e.g., `SpootyUnavailable`, `NavidromeUnavailable`)
   raised on connection / protocol failure. Callers catch the typed
   exception and degrade the panel to an empty-state.

4. **Configuration via environment variables.** No hardcoded URLs or
   credentials. Read at call time (not import time) so tests can
   monkeypatch `os.environ`. The env-var names this package owns:

   | Var | Owner | Default |
   |---|---|---|
   | `SPOOTY_API_URL` | spooty_client | `http://192.168.6.38:3003/api` |
   | `SPOOTY_API_TOKEN` | spooty_client | _(unset; LAN-only for now)_ |
   | `NAVIDROME_URL` | subsonic_client | _(required)_ |
   | `NAVIDROME_USER` | subsonic_client | _(required)_ |
   | `NAVIDROME_PASS` | subsonic_client | _(required)_ |
   | `MUSIC_INBOX_DIR` | inbox_client | `/srv/music/inbox` |
   | `MUSIC_REVIEW_DIR` | inbox_client (read), future review panel | `/srv/music/review` |
   | `MUSIC_ARCHIVE_DIR` | disk_client | `/mnt/archive` |

5. **Idempotent, side-effect-free reads.** List / get / search methods
   must be safe to call repeatedly. Polling cadence is set by the
   panel (via `<meta name="library-poll-ms">`), not by the client.

6. **Side effects are named.** Mutating methods (`submit_playlist`,
   `retry_track`, `delete_track`, `import_now`) live in the same
   client module as the matching reads, but are clearly named as
   verbs. They return a typed result (e.g., `{status, message}`),
   never raise on a normal "operation rejected" response — only on
   transport failure.

7. **Network timeouts are short.** Default 5s for HTTP, 30s for
   subprocess invocations. The Library Manager is a live UI; a
   hanging client is worse than a degraded panel.

## What lives outside this package

- HTML rendering — `archivist/service/library_*_panel.py`
- Route handlers — `archivist/service/app.py`
- Polling dispatcher — `archivist/service/chassis_js.py`
- Panel inventory (copy, glyphs) — `archivist/service/library_panel_inventory.py`

Clients return data. Panels turn data into HTML. The split keeps
each layer testable in isolation.
