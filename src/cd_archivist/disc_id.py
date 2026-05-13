from __future__ import annotations

from pathlib import Path


def next_disc_id(discs_dir: Path, prefix: str = "CD", width: int = 4) -> str:
    """Return the next available disc ID, e.g. CD_0001."""
    discs_dir.mkdir(parents=True, exist_ok=True)

    max_seen = 0
    marker = f"{prefix}_"

    for child in discs_dir.iterdir():
        if not child.name.startswith(marker):
            continue
        suffix = child.name.removeprefix(marker)
        if suffix.isdigit():
            max_seen = max(max_seen, int(suffix))

    return f"{prefix}_{max_seen + 1:0{width}d}"
