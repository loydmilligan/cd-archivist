"""Failing tests for post-FLAC WAV cleanup (sprint-4 / D-wav-cleanup).

Per CD_0018 polish item #12: cdparanoia writes a WAV per track, flac
converts to FLAC, but the WAV is currently kept — roughly doubling
per-disc disk usage with no AccurateRip benefit in sprint-4.

New helper `archivist/pipeline/rip.py::cleanup_wavs(audio_dir, *,
keep: bool = False) -> list[Path]` deletes every `trackNN.cdda.wav`
whose corresponding FLAC exists, returning the list of deleted paths.
The env-var read (`ARCHIVIST_KEEP_WAVS=1`) happens in `__main__.py`
and plumbs `keep` through to the helper — pure-helper tests live here.

Impl lands in Wave 2 (impl-wav-cleanup).
"""
from __future__ import annotations

from pathlib import Path

import pytest


def _seed(audio_dir: Path, *, with_flac: list[str], with_wav_only: list[str] | None = None) -> None:
    audio_dir.mkdir(parents=True, exist_ok=True)
    for name in with_flac:
        (audio_dir / f"track{name}.cdda.wav").write_bytes(b"RIFFwav data")
        (audio_dir / f"track{name}.cdda.flac").write_bytes(b"fLaC data")
    for name in (with_wav_only or []):
        (audio_dir / f"track{name}.cdda.wav").write_bytes(b"RIFFwav only")


# -------- (a) default — WAVs deleted when FLAC present --------------


def test_default_deletes_wavs_with_corresponding_flac(tmp_path: Path) -> None:
    from archivist.pipeline.rip import cleanup_wavs

    _seed(tmp_path, with_flac=["01", "02", "03"])
    deleted = cleanup_wavs(tmp_path)

    assert sorted(p.name for p in deleted) == [
        "track01.cdda.wav", "track02.cdda.wav", "track03.cdda.wav",
    ]
    # WAVs gone, FLACs preserved.
    for n in ("01", "02", "03"):
        assert not (tmp_path / f"track{n}.cdda.wav").exists()
        assert (tmp_path / f"track{n}.cdda.flac").is_file()


# -------- (b) keep=True preserves WAVs ------------------------------


def test_keep_true_preserves_both(tmp_path: Path) -> None:
    from archivist.pipeline.rip import cleanup_wavs

    _seed(tmp_path, with_flac=["01", "02"])
    deleted = cleanup_wavs(tmp_path, keep=True)
    assert deleted == []
    for n in ("01", "02"):
        assert (tmp_path / f"track{n}.cdda.wav").is_file()
        assert (tmp_path / f"track{n}.cdda.flac").is_file()


# -------- (c) WAV without a matching FLAC is NOT deleted ------------


def test_wav_without_matching_flac_preserved(tmp_path: Path) -> None:
    """A WAV with no sibling FLAC is a failed/in-progress conversion —
    don't delete it, the operator needs it for debugging."""
    from archivist.pipeline.rip import cleanup_wavs

    _seed(tmp_path, with_flac=["01"], with_wav_only=["02", "03"])
    deleted = cleanup_wavs(tmp_path)

    # Only the WAV whose FLAC sibling exists is removed.
    assert [p.name for p in deleted] == ["track01.cdda.wav"]
    assert not (tmp_path / "track01.cdda.wav").exists()
    assert (tmp_path / "track02.cdda.wav").is_file()
    assert (tmp_path / "track03.cdda.wav").is_file()


# -------- (d) empty directory is a no-op ----------------------------


def test_empty_directory_no_op(tmp_path: Path) -> None:
    from archivist.pipeline.rip import cleanup_wavs

    assert cleanup_wavs(tmp_path) == []


# -------- (e) missing directory raises ------------------------------


def test_missing_directory_raises(tmp_path: Path) -> None:
    from archivist.pipeline.rip import cleanup_wavs

    with pytest.raises((FileNotFoundError, NotADirectoryError)):
        cleanup_wavs(tmp_path / "does-not-exist")
