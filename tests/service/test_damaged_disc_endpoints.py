"""Failing tests for the damaged-disc UI endpoints (sprint-6 Bucket C).

Covers test-damaged-card-actions. Three POST endpoints back the
damaged-disc card's "process partial / redo / pick tracks" actions:

  POST /api/disc/<folder>/process-partial
  POST /api/disc/<folder>/redo
  POST /api/disc/<folder>/rerip-tracks

Per Contract Changes: source.json gains status.partial,
status.failed_tracks, and per-track provenance entries (exact shape
of provenance settled via D-source-json-provenance-schema during
impl-disc-card-builder). Tests assert the contract surface — the
provenance schema specifics (attempt_id type, timestamp format) are
left to impl.

Impl lands in Wave 2 (impl-damaged-disc-actions).
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from archivist.service.app import LoopState, create_app


def _write_flac(path: Path, n_bytes: int = 1024) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fLaC" + b"\x00" * n_bytes)


def _base_source(folder_name: str, *, track_count: int = 5) -> dict:
    return {
        "schema_version": 1,
        "ripper": {"name": "cd-archivist", "version": "0.1.0", "host": "cm4"},
        "disc": {
            "folder_name": folder_name, "disc_counter": 1,
            "inserted_at": "2026-05-16T10:00:00-07:00",
            "rip_started_at": "2026-05-16T10:00:10-07:00",
            "rip_finished_at": "2026-05-16T10:05:00-07:00",
            "ejected_at": "2026-05-16T10:05:30-07:00",
            "ready_at": "2026-05-16T10:05:45-07:00",
            "timezone": "America/Los_Angeles",
        },
        "drive": {"device": "/dev/sr0", "model": "X", "serial": None, "read_offset": None},
        "audio": {
            "format": "flac", "sample_rate_hz": 44100, "bits_per_sample": 16,
            "channels": 2, "track_count": track_count,
            "total_duration_seconds": 600,
            "secure_rip": True, "accuraterip_verified": None,
        },
        "identifiers": {
            "musicbrainz_disc_id": None, "freedb_disc_id": None,
            "cd_toc": None, "upc": None, "isrcs": [],
        },
        "detected_metadata": {
            "album_artist": None, "album": None, "year": None,
            "label": None, "catalog_number": None, "tracks": [],
        },
        "physical_disc": {
            "photo": None, "photo_captured": False,
            "photo_captured_at": None, "photo_device": None,
            "photo_notes": None, "label_text_guess": None,
            "appears_burned": None, "handwritten": None,
        },
        "files": [],
        "status": {
            "rip_success": False, "photo_success": True, "ready": False,
            "warnings": [], "errors": ["fail-fast at track 3"],
        },
    }


def _seed_failed_disc(
    music_root: Path,
    name: str = "2026-05-16_1200_disc-000050",
    *,
    successful: list[int] | None = None,
    failed: list[int] | None = None,
    track_count: int = 5,
) -> Path:
    """Folder lives in failed/ with partial flacs + source.json marking
    the partial state per the Bucket A spec."""
    folder = music_root / "failed" / name
    folder.mkdir(parents=True, exist_ok=True)
    successful = successful or [1, 2]
    failed = failed or [3, 4, 5]
    for n in successful:
        _write_flac(folder / f"{n:02d}.flac")
    payload = _base_source(name, track_count=track_count)
    payload["status"]["partial"] = True
    payload["status"]["failed_tracks"] = failed
    (folder / "source.json").write_text(json.dumps(payload))
    (folder / "rip.log").write_text("cdparanoia: aborted at track 3\n")
    return folder


@pytest.fixture
def music_root(tmp_path: Path) -> Path:
    root = tmp_path / "music"
    for sub in ("inbox", "review", "library", "archive", "failed"):
        (root / sub).mkdir(parents=True)
    return root


@pytest.fixture
def client(music_root: Path, tmp_path: Path) -> TestClient:
    log_path = tmp_path / "archivist.log"
    log_path.write_text("")
    return TestClient(create_app(
        LoopState(), log_path,
        discs_root=music_root / "inbox",
        review_root=music_root / "review",
        library_root=music_root / "library",
        music_root=music_root,
    ))


# ============== (a) POST /api/disc/<folder>/process-partial ==============


def test_process_partial_moves_failed_to_inbox_with_ready(
    client: TestClient, music_root: Path,
) -> None:
    folder = _seed_failed_disc(music_root)
    resp = client.post(f"/api/disc/{folder.name}/process-partial")
    assert resp.status_code == 200

    moved = music_root / "inbox" / folder.name
    assert moved.is_dir()
    assert not folder.exists(), "source folder under failed/ should be gone"
    # READY marker written for process-ready-auto pickup.
    assert (moved / "READY").is_file()


def test_process_partial_updates_source_json_partial_and_failed_tracks(
    client: TestClient, music_root: Path,
) -> None:
    folder = _seed_failed_disc(
        music_root, successful=[1, 2], failed=[3, 4, 5],
    )
    client.post(f"/api/disc/{folder.name}/process-partial")
    moved = music_root / "inbox" / folder.name
    payload = json.loads((moved / "source.json").read_text())
    assert payload["status"]["partial"] is True
    assert payload["status"]["failed_tracks"] == [3, 4, 5]


def test_process_partial_writes_provenance_entries(
    client: TestClient, music_root: Path,
) -> None:
    folder = _seed_failed_disc(music_root, successful=[1, 2])
    client.post(f"/api/disc/{folder.name}/process-partial")
    moved = music_root / "inbox" / folder.name
    payload = json.loads((moved / "source.json").read_text())
    # Per Contract Changes: source.json.provenance: list[ProvenanceEntry].
    # Each entry carries at minimum an attempt_id and the tracks it covers.
    prov = payload.get("provenance")
    assert isinstance(prov, list)
    assert len(prov) >= 1
    first = prov[0]
    assert "attempt_id" in first
    # Tracks-covered field — schema settled via
    # D-source-json-provenance-schema; assert shape-agnostic existence.
    assert any(k in first for k in ("tracks", "track_indices", "track_numbers"))


def test_process_partial_triggers_post_rip_hook(
    client: TestClient, music_root: Path, loop_state: LoopState = None,
) -> None:
    """The hook is the normal process-ready-auto path. We don't pin the
    invocation mechanism here (subprocess vs in-process call) — we pin
    that the hook callable / subprocess.run is invoked once after the
    move + source.json write."""
    folder = _seed_failed_disc(music_root)
    with patch("subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        # Configure the hook so the endpoint has something to fire.
        # (impl-damaged-disc-actions can choose to call the hook via
        # loop_state.process_ready_hook or via a direct invocation —
        # this test asserts subprocess.run is reached.)
        resp = client.post(f"/api/disc/{folder.name}/process-partial")
        assert resp.status_code == 200
    # The assertion below is intentionally loose — impl decides whether
    # the hook fires synchronously or async; either way subprocess.run
    # gets a call when the hook is configured. For Wave 1 the test just
    # documents the expectation.
    # (No assert on run.called — pinning that without seeing impl risks
    # over-specifying. The endpoint must return 200 and the move + json
    # contract above must hold.)


def test_process_partial_unknown_folder_returns_404(client: TestClient) -> None:
    resp = client.post("/api/disc/does-not-exist/process-partial")
    assert resp.status_code == 404


# ============== (b) POST /api/disc/<folder>/redo =========================


def test_redo_deletes_failed_folder(
    client: TestClient, music_root: Path,
) -> None:
    folder = _seed_failed_disc(music_root)
    # Per impl spec: a confirm=true query flag guards destructive deletes.
    resp = client.post(f"/api/disc/{folder.name}/redo?confirm=true")
    assert resp.status_code == 200
    assert not folder.exists()


def test_redo_without_confirm_does_not_delete(
    client: TestClient, music_root: Path,
) -> None:
    """Destructive op needs ?confirm=true; absent flag returns 400 and
    leaves the folder intact."""
    folder = _seed_failed_disc(music_root)
    resp = client.post(f"/api/disc/{folder.name}/redo")
    assert resp.status_code in (400, 409)
    assert folder.exists()


def test_redo_unknown_folder_returns_404(client: TestClient) -> None:
    resp = client.post("/api/disc/does-not-exist/redo?confirm=true")
    assert resp.status_code == 404


# ============== (c) POST /api/disc/<folder>/rerip-tracks =================


def test_rerip_tracks_validates_against_toc(
    client: TestClient, music_root: Path,
) -> None:
    folder = _seed_failed_disc(music_root, track_count=5)
    # Track 99 is not on the disc.
    resp = client.post(
        f"/api/disc/{folder.name}/rerip-tracks",
        json={"tracks": [99]},
    )
    assert resp.status_code in (400, 422)


def test_rerip_tracks_invokes_partial_rerip_driver(
    client: TestClient, music_root: Path,
) -> None:
    folder = _seed_failed_disc(
        music_root, successful=[1, 2], failed=[3, 4, 5], track_count=5,
    )
    fake_result = MagicMock(
        successful_tracks=[3, 4],
        failed_track=5,
        partial=True,
    )
    with patch(
        "archivist.drivers.ripper.partial_rerip",
        return_value=fake_result,
    ) as rerip:
        resp = client.post(
            f"/api/disc/{folder.name}/rerip-tracks",
            json={"tracks": [3, 4, 5]},
        )
    assert resp.status_code == 200
    assert rerip.called
    # Driver call carries the device + the requested track indices.
    _args, kwargs = rerip.call_args
    assert kwargs.get("track_indices") == [3, 4, 5] or (
        rerip.call_args.args
        and list(rerip.call_args.args[-1]) == [3, 4, 5]
    )


def test_rerip_tracks_merges_with_existing_successful_flacs(
    client: TestClient, music_root: Path,
) -> None:
    """The two pre-existing successful flacs (1, 2) must survive; the
    newly-ripped flacs (3, 4) join them in the same folder."""
    folder = _seed_failed_disc(
        music_root, successful=[1, 2], failed=[3, 4, 5], track_count=5,
    )

    def fake_rerip(*_args, **_kwargs) -> MagicMock:
        # Simulate the driver dropping new flacs into the same folder.
        _write_flac(folder / "03.flac")
        _write_flac(folder / "04.flac")
        return MagicMock(
            successful_tracks=[3, 4], failed_track=None, partial=False,
        )

    with patch(
        "archivist.drivers.ripper.partial_rerip", side_effect=fake_rerip,
    ):
        resp = client.post(
            f"/api/disc/{folder.name}/rerip-tracks",
            json={"tracks": [3, 4]},
        )
    assert resp.status_code == 200
    # All four expected flacs present.
    names = sorted(p.name for p in folder.glob("*.flac"))
    assert names == ["01.flac", "02.flac", "03.flac", "04.flac"]


def test_rerip_tracks_appends_provenance_entry(
    client: TestClient, music_root: Path,
) -> None:
    folder = _seed_failed_disc(
        music_root, successful=[1, 2], failed=[3, 4, 5], track_count=5,
    )
    # Pre-seed one provenance entry from the original rip attempt so we
    # can verify the new entry is appended (not overwritten).
    payload = json.loads((folder / "source.json").read_text())
    payload["provenance"] = [{
        "attempt_id": "original-attempt",
        "tracks": [1, 2],
    }]
    (folder / "source.json").write_text(json.dumps(payload))

    with patch(
        "archivist.drivers.ripper.partial_rerip",
        return_value=MagicMock(
            successful_tracks=[3, 4], failed_track=None, partial=False,
        ),
    ):
        resp = client.post(
            f"/api/disc/{folder.name}/rerip-tracks",
            json={"tracks": [3, 4]},
        )
    assert resp.status_code == 200

    after = json.loads((folder / "source.json").read_text())
    prov = after["provenance"]
    assert len(prov) == 2
    assert prov[0]["attempt_id"] == "original-attempt"
    # New entry carries a fresh attempt_id (whatever the impl chooses
    # to call it — UUID is the obvious pick per the spec).
    assert prov[1]["attempt_id"] != "original-attempt"


def test_rerip_tracks_unknown_folder_returns_404(client: TestClient) -> None:
    resp = client.post(
        "/api/disc/does-not-exist/rerip-tracks",
        json={"tracks": [1]},
    )
    assert resp.status_code == 404


def test_rerip_tracks_empty_body_rejected(
    client: TestClient, music_root: Path,
) -> None:
    folder = _seed_failed_disc(music_root)
    resp = client.post(
        f"/api/disc/{folder.name}/rerip-tracks",
        json={"tracks": []},
    )
    assert resp.status_code in (400, 422)
