"""Failing tests for archivist.drivers.led.LEDPanel (Tasmota HTTP client).

Per sprint-1 Wave 1 (test-led). Impl lands in Wave 2 (impl-led).

Invariant under test: LEDPanel methods NEVER raise. Failures are logged
and surfaced through the documented return-value sentinel.
"""
from __future__ import annotations

import logging
from typing import Any

import pytest
import requests

from archivist.drivers.led import LEDPanel

BASE_URL = "http://192.168.5.186"


class FakeResponse:
    def __init__(self, payload: Any, status_code: int = 200, raise_json: bool = False) -> None:
        self._payload = payload
        self.status_code = status_code
        self._raise_json = raise_json
        self.text = str(payload)

    def json(self) -> Any:
        if self._raise_json:
            raise ValueError("malformed JSON")
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


class _CapturedGets(list):
    """List of (url, kwargs) tuples plus a scriptable response slot."""

    response_holder: dict[str, Any]


@pytest.fixture
def captured_gets(monkeypatch: pytest.MonkeyPatch) -> _CapturedGets:
    """Patches requests.get in the led module; records (url, kwargs)."""
    import archivist.drivers.led as led_mod

    calls = _CapturedGets()
    calls.response_holder = {"resp": FakeResponse({"POWER": "ON"})}

    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        calls.append((url, kwargs))
        r = calls.response_holder["resp"]
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(led_mod.requests, "get", fake_get)
    return calls


def _set_response(calls: _CapturedGets, resp: Any) -> None:
    calls.response_holder["resp"] = resp


# ---------------------------- happy paths ----------------------------

def test_power_on_happy(captured_gets: _CapturedGets) -> None:
    _set_response(captured_gets, FakeResponse({"POWER": "ON"}))
    panel = LEDPanel(BASE_URL)
    assert panel.power_on() is True
    url, kwargs = captured_gets[0]
    assert url == f"{BASE_URL}/cm"
    assert kwargs["params"] == {"cmnd": "Power On"}


def test_power_off_happy(captured_gets: _CapturedGets) -> None:
    _set_response(captured_gets, FakeResponse({"POWER": "OFF"}))
    panel = LEDPanel(BASE_URL)
    assert panel.power_off() is True
    url, kwargs = captured_gets[0]
    assert url == f"{BASE_URL}/cm"
    assert kwargs["params"] == {"cmnd": "Power Off"}


def test_status_on(captured_gets: _CapturedGets) -> None:
    _set_response(captured_gets, FakeResponse({"POWER": "ON"}))
    panel = LEDPanel(BASE_URL)
    assert panel.status() == "on"
    _, kwargs = captured_gets[0]
    assert kwargs["params"] == {"cmnd": "Power"}


def test_status_off(captured_gets: _CapturedGets) -> None:
    _set_response(captured_gets, FakeResponse({"POWER": "OFF"}))
    panel = LEDPanel(BASE_URL)
    assert panel.status() == "off"


# ---------------------- network-failure paths ------------------------

def test_power_on_connection_error_returns_false(
    captured_gets: list, caplog: pytest.LogCaptureFixture
) -> None:
    _set_response(captured_gets, requests.ConnectionError("nope"))
    panel = LEDPanel(BASE_URL)
    with caplog.at_level(logging.WARNING):
        result = panel.power_on()
    assert result is False
    assert any("LED" in r.message or "led" in r.message.lower() for r in caplog.records)


def test_power_off_timeout_returns_false(captured_gets: list) -> None:
    _set_response(captured_gets, requests.Timeout("slow"))
    panel = LEDPanel(BASE_URL)
    assert panel.power_off() is False


def test_status_network_error_returns_unknown(captured_gets: list) -> None:
    _set_response(captured_gets, requests.ConnectionError("nope"))
    panel = LEDPanel(BASE_URL)
    assert panel.status() == "unknown"


# ---------------------- malformed-response path ----------------------

def test_status_malformed_json_returns_unknown(captured_gets: list) -> None:
    _set_response(captured_gets, FakeResponse(None, raise_json=True))
    panel = LEDPanel(BASE_URL)
    assert panel.status() == "unknown"


def test_status_unexpected_shape_returns_unknown(captured_gets: list) -> None:
    _set_response(captured_gets, FakeResponse({"WAT": "huh"}))
    panel = LEDPanel(BASE_URL)
    assert panel.status() == "unknown"


# ---------------------- never-raises invariant -----------------------

def test_methods_never_raise_even_on_exotic_errors(captured_gets: list) -> None:
    """Documented invariant: no LEDPanel method ever raises."""
    _set_response(captured_gets, requests.RequestException("any RequestException subclass"))
    panel = LEDPanel(BASE_URL)
    # None of these should raise.
    panel.power_on()
    panel.power_off()
    panel.status()
