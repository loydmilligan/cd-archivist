"""Failing tests for POST /api/library/CD_NNNN/recapture (sprint-3 / Bucket D).

Operator review-recapture: a single off→on→off mini-capture sequence that
writes two stills into `CD_NNNN/review/`. Five cases:

  (a) happy path        — call ordering on fake camera + fake LED,
                          response JSON, files land in review/.
  (b) 409 when busy     — LoopState.state in {CAPTURE, EJECT} → 409,
                          no camera or LED calls.
  (c) 404 unknown disc  — CD_NNNN absent → 404, no side effects.
  (d) filename shape    — review_ambient_<ts>.jpg + review_lit_<ts>.jpg
                          share the same ISO timestamp; review/ created.
  (e) LED never raises  — LED whose power_on/off throw is tolerated;
                          captures still land, response carries `errors`.

Impl lands in `impl-review-recapture` (Wave 2).
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from archivist.models.manifest import Manifest, RipRecord, write_manifest
from archivist.service.app import LoopState, create_app


# ---------- fakes ----------------------------------------------------


class FakeCamera:
    """Records call args; touches the out_path so the file exists on disk."""

    def __init__(self, *, raise_on: int | None = None) -> None:
        self.calls: list[tuple[Path, Path, int]] = []
        self._raise_on = raise_on

    def __call__(self, device: Path, out_path: Path, *, frames: int = 15) -> Path | None:
        n = len(self.calls)
        self.calls.append((device, out_path, frames))
        if self._raise_on is not None and n == self._raise_on:
            raise RuntimeError("camera blew up")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"\xff\xd8\xff\xd9")
        return out_path


class FakeLED:
    """Records call sequence; can be configured to raise on either op."""

    def __init__(self, *, raise_on_on: bool = False, raise_on_off: bool = False) -> None:
        self.calls: list[str] = []
        self._raise_on_on = raise_on_on
        self._raise_on_off = raise_on_off

    def power_on(self) -> bool:
        self.calls.append("on")
        if self._raise_on_on:
            raise RuntimeError("led on failed")
        return True

    def power_off(self) -> bool:
        self.calls.append("off")
        if self._raise_on_off:
            raise RuntimeError("led off failed")
        return True

    def status(self) -> str:
        return "unknown"


# ---------- fixtures -------------------------------------------------


def _write_minimal_manifest(disc_dir: Path, disc_id: str) -> None:
    from datetime import UTC, datetime

    m = Manifest(
        schema_version="0.2",
        disc_id=disc_id,
        media_type="audio_cd",
        created_at=datetime.now(UTC),
        status="ripped",
        captures=[],
        rips=[RipRecord(status="success", tracks=["audio/track01.flac"], errors=[])],
        pairings=[],
        metadata={},
        errors=[],
    )
    write_manifest(disc_dir / "manifest.json", m)


@pytest.fixture
def discs_root(tmp_path: Path) -> Path:
    root = tmp_path / "discs"
    d = root / "CD_0001"
    (d / "captures").mkdir(parents=True)
    (d / "audio").mkdir(parents=True)
    _write_minimal_manifest(d, "CD_0001")
    return root


@pytest.fixture
def loop_state() -> LoopState:
    return LoopState(state="IDLE")


@pytest.fixture
def camera() -> FakeCamera:
    return FakeCamera()


@pytest.fixture
def led() -> FakeLED:
    return FakeLED()


@pytest.fixture
def client(
    discs_root: Path, loop_state: LoopState, camera: FakeCamera, led: FakeLED,
    tmp_path: Path,
) -> TestClient:
    log_path = tmp_path / "archivist.log"
    log_path.write_text("")
    app = create_app(
        loop_state,
        log_path,
        discs_root=discs_root,
        recapture_camera=camera,
        recapture_led=led,
    )
    return TestClient(app)


# ---------- (a) happy path -------------------------------------------


def test_recapture_happy_path_call_order(
    client: TestClient, camera: FakeCamera, led: FakeLED, discs_root: Path,
) -> None:
    resp = client.post("/api/library/CD_0001/recapture")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "ambient" in body and "lit" in body
    assert body["ambient"].startswith("review/review_ambient_")
    assert body["ambient"].endswith(".jpg")
    assert body["lit"].startswith("review/review_lit_")
    assert body["lit"].endswith(".jpg")
    # `errors` omitted (or empty) on full success.
    assert not body.get("errors")

    # LED+camera call sequence: off, capture, on, capture, off.
    assert led.calls == ["off", "on", "off"]
    assert len(camera.calls) == 2
    amb_path, lit_path = camera.calls[0][1], camera.calls[1][1]
    assert "ambient" in amb_path.name
    assert "lit" in lit_path.name

    # Files landed under review/.
    review_dir = discs_root / "CD_0001" / "review"
    assert review_dir.is_dir()
    assert (review_dir / Path(body["ambient"]).name).is_file()
    assert (review_dir / Path(body["lit"]).name).is_file()


# ---------- (b) 409 when busy ----------------------------------------


@pytest.mark.parametrize("busy_state", ["CAPTURE", "EJECT"])
def test_recapture_409_when_loop_owns_camera(
    discs_root: Path, tmp_path: Path, busy_state: str,
) -> None:
    loop_state = LoopState(state=busy_state)
    camera = FakeCamera()
    led = FakeLED()
    log_path = tmp_path / "archivist.log"
    log_path.write_text("")
    client = TestClient(create_app(
        loop_state, log_path, discs_root=discs_root,
        recapture_camera=camera, recapture_led=led,
    ))

    resp = client.post("/api/library/CD_0001/recapture")
    assert resp.status_code == 409
    assert camera.calls == []
    assert led.calls == []


# ---------- (c) 404 unknown disc -------------------------------------


def test_recapture_404_unknown_disc(
    client: TestClient, camera: FakeCamera, led: FakeLED,
) -> None:
    resp = client.post("/api/library/CD_9999/recapture")
    assert resp.status_code == 404
    assert camera.calls == []
    assert led.calls == []


def test_recapture_404_invalid_disc_id(
    client: TestClient, camera: FakeCamera, led: FakeLED,
) -> None:
    resp = client.post("/api/library/INVALID/recapture")
    assert resp.status_code == 404
    assert camera.calls == []
    assert led.calls == []


# ---------- (d) filename convention ----------------------------------


def test_recapture_filenames_share_timestamp(
    client: TestClient, discs_root: Path,
) -> None:
    body = client.post("/api/library/CD_0001/recapture").json()
    amb_name = Path(body["ambient"]).name  # review_ambient_<ts>.jpg
    lit_name = Path(body["lit"]).name      # review_lit_<ts>.jpg
    amb_ts = amb_name[len("review_ambient_"):-len(".jpg")]
    lit_ts = lit_name[len("review_lit_"):-len(".jpg")]
    assert amb_ts == lit_ts
    assert amb_ts  # non-empty


def test_recapture_creates_review_dir_when_absent(
    discs_root: Path, tmp_path: Path,
) -> None:
    # Brand-new disc with no review/ subdir yet.
    d = discs_root / "CD_0002"
    (d / "captures").mkdir(parents=True)
    _write_minimal_manifest(d, "CD_0002")
    assert not (d / "review").exists()

    loop_state = LoopState(state="IDLE")
    camera = FakeCamera()
    led = FakeLED()
    log_path = tmp_path / "archivist.log"
    log_path.write_text("")
    client = TestClient(create_app(
        loop_state, log_path, discs_root=discs_root,
        recapture_camera=camera, recapture_led=led,
    ))

    resp = client.post("/api/library/CD_0002/recapture")
    assert resp.status_code == 200
    assert (d / "review").is_dir()


# ---------- (e) LED never raises -------------------------------------


def test_recapture_tolerates_led_failure(
    discs_root: Path, tmp_path: Path,
) -> None:
    loop_state = LoopState(state="IDLE")
    camera = FakeCamera()
    led = FakeLED(raise_on_on=True, raise_on_off=True)
    log_path = tmp_path / "archivist.log"
    log_path.write_text("")
    client = TestClient(create_app(
        loop_state, log_path, discs_root=discs_root,
        recapture_camera=camera, recapture_led=led,
    ))

    resp = client.post("/api/library/CD_0001/recapture")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Captures still landed.
    assert "ambient" in body and "lit" in body
    assert len(camera.calls) == 2
    # And errors surfaced.
    assert body.get("errors")
    assert any("led" in e.lower() for e in body["errors"])

    # Files still on disk despite LED failure.
    review_dir = discs_root / "CD_0001" / "review"
    assert (review_dir / Path(body["ambient"]).name).is_file()
    assert (review_dir / Path(body["lit"]).name).is_file()
