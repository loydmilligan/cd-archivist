"""Failing tests for archivist.drivers.usb_discovery.discover_camera_usb_path.

Per sprint-2 Wave 1 (test-usb-discovery). Impl lands in Wave 2
(impl-usb-discovery).

Invariants under test:
- Never reads real `/sys` (filesystem mocked in every test).
- Never raises.
- Logs clearly when falling back to env or returning None.
- Default vendor:product matches the documented Microdia rig
  (docs/operations/cm4-setup.md line 11: idVendor 0c45:6366).
"""
from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from archivist.drivers.usb_discovery import discover_camera_usb_path

DEFAULT_VENDOR_PRODUCT = "0c45:6366"
ENV_VAR = "ARCHIVIST_CAMERA_USB_PATH"


def _uevent(vendor_product: str, busnum: str = "1", devpath: str = "1.2.2") -> str:
    """Synthetic /sys/.../uevent body. PRODUCT is `vendor/product/bcd` in sysfs;
    we accept the simpler `vendor:product` shape too so the impl can pick."""
    vendor, product = vendor_product.split(":")
    return (
        f"MAJOR=81\n"
        f"MINOR=0\n"
        f"DEVNAME=video0\n"
        f"PRODUCT={vendor}/{product}/100\n"
        f"DEVPATH=/devices/platform/scb/.../usb1/1-1/1-{devpath}/...\n"
        f"BUSNUM={busnum}\n"
    )


def _make_fake_video(uevent_body: str, video_n: int) -> object:
    """Build a fake Path-like object whose uevent sibling read_text() returns the body."""
    fake = _FakePath(f"/sys/class/video4linux/video{video_n}")
    fake._children["device"] = _FakePath(
        f"/sys/class/video4linux/video{video_n}/device",
        children={"uevent": _FakePath(
            f"/sys/class/video4linux/video{video_n}/device/uevent",
            text=uevent_body,
        )},
    )
    return fake


class _FakePath:
    """Minimal Path-like for sysfs walking — supports / division, name,
    read_text. Used as the return value of a patched Path.glob."""

    def __init__(
        self,
        s: str,
        *,
        text: str | None = None,
        children: dict[str, _FakePath] | None = None,
    ) -> None:
        self._s = s
        self._text = text
        self._children: dict[str, _FakePath] = children or {}

    def __truediv__(self, other: str) -> _FakePath:
        if other in self._children:
            return self._children[other]
        # Synthetic child: returns a missing-file _FakePath that raises on read.
        return _FakePath(f"{self._s}/{other}")

    def read_text(self, *_args: object, **_kwargs: object) -> str:
        if self._text is None:
            raise FileNotFoundError(self._s)
        return self._text

    def exists(self) -> bool:
        return self._text is not None or bool(self._children)

    @property
    def name(self) -> str:
        return self._s.rsplit("/", 1)[-1]

    def __str__(self) -> str:
        return self._s

    def __repr__(self) -> str:
        return f"_FakePath({self._s!r})"


# ---------------------------- sysfs match -----------------------------

def test_sysfs_match_returns_bus_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """A single matching videoN under /sys → its USB bus path is returned."""
    monkeypatch.delenv(ENV_VAR, raising=False)
    fake_video = _make_fake_video(
        _uevent(DEFAULT_VENDOR_PRODUCT, devpath="1.2.2"), video_n=0
    )

    with patch("archivist.drivers.usb_discovery.Path.glob", return_value=[fake_video]):
        result = discover_camera_usb_path()

    assert result is not None
    assert "1.2.2" in result or result.endswith("1.2.2")


def test_sysfs_two_matches_returns_lowest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two matches (video0 + video2) → returns video0's bus path."""
    monkeypatch.delenv(ENV_VAR, raising=False)
    v0 = _make_fake_video(_uevent(DEFAULT_VENDOR_PRODUCT, devpath="1.2.2"), video_n=0)
    v2 = _make_fake_video(_uevent(DEFAULT_VENDOR_PRODUCT, devpath="1.4.4"), video_n=2)

    with patch(
        "archivist.drivers.usb_discovery.Path.glob",
        return_value=[v2, v0],  # intentionally unsorted; impl must pick lowest video_n
    ):
        result = discover_camera_usb_path()

    assert result is not None
    assert "1.2.2" in result, f"expected lowest-numbered video's path, got {result!r}"


def test_no_sysfs_match_falls_back_to_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """No sysfs match + env var set → env value wins."""
    monkeypatch.setenv(ENV_VAR, "9-9.9")

    # Sysfs entry exists but its PRODUCT doesn't match.
    wrong = _make_fake_video(_uevent("dead:beef", devpath="1.1.1"), video_n=0)
    with patch("archivist.drivers.usb_discovery.Path.glob", return_value=[wrong]):
        result = discover_camera_usb_path()

    assert result == "9-9.9"


def test_no_sysfs_no_env_returns_none_and_warns(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """No sysfs + no env → None, with a warning naming the expected vendor:product."""
    monkeypatch.delenv(ENV_VAR, raising=False)
    with patch("archivist.drivers.usb_discovery.Path.glob", return_value=[]):
        with caplog.at_level(logging.WARNING):
            result = discover_camera_usb_path()

    assert result is None
    msg = " ".join(r.message for r in caplog.records)
    assert DEFAULT_VENDOR_PRODUCT in msg, (
        f"warning must name the expected vendor:product; got: {msg!r}"
    )


# touch Path so the import isn't lint-stripped
_ = Path
