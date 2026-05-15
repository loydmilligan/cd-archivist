"""Camera USB bus-path autodiscovery via /sys/class/video4linux.

Per sprint-2 task impl-usb-discovery + decision D-camera-autodiscover.
Walks the sysfs tree at module-config time to resolve the USB bus path
(e.g. `1-1.2.2`) needed by the VIDIOC_STREAMON unbind/rebind recovery
path. Falls back to an env var, then `None`. Never reads real `/sys` in
tests — every test patches `Path.glob`.
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path

_logger = logging.getLogger(__name__)

_SYSFS_VIDEO_ROOT = Path("/sys/class/video4linux")
# USB bus path token (busnum-port[.port...]), e.g. `1-1.2.2`.
_USB_PATH_RE = re.compile(r"\d+-[\d.]+")
# Matches the integer suffix of a `videoN` directory name.
_VIDEO_N_RE = re.compile(r"video(\d+)$")


def discover_camera_usb_path(
    *,
    vendor_product: str = "0c45:6366",
    env_var: str = "ARCHIVIST_CAMERA_USB_PATH",
) -> str | None:
    """Resolve the USB bus path of the documented webcam.

    Strategy: walk `/sys/class/video4linux/video*`; for each, parse
    `device/uevent` for a `PRODUCT=` line matching `vendor_product`
    (`v:p` shape — sysfs encodes it as `v/p/bcd`). Returns the bus path
    of the lowest-numbered match. If no match, returns
    `os.environ.get(env_var)` (may be `None`). If that's also `None`,
    logs a warning naming `vendor_product` and `env_var` so an operator
    knows what to grep `lsusb` for.
    """
    try:
        candidates = list(_SYSFS_VIDEO_ROOT.glob("video*"))
    except OSError as exc:
        # /sys/class/video4linux missing entirely (dev laptop).
        _logger.debug("sysfs scan failed: %s", exc)
        candidates = []

    matches: list[tuple[int, str]] = []
    vendor, _, product = vendor_product.partition(":")
    # uevent's PRODUCT= field strips leading zeros from each hex component
    # (e.g. `0c45:6366` is encoded as `c45/6366/100`). Normalize both sides
    # so configured ID matches reality regardless of leading-zero shape.
    needle = f"{_norm_hex(vendor)}/{_norm_hex(product)}"

    for video_dir in candidates:
        n_match = _VIDEO_N_RE.search(video_dir.name)
        if not n_match:
            continue
        try:
            body = (video_dir / "device" / "uevent").read_text()
        except OSError:
            continue
        product_line = _find_field(body, "PRODUCT")
        if not product_line:
            continue
        parts = product_line.split("/")
        if len(parts) < 2:
            continue
        actual = f"{_norm_hex(parts[0])}/{_norm_hex(parts[1])}"
        if actual != needle:
            continue
        # On real /sys, the uevent file does NOT contain DEVPATH (that's a
        # udev event-time field, not a stored attribute). Resolve the
        # videoN symlink to recover the bus path from the filesystem.
        # Fall back to DEVPATH for tests that synthesize the field.
        devpath = _find_field(body, "DEVPATH") or ""
        if not devpath:
            try:
                devpath = str(video_dir.resolve(strict=False))
            except OSError:
                devpath = ""
        bus_path = _extract_bus_path(devpath)
        if bus_path:
            matches.append((int(n_match.group(1)), bus_path))

    if matches:
        matches.sort(key=lambda t: t[0])
        return matches[0][1]

    env_value = os.environ.get(env_var)
    if env_value:
        _logger.info("camera USB path: using %s=%s (no sysfs match)", env_var, env_value)
        return env_value

    _logger.warning(
        "camera USB path: no sysfs match for %s and %s unset",
        vendor_product,
        env_var,
    )
    return None


def _norm_hex(hex_id: str) -> str:
    """Strip leading zeros, lowercase. Mirrors how the kernel encodes
    PRODUCT= in /sys/.../uevent (e.g. `0c45` → `c45`)."""
    return hex_id.lstrip("0").lower() or "0"


def _find_field(uevent_body: str, key: str) -> str | None:
    prefix = f"{key}="
    for line in uevent_body.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):]
    return None


def _extract_bus_path(devpath: str) -> str | None:
    """The deepest USB-bus-path-shaped token in DEVPATH is the right one.

    Example: `/devices/platform/scb/.../usb1/1-1/1-1.2.2/...` → `1-1.2.2`.
    """
    tokens = _USB_PATH_RE.findall(devpath)
    return tokens[-1] if tokens else None
