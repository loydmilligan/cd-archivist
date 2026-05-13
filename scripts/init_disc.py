#!/usr/bin/env python3
from datetime import datetime
from pathlib import Path

from cd_archivist.disc_id import next_disc_id
from cd_archivist.manifest_io import save_manifest
from cd_archivist.models import DiscManifest

DISCS_DIR = Path("data/discs")

if __name__ == "__main__":
    disc_id = next_disc_id(DISCS_DIR)
    now = datetime.now()
    disc_dir = DISCS_DIR / disc_id
    manifest = DiscManifest(
        disc_id=disc_id,
        created_at=now,
        updated_at=now,
    )
    save_manifest(manifest, disc_dir / "manifest.json")
    print(disc_dir)
