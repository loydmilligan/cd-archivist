"""archivist.service.clients — thin typed wrappers around external surfaces.

Sprint-10 / setup-clients-package. See README.md in this directory for
the contract every client module follows.

Each panel implementation imports its own client module directly
(`from archivist.service.clients.disk_client import get_disk_usage`).
This package intentionally does not re-export client symbols at the
top level — callers go through the module to keep the surface honest.
"""

from __future__ import annotations
