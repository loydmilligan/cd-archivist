"""PATCH /api/disc/<folder>/hints handler (sprint-6 Bucket B+).

Merge semantics:
  - scalar fields (various_artists, burned_cd, artist, album): if
    present in the body, overwrite; if absent, preserve.
  - tracks: per `track_number` merge. Existing rows update in place
    (per-field, also via exclude_unset); new track_numbers append;
    existing rows not in the patch body preserved unchanged.

Writes are atomic (`.tmp` sibling + os.replace), matching the
existing source.json write pattern.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from archivist.service.disc_card_builder import _iter_disc_folders


class _PatchForbid(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TrackHintPatch(_PatchForbid):
    track_number: int = Field(gt=0)
    artist: str | None = None
    title: str | None = None


class OperatorHintsPatch(_PatchForbid):
    various_artists: bool | None = None
    burned_cd: bool | None = None
    artist: str | None = None
    album: str | None = None
    tracks: list[TrackHintPatch] | None = None


_DEFAULT_HINTS: dict[str, Any] = {
    "various_artists": False,
    "burned_cd": False,
    "artist": None,
    "album": None,
    "tracks": [],
}


def _find_disc_folder(music_root: Path, name: str) -> Path | None:
    for sub in ("inbox", "review", "library", "archive", "failed"):
        root = music_root / sub
        if not root.is_dir():
            continue
        for folder in _iter_disc_folders(root):
            if folder.name == name:
                return folder
    return None


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _merge_tracks(
    existing: list[dict], patches: list[TrackHintPatch],
) -> list[dict]:
    by_num: dict[int, dict] = {int(t.get("track_number")): dict(t) for t in existing}
    for patch in patches:
        n = patch.track_number
        merged = by_num.get(n, {"track_number": n})
        updates = patch.model_dump(exclude_unset=True)
        merged.update(updates)
        by_num[n] = merged
    return [by_num[k] for k in sorted(by_num.keys())]


def _apply_patch(existing: dict, patch: OperatorHintsPatch) -> dict:
    out = {**_DEFAULT_HINTS, **(existing or {})}
    updates = patch.model_dump(exclude_unset=True)
    if "tracks" in updates:
        out["tracks"] = _merge_tracks(out.get("tracks") or [], patch.tracks or [])
        updates.pop("tracks")
    out.update(updates)
    return out


def mount_operator_hints_routes(app: FastAPI, *, music_root: Path) -> None:
    @app.patch("/api/disc/{folder}/hints")
    def patch_hints(folder: str, body: OperatorHintsPatch) -> JSONResponse:
        disc_folder = _find_disc_folder(music_root, folder)
        if disc_folder is None:
            raise HTTPException(status_code=404, detail=f"folder not found: {folder}")
        source_path = disc_folder / "source.json"
        if source_path.is_file():
            payload = json.loads(source_path.read_text(encoding="utf-8"))
        else:
            payload = {}
        existing_hints = payload.get("operator_hints") or {}
        merged = _apply_patch(existing_hints, body)
        payload["operator_hints"] = merged
        _atomic_write_json(source_path, payload)
        return JSONResponse(merged)
