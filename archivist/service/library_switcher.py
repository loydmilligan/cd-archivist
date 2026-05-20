"""Brand-lockup breadcrumb switcher — surface picker.

Sprint-9 / breadcrumb-switcher per
docs/reference/mashco-design-system/cd-archivist-library/handoff/build-prompt.md §2.

Recipe (build-prompt §2):

    [cd/a]  ·  rip ▾   ← active-surface label is clickable
            └─ dropdown:
               Surfaces
               ✓ rip       4 ripping · 2 review
                 library   3 inbox · 1 download
                 settings  3 knobs · saved 2h ago

Sprint-11 / settings-link-in-switcher: the dropdown gained a `settings`
row. Its telemetry hint comes from
`archivist.service.config.get_config_summary()` (`N knobs · saved T ago`).
Callers can pass a precomputed `settings_telemetry` string; when left
empty the function looks the summary up itself so callers without
ergonomic access to `get_config_summary` (e.g., kanban_page) don't have
to plumb it through.

The shared element id `surface-switcher-pop` is the dropdown popover;
its `data-open` attribute is toggled by the inline JS below when the
`cda-switcher-btn` is clicked. The dropdown is collapsed on initial
render (no `data-open` attribute).
"""

from __future__ import annotations

import html as _html


VALID_ACTIVE = ("rip", "library", "settings")


def _default_settings_telemetry() -> str:
    """Pull `N knobs · saved T ago` from the config store. Falls back
    to the static placeholder if the helper or the store blow up — the
    switcher must never break the page."""
    try:
        from archivist.service.config import get_config_summary
        summary = get_config_summary()
        return f'{summary.get("knobs", 0)} knobs · saved {summary.get("saved", "never")}'
    except Exception:  # noqa: BLE001 — UI helper must not raise
        return "0 knobs · saved never"


def render_switcher(
    *,
    active: str,
    rip_telemetry: str = "",
    library_telemetry: str = "",
    settings_telemetry: str | None = None,
) -> str:
    """Render the breadcrumb switcher.

    `active` must be one of `VALID_ACTIVE` (`"rip"`, `"library"`,
    `"settings"`). The button label and the row `is-on` class follow.

    Telemetry args are one-line hints rendered in each dropdown row's
    `.meta` span. Callers pass live numbers for the active surface;
    the other surfaces are allowed to be static placeholders (per
    build-prompt §2). `settings_telemetry=None` (the default) pulls
    the hint from `get_config_summary()` so callers don't have to.
    Pass an explicit string (including `""`) to override.
    """
    if active not in VALID_ACTIVE:
        raise ValueError(
            f"active must be one of {VALID_ACTIVE}; got {active!r}"
        )

    if settings_telemetry is None:
        settings_telemetry = _default_settings_telemetry()

    def _row(surface_id: str, telemetry: str) -> str:
        on = "is-on" if active == surface_id else ""
        classes = f"cda-switcher-row {on}".strip()
        return (
            f'<a class="{classes}" href="/{_html.escape(surface_id)}" '
            f'data-surface="{_html.escape(surface_id)}">'
            '<span class="check">✓</span>'
            f'<span class="name">{_html.escape(surface_id)}</span>'
            f'<span class="meta">{_html.escape(telemetry)}</span>'
            '</a>'
        )

    return (
        '<div class="cda-switcher" data-surface-switcher>'
        '<span class="cda-brand-mark cda-brand-mark--header">cd/a</span>'
        '<span class="cda-switcher-sep">·</span>'
        '<button type="button" class="cda-switcher-btn" '
        'aria-haspopup="true" aria-expanded="false" '
        'aria-controls="surface-switcher-pop" '
        'data-switcher-toggle>'
        f'{_html.escape(active)}'
        '<span class="cda-switcher-caret">▾</span>'
        '</button>'
        '<div id="surface-switcher-pop" class="cda-switcher-pop" '
        'data-surface-switcher-pop hidden>'
        '<div class="cda-switcher-pop-h">Surfaces</div>'
        f'{_row("rip", rip_telemetry)}'
        f'{_row("library", library_telemetry)}'
        f'{_row("settings", settings_telemetry)}'
        '</div>'
        '</div>'
    )


# Tiny inline JS that toggles the dropdown. Lives in this module so
# both surfaces (kanban_page + library_page) inject the same script —
# no duplication. Click outside the switcher closes the popover.
SWITCHER_JS = """
(function(){
  const root = document.querySelector('[data-surface-switcher]');
  if (!root) return;
  const btn = root.querySelector('[data-switcher-toggle]');
  const pop = root.querySelector('[data-surface-switcher-pop]');
  if (!btn || !pop) return;
  function setOpen(open) {
    if (open) {
      pop.removeAttribute('hidden');
      btn.setAttribute('aria-expanded', 'true');
    } else {
      pop.setAttribute('hidden', '');
      btn.setAttribute('aria-expanded', 'false');
    }
  }
  btn.addEventListener('click', function(e){
    e.stopPropagation();
    setOpen(pop.hasAttribute('hidden'));
  });
  document.addEventListener('click', function(e){
    if (!root.contains(e.target)) setOpen(false);
  });
  document.addEventListener('keydown', function(e){
    if (e.key === 'Escape') setOpen(false);
  });
})();
""".strip()
