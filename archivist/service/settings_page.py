"""Settings page — `/settings`.

Sprint-11 / settings-page-render. A single form bound to
`/api/config`. Operator edits URLs / creds / music dirs without ssh.

Layout: chassis header (brand-lockup switcher with `settings` as the
third row — landed by lane-2's `settings-link-in-switcher` task),
then one column with three sections (Spooty / Navidrome / Music
paths). Field types match the value semantics: `url` for URL fields,
`password` for secrets (masked by the browser; placeholder shows
`●●●●●●●●` when a value is stored), `text` for the dir paths and
the Navidrome user.

Save button posts the form as JSON to `/api/config` via `fetch`.
After save: a banner shows `Saved at HH:MM` (moss accent) on 200 or
the validation error (ember accent) on 4xx. The banner is plain
HTML; no client-side framework.
"""

from __future__ import annotations

import html as _html
from typing import Any

from archivist.service.config import SECRET_FIELDS, Config, as_dict


# Section spec — each entry is (section_title, [(field_name, label, type), ...]).
# Field order inside each section matches the operator's mental model
# (URL first, then credentials).
_SECTIONS: tuple[tuple[str, tuple[tuple[str, str, str], ...]], ...] = (
    ("Spooty", (
        ("spooty_api_url",    "API URL",    "url"),
        ("spooty_api_token",  "API token",  "password"),
    )),
    ("Navidrome", (
        ("navidrome_url",     "URL",         "url"),
        ("navidrome_user",    "Username",    "text"),
        ("navidrome_pass",    "Password",    "password"),
    )),
    ("Music paths", (
        ("music_inbox_dir",   "Inbox dir",   "text"),
        ("music_library_dir", "Library dir", "text"),
        ("music_archive_dir", "Archive dir", "text"),
        ("music_spooty_dir",  "Spooty dir",  "text"),
        ("music_review_dir",  "Review dir",  "text"),
    )),
)


_MASK = "●" * 8


def _render_field(
    field_name: str, label: str, field_type: str, cfg_dict: dict[str, Any],
) -> str:
    """Render one labeled input. Password fields never carry the
    stored value — they show a placeholder when set so the operator
    can leave them blank to mean "no change" (matches the API contract
    in settings-api-endpoints)."""
    is_secret = field_name in SECRET_FIELDS
    current = cfg_dict.get(field_name)
    label_html = _html.escape(label)
    name_html = _html.escape(field_name)

    if is_secret:
        # Type=password; never re-populate the value; placeholder
        # signals whether anything is stored.
        placeholder = _MASK if current else "(unset)"
        input_html = (
            f'<input type="password" id="{name_html}" name="{name_html}" '
            f'placeholder="{_html.escape(placeholder)}" '
            'autocomplete="new-password" spellcheck="false" />'
        )
    else:
        value_attr = ""
        if current is not None and current != "":
            value_attr = f' value="{_html.escape(str(current), quote=True)}"'
        input_html = (
            f'<input type="{_html.escape(field_type)}" '
            f'id="{name_html}" name="{name_html}"{value_attr} '
            'autocomplete="off" spellcheck="false" />'
        )
    return (
        '<div class="cda-settings-field">'
        f'<label for="{name_html}">{label_html}</label>'
        f'{input_html}'
        '</div>'
    )


def _render_section(title: str, fields: tuple[tuple[str, str, str], ...],
                    cfg_dict: dict[str, Any]) -> str:
    fields_html = "".join(_render_field(n, l, t, cfg_dict) for n, l, t in fields)
    return (
        '<section class="cda-settings-section">'
        f'<h2>{_html.escape(title)}</h2>'
        f'{fields_html}'
        '</section>'
    )


_SAVE_JS = r"""
(function(){
  const form = document.querySelector('[data-cda-settings-form]');
  if (!form) return;
  const banner = document.querySelector('[data-cda-settings-banner]');
  function setBanner(kind, msg){
    if (!banner) return;
    banner.className = 'cda-settings-banner is-' + kind;
    banner.textContent = msg;
    banner.removeAttribute('hidden');
  }
  function pad(n){ return n < 10 ? '0' + n : '' + n; }
  function nowHHMM(){
    const d = new Date();
    return pad(d.getHours()) + ':' + pad(d.getMinutes());
  }
  form.addEventListener('submit', function(e){
    e.preventDefault();
    const fd = new FormData(form);
    const payload = {};
    for (const [k, v] of fd.entries()){
      // Empty-string for non-secret fields = "no change" on the
      // client side too — drop them so the API doesn't reject empty
      // non-secret values that the operator simply didn't touch.
      const isSecret = (k === 'navidrome_pass' || k === 'spooty_api_token');
      if (v === '' && !isSecret) continue;
      payload[k] = v;
    }
    fetch('/api/config', {
      method: 'POST',
      headers: {'content-type': 'application/json'},
      body: JSON.stringify(payload),
    }).then(function(r){
      return r.json().then(function(body){ return {status: r.status, body: body}; });
    }).then(function(res){
      if (res.status >= 400){
        const details = (res.body && res.body.details) ||
                        (res.body && res.body.detail) ||
                        'Save failed.';
        const msg = Array.isArray(details) ? details.join(' · ') : String(details);
        setBanner('error', msg);
        return;
      }
      setBanner('ok', 'Saved at ' + nowHHMM());
      // Reset password fields so the placeholder visibly updates;
      // the rest stay populated (the response is the new state).
      form.querySelectorAll('input[type=password]').forEach(function(el){
        el.value = '';
      });
    }).catch(function(err){
      setBanner('error', 'Network error: ' + (err && err.message || err));
    });
  });
})();
""".strip()


_INLINE_CSS = """
.cda-settings-main { max-width: 720px; margin: 24px auto; padding: 0 20px;
  display: flex; flex-direction: column; gap: 18px; }
.cda-settings-h { margin: 0; }
.cda-settings-h .eyebrow {
  font: 700 10px/1 var(--font-mono); letter-spacing: 0.14em;
  text-transform: uppercase; color: var(--mash-pulp);
}
.cda-settings-h h1 {
  margin: 4px 0 0; font: 700 24px/1.15 var(--font-display);
  letter-spacing: -0.015em; color: var(--fg);
}
.cda-settings-h .sub {
  font: 400 13px/1.5 var(--font-body); color: var(--fg-muted);
  margin: 4px 0 0; max-width: 64ch;
}
.cda-settings-section {
  display: flex; flex-direction: column; gap: 10px;
  padding: 16px 18px; border: 1px solid var(--line);
  border-radius: var(--r-3); background: var(--surface);
}
.cda-settings-section h2 {
  margin: 0 0 6px; font: 700 13px/1 var(--font-mono);
  letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--fg-2);
}
.cda-settings-field {
  display: grid; grid-template-columns: 140px 1fr; gap: 12px;
  align-items: center;
}
.cda-settings-field label {
  font: 500 12px/1 var(--font-mono); color: var(--fg-2);
}
.cda-settings-field input {
  font: 500 13px/1.4 var(--font-mono); color: var(--fg);
  background: var(--ink-0); border: 1px solid var(--line);
  border-radius: var(--r-2); padding: 8px 10px; width: 100%;
}
.cda-settings-field input::placeholder { color: var(--fg-quiet); }
.cda-settings-field input:focus {
  outline: none; border-color: var(--mash-pulp);
}
.cda-settings-actions {
  display: flex; align-items: center; gap: 14px;
}
.cda-settings-save {
  font: 700 12px/1 var(--font-mono); letter-spacing: 0.06em;
  text-transform: uppercase; color: var(--bone);
  background: var(--mash-pulp); border: 1px solid var(--mash-pulp-deep);
  border-radius: var(--r-2); padding: 10px 16px; cursor: pointer;
}
.cda-settings-save:hover { background: var(--mash-pulp-deep); }
.cda-settings-banner {
  font: 500 12px/1.4 var(--font-mono); padding: 8px 12px;
  border: 1px solid var(--line); border-radius: var(--r-2);
}
.cda-settings-banner.is-ok {
  color: var(--moss); border-color: var(--moss);
  background: var(--moss-soft, transparent);
}
.cda-settings-banner.is-error {
  color: var(--ember); border-color: var(--ember);
  background: var(--ember-soft, transparent);
}
""".strip()


def _render_settings_header() -> str:
    """Chassis header for the settings page. Uses the breadcrumb
    switcher with `active="settings"` (landed by lane-2's
    settings-link-in-switcher). Falls back to `active="library"` if
    the switcher doesn't yet accept the new value, so this commit
    stays green at its tree state even before lane-2's commit lands."""
    from archivist.service.library_switcher import render_switcher
    try:
        switcher = render_switcher(
            active="settings",
            rip_telemetry="",
            library_telemetry="",
        )
    except ValueError:
        # Pre-lane-2: switcher only accepts rip/library. Settings
        # still loads; the brand mark + library row remain clickable.
        switcher = render_switcher(
            active="library",
            rip_telemetry="",
            library_telemetry="",
        )
    return (
        '<header class="page-header">'
        '<div class="header-left">'
        f'{switcher}'
        '</div>'
        '</header>'
    )


def render_settings_page(config: Config) -> str:
    """Render the full settings page HTML."""
    cfg_dict = as_dict(config)
    sections_html = "".join(
        _render_section(title, fields, cfg_dict)
        for title, fields in _SECTIONS
    )
    return (
        '<!doctype html>'
        '<html lang="en" data-theme="dark">'
        '<head>'
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>cd-archivist · settings</title>'
        '<link rel="icon" type="image/png" sizes="32x32" '
        'href="/static/img/brand/cd-a-favicon-32x32.png">'
        '<link rel="manifest" href="/static/manifest.webmanifest">'
        '<meta name="theme-color" content="#07090c">'
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link rel="stylesheet" '
        'href="https://fonts.googleapis.com/css2'
        '?family=Bricolage+Grotesque:wght@600;800&display=swap">'
        '<link rel="stylesheet" '
        'href="https://fonts.googleapis.com/css2'
        '?family=Inter+Tight:wght@400;500;700&display=swap">'
        '<link rel="stylesheet" '
        'href="https://fonts.googleapis.com/css2'
        '?family=JetBrains+Mono:wght@400;500&display=swap">'
        '<link rel="stylesheet" href="/static/css/tokens.css">'
        '<link rel="stylesheet" href="/static/css/cda.css">'
        '<link rel="stylesheet" href="/static/css/library.css">'
        f'<style>{_INLINE_CSS}</style>'
        '</head>'
        '<body data-surface="settings">'
        f'{_render_settings_header()}'
        '<main class="cda-settings-main">'
        '<div class="cda-settings-h">'
        '<span class="eyebrow">Settings · v1</span>'
        '<h1>Library Manager configuration</h1>'
        '<p class="sub">URLs and credentials for the four Library '
        'panels. Saves to <code>~/.config/cd-archivist/config.json</code>. '
        'Empty password fields are ignored (leave blank to keep stored '
        'value).</p>'
        '</div>'
        '<form data-cda-settings-form>'
        f'{sections_html}'
        '<div class="cda-settings-actions">'
        '<button type="submit" class="cda-settings-save">Save</button>'
        '<div class="cda-settings-banner" data-cda-settings-banner hidden></div>'
        '</div>'
        '</form>'
        '</main>'
        '<script>'
        f'{_SAVE_JS}'
        '</script>'
        '<script>'
        # Bring in the switcher's open/close behavior so the dropdown
        # works the same as on other surfaces.
        'try { '
        + _switcher_js_inline()
        + ' } catch (e) {}'
        '</script>'
        '</body></html>'
    )


def _switcher_js_inline() -> str:
    from archivist.service.library_switcher import SWITCHER_JS
    return SWITCHER_JS
