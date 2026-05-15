"""Fire-and-forget post-rip hook for the music-pipeline importer.

Per D-process-ready-trigger. After the state machine atomically renames
`<inbox>/<folder>/READY.tmp → READY`, this helper kicks off the dogfood
rig's `process-ready-auto` script so the import starts with zero
latency. The systemd backup timer
(operator task `install-process-ready-timer`) catches anything this
hook misses.

Coupling: on the dogfood CM4, cd-archivist and the music-pipeline
stack live on the same box, so the default is a local binary at
`/srv/cd-music-stack/bin/process-ready-auto`. Operators can swap the
command (e.g. `ssh importer-host /srv/cd-music-stack/bin/
process-ready-auto`) or disable the hook entirely (empty string) via
`ARCHIVIST_PROCESS_READY_HOOK`.

The helper is fire-and-forget — it does NOT call `.wait()` /
`.communicate()`, so the state machine continues to WAITING_REMOVE
without blocking on the import. Common operator-rig errors
(FileNotFoundError, PermissionError) are logged at WARNING and
swallowed; the rip succeeded, and a missing importer must never
poison the state machine.
"""
from __future__ import annotations

import logging
import shlex
import subprocess

logger = logging.getLogger(__name__)


def run_process_ready_hook(hook_cmd: str | None) -> None:
    """Spawn the post-rip hook and return immediately."""
    if not hook_cmd:  # None or empty string → disabled.
        return
    argv = shlex.split(hook_cmd)
    if not argv:
        return
    try:
        subprocess.Popen(  # noqa: S603 — argv form, shell=False
            argv,
            shell=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except FileNotFoundError:
        logger.warning(
            "post-rip hook executable not found: %s — skipping (the systemd "
            "backup timer will catch this READY rename)", hook_cmd,
        )
    except PermissionError:
        logger.warning(
            "post-rip hook not executable: %s — check chmod/owner", hook_cmd,
        )
    except OSError as exc:
        logger.warning("post-rip hook spawn failed: %s (%s)", hook_cmd, exc)
