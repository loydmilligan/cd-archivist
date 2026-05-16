"""Failing tests for partial-rip preservation + RipResult schema gains.

Per sprint-6 Bucket A task `test-partial-output-preserve`. Impl lands
in `impl-partial-output-preserve`.

Contract additions on `archivist.drivers.ripper.RipResult`:

- `partial: bool = False` — true when fail-fast aborted mid-rip.
- `successful_tracks: list[int] = []` — 1-indexed track numbers whose
  FLAC landed on disk.
- `failed_track: int | None = None` — the 1-indexed track on which the
  abort fired (None for fail-fast events that aren't pinned to a
  specific track, e.g. an ASC=3e fault before track 1 starts).

When fail-fast aborts at track N:
1. Previously-completed FLACs (tracks 1..N-1) are NOT deleted.
2. `RipResult.status == "partial"`, `partial=True`,
   `successful_tracks==[1, …, N-1]`, `failed_track==N`.
3. Existing happy-path callers still see `status == "success"` with
   `partial=False`, `successful_tracks=[1..total]`, `failed_track=None`.
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest

from archivist.drivers.ripper import CDAudioRipper, RipResult

DEVICE = Path("/dev/sr0")


# ---------------------------- schema defaults ------------------------

def test_rip_result_has_new_fields_with_safe_defaults() -> None:
    """Constructing a RipResult with only the legacy fields must succeed
    and default partial=False, successful_tracks=[], failed_track=None."""
    r = RipResult(status="success", tracks=[Path("track01.flac")], errors=[])
    assert r.partial is False
    assert r.successful_tracks == []
    assert r.failed_track is None


def test_rip_result_new_fields_round_trip() -> None:
    """All new fields are passable as kwargs and round-trip on the
    dataclass."""
    r = RipResult(
        status="partial",
        tracks=[Path("track01.flac"), Path("track02.flac")],
        errors=["scsi_read error at sector 99999"],
        partial=True,
        successful_tracks=[1, 2],
        failed_track=3,
    )
    assert r.partial is True
    assert r.successful_tracks == [1, 2]
    assert r.failed_track == 3


# ---------------------------- partial rip preservation ---------------

class _PartialPopen:
    """Fake Popen that drops two WAV stubs on disk BEFORE the third
    track triggers a retry-threshold abort. After the abort, the
    already-written WAVs are expected to survive into the FLAC phase.

    The script:
        1. yield :outputting track 1   (writes track01.wav)
        2. yield :outputting track 2   (writes track02.wav)
        3. yield retry=1 sector=X
        4. yield retry=2 sector=X
        5. yield retry=3 sector=X      ← threshold; impl calls .terminate()
        6. (never reached) :outputting track 3
    """

    def __init__(self, argv: list[str], out_dir: Path, **_kwargs) -> None:
        self.args = argv
        self._out_dir = out_dir
        self.terminated = False
        self.returncode = 0
        self.stderr = self._gen()
        self.stdout = io.StringIO("")

    def _gen(self):
        # Track 1 completes.
        (self._out_dir / "track01.wav").write_bytes(b"RIFF" + b"\x00" * 64)
        yield "==PROGRESS== :outputting track 1\n"
        # Track 2 completes.
        (self._out_dir / "track02.wav").write_bytes(b"RIFF" + b"\x00" * 64)
        yield "==PROGRESS== :outputting track 2\n"
        # Track 3 starts but hits a damaged sector and crosses threshold.
        yield "==PROGRESS== :outputting track 3\n"
        yield "scsi_read error: sector=12345 length=27 retry=1\n"
        if self.terminated:
            return
        yield "scsi_read error: sector=12345 length=27 retry=2\n"
        if self.terminated:
            return
        yield "scsi_read error: sector=12345 length=27 retry=3\n"
        # If the impl hasn't called terminate() by now, the test will
        # catch it via the terminated assertion. Yield a sentinel
        # that should never be consumed.
        if self.terminated:
            return
        yield "SENTINEL_SHOULD_NEVER_BE_READ\n"

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = -15

    def wait(self, timeout: float | None = None) -> int:
        return self.returncode


@pytest.fixture
def _patched_subprocess(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Install _PartialPopen + a no-op flac fake."""
    import archivist.drivers.ripper as ripper_mod

    out_dir = tmp_path / "rip"
    out_dir.mkdir()
    holder: dict[str, _PartialPopen] = {}

    def popen_factory(argv, **kwargs):
        p = _PartialPopen(argv, out_dir, **kwargs)
        holder["proc"] = p
        return p

    def fake_flac_run(args, **_kwargs):
        # The post-cdparanoia loop walks track*.wav and runs `flac` on
        # each. Convert the wav to a sibling .flac so the impl's
        # path-exists guard passes.
        argv = list(args) if isinstance(args, (list, tuple)) else [args]
        wav = Path(argv[-1])
        if wav.suffix == ".wav":
            wav.with_suffix(".flac").write_bytes(b"fLaC")
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(ripper_mod.subprocess, "Popen", popen_factory)
    monkeypatch.setattr(ripper_mod.subprocess, "run", fake_flac_run)
    return out_dir, holder


def test_partial_rip_preserves_completed_tracks_on_disk(_patched_subprocess) -> None:
    """After fail-fast abort at track 3, tracks 1+2 FLACs survive on
    disk in the working dir."""
    out_dir, _ = _patched_subprocess

    CDAudioRipper().rip(DEVICE, out_dir, retry_threshold=3)

    # The .flac sidecars must still exist post-rip — fail-fast must NOT
    # clean up the working dir.
    assert (out_dir / "track01.flac").exists()
    assert (out_dir / "track02.flac").exists()


def test_partial_rip_result_status_and_new_fields(_patched_subprocess) -> None:
    """RipResult reports status='partial', partial=True,
    successful_tracks=[1, 2], failed_track=3 after the abort."""
    out_dir, _ = _patched_subprocess

    result = CDAudioRipper().rip(DEVICE, out_dir, retry_threshold=3)

    assert result.status == "partial"
    assert result.partial is True
    assert result.successful_tracks == [1, 2]
    assert result.failed_track == 3


# ---------------------------- happy path unchanged -------------------

class _CleanPopen:
    """Clean rip — yields three completed-track progress lines, no
    errors, exits 0."""

    def __init__(self, argv: list[str], out_dir: Path, **_kwargs) -> None:
        self.args = argv
        self._out_dir = out_dir
        self.terminated = False
        self.returncode = 0
        self.stderr = self._gen()
        self.stdout = io.StringIO("")

    def _gen(self):
        for n in (1, 2, 3):
            (self._out_dir / f"track{n:02d}.wav").write_bytes(
                b"RIFF" + b"\x00" * 64
            )
            yield f"==PROGRESS== :outputting track {n}\n"

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float | None = None) -> int:
        return self.returncode


def test_happy_path_keeps_success_status_with_defaulted_new_fields(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A clean rip still reports status="success" with the new
    schema fields at their safe defaults (partial=False,
    successful_tracks=[1, 2, 3], failed_track=None)."""
    import archivist.drivers.ripper as ripper_mod

    out_dir = tmp_path / "rip"
    out_dir.mkdir()

    def popen_factory(argv, **kwargs):
        return _CleanPopen(argv, out_dir, **kwargs)

    def fake_flac_run(args, **_kwargs):
        argv = list(args) if isinstance(args, (list, tuple)) else [args]
        wav = Path(argv[-1])
        if wav.suffix == ".wav":
            wav.with_suffix(".flac").write_bytes(b"fLaC")
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(ripper_mod.subprocess, "Popen", popen_factory)
    monkeypatch.setattr(ripper_mod.subprocess, "run", fake_flac_run)

    result = CDAudioRipper().rip(DEVICE, out_dir, retry_threshold=3)

    assert result.status == "success"
    assert result.partial is False
    assert result.successful_tracks == [1, 2, 3]
    assert result.failed_track is None
