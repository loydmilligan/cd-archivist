"""Failing tests for cdparanoia retry-threshold fail-fast detection.

Per sprint-6 Bucket A task `test-fail-fast-detection`. Impl lands in
`impl-fail-fast-detection` and `D-failfast-threshold`.

Contract: `CDAudioRipper.rip(...)` watches cdparanoia stderr; when any
single sector accumulates retries past the configured threshold OR a
sense code matching `ASC=3e` (Target hardware fault) is seen, the
ripper SIGTERMs the cdparanoia subprocess and returns a partial result
rather than grinding for ~25 min on unreadable sectors. Default
threshold: 3 retries. Configurable via env
`ARCHIVIST_RIP_RETRY_THRESHOLD` (impl detail).

Test posture: a `_FakePopen` records `.terminate()` calls. The synthetic
stderr stream is fully scripted — no real timing, no real cdparanoia.
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest

from archivist.drivers.ripper import CDAudioRipper

DEVICE = Path("/dev/sr0")


class _FakePopen:
    """Minimal Popen stand-in with a scripted stderr stream and a
    spy on .terminate() / .wait() so tests can assert the abort fired."""

    def __init__(self, argv: list[str], stderr_lines: list[str], **_kwargs) -> None:
        self.args = argv
        self.terminated = False
        self._lines = iter(stderr_lines)
        # We expose `stderr` as a line-iterator the impl's
        # `for line in proc.stderr:` loop walks.
        self.stderr = _TerminableIter(self._lines, self)
        self.stdout = io.StringIO("")
        # Exit code: SIGTERM=-15 if terminated, 0 otherwise.
        self.returncode = 0

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = -15

    def wait(self, timeout: float | None = None) -> int:
        return self.returncode


class _TerminableIter:
    """Iterator that stops yielding once the parent Popen is terminated."""

    def __init__(self, source, parent: _FakePopen) -> None:
        self._source = source
        self._parent = parent

    def __iter__(self):
        return self

    def __next__(self) -> str:
        if self._parent.terminated:
            raise StopIteration
        return next(self._source)


def _install_popen(
    monkeypatch: pytest.MonkeyPatch, stderr_lines: list[str]
) -> list[_FakePopen]:
    """Patch subprocess.Popen in the ripper module to return _FakePopens.

    Returns a list that's appended to per construct call so tests can
    introspect the most-recent Popen.
    """
    import archivist.drivers.ripper as ripper_mod

    spawned: list[_FakePopen] = []

    def factory(argv, **kwargs):
        p = _FakePopen(argv, stderr_lines, **kwargs)
        spawned.append(p)
        return p

    monkeypatch.setattr(ripper_mod.subprocess, "Popen", factory)
    # Stub flac so the post-cdparanoia phase doesn't try to invoke it
    # for real.
    def fake_run(args, **_kwargs):
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    monkeypatch.setattr(ripper_mod.subprocess, "run", fake_run)
    return spawned


# ---------------------------- (a) retry threshold --------------------

def test_retry_threshold_aborts_within_one_line_of_crossing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """3 retries on the same sector → ripper SIGTERMs cdparanoia.

    Default threshold is 3; the 3rd retry line on the same sector is
    the one that pulls the trigger. We feed a stream of retry=1, 2, 3,
    then a tail line that should NEVER be consumed because the iterator
    must have stopped at the terminate().
    """
    out_dir = tmp_path / "rip"
    out_dir.mkdir()
    stderr_lines = [
        "scsi_read error: sector=1234 length=27 retry=1\n",
        "scsi_read error: sector=1234 length=27 retry=2\n",
        "scsi_read error: sector=1234 length=27 retry=3\n",
        # Sentinel: if the iterator consumes this line, the impl didn't
        # abort at retry=3.
        "TAIL_LINE_SHOULD_NEVER_BE_READ\n",
    ]
    spawned = _install_popen(monkeypatch, stderr_lines)

    result = CDAudioRipper().rip(DEVICE, out_dir, retry_threshold=3)

    assert spawned, "expected subprocess.Popen to be invoked"
    proc = spawned[-1]
    assert proc.terminated is True, (
        "expected cdparanoia to be SIGTERMed once a sector crossed the "
        "retry threshold"
    )
    # No WAVs were produced → fail-fast returns a fail/partial result,
    # not "success".
    assert result.status != "success"


def test_retries_below_threshold_do_not_abort(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """1-2 retries on a sector are tolerated; only ≥3 triggers abort."""
    out_dir = tmp_path / "rip"
    out_dir.mkdir()
    stderr_lines = [
        "scsi_read error: sector=42 length=27 retry=1\n",
        "scsi_read error: sector=42 length=27 retry=2\n",
        # …and then we move on to a clean track.
        "==PROGRESS== :readtoc complete\n",
    ]
    spawned = _install_popen(monkeypatch, stderr_lines)

    CDAudioRipper().rip(DEVICE, out_dir, retry_threshold=3)

    assert spawned[-1].terminated is False, (
        "below-threshold retries must not abort the rip"
    )


def test_retries_across_different_sectors_do_not_accumulate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """retry=1 on sector A, retry=1 on sector B, retry=1 on sector C are
    NOT a 3-retry event — the threshold is per-sector."""
    out_dir = tmp_path / "rip"
    out_dir.mkdir()
    stderr_lines = [
        "scsi_read error: sector=100 length=27 retry=1\n",
        "scsi_read error: sector=200 length=27 retry=1\n",
        "scsi_read error: sector=300 length=27 retry=1\n",
        "scsi_read error: sector=400 length=27 retry=1\n",
    ]
    spawned = _install_popen(monkeypatch, stderr_lines)

    CDAudioRipper().rip(DEVICE, out_dir, retry_threshold=3)

    assert spawned[-1].terminated is False, (
        "retry-count accumulator must be keyed per-sector, not global"
    )


# ---------------------------- (b) ASC=3e immediate abort -------------

def test_asc_3e_target_hardware_fault_triggers_immediate_abort(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A single ASC=3e (Target hardware fault) sense code aborts
    regardless of retry count — drive is reporting unrecoverable
    hardware error."""
    out_dir = tmp_path / "rip"
    out_dir.mkdir()
    stderr_lines = [
        "==PROGRESS== :reading track 1\n",
        "scsi: SENSE KEY=4 ASC=3e ASCQ=2 (Target hardware fault)\n",
        "TAIL_LINE_SHOULD_NEVER_BE_READ\n",
    ]
    spawned = _install_popen(monkeypatch, stderr_lines)

    CDAudioRipper().rip(DEVICE, out_dir, retry_threshold=99)

    assert spawned[-1].terminated is True, (
        "ASC=3e must trigger immediate abort regardless of retry threshold"
    )


# ---------------------------- (c) clean rip --------------------------

def test_clean_rip_completes_without_abort(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No retry/sense-code lines → cdparanoia runs to natural exit; no
    terminate() call."""
    out_dir = tmp_path / "rip"
    out_dir.mkdir()
    # Synthetic clean-rip stderr — pure progress lines, no errors.
    stderr_lines = [
        "==PROGRESS== :readtoc complete\n",
        "==PROGRESS== :outputting track 1\n",
        "==PROGRESS== :outputting track 2\n",
        "==PROGRESS== :outputting track 3\n",
    ]
    spawned = _install_popen(monkeypatch, stderr_lines)

    CDAudioRipper().rip(DEVICE, out_dir, retry_threshold=3)

    assert spawned[-1].terminated is False, (
        "a clean rip must complete to natural exit — no spurious abort"
    )
