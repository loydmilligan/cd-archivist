"""Failing tests for archivist.pipeline.capture.capture_disc.

Implements the LED dance documented in docs/operations/cm4-setup.md
§"Capture pipeline LED dance":

    led off → settle → ambient burst (3 frames) → led on → settle →
    lit burst (3 frames) → led off

`camera` and `led` are injected — production wires in
`archivist.drivers.camera.capture_frame` and `archivist.drivers.led.LEDPanel`.

Impl lands in Wave 2 (impl-capture). Until then the import fails.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from archivist.models.manifest import CaptureRecord
from archivist.pipeline.capture import capture_disc


class _FakeCamera:
    """Records calls; returns a written JPG path per call (or None for misses)."""

    def __init__(self, fail_indices: set[int] | None = None) -> None:
        self.calls: list[tuple[Path, Path, int]] = []
        self._fail = fail_indices or set()
        self._n = 0

    def __call__(self, device: Path, out_path: Path, *, frames: int = 15) -> Path | None:
        idx = self._n
        self._n += 1
        self.calls.append((device, out_path, frames))
        if idx in self._fail:
            return None
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"\xff\xd8\xff\xd9")  # 1-byte JPG-ish stub
        return out_path


class _FakeLED:
    def __init__(self, *, on_result: bool = True, off_result: bool = True) -> None:
        self.events: list[str] = []
        self._on_result = on_result
        self._off_result = off_result

    def power_on(self) -> bool:
        self.events.append("on")
        return self._on_result

    def power_off(self) -> bool:
        self.events.append("off")
        return self._off_result

    def status(self) -> str:
        return "unknown"


@pytest.fixture
def disc_dir(tmp_disc_root) -> Path:
    root = tmp_disc_root()
    d = root / "CD_0001"
    (d / "captures").mkdir(parents=True)
    return d


def test_capture_disc_happy_path(disc_dir: Path) -> None:
    camera = _FakeCamera()
    led = _FakeLED()
    records = capture_disc(disc_dir, camera=camera, led=led, settle_seconds=0)

    assert isinstance(records, list)
    assert len(records) == 2
    ambient, lit = records
    assert isinstance(ambient, CaptureRecord)
    assert ambient.lighting == "ambient"
    assert len(ambient.image_paths) == 3
    assert lit.lighting == "lit"
    assert len(lit.image_paths) == 3

    # LED dance: off → on → off (final off is the failsafe).
    assert led.events == ["off", "on", "off"]

    # JPG filenames follow the documented pattern.
    for p in ambient.image_paths:
        assert "ambient" in p
    for p in lit.image_paths:
        assert "lit" in p


def test_capture_disc_tasmota_unreachable(disc_dir: Path) -> None:
    """power_on() returning False must not raise; ambient record still lands."""
    camera = _FakeCamera()
    led = _FakeLED(on_result=False)

    records = capture_disc(disc_dir, camera=camera, led=led, settle_seconds=0)

    assert len(records) >= 1
    ambient = records[0]
    assert ambient.lighting == "ambient"
    assert len(ambient.image_paths) == 3
    # Never raise.


def test_capture_disc_partial_camera_misses(disc_dir: Path) -> None:
    """Camera returns None for some frames → records only the JPGs that landed."""
    # Fail frame 0 (first ambient) and frame 4 (second lit).
    camera = _FakeCamera(fail_indices={0, 4})
    led = _FakeLED()
    records = capture_disc(disc_dir, camera=camera, led=led, settle_seconds=0)

    ambient, lit = records
    assert len(ambient.image_paths) == 2  # one miss in the ambient burst
    assert len(lit.image_paths) == 2      # one miss in the lit burst


def test_capture_disc_led_off_in_finally(disc_dir: Path) -> None:
    """If the lit-burst loop raises, led.power_off() still runs (failsafe)."""

    class _ExplodingCamera(_FakeCamera):
        def __call__(self, device, out_path, *, frames=15):
            # Succeed for the ambient burst; raise mid-lit-burst.
            if self._n < 3:
                return super().__call__(device, out_path, frames=frames)
            raise RuntimeError("camera exploded mid lit-burst")

    camera = _ExplodingCamera()
    led = _FakeLED()

    with pytest.raises(RuntimeError):
        capture_disc(disc_dir, camera=camera, led=led, settle_seconds=0)

    # The failsafe off MUST have fired even though we crashed.
    assert led.events.count("off") >= 1
    assert led.events[-1] == "off"
