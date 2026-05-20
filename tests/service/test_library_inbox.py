"""Sprint-10 / inbox-impl — Inbox panel tests.

Covers:
  - `inbox_client.list_inbox_folders` against a tmp_path inbox tree
    (cd_rip + spooty subdirs, READY markers, byte/count rollups).
  - `inbox_client.import_now` happy + error paths (folder missing,
    importer binary missing) via subprocess monkeypatch.
  - `/api/library/inbox` endpoint shape.
  - `/api/library/inbox/import-now` happy + error responses.
  - `library_inbox_panel.render` HTML structure (row count, source
    tag, READY pip, import-now button, poll meta tags).
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from archivist.service.app import LoopState, create_app
from archivist.service.clients.inbox_client import (
    InboxFolder,
    InboxUnavailable,
    import_now,
    list_inbox_folders,
)
from archivist.service.library_inbox_panel import POLL_ENDPOINT, POLL_MS, render
from archivist.service.library_panel_inventory import BY_ID


# ---- fixtures ----------------------------------------------------------------


@pytest.fixture
def inbox_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a representative inbox tree:

        inbox/
          album_a/                <- cd_rip, READY present
            track1.flac
            track2.flac
            READY
          album_b/                <- cd_rip, no READY
            track1.flac
          spooty/
            playlist_x/           <- spooty
              song1.mp3
              song2.mp3
              song3.mp3
    """
    root = tmp_path / "inbox"
    root.mkdir()

    a = root / "album_a"
    a.mkdir()
    (a / "track1.flac").write_bytes(b"x" * 1000)
    (a / "track2.flac").write_bytes(b"y" * 2000)
    (a / "READY").write_text("")

    b = root / "album_b"
    b.mkdir()
    (b / "track1.flac").write_bytes(b"z" * 500)

    spooty = root / "spooty"
    spooty.mkdir()
    px = spooty / "playlist_x"
    px.mkdir()
    (px / "song1.mp3").write_bytes(b"a" * 100)
    (px / "song2.mp3").write_bytes(b"b" * 200)
    (px / "song3.mp3").write_bytes(b"c" * 300)

    monkeypatch.setenv("MUSIC_INBOX_DIR", str(root))
    return root


@pytest.fixture
def loop_state() -> LoopState:
    return LoopState(
        state="IDLE",
        disc_id=None,
        last_rip_status=None,
        state_entered_at=datetime(2026, 5, 19, 12, 0, 0),
        last_tick_at=datetime(2026, 5, 19, 12, 0, 0),
    )


@pytest.fixture
def client(loop_state: LoopState, inbox_root: Path, tmp_path: Path) -> TestClient:
    music_root = tmp_path / "music"
    music_root.mkdir()
    review = tmp_path / "review"
    review.mkdir()
    app = create_app(
        loop_state=loop_state,
        log_path=tmp_path / "pipeline.log",
        music_root=music_root,
        review_root=review,
        discs_root=music_root,
    )
    return TestClient(app)


# ---- inbox_client.list_inbox_folders -----------------------------------------


def test_list_inbox_folders_enumerates_cd_rip_and_spooty(inbox_root: Path) -> None:
    folders = list_inbox_folders()
    by_name = {f.name: f for f in folders}
    assert set(by_name) == {"album_a", "album_b", "playlist_x"}
    assert by_name["album_a"].source == "cd_rip"
    assert by_name["album_b"].source == "cd_rip"
    assert by_name["playlist_x"].source == "spooty"


def test_list_inbox_folders_excludes_spooty_dir_itself(inbox_root: Path) -> None:
    folders = list_inbox_folders()
    assert all(f.name != "spooty" for f in folders)


def test_list_inbox_folders_counts_files_and_size(inbox_root: Path) -> None:
    folders = {f.name: f for f in list_inbox_folders()}
    # album_a: 2 audio files + READY marker = 3 files; 3000 + (empty READY) bytes
    assert folders["album_a"].file_count == 3
    assert folders["album_a"].size_bytes == 3000  # READY is empty
    assert folders["album_b"].file_count == 1
    assert folders["album_b"].size_bytes == 500
    assert folders["playlist_x"].file_count == 3
    assert folders["playlist_x"].size_bytes == 600


def test_list_inbox_folders_detects_ready_marker(inbox_root: Path) -> None:
    folders = {f.name: f for f in list_inbox_folders()}
    assert folders["album_a"].ready_marker_present is True
    assert folders["album_b"].ready_marker_present is False
    assert folders["playlist_x"].ready_marker_present is False


def test_list_inbox_folders_last_modified_is_iso(inbox_root: Path) -> None:
    for f in list_inbox_folders():
        # Round-trips through fromisoformat — that's the contract.
        datetime.fromisoformat(f.last_modified)


def test_list_inbox_folders_sorts_newest_first(inbox_root: Path) -> None:
    # Bump album_b mtime so it should rank newest.
    target = inbox_root / "album_b" / "track1.flac"
    old = target.stat().st_mtime
    os.utime(target, (old + 10000, old + 10000))
    folders = list_inbox_folders()
    assert folders[0].name == "album_b"


def test_list_inbox_folders_raises_when_root_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MUSIC_INBOX_DIR", str(tmp_path / "nope"))
    with pytest.raises(InboxUnavailable):
        list_inbox_folders()


def test_list_inbox_folders_handles_empty_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "empty_inbox"
    root.mkdir()
    monkeypatch.setenv("MUSIC_INBOX_DIR", str(root))
    assert list_inbox_folders() == []


def test_list_inbox_folders_handles_missing_spooty_subdir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spooty subdir is optional — its absence shouldn't break enumeration."""
    root = tmp_path / "no_spooty_inbox"
    root.mkdir()
    a = root / "album"
    a.mkdir()
    (a / "t.flac").write_bytes(b"x")
    monkeypatch.setenv("MUSIC_INBOX_DIR", str(root))
    folders = list_inbox_folders()
    assert len(folders) == 1
    assert folders[0].source == "cd_rip"


def test_inbox_folder_to_dict_is_json_safe(inbox_root: Path) -> None:
    import json
    f = list_inbox_folders()[0]
    json.dumps(f.to_dict())  # must not raise


# ---- inbox_client.import_now -------------------------------------------------


def test_import_now_returns_failed_when_folder_unknown(inbox_root: Path) -> None:
    result = import_now("does_not_exist")
    assert result["status"] == "failed"
    assert "not found" in result["message"]


def test_import_now_returns_failed_when_inbox_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MUSIC_INBOX_DIR", str(tmp_path / "nope"))
    result = import_now("anything")
    assert result["status"] == "failed"
    assert "inbox unavailable" in result["message"]


def test_import_now_spawns_correct_binary_for_cd_rip(
    inbox_root: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[list[str]] = []

    class _DummyPopen:
        def __init__(self, argv, **kwargs):
            captured.append(list(argv))

    monkeypatch.setattr(
        "archivist.service.clients.inbox_client.subprocess.Popen", _DummyPopen,
    )
    monkeypatch.setenv("CDA_PROCESS_READY_BIN", "/usr/local/bin/process-ready-auto")

    result = import_now("album_a")
    assert result["status"] == "started"
    assert captured, "Popen was not invoked"
    assert captured[0][0] == "/usr/local/bin/process-ready-auto"
    # Folder path (absolute) is passed as the trailing argument.
    assert captured[0][1].endswith("album_a")


def test_import_now_spawns_correct_binary_for_spooty(
    inbox_root: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[list[str]] = []

    class _DummyPopen:
        def __init__(self, argv, **kwargs):
            captured.append(list(argv))

    monkeypatch.setattr(
        "archivist.service.clients.inbox_client.subprocess.Popen", _DummyPopen,
    )
    monkeypatch.setenv("CDA_SPOOTY_IMPORT_BIN", "/usr/local/bin/spooty-import.sh")

    result = import_now("playlist_x")
    assert result["status"] == "started"
    assert captured[0][0] == "/usr/local/bin/spooty-import.sh"
    assert captured[0][1].endswith("playlist_x")


def test_import_now_handles_filenotfound(
    inbox_root: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(*args, **kwargs):
        raise FileNotFoundError("no such binary")

    monkeypatch.setattr(
        "archivist.service.clients.inbox_client.subprocess.Popen", _raise,
    )
    result = import_now("album_a")
    assert result["status"] == "failed"
    assert "not found" in result["message"]


# ---- /api/library/inbox -------------------------------------------------------


def test_api_library_inbox_returns_folders(
    client: TestClient, inbox_root: Path,
) -> None:
    resp = client.get("/api/library/inbox")
    assert resp.status_code == 200
    body = resp.json()
    assert "folders" in body
    names = {f["name"] for f in body["folders"]}
    assert names == {"album_a", "album_b", "playlist_x"}


def test_api_library_inbox_folder_shape(
    client: TestClient, inbox_root: Path,
) -> None:
    resp = client.get("/api/library/inbox")
    folder = resp.json()["folders"][0]
    for key in (
        "name", "path", "source", "file_count", "size_bytes",
        "last_modified", "ready_marker_present",
    ):
        assert key in folder, f"missing key: {key}"


def test_api_library_inbox_503_when_root_missing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("MUSIC_INBOX_DIR", str(tmp_path / "nope"))
    resp = client.get("/api/library/inbox")
    assert resp.status_code == 503
    body = resp.json()
    assert body["folders"] == []
    assert "error" in body


# ---- /api/library/inbox/import-now -------------------------------------------


def test_api_import_now_happy_path(
    client: TestClient, inbox_root: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _DummyPopen:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr(
        "archivist.service.clients.inbox_client.subprocess.Popen", _DummyPopen,
    )
    resp = client.post(
        "/api/library/inbox/import-now", json={"folder": "album_a"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "started"


def test_api_import_now_unknown_folder_returns_409(
    client: TestClient, inbox_root: Path,
) -> None:
    resp = client.post(
        "/api/library/inbox/import-now", json={"folder": "no_such_folder"},
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body["status"] == "failed"


def test_api_import_now_missing_folder_field_returns_400(
    client: TestClient, inbox_root: Path,
) -> None:
    resp = client.post("/api/library/inbox/import-now", json={})
    assert resp.status_code == 400


def test_api_import_now_invalid_json_returns_400(
    client: TestClient, inbox_root: Path,
) -> None:
    resp = client.post(
        "/api/library/inbox/import-now",
        content=b"not json",
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 400


# ---- library_inbox_panel.render ----------------------------------------------


def test_render_includes_poll_meta_tags(inbox_root: Path) -> None:
    html_out = render(BY_ID["inbox"])
    assert f'<meta name="library-poll-ms" content="{POLL_MS}">' in html_out
    assert (
        f'<meta name="library-poll-endpoint" content="{POLL_ENDPOINT}">'
        in html_out
    )


def test_render_emits_one_row_per_folder(inbox_root: Path) -> None:
    html_out = render(BY_ID["inbox"])
    # Three folders → three rows.
    assert html_out.count('class="cda-inbox-row"') == 3


def test_render_emits_source_tags(inbox_root: Path) -> None:
    html_out = render(BY_ID["inbox"])
    assert "tag--cd_rip" in html_out
    assert "tag--spooty" in html_out


def test_render_emits_ready_pip_for_ready_folder(inbox_root: Path) -> None:
    html_out = render(BY_ID["inbox"])
    assert "pip--ready" in html_out
    assert "pip--pending" in html_out


def test_render_emits_import_now_button_per_row(inbox_root: Path) -> None:
    html_out = render(BY_ID["inbox"])
    assert html_out.count("cda-inbox-import") == 3
    # Each button carries its folder name as a data attribute.
    assert 'data-folder="album_a"' in html_out
    assert 'data-folder="playlist_x"' in html_out


def test_render_panel_title_and_eyebrow_from_spec(inbox_root: Path) -> None:
    spec = BY_ID["inbox"]
    html_out = render(spec)
    assert spec["title"] in html_out
    assert spec["eyebrow"] in html_out


def test_render_degrades_when_inbox_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MUSIC_INBOX_DIR", str(tmp_path / "nope"))
    html_out = render(BY_ID["inbox"])
    # Still emits the panel shell + poll meta tags.
    assert "library-poll-ms" in html_out
    assert "inbox unavailable" in html_out


def test_render_empty_state_when_no_folders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty = tmp_path / "empty_inbox"
    empty.mkdir()
    monkeypatch.setenv("MUSIC_INBOX_DIR", str(empty))
    html_out = render(BY_ID["inbox"])
    assert "no pending folders" in html_out


def test_render_pluggable_into_library_panels_dispatcher(inbox_root: Path) -> None:
    """The dispatcher in library_panels.render_panel should now resolve
    `inbox` to our render() instead of the placeholder."""
    from archivist.service.library_panels import render_panel
    html_out = render_panel("inbox")
    assert "cda-inbox-row" in html_out
