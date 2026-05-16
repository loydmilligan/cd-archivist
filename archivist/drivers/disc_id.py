"""MusicBrainz disc-id reader (libdiscid wrapper).

Per sprint-5 task `impl-disc-id-capture` + `D-disc-id-libdiscid`.
`read_disc_id(device)` reads the audio-CD TOC at rip start (before
tray-open / EJECT, while the disc is still in the drive) and returns
the MusicBrainz disc-id — a CDDB-style hash of (track count, track
lengths). The music-pipeline importer uses this to resolve the
release when AcoustID's audio fingerprint misses (which happens on
burned copies of commercial pressings: the burn's audio bits differ
from the original press, but the TOC is identical).

Failure posture: never raises. Missing libdiscid, no disc, drive
busy, or any other library outcome all return `None` and log at the
documented level. The rip path must not be poisoned by a flaky
libdiscid.

Runtime deps: the `discid` Python package (added to `pyproject.toml`)
plus the `libdiscid0` C library on the host (documented in
`docs/operations/cm4-setup.md` § "Runtime apt dependencies").
"""
from __future__ import annotations

import logging
from pathlib import Path

_logger = logging.getLogger(__name__)


def read_disc_id(device: Path) -> str | None:
    """Read the MusicBrainz disc-id off the disc in `device`.

    Returns the disc-id string on success, `None` on any failure.
    Never raises.
    """
    try:
        import discid  # noqa: PLC0415 — lazy so dev machines without libdiscid still import this module
    except ImportError as exc:
        _logger.warning(
            "disc-id read skipped: `discid` package unavailable (%s); "
            "install `libdiscid0` apt pkg + `discid>=1.2` python pkg — "
            "see docs/operations/cm4-setup.md § 'Runtime apt dependencies'",
            exc,
        )
        return None

    try:
        disc = discid.read(str(device))
    except discid.DiscError as exc:
        _logger.info("disc-id read: no disc in %s (%s)", device, exc)
        return None
    except OSError as exc:
        _logger.warning("disc-id read failed on %s: %s", device, exc)
        return None
    except Exception as exc:  # noqa: BLE001 — never-raises invariant
        _logger.warning(
            "disc-id read raised unexpectedly on %s: %s: %s",
            device, type(exc).__name__, exc,
        )
        return None

    return getattr(disc, "id", None)
