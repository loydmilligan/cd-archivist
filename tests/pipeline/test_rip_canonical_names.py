"""Failing tests for the post-FLAC track rename step (sprint-4).

After `flac` converts each `trackNN.cdda.wav` to `trackNN.cdda.flac`,
the new helper `rename_tracks_to_canonical(audio_dir) -> list[Path]`
renames every file to `NN Track.flac` (zero-padded NN, single space).
No metadata-aware naming this sprint — that lands in sprint-5+ when
MB-disc-id / OCR populate `detected_metadata.tracks[]`.

Helper lives in `archivist/pipeline/rip.py` next to `rip_disc`.

Impl lands in Wave 2 (impl-track-rename).
"""
from __future__ import annotations

from pathlib import Path

import pytest


def _touch(p: Path, content: bytes = b"fLaC") -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


# -------- (a) happy path — 01, 02, 12 renamed correctly --------------


def test_renames_to_canonical_filenames(tmp_path: Path) -> None:
    from archivist.pipeline.rip import rename_tracks_to_canonical

    _touch(tmp_path / "track01.cdda.flac")
    _touch(tmp_path / "track02.cdda.flac")
    _touch(tmp_path / "track12.cdda.flac")

    new_paths = rename_tracks_to_canonical(tmp_path)

    assert (tmp_path / "01 Track.flac").is_file()
    assert (tmp_path / "02 Track.flac").is_file()
    assert (tmp_path / "12 Track.flac").is_file()
    # Originals gone.
    assert not (tmp_path / "track01.cdda.flac").exists()
    assert not (tmp_path / "track02.cdda.flac").exists()
    assert not (tmp_path / "track12.cdda.flac").exists()


# -------- (b) returns new paths in track order ----------------------


def test_returns_new_paths_in_track_order(tmp_path: Path) -> None:
    from archivist.pipeline.rip import rename_tracks_to_canonical

    # Create in deliberately wrong order to ensure return-order is by track #.
    _touch(tmp_path / "track12.cdda.flac")
    _touch(tmp_path / "track01.cdda.flac")
    _touch(tmp_path / "track03.cdda.flac")

    new_paths = rename_tracks_to_canonical(tmp_path)
    names = [p.name for p in new_paths]
    assert names == ["01 Track.flac", "03 Track.flac", "12 Track.flac"]


# -------- (c) idempotent — second call is a no-op -------------------


def test_idempotent_when_already_canonical(tmp_path: Path) -> None:
    from archivist.pipeline.rip import rename_tracks_to_canonical

    _touch(tmp_path / "01 Track.flac")
    _touch(tmp_path / "02 Track.flac")

    # Second call against an already-canonical dir must not raise.
    new_paths = rename_tracks_to_canonical(tmp_path)
    assert (tmp_path / "01 Track.flac").is_file()
    assert (tmp_path / "02 Track.flac").is_file()
    # And the returned list reflects the canonical files.
    names = sorted(p.name for p in new_paths)
    assert names == ["01 Track.flac", "02 Track.flac"]


# -------- (d) leaves unrelated files alone --------------------------


def test_leaves_unrelated_files_untouched(tmp_path: Path) -> None:
    from archivist.pipeline.rip import rename_tracks_to_canonical

    _touch(tmp_path / "track01.cdda.flac")
    _touch(tmp_path / "album.cue", b"CUE")
    _touch(tmp_path / "README", b"hi")

    rename_tracks_to_canonical(tmp_path)
    assert (tmp_path / "01 Track.flac").is_file()
    assert (tmp_path / "album.cue").read_bytes() == b"CUE"
    assert (tmp_path / "README").read_bytes() == b"hi"


# -------- (e) collision guard — refuses to overwrite ----------------


def test_collision_guard_raises_rather_than_overwrites(tmp_path: Path) -> None:
    from archivist.pipeline.rip import rename_tracks_to_canonical

    _touch(tmp_path / "track01.cdda.flac", b"new")
    _touch(tmp_path / "01 Track.flac", b"existing")

    with pytest.raises(FileExistsError):
        rename_tracks_to_canonical(tmp_path)
    # Existing canonical untouched.
    assert (tmp_path / "01 Track.flac").read_bytes() == b"existing"
    # Source still present (not consumed before failure).
    assert (tmp_path / "track01.cdda.flac").is_file()
