from __future__ import annotations

import json
from pathlib import Path

from cd_archivist.models import DiscManifest


def save_manifest(manifest: DiscManifest, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        manifest.model_dump_json(indent=2),
        encoding="utf-8",
    )


def load_manifest(path: Path) -> DiscManifest:
    return DiscManifest.model_validate(json.loads(path.read_text(encoding="utf-8")))
