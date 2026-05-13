#!/usr/bin/env python3
from pathlib import Path

from cd_archivist.camera.capture import capture_burst_stub

if __name__ == "__main__":
    paths = capture_burst_stub(Path("data/captures/manual-test"))
    for path in paths:
        print(path)
