"""Failing tests for GET /api/disc/<folder>/candidates (sprint-7 D).

Per D-candidates-source-priority: query MusicBrainz in priority order
(1) musicbrainz_disc_id lookup → prepended at score 1.0;
(2) AcoustID fingerprint lookup if chroma cache exists;
(3) metadata search using operator_hints.artist|album.
Dedupe by MBID, sort by score desc, return top 5.

Impl lands in Wave 2 (impl-candidates-endpoint).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from archivist.service.app import LoopState, create_app


def _write_flac(path: Path, n_bytes: int = 1024) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fLaC" + b"\x00" * n_bytes)


def _base_source(name: str, **overrides) -> dict:
    payload = {
        "schema_version": 1,
        "ripper": {"name": "cd-archivist", "version": "0.1.0", "host": "cm4"},
        "disc": {
            "folder_name": name, "disc_counter": 1,
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
            "channels": 2, "track_count": 10,
            "total_duration_seconds": 2400,
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
            "rip_success": True, "photo_success": True, "ready": True,
            "warnings": [], "errors": [],
            "partial": False, "failed_tracks": [],
        },
    }
    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(payload.get(k), dict):
            payload[k] = {**payload[k], **v}
        else:
            payload[k] = v
    return payload


def _seed(parent: Path, name: str, payload: dict | None = None) -> Path:
    folder = parent / name
    _write_flac(folder / "01.flac")
    folder.mkdir(parents=True, exist_ok=True)
    if payload is None:
        payload = _base_source(name)
    (folder / "source.json").write_text(json.dumps(payload))
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


class _FakeMBClient:
    """Minimal fake matching the surface impl-candidates-endpoint uses."""

    def __init__(
        self,
        *,
        disc_id_hit: dict | None = None,
        fingerprint_hits: list[dict] | None = None,
        search_hits: list[dict] | None = None,
        raise_on: str | None = None,
    ) -> None:
        self.disc_id_hit = disc_id_hit
        self.fingerprint_hits = fingerprint_hits or []
        self.search_hits = search_hits or []
        self.raise_on = raise_on
        self.calls: list[str] = []

    def lookup_by_disc_id(self, disc_id: str) -> dict | None:
        self.calls.append("disc-id")
        if self.raise_on == "disc-id":
            raise RuntimeError("network down")
        return self.disc_id_hit

    def search_by_fingerprint(self, folder: Path) -> list[dict]:
        self.calls.append("fingerprint")
        if self.raise_on == "fingerprint":
            raise RuntimeError("network down")
        return self.fingerprint_hits

    def search_by_metadata(self, *, artist: str | None, album: str | None) -> list[dict]:
        self.calls.append("metadata")
        if self.raise_on == "metadata":
            raise RuntimeError("network down")
        return self.search_hits


@pytest.fixture
def install_fake_mb(monkeypatch: pytest.MonkeyPatch):
    def _install(fake: _FakeMBClient) -> _FakeMBClient:
        from archivist.service import mb_client as mb_module

        monkeypatch.setattr(mb_module, "get_mb_client", lambda: fake)
        return fake

    return _install


# ============== (a) response shape ======================================


def test_candidates_response_shape(
    client: TestClient, music_root: Path, install_fake_mb,
) -> None:
    install_fake_mb(_FakeMBClient(search_hits=[
        {"mbid": "11111111-1111-1111-1111-111111111111", "score": 0.82,
         "artist": "Foo", "title": "Bar", "year": 2003,
         "track_count": 10, "country": "US"},
    ]))
    folder = _seed(music_root / "review", "cand-shape", _base_source(
        "cand-shape",
        operator_hints={"artist": "Foo", "album": "Bar"},
    ))
    res = client.get(f"/api/disc/{folder.name}/candidates")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["source"] == "musicbrainzngs"
    assert isinstance(body["candidates"], list)
    assert body["candidates"], "expected at least one candidate"
    row = body["candidates"][0]
    for key in ("mbid", "score", "artist", "title", "year",
                "track_count", "country"):
        assert key in row, f"missing key {key!r} in candidate row"


# ============== (b) up to 5, sorted desc by score ========================


def test_candidates_capped_at_five_and_sorted_desc(
    client: TestClient, music_root: Path, install_fake_mb,
) -> None:
    hits = [
        {"mbid": f"00000000-0000-0000-0000-{i:012d}",
         "score": s,
         "artist": "X", "title": "Y", "year": 2000 + i,
         "track_count": 10, "country": "US"}
        for i, s in enumerate([0.40, 0.99, 0.55, 0.71, 0.10, 0.88, 0.62])
    ]
    install_fake_mb(_FakeMBClient(search_hits=hits))
    folder = _seed(music_root / "review", "cand-sort", _base_source(
        "cand-sort",
        operator_hints={"artist": "X", "album": "Y"},
    ))
    body = client.get(f"/api/disc/{folder.name}/candidates").json()
    scores = [c["score"] for c in body["candidates"]]
    assert len(scores) <= 5
    assert scores == sorted(scores, reverse=True)


# ============== (c) disc-id lookup prepended at score 1.0 ================


def test_candidates_prepends_disc_id_lookup_at_score_one(
    client: TestClient, music_root: Path, install_fake_mb,
) -> None:
    disc_id_hit = {
        "mbid": "ddddddd0-0000-0000-0000-000000000000",
        "score": 1.0, "artist": "DiscID", "title": "Album",
        "year": 1999, "track_count": 10, "country": "US",
    }
    fake = install_fake_mb(_FakeMBClient(
        disc_id_hit=disc_id_hit,
        search_hits=[{
            "mbid": "ssssssss-0000-0000-0000-000000000000",
            "score": 0.82, "artist": "X", "title": "Y",
            "year": 2003, "track_count": 10, "country": "US",
        }],
    ))
    folder = _seed(music_root / "review", "cand-discid", _base_source(
        "cand-discid",
        identifiers={"musicbrainz_disc_id": "abc123", "freedb_disc_id": None,
                     "cd_toc": None, "upc": None, "isrcs": []},
        operator_hints={"artist": "X", "album": "Y"},
    ))
    body = client.get(f"/api/disc/{folder.name}/candidates").json()
    assert "disc-id" in fake.calls
    assert body["candidates"][0]["mbid"] == disc_id_hit["mbid"]
    assert body["candidates"][0]["score"] == 1.0


# ============== (d) fingerprint path when no disc-id ====================


def test_candidates_falls_back_to_fingerprint_when_no_disc_id(
    client: TestClient, music_root: Path, install_fake_mb,
) -> None:
    fake = install_fake_mb(_FakeMBClient(fingerprint_hits=[
        {"mbid": "ffffffff-0000-0000-0000-000000000000",
         "score": 0.77, "artist": "FP", "title": "Album",
         "year": 2010, "track_count": 10, "country": "US"},
    ]))
    folder = _seed(music_root / "review", "cand-fp", _base_source(
        "cand-fp",
        identifiers={"musicbrainz_disc_id": None, "freedb_disc_id": None,
                     "cd_toc": None, "upc": None, "isrcs": []},
    ))
    # No operator hints — disc-id absent — fingerprint is the only path.
    body = client.get(f"/api/disc/{folder.name}/candidates").json()
    assert "fingerprint" in fake.calls
    assert any(c["mbid"].startswith("ffffffff") for c in body["candidates"])


# ============== (e) metadata-search path when only hints =================


def test_candidates_uses_operator_hints_metadata_search(
    client: TestClient, music_root: Path, install_fake_mb,
) -> None:
    fake = install_fake_mb(_FakeMBClient(search_hits=[
        {"mbid": "aaaaaaaa-0000-0000-0000-000000000000",
         "score": 0.66, "artist": "Op", "title": "Hint",
         "year": None, "track_count": None, "country": None},
    ]))
    folder = _seed(music_root / "review", "cand-hints", _base_source(
        "cand-hints",
        operator_hints={"artist": "Op", "album": "Hint"},
    ))
    body = client.get(f"/api/disc/{folder.name}/candidates").json()
    assert "metadata" in fake.calls
    assert body["candidates"][0]["mbid"].startswith("aaaaaaaa")


# ============== (f) 404 when disc folder does not exist =================


def test_candidates_404_when_folder_missing(
    client: TestClient, install_fake_mb,
) -> None:
    install_fake_mb(_FakeMBClient())
    res = client.get("/api/disc/nope-does-not-exist/candidates")
    assert res.status_code == 404


# ============== (g) 503 + error payload on network failure ==============


def test_candidates_503_on_musicbrainz_network_failure(
    client: TestClient, music_root: Path, install_fake_mb,
) -> None:
    install_fake_mb(_FakeMBClient(
        raise_on="metadata",
    ))
    folder = _seed(music_root / "review", "cand-down", _base_source(
        "cand-down",
        operator_hints={"artist": "X", "album": "Y"},
    ))
    res = client.get(f"/api/disc/{folder.name}/candidates")
    assert res.status_code == 503
    body = res.json()
    assert "musicbrainz" in json.dumps(body).lower()
