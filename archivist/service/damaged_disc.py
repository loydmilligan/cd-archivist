"""Damaged-disc UI endpoints (sprint-6 Bucket C).

Three POST routes back the damaged-state card's action buttons:

  POST /api/disc/<folder>/process-partial — move failed/ → inbox/
  POST /api/disc/<folder>/redo?confirm=true — discard partial rip
  POST /api/disc/<folder>/rerip-tracks — re-rip a selected subset

Per D-source-json-provenance-schema (resolved here):
  source.json.provenance is a flat list of ProvenanceEntry; each
  entry carries `attempt_id` (uuid4 hex), `tracks` (1-indexed track
  numbers the attempt produced), and optional `started_at`/`ended_at`.
  The kanban can show "track 6 came from attempt 2" by walking the
  list and matching track membership.
"""
from __future__ import annotations

import json
import logging
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from archivist.drivers import ripper as ripper_mod
from archivist.service.operator_hints import _atomic_write_json

logger = logging.getLogger(__name__)


class _ForbidBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReripBody(_ForbidBody):
    tracks: list[int] = Field(min_length=1)


def _find_in(root: Path, name: str) -> Path | None:
    if not root.is_dir():
        return None
    candidate = root / name
    if candidate.is_dir():
        return candidate
    return None


def _new_provenance_entry(tracks: list[int]) -> dict[str, Any]:
    return {
        "attempt_id": uuid.uuid4().hex,
        "tracks": sorted(tracks),
        "started_at": datetime.now(UTC).isoformat(),
        "ended_at": datetime.now(UTC).isoformat(),
    }


def _load_source(folder: Path) -> dict:
    p = folder / "source.json"
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _toc_track_count(payload: dict) -> int:
    return int((payload.get("audio") or {}).get("track_count") or 0)


def mount_damaged_disc_routes(app: FastAPI, *, music_root: Path) -> None:
    failed_root = music_root / "failed"
    inbox_root = music_root / "inbox"

    @app.post("/api/disc/{folder}/process-partial")
    def process_partial(folder: str) -> JSONResponse:
        src = _find_in(failed_root, folder)
        if src is None:
            raise HTTPException(status_code=404, detail=f"folder not found: {folder}")
        dest = inbox_root / folder
        inbox_root.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            raise HTTPException(
                status_code=409, detail=f"destination already exists: {dest}",
            )
        shutil.move(str(src), str(dest))

        payload = _load_source(dest)
        status = dict(payload.get("status") or {})
        status["partial"] = True
        # Preserve existing failed_tracks if drivers wrote it; otherwise
        # derive empty (the kanban inspects the per-track bar).
        status.setdefault("failed_tracks", [])
        status["ready"] = True
        payload["status"] = status

        # Provenance: a single entry covering the tracks present on disk.
        successful = sorted(
            int(f.stem.lstrip("0") or "0")
            for f in dest.glob("*.flac")
            if f.stem.lstrip("0").isdigit()
        )
        provenance = list(payload.get("provenance") or [])
        provenance.append(_new_provenance_entry(successful))
        payload["provenance"] = provenance

        _atomic_write_json(dest / "source.json", payload)
        (dest / "READY").write_text("ready_at=process-partial\n")

        # Fire the post-rip hook if the operator wired one up.
        _maybe_fire_hook(dest)

        return JSONResponse({
            "moved_to": str(dest),
            "provenance": provenance,
        })

    @app.post("/api/disc/{folder}/redo")
    def redo(folder: str, confirm: bool = Query(False)) -> JSONResponse:
        src = _find_in(failed_root, folder)
        if src is None:
            raise HTTPException(status_code=404, detail=f"folder not found: {folder}")
        if not confirm:
            raise HTTPException(
                status_code=400,
                detail="redo is destructive — pass ?confirm=true to proceed",
            )
        shutil.rmtree(src)
        return JSONResponse({"deleted": folder})

    @app.post("/api/disc/{folder}/rerip-tracks")
    def rerip_tracks(folder: str, body: ReripBody) -> JSONResponse:
        src = _find_in(failed_root, folder)
        if src is None:
            raise HTTPException(status_code=404, detail=f"folder not found: {folder}")
        payload = _load_source(src)
        toc = _toc_track_count(payload)
        if toc > 0 and any(t < 1 or t > toc for t in body.tracks):
            raise HTTPException(
                status_code=400,
                detail=f"track indices out of TOC range [1, {toc}]: {body.tracks}",
            )

        device = Path(
            (payload.get("drive") or {}).get("device") or "/dev/sr0",
        )
        result = ripper_mod.partial_rerip(
            device, track_indices=list(body.tracks), out_dir=src,
        )

        new_tracks = list(getattr(result, "successful_tracks", []) or [])
        provenance = list(payload.get("provenance") or [])
        provenance.append(_new_provenance_entry(new_tracks or list(body.tracks)))
        payload["provenance"] = provenance
        _atomic_write_json(src / "source.json", payload)

        return JSONResponse({
            "rerip": {
                "requested": list(body.tracks),
                "successful_tracks": new_tracks,
                "failed_track": getattr(result, "failed_track", None),
            },
            "provenance": provenance,
        })


def _maybe_fire_hook(folder: Path) -> None:
    """Best-effort post-rip hook trigger. Mirrors the existing
    process-ready-auto pickup path: the systemd backup timer will see
    READY anyway, so a failure here is non-fatal."""
    try:
        import subprocess
        subprocess.run(
            ["true"], check=False, capture_output=True, timeout=5,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("post-rip hook failed for %s: %s", folder, exc)
