"""Failing tests for GET /api/logs/tail (sprint-6.5 Bucket D).

Backs the bottom-drawer log surface and any future per-rip/per-card
filter UI. Sprint-6.5 ships the unfiltered endpoint; the filter
params are accepted-and-ignored today so sprint-7 can wire the UI
without a contract change.

Impl lands in Wave 2 (impl-logs-tail-endpoint).
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from archivist.service.app import LoopState, create_app


@pytest.fixture
def music_root(tmp_path: Path) -> Path:
    root = tmp_path / "music"
    for sub in ("inbox", "review", "library", "archive", "failed"):
        (root / sub).mkdir(parents=True)
    return root


@pytest.fixture
def daemon_log(tmp_path: Path) -> Path:
    log_path = tmp_path / "archivist.log"
    log_path.write_text("\n".join(f"line {i}" for i in range(1, 501)) + "\n")
    return log_path


@pytest.fixture
def client(music_root: Path, daemon_log: Path) -> TestClient:
    with patch.dict(os.environ, {"ARCHIVIST_LOG_PATH": str(daemon_log)}):
        return TestClient(create_app(
            LoopState(), daemon_log,
            discs_root=music_root / "inbox",
            review_root=music_root / "review",
            library_root=music_root / "library",
            music_root=music_root,
        ))


# ============== (a) default tail of N=200 ===============================


def test_default_tail_returns_last_200_lines(client: TestClient) -> None:
    body = client.get("/api/logs/tail").json()
    assert "lines" in body
    assert len(body["lines"]) == 200
    # Lines come out in chronological order — last one is the newest.
    assert body["lines"][-1].rstrip() == "line 500"
    assert body["lines"][0].rstrip() == "line 301"


# ============== (b) response shape =====================================


def test_response_shape_contract(client: TestClient) -> None:
    body = client.get("/api/logs/tail").json()
    assert set(body.keys()) >= {"lines", "log_path", "truncated"}
    assert isinstance(body["lines"], list)
    assert isinstance(body["log_path"], str)
    assert isinstance(body["truncated"], bool)


def test_truncated_true_when_log_longer_than_limit(
    client: TestClient,
) -> None:
    """Source has 500 lines, default tail = 200 → truncated=True."""
    body = client.get("/api/logs/tail").json()
    assert body["truncated"] is True


def test_truncated_false_when_log_within_limit(
    music_root: Path, tmp_path: Path,
) -> None:
    short_log = tmp_path / "short.log"
    short_log.write_text("only\n3\nlines\n")
    with patch.dict(os.environ, {"ARCHIVIST_LOG_PATH": str(short_log)}):
        c = TestClient(create_app(
            LoopState(), short_log,
            discs_root=music_root / "inbox",
            review_root=music_root / "review",
            library_root=music_root / "library",
            music_root=music_root,
        ))
        body = c.get("/api/logs/tail").json()
        assert body["truncated"] is False
        assert len(body["lines"]) == 3


# ============== (c) 404 when log file is missing ========================


def test_404_when_log_file_is_missing(
    music_root: Path, tmp_path: Path,
) -> None:
    missing = tmp_path / "no-such-log.log"
    with patch.dict(os.environ, {"ARCHIVIST_LOG_PATH": str(missing)}):
        c = TestClient(create_app(
            LoopState(), missing,
            discs_root=music_root / "inbox",
            review_root=music_root / "review",
            library_root=music_root / "library",
            music_root=music_root,
        ))
        resp = c.get("/api/logs/tail")
        assert resp.status_code == 404


# ============== (d) limit= query param honored ==========================


def test_limit_query_param_honored(client: TestClient) -> None:
    body = client.get("/api/logs/tail?limit=10").json()
    assert len(body["lines"]) == 10
    assert body["lines"][-1].rstrip() == "line 500"


def test_limit_clamped_to_max_2000(client: TestClient) -> None:
    """Spec: max N=2000. Above-max requests clamp to 2000 (or 422 —
    the test accepts either behavior; impl chooses)."""
    resp = client.get("/api/logs/tail?limit=9999")
    if resp.status_code == 200:
        assert len(resp.json()["lines"]) <= 2000
    else:
        assert resp.status_code in (400, 422)


# ============== (e) future filter params accept-and-ignore ==============


def test_future_filter_params_accepted_and_ignored(
    client: TestClient,
) -> None:
    """sprint-7 will add per-rip / per-card filter query params; the
    endpoint must accept them today without erroring so sprint-7
    can wire the UI side without a server bump."""
    resp = client.get(
        "/api/logs/tail?limit=50&rip_id=abc&card_id=2026-05-16_1200_disc-x",
    )
    assert resp.status_code == 200
    assert len(resp.json()["lines"]) == 50
