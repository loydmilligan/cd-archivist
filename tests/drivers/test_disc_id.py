"""Failing tests for archivist.drivers.disc_id.read_disc_id.

Per sprint-5 task `test-disc-id-capture` (D-disc-id-libdiscid). Impl
lands in `impl-disc-id-capture`.

Contract: `read_disc_id(device: Path) -> str | None`. Returns the
MusicBrainz disc-id string when libdiscid reads the TOC successfully,
`None` on any failure (no disc, drive busy, libdiscid missing). The
function never raises — the rip path must not be poisoned by a missing
or flaky libdiscid.
"""
from __future__ import annotations

import logging
import sys
import types
from pathlib import Path

import pytest

DEVICE = Path("/dev/sr0")


def _read_disc_id():
    """Lazy import of the not-yet-implemented function."""
    from archivist.drivers.disc_id import read_disc_id  # noqa: PLC0415

    return read_disc_id


def _install_fake_discid(
    monkeypatch: pytest.MonkeyPatch,
    *,
    id_value: str | None = None,
    raise_disc_error: bool = False,
    raise_oserror: BaseException | None = None,
):
    """Install a fake `discid` module so the impl's lazy-import resolves."""
    fake = types.ModuleType("discid")

    class _DiscError(Exception):
        """Stand-in for discid.DiscError."""

    def _read(device_str: str):
        if raise_oserror is not None:
            raise raise_oserror
        if raise_disc_error:
            raise _DiscError("no disc")
        return types.SimpleNamespace(id=id_value)

    fake.DiscError = _DiscError
    fake.read = _read
    monkeypatch.setitem(sys.modules, "discid", fake)
    return fake


# ---------------------------- happy path -----------------------------

def test_audio_cd_returns_disc_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """libdiscid reads the TOC → return its `.id` string."""
    _install_fake_discid(monkeypatch, id_value="abc123base64DiscIdValue.-_")
    assert _read_disc_id()(DEVICE) == "abc123base64DiscIdValue.-_"


# ---------------------------- no disc --------------------------------

def test_no_disc_returns_none_logs_info(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """discid.DiscError (empty drive) → None, logged at INFO."""
    _install_fake_discid(monkeypatch, raise_disc_error=True)
    with caplog.at_level(logging.INFO):
        assert _read_disc_id()(DEVICE) is None
    # Some INFO record must mention the device or "disc"; we don't
    # over-constrain the wording.
    msgs = " ".join(r.message for r in caplog.records if r.levelname == "INFO")
    assert "disc" in msgs.lower() or str(DEVICE) in msgs


# ---------------------------- OSError --------------------------------

def test_oserror_returns_none_logs_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Underlying OSError (drive busy etc.) → None, logged at WARNING with
    exception message + device path."""
    _install_fake_discid(monkeypatch, raise_oserror=OSError("drive busy"))
    with caplog.at_level(logging.WARNING):
        assert _read_disc_id()(DEVICE) is None
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert warnings, "expected a WARNING record"
    msg = " ".join(r.message for r in warnings)
    assert "drive busy" in msg
    assert str(DEVICE) in msg


# ---------------------------- ImportError ----------------------------

def test_import_error_returns_none_logs_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`discid` package missing entirely → None, warning with remediation hint."""
    # Force `import discid` to raise.
    monkeypatch.setitem(sys.modules, "discid", None)
    with caplog.at_level(logging.WARNING):
        assert _read_disc_id()(DEVICE) is None
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert warnings, "expected a WARNING record on ImportError"
    msg = " ".join(r.message for r in warnings)
    # Remediation hint must point at cm4-setup.md (the runtime apt deps
    # subsection where libdiscid0 is documented).
    assert "cm4-setup" in msg or "libdiscid" in msg


# ---------------------------- invariant ------------------------------

def test_never_raises_on_unexpected_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No library outcome causes the function to raise.

    The rip path must not be poisoned by a flaky libdiscid. Cover the
    documented OSError / DiscError / ImportError cases above plus a
    blanket "anything else" exception that the broad-except guard
    should still swallow.
    """
    for exc in (
        RuntimeError("internal libdiscid"),
        ValueError("bad TOC"),
        MemoryError("oom inside libdiscid"),
    ):
        _install_fake_discid(monkeypatch, raise_oserror=exc)
        result = _read_disc_id()(DEVICE)
        assert result is None, f"expected None for {type(exc).__name__}, got {result!r}"
