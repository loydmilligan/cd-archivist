"""Tasmota HTTP client for the white LED panel aimed at the CD-ROM drive.

Per sprint-1 task impl-led. The documented invariant is that no method
ever raises: network failures and malformed responses are logged and
surfaced through the documented return-value sentinels (`False` /
`"unknown"`).
"""
from __future__ import annotations

import logging
from typing import Literal
from urllib.parse import quote

import requests

_TIMEOUT_SECONDS = 5.0
_logger = logging.getLogger(__name__)

LEDStatus = Literal["on", "off", "unknown"]


class LEDPanel:
    """Thin HTTP client around Tasmota's `/cm?cmnd=Power...` endpoint."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def power_on(self) -> bool:
        return self._set_power("On")

    def power_off(self) -> bool:
        return self._set_power("Off")

    def status(self) -> LEDStatus:
        payload = self._get("Power")
        if payload is None:
            return "unknown"
        value = payload.get("POWER") if isinstance(payload, dict) else None
        if value == "ON":
            return "on"
        if value == "OFF":
            return "off"
        return "unknown"

    def _set_power(self, action: Literal["On", "Off"]) -> bool:
        payload = self._get(f"Power {action}")
        if payload is None:
            return False
        value = payload.get("POWER") if isinstance(payload, dict) else None
        return value in {"ON", "OFF"}

    def _get(self, cmnd: str) -> dict | None:
        url = f"{self.base_url}/cm?cmnd={quote(cmnd)}"
        try:
            resp = requests.get(url, timeout=_TIMEOUT_SECONDS)
            return resp.json()
        except requests.RequestException as exc:
            _logger.warning("LED %s failed: %s", cmnd, exc)
            return None
        except ValueError as exc:  # JSON decode error
            _logger.warning("LED %s returned malformed JSON: %s", cmnd, exc)
            return None
