"""Failing tests for the /api/review/* endpoint family (sprint-5 Bucket B).

Covers test-review-folder-list, test-review-candidates-search,
test-review-candidates-mbid, test-review-apply, test-review-use-as-is.

The endpoints back the in-UI beets review surface per
docs/design/2026-05-16-in-ui-beets-review.md. Folder discovery
follows D-review-folder-discovery (aggregate MUSIC_REVIEW_DIR +
READY-no-PROCESSING in MUSIC_INBOX_DIR). MB queries follow
D-mb-query-direct-not-beets (musicbrainzngs directly for candidates,
docker exec beet for the actual import).

Impl lands in Wave 2 (impl-review-routes).
"""
from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from archivist.service.app import LoopState, create_app


# ---------------- fixtures -------------------------------------------


def _write_flac(path: Path, n_bytes: int = 1024) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fLaC" + b"\x00" * n_bytes)


def _write_source_json(folder: Path, *, disc_id: str | None = None) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "ripper": {"name": "cd-archivist", "version": "0.1.0", "host": "cm4"},
        "disc": {
            "folder_name": folder.name,
            "disc_counter": 1,
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
            "channels": 2, "track_count": 2, "total_duration_seconds": 480,
            "secure_rip": True, "accuraterip_verified": None,
        },
        "identifiers": {
            "musicbrainz_disc_id": disc_id,
            "freedb_disc_id": None, "cd_toc": None, "upc": None, "isrcs": [],
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
            "rip_success": True, "photo_success": False, "ready": True,
            "warnings": [], "errors": [],
        },
    }
    (folder / "source.json").write_text(json.dumps(payload))


@pytest.fixture
def music_roots(tmp_path: Path) -> tuple[Path, Path]:
    """Returns (review_root, inbox_root) populated with a few fixture folders."""
    review = tmp_path / "music" / "review"
    inbox = tmp_path / "music" / "inbox"
    review.mkdir(parents=True)
    inbox.mkdir(parents=True)
    return review, inbox


@pytest.fixture
def loop_state() -> LoopState:
    return LoopState()


@pytest.fixture
def client(
    music_roots: tuple[Path, Path], loop_state: LoopState, tmp_path: Path,
) -> TestClient:
    review_root, inbox_root = music_roots
    log_path = tmp_path / "archivist.log"
    log_path.write_text("")
    return TestClient(create_app(
        loop_state, log_path,
        discs_root=inbox_root,
        review_root=review_root,
    ))


# ============== test-review-folder-list (6 cases) ====================


def test_folder_list_empty(client: TestClient) -> None:
    resp = client.get("/api/review/folders")
    assert resp.status_code == 200
    assert resp.json() == {"folders": []}


def test_folder_list_review_folder_surfaces(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    review_root, _ = music_roots
    folder = review_root / "2026-05-16_1200_disc-000001"
    _write_flac(folder / "01 Track.flac")
    _write_flac(folder / "02 Track.flac")
    _write_source_json(folder)

    body = client.get("/api/review/folders").json()
    assert len(body["folders"]) == 1
    entry = body["folders"][0]
    assert entry["name"] == folder.name
    assert entry["source"] == "review"
    assert entry["audio_count"] == 2
    assert entry["source_json"] is not None
    assert isinstance(entry["source_json"], dict)


def test_folder_list_inbox_ready_no_processing_surfaces(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    _, inbox_root = music_roots
    folder = inbox_root / "2026-05-16_1300_disc-000002"
    _write_flac(folder / "01 Track.flac")
    (folder / "READY").write_text("ready_at=...\n")
    _write_source_json(folder)

    body = client.get("/api/review/folders").json()
    names = [f["name"] for f in body["folders"]]
    assert folder.name in names
    entry = next(f for f in body["folders"] if f["name"] == folder.name)
    assert entry["source"] == "inbox-stuck"


def test_folder_list_inbox_ready_with_processing_excluded(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    _, inbox_root = music_roots
    folder = inbox_root / "2026-05-16_1400_disc-000003"
    _write_flac(folder / "01 Track.flac")
    (folder / "READY").write_text("ready_at=...\n")
    (folder / "PROCESSING").write_text("claimed\n")
    _write_source_json(folder)

    body = client.get("/api/review/folders").json()
    assert folder.name not in [f["name"] for f in body["folders"]]


def test_folder_list_inbox_without_ready_excluded(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    """Rip-in-progress folder (no READY yet) must not surface."""
    _, inbox_root = music_roots
    folder = inbox_root / "2026-05-16_1500_disc-000004"
    _write_flac(folder / "01 Track.flac")
    _write_source_json(folder)
    # No READY marker.

    body = client.get("/api/review/folders").json()
    assert folder.name not in [f["name"] for f in body["folders"]]


def test_folder_list_legacy_folder_without_source_json(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    review_root, _ = music_roots
    folder = review_root / "CD_0007"
    _write_flac(folder / "01 Track.flac")
    # No source.json (legacy folder).

    body = client.get("/api/review/folders").json()
    entry = next(f for f in body["folders"] if f["name"] == "CD_0007")
    assert entry["source_json"] is None


# ============== test-review-candidates-search (6 cases) ==============


def _mb_release_candidate(*, mbid: str = "fake-mbid-1") -> dict:
    return {
        "id": mbid,
        "ext:score": "92",
        "title": "Sing the Sorrow",
        "artist-credit-phrase": "AFI",
        "date": "2003-03-11",
        "label-info-list": [{"label": {"name": "DreamWorks Records"}}],
        "label-info": [{"catalog-number": "B0000401"}],
        "medium-list": [{
            "track-list": [
                {"position": "1", "recording": {
                    "title": "Miseria Cantare", "length": "121000",
                }},
                {"position": "2", "recording": {
                    "title": "The Leaving Song", "length": "243000",
                }},
            ],
        }],
    }


def _seed_folder(review_root: Path, name: str = "afi-sts") -> Path:
    folder = review_root / name
    _write_flac(folder / "01 Track.flac", n_bytes=120 * 44100 * 4)
    _write_flac(folder / "02 Track.flac", n_bytes=250 * 44100 * 4)
    _write_source_json(folder)
    return folder


def test_candidates_search_invokes_mb(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    review_root, _ = music_roots
    folder = _seed_folder(review_root)
    fake_mb = MagicMock()
    fake_mb.search_releases.return_value = {"release-list": [_mb_release_candidate()]}
    with patch("archivist.service.beets_review.get_mb_client", return_value=fake_mb):
        resp = client.get(f"/api/review/{folder.name}/candidates?search=afi+sing+the+sorrow")
    assert resp.status_code == 200, resp.text
    fake_mb.search_releases.assert_called_once()
    args, kwargs = fake_mb.search_releases.call_args
    # Query string must be the user's query; limit 5 per spec.
    assert "afi" in (args[0] if args else kwargs.get("query", ""))
    assert kwargs.get("limit") == 5


def test_candidates_search_empty_result(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    review_root, _ = music_roots
    folder = _seed_folder(review_root)
    fake_mb = MagicMock()
    fake_mb.search_releases.return_value = {"release-list": []}
    with patch("archivist.service.beets_review.get_mb_client", return_value=fake_mb):
        body = client.get(f"/api/review/{folder.name}/candidates?search=x").json()
    assert body["candidates"] == []


def test_candidates_search_transforms_response(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    review_root, _ = music_roots
    folder = _seed_folder(review_root)
    fake_mb = MagicMock()
    fake_mb.search_releases.return_value = {
        "release-list": [_mb_release_candidate()],
    }
    with patch("archivist.service.beets_review.get_mb_client", return_value=fake_mb):
        body = client.get(f"/api/review/{folder.name}/candidates?search=afi").json()
    assert len(body["candidates"]) == 1
    c = body["candidates"][0]
    for key in ("mbid", "score", "artist", "title", "year", "track_count", "tracks"):
        assert key in c, f"missing key {key!r}"
    assert c["mbid"] == "fake-mbid-1"
    assert c["title"] == "Sing the Sorrow"
    assert c["artist"] == "AFI"
    assert c["year"] == "2003"
    assert c["track_count"] == 2
    assert len(c["tracks"]) == 2


def test_candidates_search_includes_tracks_diff(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    review_root, _ = music_roots
    folder = _seed_folder(review_root)
    fake_mb = MagicMock()
    fake_mb.search_releases.return_value = {"release-list": [_mb_release_candidate()]}
    with patch("archivist.service.beets_review.get_mb_client", return_value=fake_mb):
        body = client.get(f"/api/review/{folder.name}/candidates?search=afi").json()
    c = body["candidates"][0]
    assert "tracks_diff" in c
    assert len(c["tracks_diff"]) >= 1
    row = c["tracks_diff"][0]
    for key in ("file", "proposed_title", "proposed_length_seconds",
                "delta_seconds", "delta_warning"):
        assert key in row


def test_candidates_search_unknown_folder_404(client: TestClient) -> None:
    resp = client.get("/api/review/does-not-exist/candidates?search=x")
    assert resp.status_code == 404


def test_candidates_search_mb_unavailable_502(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    import musicbrainzngs
    review_root, _ = music_roots
    folder = _seed_folder(review_root)
    fake_mb = MagicMock()
    fake_mb.search_releases.side_effect = musicbrainzngs.WebServiceError("boom")
    with patch("archivist.service.beets_review.get_mb_client", return_value=fake_mb):
        resp = client.get(f"/api/review/{folder.name}/candidates?search=x")
    assert resp.status_code == 502
    body = resp.json()
    assert "musicbrainz" in str(body).lower()


# ============== test-review-candidates-mbid (4 cases) ================


def test_candidates_mbid_invokes_get_release_by_id(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    review_root, _ = music_roots
    folder = _seed_folder(review_root)
    fake_mb = MagicMock()
    mbid = str(uuid.uuid4())
    fake_mb.get_release_by_id.return_value = {
        "release": _mb_release_candidate(mbid=mbid),
    }
    with patch("archivist.service.beets_review.get_mb_client", return_value=fake_mb):
        resp = client.get(f"/api/review/{folder.name}/candidates?mbid={mbid}")
    assert resp.status_code == 200
    fake_mb.get_release_by_id.assert_called_once()
    args, kwargs = fake_mb.get_release_by_id.call_args
    assert args[0] == mbid
    includes = kwargs.get("includes", [])
    for inc in ("recordings", "artist-credits", "labels", "release-groups"):
        assert inc in includes


def test_candidates_mbid_invalid_format_400(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    review_root, _ = music_roots
    folder = _seed_folder(review_root)
    resp = client.get(f"/api/review/{folder.name}/candidates?mbid=not-a-uuid")
    assert resp.status_code == 400


def test_candidates_unknown_mbid_404(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    import musicbrainzngs
    review_root, _ = music_roots
    folder = _seed_folder(review_root)
    fake_mb = MagicMock()
    fake_mb.get_release_by_id.side_effect = musicbrainzngs.ResponseError(
        message="404 Not Found",
    )
    mbid = str(uuid.uuid4())
    with patch("archivist.service.beets_review.get_mb_client", return_value=fake_mb):
        resp = client.get(f"/api/review/{folder.name}/candidates?mbid={mbid}")
    assert resp.status_code == 404


def test_candidates_search_and_mbid_mutually_exclusive(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    review_root, _ = music_roots
    folder = _seed_folder(review_root)
    mbid = str(uuid.uuid4())
    resp = client.get(f"/api/review/{folder.name}/candidates?search=x&mbid={mbid}")
    assert resp.status_code == 400


# ============== test-review-apply (7 cases) ==========================


def _patch_subprocess_run(returncode: int = 0, stdout: str = "", stderr: str = ""):
    """Return a MagicMock to patch subprocess.run in the review module."""
    result = MagicMock()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return MagicMock(return_value=result)


def test_apply_happy_path(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    review_root, _ = music_roots
    folder = _seed_folder(review_root)
    mbid = str(uuid.uuid4())
    beets_stdout = (
        "Tagging:\n  AFI - Sing the Sorrow\n"
        "-> /srv/music/library/AFI/Sing the Sorrow\n"
    )
    fake_run = _patch_subprocess_run(0, beets_stdout, "")
    with patch("archivist.service.beets_review.subprocess.run", fake_run):
        resp = client.post(
            f"/api/review/{folder.name}/apply",
            json={"mbid": mbid},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "applied"
    assert body["mbid"] == mbid


def test_apply_argv_locked(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    """Regression: exact argv list, never shell=True."""
    review_root, _ = music_roots
    folder = _seed_folder(review_root)
    mbid = str(uuid.uuid4())
    fake_run = _patch_subprocess_run(0, "-> /lib/path\n", "")
    with patch("archivist.service.beets_review.subprocess.run", fake_run):
        client.post(f"/api/review/{folder.name}/apply", json={"mbid": mbid})

    fake_run.assert_called_once()
    args, kwargs = fake_run.call_args
    assert args[0] == [
        "docker", "exec", "cd_beets",
        "beet", "import", "-q", "--search-id", mbid,
        f"/downloads/{folder.name}",
    ]
    assert kwargs.get("shell") in (False, None)


def test_apply_beets_failure_500(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    review_root, _ = music_roots
    folder = _seed_folder(review_root)
    mbid = str(uuid.uuid4())
    fake_run = _patch_subprocess_run(1, "", "beets exploded")
    with patch("archivist.service.beets_review.subprocess.run", fake_run):
        resp = client.post(f"/api/review/{folder.name}/apply", json={"mbid": mbid})
    assert resp.status_code == 500
    body = resp.json()["detail"]
    assert body["status"] == "failed"
    assert "beets exploded" in body["stderr"]


def test_apply_timeout_504(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    review_root, _ = music_roots
    folder = _seed_folder(review_root)
    mbid = str(uuid.uuid4())
    fake_run = MagicMock(side_effect=subprocess.TimeoutExpired(cmd="beet", timeout=120))
    with patch("archivist.service.beets_review.subprocess.run", fake_run):
        resp = client.post(f"/api/review/{folder.name}/apply", json={"mbid": mbid})
    assert resp.status_code == 504
    assert "120" in resp.text or "exceeded" in resp.text.lower()


@pytest.mark.parametrize("busy_state", ["RIP", "EJECT", "CAPTURE"])
def test_apply_busy_state_409(
    music_roots: tuple[Path, Path], tmp_path: Path, busy_state: str,
) -> None:
    review_root, inbox_root = music_roots
    folder = _seed_folder(review_root)
    mbid = str(uuid.uuid4())

    loop_state = LoopState(state=busy_state)
    log_path = tmp_path / "archivist.log"
    log_path.write_text("")
    client = TestClient(create_app(
        loop_state, log_path,
        discs_root=inbox_root,
        review_root=review_root,
    ))
    resp = client.post(f"/api/review/{folder.name}/apply", json={"mbid": mbid})
    assert resp.status_code == 409


def test_apply_folder_not_found_404(client: TestClient) -> None:
    mbid = str(uuid.uuid4())
    resp = client.post("/api/review/does-not-exist/apply", json={"mbid": mbid})
    assert resp.status_code == 404


def test_apply_invalid_mbid_400(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    review_root, _ = music_roots
    folder = _seed_folder(review_root)
    resp = client.post(f"/api/review/{folder.name}/apply", json={"mbid": "garbage"})
    assert resp.status_code == 400
    resp_missing = client.post(f"/api/review/{folder.name}/apply", json={})
    assert resp_missing.status_code in (400, 422)


# ============== test-review-use-as-is (5 cases) ======================


def test_use_as_is_happy_path(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    review_root, _ = music_roots
    folder = _seed_folder(review_root)
    beets_stdout = "-> /srv/music/library/Unknown/Unknown Album\n"
    fake_run = _patch_subprocess_run(0, beets_stdout, "")
    with patch("archivist.service.beets_review.subprocess.run", fake_run):
        resp = client.post(f"/api/review/{folder.name}/use-as-is")
    assert resp.status_code == 200
    assert resp.json()["status"] == "applied"


def test_use_as_is_argv_includes_dash_a(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    review_root, _ = music_roots
    folder = _seed_folder(review_root)
    fake_run = _patch_subprocess_run(0, "-> /lib\n", "")
    with patch("archivist.service.beets_review.subprocess.run", fake_run):
        client.post(f"/api/review/{folder.name}/use-as-is")

    args, kwargs = fake_run.call_args
    assert args[0] == [
        "docker", "exec", "cd_beets",
        "beet", "import", "-A", f"/downloads/{folder.name}",
    ]
    assert kwargs.get("shell") in (False, None)


def test_use_as_is_beets_failure_500(
    client: TestClient, music_roots: tuple[Path, Path],
) -> None:
    review_root, _ = music_roots
    folder = _seed_folder(review_root)
    fake_run = _patch_subprocess_run(2, "", "beets failure")
    with patch("archivist.service.beets_review.subprocess.run", fake_run):
        resp = client.post(f"/api/review/{folder.name}/use-as-is")
    assert resp.status_code == 500


def test_use_as_is_busy_state_409(
    music_roots: tuple[Path, Path], tmp_path: Path,
) -> None:
    review_root, inbox_root = music_roots
    folder = _seed_folder(review_root)
    loop_state = LoopState(state="RIP")
    log_path = tmp_path / "archivist.log"
    log_path.write_text("")
    client = TestClient(create_app(
        loop_state, log_path,
        discs_root=inbox_root,
        review_root=review_root,
    ))
    resp = client.post(f"/api/review/{folder.name}/use-as-is")
    assert resp.status_code == 409


def test_use_as_is_unknown_folder_404(client: TestClient) -> None:
    resp = client.post("/api/review/missing/use-as-is")
    assert resp.status_code == 404
