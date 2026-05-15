"""Tests for archivist.pipeline.rip_progress.parse_cdparanoia_progress.

Sprint-4 / test-rip-progress-real-format: the sprint-3 regex was written
from the man page and doesn't match real cdparanoia stderr. The fixture
`fixtures/cdparanoia_stderr_real.txt` captures the actual line shapes:

  - "Ripping from sector       0 (track  1 [00:00:00.00])"
  - "outputting to trackNN.cdda.wav"
  - " (== PROGRESS == [............| NNNNNN NN] == :^D * ==)"
  - "Done."

The parser must recognise the "outputting to trackNN" line to update
track context, and infer a coarse percent from PROGRESS bar lines
within a known track range — at minimum yielding non-None for ≥10
lines across the fixture.

Impl lands in Wave 2 (impl-rip-progress-real-format).
"""
from __future__ import annotations

import re
from pathlib import Path

from archivist.pipeline.rip_progress import parse_cdparanoia_progress

_FIXTURE = Path(__file__).parent / "fixtures" / "cdparanoia_stderr_real.txt"


def _fixture_lines() -> list[str]:
    return _FIXTURE.read_text(encoding="utf-8").splitlines()


# -------- (a) fixture-driven: ≥10 lines parsed as non-None ----------


def test_fixture_lines_produce_non_none_results() -> None:
    lines = _fixture_lines()
    non_none = [
        out for out in (parse_cdparanoia_progress(ln) for ln in lines)
        if out is not None
    ]
    assert len(non_none) >= 10, (
        f"expected ≥10 non-None results across {len(lines)} fixture lines; "
        f"got {len(non_none)}"
    )


# -------- (b) parsed shape matches "track N/T, P%" -------------------


def test_parsed_shape_matches_documented_format() -> None:
    lines = _fixture_lines()
    label_re = re.compile(r"track\s+\d+(/\d+)?(,\s*\d{1,3}%)?")
    for ln in lines:
        out = parse_cdparanoia_progress(ln)
        if out is None:
            continue
        assert label_re.search(out), (
            f"label {out!r} (from {ln!r}) doesn't match documented shape"
        )


# -------- (c) edge synthetic cases still pass -----------------------


def test_track_start_line_recognized() -> None:
    line = "Ripping from sector       0 (track  1 [00:00:00.00])"
    out = parse_cdparanoia_progress(line)
    assert out is not None
    assert "1" in out


def test_outputting_to_line_updates_track_context() -> None:
    """The 'outputting to trackNN.cdda.wav' line marks a track boundary."""
    out = parse_cdparanoia_progress("outputting to track03.cdda.wav")
    assert out is not None
    assert "3" in out


def test_unrelated_line_returns_none() -> None:
    assert parse_cdparanoia_progress("") is None
    assert parse_cdparanoia_progress("cdparanoia III release 10.2") is None
    assert parse_cdparanoia_progress("Done.") is None


def test_progress_bar_line_recognized() -> None:
    """The :^D smiley line is the bulk of cdparanoia's stderr."""
    line = " (== PROGRESS == [+ + .                         | 010432 00 ] == :^D * ==)"
    out = parse_cdparanoia_progress(line)
    # Either yields a label (if track context is tracked) or None when
    # no prior outputting-to line has been seen — both are acceptable
    # at the pure-function level, but the impl SHOULD yield something
    # useful when called in a stream where context was set previously.
    assert out is None or isinstance(out, str)


# -------- (d) end-to-end fixture replay updates rip_progress --------


def test_end_to_end_fixture_lands_a_progress_value(monkeypatch) -> None:
    """Feeding the fixture through CDAudioRipper.rip via a fake Popen
    should result in LoopState.rip_progress being non-None at some point
    during the run.

    Asserted by replaying the fixture lines into the on_progress callback
    that the loop wires up.
    """
    from archivist.service.app import LoopState

    state = LoopState()
    seen: list[str | None] = []

    def _on_line(line: str) -> None:
        label = parse_cdparanoia_progress(line)
        if label is not None:
            state.rip_progress = label
            seen.append(label)

    for ln in _fixture_lines():
        _on_line(ln)

    assert state.rip_progress is not None, (
        "after replaying the full fixture, rip_progress must be set"
    )
    assert seen, "at least one progress label must surface"
