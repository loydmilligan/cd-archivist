"""In-UI beets review handlers + page renderers (sprint-5 / Bucket B).

Module owns the /api/review/* surface per
docs/design/2026-05-16-in-ui-beets-review.md and the route-test
contracts in `tests/service/test_review_endpoints.py`. Route
registrations live in `archivist/service/app.py`; the handlers
+ helpers live here to keep `app.py` thin.

Folder discovery follows D-review-folder-discovery: aggregate
direct children of MUSIC_REVIEW_DIR + READY-no-PROCESSING children
of MUSIC_INBOX_DIR. MB queries follow D-mb-query-direct-not-beets:
`musicbrainzngs` directly for candidates, `docker exec cd_beets
beet import ...` for the actual file moves.
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import musicbrainzngs
from fastapi import HTTPException
from pydantic import BaseModel, ValidationError

from archivist.service.mb_client import get_mb_client

logger = logging.getLogger(__name__)

_AUDIO_GLOB = "*.flac"
_BUSY_STATES = {"RIP", "EJECT", "CAPTURE"}
_BEETS_TIMEOUT_SECONDS = 120
_DELTA_WARN_SECONDS = 5
_DEFAULT_BYTES_PER_SECOND = 44100 * 2 * 2  # CDDA stereo 16-bit


# ============== folder discovery ====================================


@dataclass
class _FolderEntry:
    name: str
    source: str  # "review" | "inbox-stuck"
    path: Path
    audio_count: int
    total_seconds: int
    source_json: dict | None


def _audio_count_and_duration(folder: Path) -> tuple[int, int]:
    flacs = sorted(folder.glob(_AUDIO_GLOB))
    total_bytes = sum(f.stat().st_size for f in flacs)
    return len(flacs), max(0, total_bytes // _DEFAULT_BYTES_PER_SECOND)


def _load_source_json(folder: Path) -> dict | None:
    p = folder / "source.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("source.json at %s is unreadable; treating as missing", p)
        return None


def list_review_folders(
    review_root: Path | None,
    inbox_root: Path | None,
) -> list[dict]:
    entries: dict[str, _FolderEntry] = {}

    if review_root is not None and review_root.is_dir():
        for child in sorted(review_root.iterdir()):
            if not child.is_dir():
                continue
            audio_count, total = _audio_count_and_duration(child)
            entries[child.name] = _FolderEntry(
                name=child.name, source="review", path=child,
                audio_count=audio_count, total_seconds=total,
                source_json=_load_source_json(child),
            )

    if inbox_root is not None and inbox_root.is_dir():
        for child in sorted(inbox_root.iterdir()):
            if not child.is_dir():
                continue
            if not (child / "READY").is_file():
                continue
            if (child / "PROCESSING").exists():
                continue
            if child.name in entries:
                continue
            audio_count, total = _audio_count_and_duration(child)
            entries[child.name] = _FolderEntry(
                name=child.name, source="inbox-stuck", path=child,
                audio_count=audio_count, total_seconds=total,
                source_json=_load_source_json(child),
            )

    # Sort by mtime descending.
    out = sorted(
        entries.values(),
        key=lambda e: e.path.stat().st_mtime,
        reverse=True,
    )
    return [
        {
            "name": e.name,
            "source": e.source,
            "audio_count": e.audio_count,
            "total_seconds": e.total_seconds,
            "source_json": e.source_json,
        }
        for e in out
    ]


def find_folder(
    folder_name: str,
    review_root: Path | None,
    inbox_root: Path | None,
) -> tuple[Path, str] | None:
    """Resolve folder_name against both roots. Returns (path, source) or None."""
    for root, source in (
        (review_root, "review"),
        (inbox_root, "inbox-stuck"),
    ):
        if root is None or not root.is_dir():
            continue
        candidate = (root / folder_name).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            continue
        if not candidate.is_dir():
            continue
        return candidate, source
    return None


# ============== MB candidate fetch + transform ======================


def _candidate_year(release: dict) -> str | None:
    date = release.get("date")
    if not date:
        return None
    return date.split("-", 1)[0]


def _candidate_label(release: dict) -> tuple[str | None, str | None]:
    label_info_list = release.get("label-info-list") or release.get("label-info") or []
    if not label_info_list:
        return None, None
    first = label_info_list[0]
    label_name = (first.get("label") or {}).get("name")
    catalog = first.get("catalog-number")
    return label_name, catalog


def _candidate_tracks(release: dict) -> list[dict]:
    mediums = release.get("medium-list") or []
    tracks: list[dict] = []
    for medium in mediums:
        for t in medium.get("track-list", []) or []:
            rec = t.get("recording") or {}
            length_ms = t.get("length") or rec.get("length")
            length_sec = int(length_ms) // 1000 if length_ms else None
            tracks.append({
                "position": t.get("position") or rec.get("position"),
                "title": rec.get("title") or t.get("title"),
                "length_seconds": length_sec,
            })
    return tracks


def _file_lengths_seconds(folder: Path) -> list[tuple[Path, int]]:
    pairs: list[tuple[Path, int]] = []
    for flac in sorted(folder.glob(_AUDIO_GLOB)):
        # Coarse: file size / bytes-per-second. Sprint-5 stays with this
        # proxy until ffprobe parsing lands.
        seconds = max(0, flac.stat().st_size // _DEFAULT_BYTES_PER_SECOND)
        pairs.append((flac, seconds))
    return pairs


def _tracks_diff(folder: Path, candidate_tracks: list[dict]) -> list[dict]:
    rows: list[dict] = []
    file_pairs = _file_lengths_seconds(folder)
    for idx, (flac, file_seconds) in enumerate(file_pairs):
        proposed = candidate_tracks[idx] if idx < len(candidate_tracks) else None
        proposed_title = proposed["title"] if proposed else None
        proposed_length = proposed["length_seconds"] if proposed else None
        delta = (
            (file_seconds - proposed_length) if proposed_length is not None else 0
        )
        rows.append({
            "file": flac.name,
            "proposed_title": proposed_title,
            "proposed_length_seconds": proposed_length,
            "delta_seconds": delta,
            "delta_warning": abs(delta) > _DELTA_WARN_SECONDS,
        })
    return rows


def transform_candidate(release: dict, folder: Path) -> dict:
    tracks = _candidate_tracks(release)
    label, catalog = _candidate_label(release)
    score_raw = release.get("ext:score") or release.get("score") or "0"
    try:
        score = int(score_raw)
    except (TypeError, ValueError):
        score = 0
    return {
        "mbid": release.get("id"),
        "score": score,
        "artist": release.get("artist-credit-phrase"),
        "title": release.get("title"),
        "year": _candidate_year(release),
        "label": label,
        "catalog_no": catalog,
        "track_count": len(tracks),
        "tracks": tracks,
        "tracks_diff": _tracks_diff(folder, tracks),
    }


# ============== route handler bodies ================================


_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _validate_mbid(mbid: str) -> None:
    if not _UUID_RE.match(mbid):
        raise HTTPException(status_code=400, detail=f"invalid MBID shape: {mbid!r}")
    try:
        uuid.UUID(mbid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid MBID: {exc}") from exc


def handle_folder_list(review_root: Path | None, inbox_root: Path | None) -> dict:
    return {"folders": list_review_folders(review_root, inbox_root)}


def handle_candidates(
    folder_name: str,
    *,
    review_root: Path | None,
    inbox_root: Path | None,
    search: str | None,
    mbid: str | None,
) -> dict:
    if search and mbid:
        raise HTTPException(
            status_code=400,
            detail="`search` and `mbid` are mutually exclusive",
        )

    resolved = find_folder(folder_name, review_root, inbox_root)
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"folder not found: {folder_name}")
    folder, _source = resolved

    if mbid is not None:
        _validate_mbid(mbid)
        try:
            response = get_mb_client().get_release_by_id(
                mbid,
                includes=["recordings", "artist-credits", "labels", "release-groups"],
            )
        except musicbrainzngs.ResponseError as exc:
            raise HTTPException(status_code=404, detail=f"MBID lookup failed: {exc}") from exc
        except musicbrainzngs.WebServiceError as exc:
            raise HTTPException(status_code=502, detail=f"musicbrainz unavailable: {exc}") from exc
        release = response.get("release") if isinstance(response, dict) else None
        if not release:
            return {"candidates": []}
        return {"candidates": [transform_candidate(release, folder)]}

    # Default path: text search.
    query = search or ""
    try:
        response = get_mb_client().search_releases(query=query, limit=5)
    except musicbrainzngs.WebServiceError as exc:
        raise HTTPException(status_code=502, detail=f"musicbrainz unavailable: {exc}") from exc

    releases = response.get("release-list") if isinstance(response, dict) else []
    return {
        "candidates": [
            transform_candidate(r, folder) for r in (releases or [])
        ],
    }


class _ApplyBody(BaseModel):
    mbid: str


_LIB_PATH_RE = re.compile(r"->\s+(?P<path>.+?)\s*$", re.MULTILINE)


def _parse_library_path(beets_stdout: str) -> str | None:
    m = _LIB_PATH_RE.search(beets_stdout)
    if not m:
        return None
    return m.group("path").strip()


def _check_not_busy(loop_state: Any) -> None:
    if getattr(loop_state, "state", None) in _BUSY_STATES:
        raise HTTPException(
            status_code=409,
            detail={"status": "busy", "phase": loop_state.state},
        )


def _run_beets_import(argv: list[str]) -> tuple[int, str, str]:
    try:
        result = subprocess.run(  # noqa: S603 — argv form, shell=False
            argv,
            capture_output=True,
            text=True,
            timeout=_BEETS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            status_code=504,
            detail=f"beets import exceeded {_BEETS_TIMEOUT_SECONDS}s",
        ) from exc
    return result.returncode, result.stdout, result.stderr


def handle_apply(
    folder_name: str,
    payload: dict | None,
    *,
    loop_state: Any,
    review_root: Path | None,
    inbox_root: Path | None,
) -> dict:
    _check_not_busy(loop_state)

    if not isinstance(payload, dict) or "mbid" not in payload:
        raise HTTPException(status_code=400, detail="body must include `mbid`")
    try:
        body = _ApplyBody.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.errors()) from exc

    _validate_mbid(body.mbid)

    resolved = find_folder(folder_name, review_root, inbox_root)
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"folder not found: {folder_name}")

    argv = [
        "docker", "exec", "cd_beets",
        "beet", "import", "-q", "--search-id", body.mbid,
        f"/downloads/{folder_name}",
    ]
    rc, stdout, stderr = _run_beets_import(argv)
    if rc != 0:
        raise HTTPException(
            status_code=500,
            detail={"status": "failed", "stdout": stdout, "stderr": stderr},
        )
    return {
        "status": "applied",
        "mbid": body.mbid,
        "library_path": _parse_library_path(stdout),
    }


def handle_use_as_is(
    folder_name: str,
    *,
    loop_state: Any,
    review_root: Path | None,
    inbox_root: Path | None,
) -> dict:
    _check_not_busy(loop_state)

    resolved = find_folder(folder_name, review_root, inbox_root)
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"folder not found: {folder_name}")

    argv = [
        "docker", "exec", "cd_beets",
        "beet", "import", "-A", f"/downloads/{folder_name}",
    ]
    rc, stdout, stderr = _run_beets_import(argv)
    if rc != 0:
        raise HTTPException(
            status_code=500,
            detail={"status": "failed", "stdout": stdout, "stderr": stderr},
        )
    return {
        "status": "applied",
        "library_path": _parse_library_path(stdout),
    }


# ============== HTML page rendering ================================
# Sprint-5 / impl-review-pages. Mash Co. dressed; no JS for filtering
# or candidate selection — same-page `<form method="get">` reload.

import html as _html


def _esc(s: Any) -> str:
    if s is None:
        return ""
    return _html.escape(str(s))


_BASE_STYLES = r"""
<style>
  html, body { margin: 0; background: var(--bg); color: var(--fg);
               font-family: var(--font-body); }
  .wrap { max-width: 960px; margin: 0 auto; padding: var(--s-7) var(--s-5); }
  .nav { display: flex; gap: var(--s-4); margin-bottom: var(--s-5);
         font-family: var(--font-body); font-size: var(--fs-sm); }
  .nav a { color: var(--fg-muted); text-decoration: none;
           padding-bottom: 2px; border-bottom: 1px solid transparent; }
  .nav a.active { color: var(--fg); border-bottom-color: var(--accent); }
  .eyebrow { font-family: var(--font-body); font-size: var(--fs-xs);
             letter-spacing: 0.08em; text-transform: uppercase;
             color: var(--fg-muted); margin: 0 0 var(--s-2) 0; }
  .page-title { font-family: var(--font-display); font-weight: 700;
                font-size: 32px; margin: 0 0 var(--s-7) 0; color: var(--fg); }
  .card { background: var(--surface); border: 1px solid var(--line);
          border-left: 3px solid var(--accent); border-radius: var(--r-4);
          padding: var(--s-5); margin-bottom: var(--s-4); }
  .meta { font-family: var(--font-mono); font-size: var(--fs-sm);
          color: var(--fg-muted); line-height: 1.6; }
  .empty-hint { font-family: var(--font-body); color: var(--ink-3);
                font-size: var(--fs-md); }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
          gap: var(--s-4); }
  a.card { display: block; text-decoration: none; color: inherit; }
  .card-title { font-family: var(--font-display); font-weight: 700;
                font-size: 18px; margin: 0 0 var(--s-2) 0; color: var(--fg); }
  .chip { display: inline-block; font-family: var(--font-body);
          font-size: var(--fs-xs); padding: 2px 8px; border-radius: var(--r-full);
          background: var(--surface-2); color: var(--fg-muted); }
  .btn { display: inline-block; font-family: var(--font-body);
         font-size: var(--fs-sm); padding: 8px 14px;
         border-radius: var(--r-3); border: 1px solid var(--line);
         color: var(--fg); background: var(--surface-2);
         text-decoration: none; cursor: pointer; }
  .btn--accent { background: var(--accent); color: var(--bg);
                 border-color: var(--accent); }
  .btn--secondary { background: var(--ink-3); color: var(--bg);
                    border-color: var(--ink-3); }
  .search-form { display: flex; gap: var(--s-3); flex-wrap: wrap;
                 margin: 0 0 var(--s-5) 0; }
  .search-form input { font-family: var(--font-body); font-size: var(--fs-sm);
                       padding: 6px 10px; border-radius: var(--r-2);
                       border: 1px solid var(--line); background: var(--surface);
                       color: var(--fg); min-width: 220px; }
  table.tracks-diff { width: 100%; border-collapse: collapse;
                      font-family: var(--font-mono); font-size: var(--fs-sm);
                      margin-top: var(--s-3); }
  table.tracks-diff td, table.tracks-diff th { padding: 6px 10px;
                                               border-bottom: 1px solid var(--line);
                                               text-align: left; }
  tr.row--warn td { color: var(--amber); }
  td.col-file code { font-family: var(--font-mono); }
  progress { width: 100%; height: 6px; }
  audio { width: 100%; margin-top: 4px; }
</style>
"""


def _page_shell(title: str, body_inner: str) -> str:
    return (
        '<!doctype html>'
        '<html lang="en" data-theme="dark">'
        '<head>'
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>cd-archivist · {_esc(title)}</title>'
        '<link rel="stylesheet" href="/static/css/tokens.css">'
        + _BASE_STYLES +
        '</head>'
        '<body>'
        '<main class="wrap">'
        '<nav class="nav">'
        '<a href="/">status</a>'
        '<a href="/library">library</a>'
        '<a href="/review" class="active">review</a>'
        '</nav>'
        + body_inner +
        '</main>'
        '</body></html>'
    )


def render_review_list(folders: list[dict]) -> str:
    if not folders:
        body = (
            '<p class="eyebrow">REVIEW</p>'
            '<h1 class="page-title">cd-archivist</h1>'
            '<p class="empty-hint">nothing to review. discs land here when '
            'beets quiet-mode misses an auto-match.</p>'
        )
        return _page_shell("review", body)

    cards: list[str] = []
    for f in folders:
        name = _esc(f["name"])
        chip = ""
        if f.get("source") == "inbox-stuck":
            chip = '<span class="chip" data-source="inbox-stuck">inbox-stuck</span>'
        else:
            chip = '<span class="chip" data-source="review">review</span>'
        cards.append(
            f'<a class="card" href="/review/{name}">'
            f'  <p class="eyebrow">{chip}</p>'
            f'  <h2 class="card-title">{name}</h2>'
            f'  <p class="meta">{f["audio_count"]} tracks</p>'
            f'  <p><span class="btn btn--accent">review now</span></p>'
            f'</a>'
        )
    body = (
        '<p class="eyebrow">REVIEW</p>'
        '<h1 class="page-title">cd-archivist</h1>'
        '<div class="grid">' + "\n".join(cards) + '</div>'
    )
    return _page_shell("review", body)


def _render_candidate_card(folder_name: str, c: dict) -> str:
    mbid = _esc(c.get("mbid"))
    score = c.get("score") or 0
    rows: list[str] = []
    for row in c.get("tracks_diff", []):
        delta = row.get("delta_seconds") or 0
        proposed_len = row.get("proposed_length_seconds")
        cls = "row--warn" if row.get("delta_warning") else ""
        rows.append(
            f'<tr class="{cls}">'
            f'<td class="col-file"><code>{_esc(row.get("file"))}</code></td>'
            f'<td>{_esc(row.get("proposed_title") or "—")}</td>'
            f'<td>{_esc(proposed_len if proposed_len is not None else "—")}</td>'
            f'<td>{_esc(delta)}</td>'
            f'</tr>'
        )
    diff_table = (
        '<table class="tracks-diff">'
        '<thead><tr><th>file</th><th>proposed title</th>'
        '<th>length (s)</th><th>delta (s)</th></tr></thead>'
        '<tbody>' + "\n".join(rows) + '</tbody></table>'
    )
    return (
        '<section class="card">'
        f'<p class="eyebrow">CANDIDATE</p>'
        f'<h3 class="card-title">{_esc(c.get("artist"))} — {_esc(c.get("title"))}</h3>'
        f'<p class="meta">{_esc(c.get("year") or "year unknown")} · '
        f'{_esc(c.get("label") or "label unknown")} · '
        f'{_esc(c.get("catalog_no") or "no catalog #")} · '
        f'{c.get("track_count", 0)} tracks · '
        f'<code>{mbid}</code></p>'
        f'<progress max="100" value="{score}"></progress> '
        f'<span class="meta">{score}% confidence</span>'
        '<details><summary class="meta">track diff</summary>'
        f'{diff_table}'
        '</details>'
        f'<form method="post" action="/api/review/{_esc(folder_name)}/apply" '
        f'style="display:inline; margin-right: var(--s-3);">'
        f'<input type="hidden" name="mbid" value="{mbid}">'
        f'<button class="btn btn--accent" type="submit">apply</button>'
        '</form>'
        '</section>'
    )


def render_review_detail(
    folder_name: str,
    folder_path: Path,
    candidates: list[dict],
) -> str:
    # Audio preview row — one <audio> per FLAC in the folder.
    audio_blocks: list[str] = []
    for flac in sorted(folder_path.glob("*.flac")):
        audio_blocks.append(
            f'<div class="meta"><code>{_esc(flac.name)}</code>'
            f'<audio controls preload="none" '
            f'src="/api/review/{_esc(folder_name)}/audio/{_esc(flac.name)}"></audio>'
            f'</div>'
        )
    audio_section = (
        '<section class="card">'
        '<p class="eyebrow">AUDIO</p>'
        + "\n".join(audio_blocks) +
        '</section>'
    )

    # Search controls (no-JS — same-page <form method="get">).
    controls = (
        f'<form class="search-form" method="get" action="/review/{_esc(folder_name)}">'
        '<input name="search" placeholder="artist + album" />'
        '<button class="btn btn--accent" type="submit">search MB</button>'
        '</form>'
        f'<form class="search-form" method="get" action="/review/{_esc(folder_name)}">'
        '<input name="mbid" placeholder="MusicBrainz release ID" />'
        '<button class="btn" type="submit">fetch by ID</button>'
        '</form>'
    )

    # Candidate cards or empty hint.
    if candidates:
        cards_html = "\n".join(
            _render_candidate_card(folder_name, c) for c in candidates
        )
    else:
        cards_html = (
            '<p class="empty-hint">no candidates yet — search by text '
            'or paste a MusicBrainz release ID to start.</p>'
        )

    # Use-as-is (quieter — last resort).
    use_as_is = (
        '<section class="card">'
        '<p class="eyebrow">LAST RESORT</p>'
        '<p class="meta">tag with directory name only — no metadata.</p>'
        f'<form method="post" action="/api/review/{_esc(folder_name)}/use-as-is">'
        '<button class="btn btn--secondary" type="submit">use as-is</button>'
        '</form>'
        '</section>'
    )

    body = (
        f'<p class="eyebrow">REVIEW</p>'
        f'<h1 class="page-title">{_esc(folder_name)}</h1>'
        + audio_section
        + controls
        + cards_html
        + use_as_is
    )
    return _page_shell(folder_name, body)


def render_review_detail_handler(
    folder_name: str,
    *,
    review_root: Path | None,
    inbox_root: Path | None,
    search: str | None,
    mbid: str | None,
) -> str:
    resolved = find_folder(folder_name, review_root, inbox_root)
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"folder not found: {folder_name}")
    folder_path, _source = resolved

    candidates: list[dict] = []
    if search or mbid:
        result = handle_candidates(
            folder_name,
            review_root=review_root, inbox_root=inbox_root,
            search=search, mbid=mbid,
        )
        candidates = result.get("candidates", [])
    return render_review_detail(folder_name, folder_path, candidates)
