"""In-UI beets review handlers (sprint-5 / Bucket B).

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
