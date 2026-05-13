from __future__ import annotations

from datetime import datetime
from pathlib import Path
from time import sleep


def capture_burst_stub(
    output_dir: Path,
    count: int = 5,
    interval_seconds: float = 0.5,
) -> list[Path]:
    """Stub capture implementation.

    Replace this with Pi camera or USB webcam capture.
    For now, creates placeholder files so the rest of the pipeline can be built.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    for index in range(count):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = output_dir / f"disc_front_{index + 1:03d}_{timestamp}.jpg"
        path.write_bytes(b"")
        paths.append(path)
        sleep(interval_seconds)

    return paths
