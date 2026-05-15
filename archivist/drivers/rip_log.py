"""Per-disc `rip.log` plain-text writer.

Per sprint-4 task impl-rip-log-writer. Append-only, line-flushed text
log keyed to a disc folder. Lines are shaped
`[<ISO-8601-local-with-offset>] <message>\\n`.

The flush-on-event posture is load-bearing: the importer may pick up a
partial log on a crash, and we want the trailing events visible. Used
as the `progress_callback` for `CDAudioRipper.rip` so each cdparanoia
stderr line lands in the log alongside higher-level state-machine
events.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import TextIO

_LOG_NAME = "rip.log"


class RipLogWriter:
    """Append-mode log writer scoped to a disc folder.

    Usage::

        with RipLogWriter(disc_dir) as log:
            log.event("Rip started")
            ripper.rip(device, audio_dir, progress_callback=log.event)
            log.event("Rip completed")
    """

    def __init__(self, disc_dir: Path) -> None:
        self.path: Path = disc_dir / _LOG_NAME
        self._fh: TextIO | None = None

    def __enter__(self) -> RipLogWriter:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a", encoding="utf-8")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._fh is not None:
            try:
                self._fh.flush()
            finally:
                self._fh.close()
                self._fh = None

    def event(self, message: str) -> None:
        """Append one timestamped line and flush."""
        if self._fh is None:
            # Allow event() before __enter__ as a convenience — open lazily.
            self.__enter__()
        assert self._fh is not None  # for type-checkers
        stamp = datetime.now().astimezone().isoformat(timespec="seconds")
        self._fh.write(f"[{stamp}] {message}\n")
        self._fh.flush()
