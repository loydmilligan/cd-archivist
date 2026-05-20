"""Sprint-10 / disk-impl — Disk panel tests.

Covers:
  - disk_client snapshot shape (mocked shutil + tmp_path surfaces)
  - threshold_class boundaries
  - format_bytes formatting
  - /api/library/disk endpoint shape
  - Disk panel render: three rows, threshold classes, drilldown table
  - Disk panel meta tags wire it to chassis_js polling
  - render_panel("disk") dispatches to the Disk panel module (not placeholder)
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from archivist.service.app import LoopState, create_app
from archivist.service.clients import disk_client
from archivist.service.clients.disk_client import (
    DiskUsageSnapshot,
    MountUsage,
    _resolve_surface_paths,
    format_bytes,
    get_disk_usage,
    threshold_class,
)
from archivist.service.config import reload_config, save_config
from archivist.service.library_panels import render_panel


# Env vars the config store consults. We scrub them in every test so a
# host-level export doesn't leak in and override the expected default.
_CONFIG_ENV_VARS = (
    "SPOOTY_API_URL", "SPOOTY_API_TOKEN",
    "NAVIDROME_URL", "NAVIDROME_USER", "NAVIDROME_PASS",
    "MUSIC_INBOX_DIR", "MUSIC_LIBRARY_DIR", "MUSIC_ARCHIVE_DIR",
    "MUSIC_SPOOTY_DIR", "MUSIC_REVIEW_DIR",
)


@pytest.fixture(autouse=True)
def _isolated_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """Sprint-11 / config-runtime-wiring: disk_client reads
    music_*_dir via `get_config()`. Tests that don't pass an explicit
    `surfaces=` kwarg get a clean config store per test."""
    monkeypatch.setenv(
        "ARCHIVIST_CONFIG_PATH", str(tmp_path / "_test_config.json"),
    )
    for var in _CONFIG_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    reload_config()
    yield
    reload_config()


# ---------- threshold_class --------------------------------------------------

@pytest.mark.parametrize("pct,expected", [
    (0.0, "is-pulp"),
    (12.5, "is-pulp"),
    (59.99, "is-pulp"),
    (60.0, "is-amber"),
    (75.0, "is-amber"),
    (85.0, "is-amber"),
    (85.01, "is-ember"),
    (92.0, "is-ember"),
    (100.0, "is-ember"),
])
def test_threshold_class_boundaries(pct: float, expected: str) -> None:
    assert threshold_class(pct) == expected


# ---------- format_bytes -----------------------------------------------------

@pytest.mark.parametrize("n,expected", [
    (0, "0 B"),
    (512, "512 B"),
    (2048, "2.0 KB"),
    (1024 * 1024, "1.0 MB"),
    (5 * 1024 * 1024 * 1024, "5.0 GB"),
    (200 * 1024 * 1024 * 1024, "200 GB"),
])
def test_format_bytes(n: int, expected: str) -> None:
    assert format_bytes(n) == expected


# ---------- disk_client.get_disk_usage --------------------------------------

class _FakeDiskUsage:
    def __init__(self, total: int, used: int, free: int) -> None:
        self.total = total
        self.used = used
        self.free = free


@pytest.fixture
def fake_filesystem(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Build a fake mount + surface layout under tmp_path:

        tmp_path/root/                       (mount: /)
        tmp_path/seagate/                    (mount: /mnt/seagate)
            library/  (3 KB files inside)
        tmp_path/archive/                    (mount: /mnt/archive)
            (archive surface itself)
        tmp_path/root/srv/music/inbox/       (inbox surface; 1 KB)
            spooty/                          (spooty surface; 2 KB)

    Returns the resolved mount + surface map and monkeypatches
    `shutil.disk_usage` so it returns deterministic numbers per mount.
    """
    root = tmp_path / "root"
    seagate = tmp_path / "seagate"
    archive = tmp_path / "archive"
    root.mkdir()
    seagate.mkdir()
    archive.mkdir()

    inbox = root / "srv" / "music" / "inbox"
    inbox.mkdir(parents=True)
    (inbox / "album.flac").write_bytes(b"a" * 1024)  # 1 KB

    spooty = inbox / "spooty"
    spooty.mkdir()
    (spooty / "track.mp3").write_bytes(b"b" * 2048)  # 2 KB

    library = seagate / "library"
    library.mkdir()
    (library / "song1.flac").write_bytes(b"c" * 1024)
    (library / "song2.flac").write_bytes(b"d" * 2048)  # total 3 KB

    # No files in archive surface.
    (archive / ".keep").write_bytes(b"")

    mounts = (str(root), str(seagate), str(archive))
    surfaces = {
        "inbox":   inbox,
        "library": library,
        "archive": archive,
        "spooty":  spooty,
    }

    fake_usage_by_mount = {
        str(root):    _FakeDiskUsage(total=100, used=10, free=90),       # 10 %
        str(seagate): _FakeDiskUsage(total=1000, used=700, free=300),    # 70 %
        str(archive): _FakeDiskUsage(total=2000, used=1800, free=200),   # 90 %
    }

    def _fake_disk_usage(path):
        key = str(path)
        if key not in fake_usage_by_mount:
            raise OSError(f"unknown mount in fake: {key}")
        return fake_usage_by_mount[key]

    monkeypatch.setattr(disk_client.shutil, "disk_usage", _fake_disk_usage)

    return {"mounts": mounts, "surfaces": surfaces}


def test_get_disk_usage_snapshot_shape(fake_filesystem: dict) -> None:
    snap = get_disk_usage(mounts=fake_filesystem["mounts"], surfaces=fake_filesystem["surfaces"])
    assert isinstance(snap, DiskUsageSnapshot)
    assert len(snap.mounts) == 3

    by_path = {m.mount_path: m for m in snap.mounts}
    root_mount = by_path[fake_filesystem["mounts"][0]]
    seagate_mount = by_path[fake_filesystem["mounts"][1]]
    archive_mount = by_path[fake_filesystem["mounts"][2]]

    # mount usage
    assert root_mount.mounted is True
    assert root_mount.pct_used == 10.0
    assert seagate_mount.pct_used == 70.0
    assert archive_mount.pct_used == 90.0

    # surface attribution — inbox + spooty land on root mount because
    # they live under tmp_path/root/srv/music/inbox{,/spooty}.
    assert root_mount.surfaces["inbox"] == 1024
    assert root_mount.surfaces["spooty"] == 2048
    # library surface lives under seagate
    assert seagate_mount.surfaces["library"] == 3 * 1024
    # archive surface = the archive mount itself
    assert archive_mount.surfaces["archive"] == 0  # only an empty .keep
    # surfaces dict always has all four keys
    for m in snap.mounts:
        assert set(m.surfaces.keys()) == {"inbox", "library", "archive", "spooty"}


def test_get_disk_usage_handles_missing_mount(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mount that doesn't exist on this host renders gracefully as
    `mounted=False` with zero counts."""
    real = tmp_path / "real"
    real.mkdir()
    missing = tmp_path / "does-not-exist"

    monkeypatch.setattr(
        disk_client.shutil, "disk_usage",
        lambda p: _FakeDiskUsage(total=100, used=50, free=50),
    )

    snap = get_disk_usage(
        mounts=(str(real), str(missing)),
        surfaces={"inbox": real, "library": real, "archive": real, "spooty": real},
    )
    by_path = {m.mount_path: m for m in snap.mounts}
    assert by_path[str(real)].mounted is True
    assert by_path[str(missing)].mounted is False
    assert by_path[str(missing)].total_bytes == 0
    assert by_path[str(missing)].pct_used == 0.0


# ---------- config-store wiring ---------------------------------------------

def test_resolve_surface_paths_reads_from_config_store(tmp_path: Path) -> None:
    """Sprint-11 / config-runtime-wiring: when no explicit surfaces
    are passed, disk_client resolves them via `get_config()` instead
    of `os.environ`."""
    inbox = tmp_path / "inbox"
    library = tmp_path / "library"
    archive = tmp_path / "archive"
    spooty = tmp_path / "spooty"
    for p in (inbox, library, archive, spooty):
        p.mkdir()
    save_config({
        "music_inbox_dir":   str(inbox),
        "music_library_dir": str(library),
        "music_archive_dir": str(archive),
        "music_spooty_dir":  str(spooty),
    })
    resolved = _resolve_surface_paths()
    assert resolved["inbox"]   == inbox
    assert resolved["library"] == library
    assert resolved["archive"] == archive
    assert resolved["spooty"]  == spooty


# ---------- /api/library/disk endpoint --------------------------------------

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


def test_api_library_disk_endpoint_shape(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_snap = DiskUsageSnapshot(mounts=[
        MountUsage(
            mount_path="/", mounted=True,
            total_bytes=200, used_bytes=80, available_bytes=120, pct_used=40.0,
            surfaces={"inbox": 10, "library": 0, "archive": 0, "spooty": 5},
        ),
        MountUsage(
            mount_path="/mnt/seagate", mounted=False,
            total_bytes=0, used_bytes=0, available_bytes=0, pct_used=0.0,
            surfaces={"inbox": 0, "library": 0, "archive": 0, "spooty": 0},
        ),
    ])
    monkeypatch.setattr(
        "archivist.service.clients.disk_client.get_disk_usage",
        lambda: fake_snap,
    )

    res = client.get("/api/library/disk")
    assert res.status_code == 200
    body = res.json()
    assert "mounts" in body and len(body["mounts"]) == 2
    m0 = body["mounts"][0]
    assert m0["mount_path"] == "/"
    assert m0["mounted"] is True
    assert m0["pct_used"] == 40.0
    assert m0["surfaces"] == {"inbox": 10, "library": 0, "archive": 0, "spooty": 5}
    assert body["mounts"][1]["mounted"] is False


# ---------- panel render -----------------------------------------------------

@pytest.fixture
def stub_snapshot(monkeypatch: pytest.MonkeyPatch) -> DiskUsageSnapshot:
    """Force the panel renderer to see a known snapshot — one mount per
    threshold band so the assertions cover all three."""
    snap = DiskUsageSnapshot(mounts=[
        MountUsage(
            mount_path="/", mounted=True,
            total_bytes=1024**3, used_bytes=int(1024**3 * 0.10),
            available_bytes=int(1024**3 * 0.90), pct_used=10.0,
            surfaces={"inbox": 1024, "library": 0, "archive": 0, "spooty": 512},
        ),
        MountUsage(
            mount_path="/mnt/seagate", mounted=True,
            total_bytes=1024**4, used_bytes=int(1024**4 * 0.72),
            available_bytes=int(1024**4 * 0.28), pct_used=72.0,
            surfaces={"inbox": 0, "library": 5 * 1024**3, "archive": 0, "spooty": 0},
        ),
        MountUsage(
            mount_path="/mnt/archive", mounted=False,
            total_bytes=0, used_bytes=0, available_bytes=0, pct_used=0.0,
            surfaces={"inbox": 0, "library": 0, "archive": 0, "spooty": 0},
        ),
    ])
    monkeypatch.setattr(
        "archivist.service.library_disk_panel.get_disk_usage", lambda: snap,
    )
    return snap


def test_panel_renders_three_rows(stub_snapshot) -> None:
    html = render_panel("disk")
    rows = re.findall(r'class="cda-lib-disk-row (?:is-[a-z]+)"', html)
    assert len(rows) == 3


def test_panel_threshold_classes_applied(stub_snapshot) -> None:
    html = render_panel("disk")
    # 10% mount → is-pulp
    assert "cda-lib-disk-row is-pulp" in html
    # 72% mount → is-amber
    assert "cda-lib-disk-row is-amber" in html
    # unmounted → is-unmounted (no threshold class)
    assert "cda-lib-disk-row is-unmounted" in html


def test_panel_renders_drilldown_table_with_surface_columns(stub_snapshot) -> None:
    html = render_panel("disk")
    assert 'class="cda-lib-disk-drilldown"' in html
    # all four surface column headers
    for col in ("inbox", "library", "archive", "spooty"):
        assert f"<th>{col}</th>" in html
    # one row per mount in tbody
    rows_in_tbody = re.findall(
        r'<tr><th scope="row">(/mnt/[^<]*|/)</th>', html,
    )
    assert rows_in_tbody == ["/", "/mnt/seagate", "/mnt/archive"]


def test_panel_unmounted_row_shows_not_mounted(stub_snapshot) -> None:
    html = render_panel("disk")
    assert "not mounted" in html


def test_panel_emits_polling_meta_tags(stub_snapshot) -> None:
    html = render_panel("disk")
    assert '<meta name="library-poll-ms" content="30000">' in html
    assert '<meta name="library-poll-endpoint" content="/api/library/disk">' in html


def test_panel_renders_eyebrow_and_title(stub_snapshot) -> None:
    html = render_panel("disk")
    assert '<span class="eyebrow">Disk usage</span>' in html
    assert "<h1>Where the bytes live</h1>" in html


def test_dispatcher_no_longer_uses_placeholder_for_disk(stub_snapshot) -> None:
    """Sanity: the placeholder's `in design` tag must not appear when
    the Disk panel module is present."""
    html = render_panel("disk")
    assert '<span class="tag">in design</span>' not in html
