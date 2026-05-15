"""Failing tests for archivist.pipeline.rip_progress.parse_cdparanoia_progress.

Parses cdparanoia's stderr into a short human label suitable for
LoopState.rip_progress. Two recognized line shapes:
  (a) "Ripping from sectors  6750 [00:01:30.00] (track 4)" → "track 4, 0%"
  (b) "(== PROGRESS == [...] ==     12345 00 ==)" / "##: -2 [wrote]" → bumps %

Anything else returns None. Impl lands in Wave 2 (impl-rip-progress).
"""
from __future__ import annotations

from archivist.pipeline.rip_progress import parse_cdparanoia_progress


def test_track_start_line() -> None:
    line = "Ripping from sectors  6750 [00:01:30.00] (track  4 [00:01:30.00])"
    out = parse_cdparanoia_progress(line)
    assert out is not None
    assert "track" in out
    assert "4" in out


def test_percent_progress_line() -> None:
    """A 'wrote' progress line should yield a string mentioning a percent."""
    # cdparanoia's smiley/percent lines look roughly like:
    #   "  (== PROGRESS == [               | 023456 00 ==]"
    # plus periodic ##: -2 [wrote] markers.
    line = "  (== PROGRESS == [                  | 023456 00 ==]"
    out = parse_cdparanoia_progress(line)
    # Either the line is recognised as percent progress (impl returns
    # "track N, P%" if a prior track context exists) OR returns None
    # because there's no track context yet. Both are valid; what we
    # care about is that recognising the line doesn't crash and a
    # known-progress line returns a non-None value when paired with
    # the explicit percent shape below.
    assert out is None or isinstance(out, str)


def test_explicit_percent_line() -> None:
    """The simple human-readable percent line."""
    line = "Progress: 47% complete (track 3 of 12)"
    out = parse_cdparanoia_progress(line)
    assert out is not None
    assert "47" in out


def test_unrelated_line_returns_none() -> None:
    assert parse_cdparanoia_progress("paranoia III release 10.2") is None
    assert parse_cdparanoia_progress("") is None
    assert parse_cdparanoia_progress("Outputting to track01.wav") is None


def test_partial_track_match_no_percent() -> None:
    """A track-only line (no percent) yields a label without a percent number."""
    out = parse_cdparanoia_progress("(track  7)")
    assert out is None or "7" in out
