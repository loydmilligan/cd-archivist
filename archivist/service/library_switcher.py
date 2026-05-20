"""Brand-lockup breadcrumb switcher — surface picker.

Sprint-9 / breadcrumb-switcher per
docs/reference/mashco-design-system/cd-archivist-library/handoff/build-prompt.md §2.

Recipe (build-prompt §2):

    [cd/a]  ·  rip ▾   ← active-surface label is clickable
            └─ dropdown:
               Surfaces
               ✓ rip      4 ripping · 2 review
                 library  3 inbox · 1 download

The shared element id `surface-switcher-pop` is the dropdown popover;
its `data-open` attribute is toggled by the inline JS below when the
`cda-switcher-btn` is clicked. The dropdown is collapsed on initial
render (no `data-open` attribute).
"""

from __future__ import annotations

import html as _html


def render_switcher(
    *,
    active: str,
    rip_telemetry: str = "",
    library_telemetry: str = "",
) -> str:
    """Render the breadcrumb switcher.

    `active` must be "rip" or "library". The button label and the row
    `is-on` class follow.

    `rip_telemetry` and `library_telemetry` are one-line hints rendered
    in each dropdown row's `.meta` span. Callers pass live numbers for
    the active surface; the other surface is allowed to be a static
    placeholder (per build-prompt §2 — per-panel briefs revisit).
    """
    if active not in ("rip", "library"):
        raise ValueError(f"active must be 'rip' or 'library'; got {active!r}")

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
