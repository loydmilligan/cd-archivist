"""Sprint-10 / chassis-poll-dispatcher — per-panel polling cadence.

The dispatcher lives in ``archivist.service.chassis_js.CHASSIS_JS`` as a
JS string. There is no JS runtime in this test suite, so these tests
assert the structural contract of the source: meta-tag names, the
no-op gate, the setInterval wiring, and the visibilitychange handler.

The acceptance criteria in sprint-10.md call out:
  (a) no-op when no meta present
  (b) fires fetch on interval when meta is present
  (c) clears on page-hide
"""

from __future__ import annotations

from archivist.service.chassis_js import CHASSIS_JS


# ---- contract: meta tag names -------------------------------------------------

def test_dispatcher_reads_documented_meta_tag_names() -> None:
    """Per-panel render modules emit these exact meta names — must
    match the contract documented in chassis_js.py's docstring."""
    assert 'meta[name="library-poll-ms"]' in CHASSIS_JS
    assert 'meta[name="library-poll-endpoint"]' in CHASSIS_JS


def test_dispatcher_reads_meta_content_attribute() -> None:
    """Cadence + endpoint live on the `content` attribute."""
    assert "getAttribute('content')" in CHASSIS_JS


# ---- (a) no-op when no meta present ------------------------------------------

def test_dispatcher_returns_null_when_meta_absent() -> None:
    """readPollMeta() must short-circuit to null when either meta tag
    is missing — that's how `/rip` and the landing grid stay quiet."""
    assert "if (!msEl || !epEl) return null;" in CHASSIS_JS


def test_dispatcher_returns_null_when_ms_nonpositive() -> None:
    """A zero or negative cadence is treated as 'disabled', mirroring
    the docstring contract ('values <= 0 disable polling')."""
    assert "ms <= 0" in CHASSIS_JS


def test_start_polling_is_guarded_by_meta_presence() -> None:
    """startPolling must re-check meta and bail before scheduling so
    a page with no meta never gets a timer."""
    assert "function startPolling()" in CHASSIS_JS
    # The function body checks readPollMeta() and returns when absent.
    start_block = CHASSIS_JS.split("function startPolling()", 1)[1]
    start_block = start_block.split("function stopPolling()", 1)[0]
    assert "readPollMeta()" in start_block
    assert "if (!meta) return;" in start_block


def test_initial_start_is_gated_on_meta() -> None:
    """At page load, polling only kicks off when meta is present."""
    assert "if (readPollMeta()) {" in CHASSIS_JS
    assert "startPolling();" in CHASSIS_JS


# ---- (b) fires fetch on interval when meta is present ------------------------

def test_dispatcher_uses_setInterval_with_meta_ms() -> None:
    """The interval is driven by the parsed meta-ms value, not a
    hard-coded constant."""
    assert "setInterval(pollTick, meta.ms)" in CHASSIS_JS


def test_poll_tick_fetches_meta_endpoint() -> None:
    """Each tick fetches the endpoint from the meta tag verbatim."""
    assert "fetch(meta.endpoint)" in CHASSIS_JS


def test_poll_tick_dispatches_custom_event_on_success() -> None:
    """Per-panel modules subscribe to `library:poll-tick` to consume
    the response — that's the documented hand-off seam."""
    assert "library:poll-tick" in CHASSIS_JS
    # both branches (then + catch) dispatch the event
    assert CHASSIS_JS.count("library:poll-tick") >= 2


def test_poll_tick_error_branch_carries_error_in_detail() -> None:
    """Failed fetches must still notify panels (so they can show an
    "unavailable" state) rather than swallow the error silently."""
    assert "error: err" in CHASSIS_JS


# ---- (c) clears on page-hide --------------------------------------------------

def test_visibilitychange_handler_is_wired() -> None:
    assert "addEventListener('visibilitychange'" in CHASSIS_JS


def test_visibility_hidden_stops_polling_and_visible_restarts() -> None:
    """Background tabs must not hammer endpoints; foreground tabs
    must resume cleanly."""
    handler_block = CHASSIS_JS.split("'visibilitychange'", 1)[1]
    # The handler body should reference both stop and start paths.
    assert "document.hidden" in handler_block
    assert "stopPolling()" in handler_block
    assert "startPolling()" in handler_block


def test_stop_polling_calls_clearInterval_and_nulls_timer() -> None:
    """clearInterval + nulling the handle is what makes a subsequent
    startPolling() schedulable again."""
    stop_block = CHASSIS_JS.split("function stopPolling()", 1)[1]
    stop_block = stop_block.split("addEventListener('visibilitychange'", 1)[0]
    assert "clearInterval(pollTimer)" in stop_block
    assert "pollTimer = null" in stop_block


def test_start_polling_is_idempotent() -> None:
    """Calling startPolling() twice (e.g., visible -> visible) must
    not stack timers — the second call short-circuits."""
    start_block = CHASSIS_JS.split("function startPolling()", 1)[1]
    start_block = start_block.split("function stopPolling()", 1)[0]
    assert "if (pollTimer !== null) return;" in start_block


# ---- drive-status polling is untouched ---------------------------------------

def test_drive_status_polling_remains_chassis_level() -> None:
    """The new dispatcher is independent of the existing
    /api/drive/status polling — both must coexist."""
    assert "/api/drive/status" in CHASSIS_JS
    assert "setInterval(refreshDriveStatus, 5000)" in CHASSIS_JS
