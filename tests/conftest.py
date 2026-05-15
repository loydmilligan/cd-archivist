"""Shared test fixtures for the cd-archivist test suite."""
from __future__ import annotations

import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def tmp_disc_root(tmp_path: Path) -> Callable[[], Path]:
    """Factory yielding a tmp directory laid out like /srv/cd-archivist/discs/.

    Each call returns a fresh, isolated discs-root directory under the
    per-test tmp_path. The directory exists and is empty on return.
    """
    counter = {"n": 0}

    def _make() -> Path:
        counter["n"] += 1
        root = tmp_path / f"discs_{counter['n']}"
        root.mkdir(parents=True, exist_ok=True)
        return root

    return _make


class FakeCompletedProcess:
    """Minimal stand-in for subprocess.CompletedProcess."""

    def __init__(
        self,
        args: Any,
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        self.args = args
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def fake_completed_process(
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
    args: Any = None,
) -> FakeCompletedProcess:
    """Shared helper for building a fake subprocess.CompletedProcess.

    Hoisted out of `tests/drivers/test_ripper.py` per sprint-2 task
    `tests-pkg` so any test module can import it as
    `from tests.conftest import fake_completed_process`.
    """
    return FakeCompletedProcess(args, returncode=returncode, stdout=stdout, stderr=stderr)


class FakeSubprocess:
    """Records subprocess.run / Popen calls and returns scripted results.

    Usage:
        fake_subprocess.set_result(returncode=0, stdout="...")
        # or queue multiple:
        fake_subprocess.queue(FakeCompletedProcess([], 0))
        fake_subprocess.queue(FakeCompletedProcess([], 1, stderr="boom"))

        # After exercising code:
        assert fake_subprocess.calls[0].args == [...]
    """

    def __init__(self) -> None:
        self.calls: list[Any] = []
        self._results: list[FakeCompletedProcess | Exception] = []
        self._default: FakeCompletedProcess | Exception = FakeCompletedProcess([], 0)

    def set_result(
        self,
        *,
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        self._default = FakeCompletedProcess([], returncode, stdout, stderr)

    def set_exception(self, exc: Exception) -> None:
        self._default = exc

    def queue(self, result: FakeCompletedProcess | Exception) -> None:
        self._results.append(result)

    def run(self, args: Any, **kwargs: Any) -> FakeCompletedProcess:
        self.calls.append(types_call(args, kwargs))
        result = self._results.pop(0) if self._results else self._default
        if isinstance(result, Exception):
            raise result
        return result


class _Call:
    __slots__ = ("args", "kwargs")

    def __init__(self, args: Any, kwargs: dict[str, Any]) -> None:
        self.args = args
        self.kwargs = kwargs


def types_call(args: Any, kwargs: dict[str, Any]) -> _Call:
    return _Call(args, kwargs)


@pytest.fixture
def fake_subprocess(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeSubprocess]:
    """Stubs subprocess.run cleanly; tests inspect .calls and script results."""
    fake = FakeSubprocess()
    monkeypatch.setattr(subprocess, "run", fake.run)
    yield fake
