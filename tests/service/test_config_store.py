"""Sprint-11 / setup-config-store — config store tests.

Covers:
  (a) FILE > ENV > DEFAULT precedence
  (b) Atomic write — no stale `.tmp` file remains after save
  (c) File mode 0600 on the saved file
  (d) save_config rejects unknown keys (UnknownConfigKey, no disk write)
  (e) reload_config clears the cache so next get_config re-reads disk
  (+) Sparse updates preserve untouched keys
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from archivist.service import config as config_module
from archivist.service.config import (
    CONFIG_KEYS,
    Config,
    UnknownConfigKey,
    get_config,
    reload_config,
    save_config,
)


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Each test gets a fresh config path + a clean env + a cold cache."""
    config_path = tmp_path / "cd-archivist" / "config.json"
    monkeypatch.setenv("ARCHIVIST_CONFIG_PATH", str(config_path))
    # Strip every env var the config knows about so we control the env tier.
    for env_var in (
        "SPOOTY_API_URL", "SPOOTY_API_TOKEN",
        "NAVIDROME_URL", "NAVIDROME_USER", "NAVIDROME_PASS",
        "MUSIC_INBOX_DIR", "MUSIC_LIBRARY_DIR", "MUSIC_ARCHIVE_DIR",
        "MUSIC_SPOOTY_DIR", "MUSIC_REVIEW_DIR",
    ):
        monkeypatch.delenv(env_var, raising=False)
    reload_config()
    yield config_path
    reload_config()


# ---------- (a) FILE > ENV > DEFAULT precedence -----------------------------

def test_default_when_neither_file_nor_env() -> None:
    cfg = get_config()
    # Music dirs ship with sensible defaults.
    assert cfg.music_inbox_dir == "/srv/music/inbox"
    assert cfg.music_archive_dir == "/mnt/archive"
    # str | None fields are None when nothing is configured.
    assert cfg.navidrome_url is None
    assert cfg.navidrome_pass is None
    assert cfg.spooty_api_url is None


def test_env_overrides_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NAVIDROME_URL", "https://from-env.example")
    monkeypatch.setenv("MUSIC_INBOX_DIR", "/from-env/inbox")
    reload_config()
    cfg = get_config()
    assert cfg.navidrome_url == "https://from-env.example"
    assert cfg.music_inbox_dir == "/from-env/inbox"


def test_file_overrides_env(
    _isolated_config: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NAVIDROME_URL", "https://from-env.example")
    _isolated_config.parent.mkdir(parents=True, exist_ok=True)
    _isolated_config.write_text(json.dumps({
        "navidrome_url": "https://from-file.example",
    }))
    reload_config()
    cfg = get_config()
    assert cfg.navidrome_url == "https://from-file.example"


def test_file_with_null_falls_through_to_env(
    _isolated_config: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A null value in the file means 'not set' — env should win,
    not file's null. This is what makes systemd vars work as
    bootstrap fallbacks for keys the operator never touched."""
    monkeypatch.setenv("NAVIDROME_URL", "https://from-env.example")
    _isolated_config.parent.mkdir(parents=True, exist_ok=True)
    _isolated_config.write_text(json.dumps({"navidrome_url": None}))
    reload_config()
    cfg = get_config()
    assert cfg.navidrome_url == "https://from-env.example"


def test_empty_env_value_treated_as_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NAVIDROME_URL", "")
    reload_config()
    cfg = get_config()
    assert cfg.navidrome_url is None


# ---------- (b) Atomic write ------------------------------------------------

def test_save_leaves_no_tmp_file_behind(_isolated_config: Path) -> None:
    save_config({"navidrome_url": "https://saved.example"})
    tmp_path = _isolated_config.with_suffix(_isolated_config.suffix + ".tmp")
    assert _isolated_config.is_file()
    assert not tmp_path.exists()


def test_save_uses_os_replace_not_inplace_write(
    _isolated_config: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the write goes through `os.replace(tmp, real)` — the
    seam that makes concurrent reads see whole-old or whole-new,
    never half-written."""
    calls: list[tuple[str, str]] = []
    real_replace = os.replace

    def _spy(src, dst):
        calls.append((str(src), str(dst)))
        real_replace(src, dst)

    monkeypatch.setattr(config_module.os, "replace", _spy)
    save_config({"navidrome_url": "https://atomic.example"})
    assert len(calls) == 1
    src, dst = calls[0]
    assert src.endswith(".tmp")
    assert dst == str(_isolated_config)


def test_save_failure_cleans_up_tmp_file(
    _isolated_config: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the write fails mid-flight, the `.tmp` file is removed so a
    later read doesn't pick up a half-written carcass."""
    def _boom(*a, **kw):
        raise RuntimeError("disk full")

    # Force the write to fail after the tmp file exists.
    monkeypatch.setattr(config_module.json, "dump", _boom)
    with pytest.raises(RuntimeError):
        save_config({"navidrome_url": "https://x"})
    tmp_path = _isolated_config.with_suffix(_isolated_config.suffix + ".tmp")
    assert not tmp_path.exists()


# ---------- (c) File mode 0600 ----------------------------------------------

def test_saved_file_is_mode_0600(_isolated_config: Path) -> None:
    save_config({"navidrome_pass": "hunter2"})
    mode = stat.S_IMODE(os.stat(_isolated_config).st_mode)
    assert mode == 0o600, f"expected 0o600, got {oct(mode)}"


# ---------- (d) Unknown-key rejection ---------------------------------------

def test_save_rejects_unknown_key(_isolated_config: Path) -> None:
    with pytest.raises(UnknownConfigKey) as exc:
        save_config({"bogus_field": "x"})
    assert "bogus_field" in str(exc.value)
    # No file written on rejection.
    assert not _isolated_config.exists()


def test_save_rejects_partly_unknown_payload(_isolated_config: Path) -> None:
    """Even one bad key in a multi-key update rejects the whole
    request — atomic semantics extend to validation."""
    with pytest.raises(UnknownConfigKey):
        save_config({
            "navidrome_url": "https://ok.example",
            "made_up_key": "nope",
        })
    assert not _isolated_config.exists()


# ---------- (e) reload_config clears cache ----------------------------------

def test_reload_clears_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg1 = get_config()
    assert cfg1.navidrome_url is None
    monkeypatch.setenv("NAVIDROME_URL", "https://now-set.example")
    # Without reload the cache returns the stale value.
    assert get_config().navidrome_url is None
    reload_config()
    assert get_config().navidrome_url == "https://now-set.example"


def test_save_auto_reloads_cache(_isolated_config: Path) -> None:
    # Prime the cache.
    assert get_config().navidrome_url is None
    save_config({"navidrome_url": "https://post-save.example"})
    # No manual reload_config() call — save did it for us.
    assert get_config().navidrome_url == "https://post-save.example"


# ---------- (+) Sparse updates preserve other keys --------------------------

def test_sparse_update_preserves_existing_keys(_isolated_config: Path) -> None:
    save_config({
        "navidrome_url": "https://nav.example",
        "navidrome_user": "operator",
        "navidrome_pass": "hunter2",
    })
    # Now update just the URL.
    save_config({"navidrome_url": "https://nav2.example"})
    cfg = get_config()
    assert cfg.navidrome_url == "https://nav2.example"
    assert cfg.navidrome_user == "operator"
    assert cfg.navidrome_pass == "hunter2"


def test_config_keys_matches_dataclass_fields() -> None:
    from dataclasses import fields as _f
    assert CONFIG_KEYS == {f.name for f in _f(Config)}
