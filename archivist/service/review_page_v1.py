"""Review v1 HTML page (sprint-6 Bucket C / impl-review-page-v1).

Read-only surface: each folder card shows
  - the explainer text from review_explainer.explain(folder)
  - a <details> block with copy-paste shell commands for the operator
  - the disc photo (if captured) and the folder path
  - a link to the beets web UI at http://cm4:8337/

No POST forms in v1. In-UI candidate selection is sprint-7 (see
Sprint-7 Candidates in sprint-6.md).
"""
from __future__ import annotations

import html as _html
from pathlib import Path

from archivist.service.review_explainer import explain


def _esc(s: object) -> str:
    return _html.escape("" if s is None else str(s), quote=True)


def _manual_steps(folder_path: Path, folder_name: str) -> str:
    cmd = (
        f"docker exec -it cd_beets beet import "
        f"/downloads/{folder_name}"
    )
    cmd_by_id = (
        f"docker exec -it cd_beets beet import --search-id <MBID> "
        f"/downloads/{folder_name}"
    )
    return (
        '<details class="manual-steps">'
        '<summary>manual steps</summary>'
        '<pre><code>'
        f'{_esc(cmd)}\n'
        '\n'
        f'# or, if you have a MusicBrainz release ID:\n'
        f'{_esc(cmd_by_id)}\n'
        '</code></pre>'
        f'<p class="hint">folder: <code>{_esc(folder_path)}</code></p>'
        '</details>'
    )


def _render_card(folder_path: Path) -> str:
    name = _esc(folder_path.name)
    why = _esc(explain(folder_path))
    photo_html = ""
    photo = folder_path / "captures" / "disc-photo.jpg"
    if photo.is_file():
        photo_html = (
            f'<img class="disc-photo" alt="disc photo for {name}" '
            f'src="/library/{name}/photo" />'
        )
    return (
        f'<article class="card" data-folder="{name}">'
        f'<header><h3 class="card-title">{name}</h3></header>'
        f'{photo_html}'
        f'<p class="why-in-review">{why}</p>'
        f'{_manual_steps(folder_path, folder_path.name)}'
        '<p class="meta">'
        '<a href="http://cm4:8337/" target="_blank" rel="noopener">'
        'open beets web UI'
        '</a>'
        '</p>'
        '</article>'
    )


_STYLES = """
:root { color-scheme: dark; }
body { font-family: var(--font-body, system-ui); background: var(--bg, #111);
       color: var(--ink, #eee); margin: 0; padding: var(--s-4, 16px); }
.card { background: var(--surface-2, #222); border: 1px solid var(--line, #333);
        border-left: 3px solid var(--warn, #ffb84a);
        border-radius: var(--r-2, 4px); padding: var(--s-3, 12px);
        margin-bottom: var(--s-3, 12px); }
.card-title { margin: 0 0 var(--s-2, 8px) 0; font-size: var(--fs-md, 14px); }
.why-in-review { color: var(--ink-2, #ddd); margin: var(--s-2, 8px) 0; }
.manual-steps pre { background: var(--bg, #111); padding: var(--s-2, 8px);
                    border-radius: var(--r-2, 4px);
                    overflow-x: auto; }
.disc-photo { max-width: 200px; border-radius: var(--r-2, 4px);
              float: right; margin-left: var(--s-3, 12px); }
"""


def render_review_v1(
    *, review_root: Path | None, inbox_root: Path | None,
) -> str:
    folders: list[Path] = []
    for root in (review_root, inbox_root):
        if root is None or not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            # Reuse sprint-5's filter loosely: inbox children need a READY
            # marker and no PROCESSING to be reviewable.
            if root is inbox_root:
                if not (child / "READY").is_file():
                    continue
                if (child / "PROCESSING").exists():
                    continue
            folders.append(child)

    cards_html = "\n".join(_render_card(f) for f in folders)
    if not cards_html:
        cards_html = (
            '<p class="empty-hint">nothing to review.</p>'
        )
    return (
        '<!doctype html>'
        '<html lang="en" data-theme="dark">'
        '<head>'
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>cd-archivist · review</title>'
        '<link rel="stylesheet" href="/static/css/tokens.css">'
        f'<style>{_STYLES}</style>'
        '</head>'
        '<body>'
        '<main>'
        '<h1>review</h1>'
        f'{cards_html}'
        '</main>'
        '</body></html>'
    )
