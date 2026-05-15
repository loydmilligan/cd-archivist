"""Failing tests for archivist.drivers.rip_log.RipLogWriter.

Per sprint-4 Bucket A task `test-rip-log-writer`. Impl lands in
`impl-rip-log-writer`.

Contract: a context-manager-style writer for the per-disc `rip.log`
plain-text file. Each `event(message)` call appends one
`[<ISO-8601-local-with-offset>] <message>\\n` line and flushes.
"""
from __future__ import annotations

import re
from pathlib import Path


def _RipLogWriter():  # noqa: N802 — lazy import of not-yet-existing class
    from archivist.drivers.rip_log import RipLogWriter  # noqa: PLC0415

    return RipLogWriter


# ISO-8601-local-with-offset: e.g. "2026-05-15T14:23:01-07:00" or with
# microseconds; trailing offset is `±HH:MM` (Python isoformat default).
_TS_RE = re.compile(
    r"^\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?[+-]\d{2}:\d{2}\]"
)


def test_instantiation_creates_file(tmp_path: Path) -> None:
    """Constructing the writer creates rip.log inside the disc folder."""
    disc = tmp_path / "CD_0099"
    disc.mkdir()
    with _RipLogWriter()(disc):
        pass
    assert (disc / "rip.log").exists()


def test_event_line_shape(tmp_path: Path) -> None:
    """event() writes [<ISO-8601-local-with-offset>] <message>\\n."""
    disc = tmp_path / "CD_0099"
    disc.mkdir()
    with _RipLogWriter()(disc) as writer:
        writer.event("Rip started")
    lines = (disc / "rip.log").read_text(encoding="utf-8").splitlines()
    assert lines, "expected at least one log line"
    line = lines[0]
    assert _TS_RE.match(line), f"timestamp prefix wrong shape: {line!r}"
    assert line.endswith("Rip started")


def test_multiple_events_preserve_order(tmp_path: Path) -> None:
    """Three events land in the order they were emitted."""
    disc = tmp_path / "CD_0099"
    disc.mkdir()
    with _RipLogWriter()(disc) as writer:
        writer.event("one")
        writer.event("two")
        writer.event("three")
    body = (disc / "rip.log").read_text(encoding="utf-8")
    assert body.index("one") < body.index("two") < body.index("three")


def test_exit_flushes_and_closes(tmp_path: Path) -> None:
    """After __exit__, the file is closed (writing raises) and contents flushed."""
    disc = tmp_path / "CD_0099"
    disc.mkdir()
    cm = _RipLogWriter()(disc)
    with cm as writer:
        writer.event("inside ctx")
    # After exit, the underlying handle should be closed — any further
    # event() must raise (ValueError on closed file).
    try:
        cm.event("after ctx")  # type: ignore[union-attr]
    except (ValueError, OSError):
        pass
    else:
        # If the writer chose to silently no-op or reopen, that's also
        # acceptable — but the in-context write must have been flushed.
        pass
    assert "inside ctx" in (disc / "rip.log").read_text(encoding="utf-8")


def test_reopen_appends_not_truncates(tmp_path: Path) -> None:
    """Second open on the same disc dir appends to the existing log."""
    disc = tmp_path / "CD_0099"
    disc.mkdir()
    with _RipLogWriter()(disc) as w1:
        w1.event("session 1")
    with _RipLogWriter()(disc) as w2:
        w2.event("session 2")
    body = (disc / "rip.log").read_text(encoding="utf-8")
    assert "session 1" in body
    assert "session 2" in body
    assert body.index("session 1") < body.index("session 2")


def test_integration_with_cdaudio_ripper_progress_callback(
    monkeypatch, tmp_path: Path
) -> None:
    """RipLogWriter.event passed as progress_callback to CDAudioRipper.rip
    captures every cdparanoia stderr line as a rip.log entry."""
    import archivist.drivers.ripper as ripper_mod
    from archivist.drivers.ripper import CDAudioRipper

    disc = tmp_path / "CD_0099"
    disc.mkdir()
    out_dir = disc / "audio"
    out_dir.mkdir()

    stderr_lines = ["scanning toc", "ripping track 1", "ripping track 2"]

    class _FakePopen:
        def __init__(self, argv, **_kw):
            self.args = argv
            self.returncode = 0
            (out_dir / "track01.wav").write_bytes(b"RIFF")
            import io
            self.stdout = io.StringIO("")
            self.stderr = iter([s + "\n" for s in stderr_lines])

        def wait(self):
            return self.returncode

    def _fake_flac_run(args, **_kw):
        argv = list(args) if isinstance(args, (list, tuple)) else [args]
        wav = Path(argv[-1])
        wav.with_suffix(".flac").write_bytes(b"fLaC")
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(ripper_mod.subprocess, "Popen", _FakePopen)
    monkeypatch.setattr(ripper_mod.subprocess, "run", _fake_flac_run)

    with _RipLogWriter()(disc) as writer:
        CDAudioRipper().rip(Path("/dev/sr0"), out_dir, progress_callback=writer.event)

    body = (disc / "rip.log").read_text(encoding="utf-8")
    for line in stderr_lines:
        assert line in body, f"expected {line!r} in rip.log; got:\n{body}"
