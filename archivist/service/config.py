"""Config store — read/write JSON config for the Library Manager.

Sprint-11 / setup-config-store. The four service-clients (and the
Settings page) read URLs / creds / dirs through this module instead
of hitting `os.environ` directly. The Settings page (`/settings`)
writes through `save_config`.

Precedence per D-config-precedence (FILE > ENV > DEFAULT):

  1. JSON file at `$ARCHIVIST_CONFIG_PATH` (default
     `~/.config/cd-archivist/config.json`). If the key is present
     and non-null in the file, that value wins.
  2. Environment variable (the matching `SPOOTY_*` / `NAVIDROME_*`
     / `MUSIC_*` name) if set and non-empty.
  3. Built-in default baked into the `Config` dataclass.

Rationale: the whole point of the Settings page is editing without
ssh; if env vars won, web edits would be silently masked by systemd's
`Environment=` lines. systemd vars therefore become *bootstrap-only*
— once the operator saves a key via the web, the file is the source
of truth for that key. Keys never touched via the web continue to
take their value from env / default, so existing systemd / `.env`
deployments keep working.

Write semantics for `save_config`:

  - Atomic write via `os.replace(tmp_path, real_path)` so a concurrent
    reader never observes a partial file.
  - File mode 0600 (rw owner only) so a public-tunnel reader can't
    `cat` the file off disk if they get shell.
  - Unknown keys raise `UnknownConfigKey` *before* any disk write so
    a typo can't bork the on-disk config.
  - Auto-calls `reload_config()` on success — the next `get_config()`
    sees the saved value without the caller having to remember.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any


# --------------------------------------------------------------------- defaults

# Music-dir defaults match the sprint-10 client defaults so existing
# `disk_client.get_disk_usage()` behavior is preserved when nothing is
# configured.
_DEFAULT_INBOX_DIR = "/srv/music/inbox"
_DEFAULT_LIBRARY_DIR = "/srv/music/library"
_DEFAULT_ARCHIVE_DIR = "/mnt/archive"
_DEFAULT_SPOOTY_DIR = "/srv/music/inbox/spooty"
_DEFAULT_REVIEW_DIR = "/srv/music/review"


@dataclass(frozen=True)
class Config:
    """All ten knobs the Library Manager + Settings page operate on.

    `str | None` fields are unset by default (None = "not
    configured"; client decides how to degrade). Music-dir fields are
    always populated with a sensible default so the disk/inbox panels
    can render without per-call None checks.
    """

    spooty_api_url: str | None = None
    spooty_api_token: str | None = None
    navidrome_url: str | None = None
    navidrome_user: str | None = None
    navidrome_pass: str | None = None
    music_inbox_dir: str = _DEFAULT_INBOX_DIR
    music_library_dir: str = _DEFAULT_LIBRARY_DIR
    music_archive_dir: str = _DEFAULT_ARCHIVE_DIR
    music_spooty_dir: str = _DEFAULT_SPOOTY_DIR
    music_review_dir: str = _DEFAULT_REVIEW_DIR


# Field name → matching env var (the precedence-tier-2 fallback).
_FIELD_ENV: dict[str, str] = {
    "spooty_api_url":     "SPOOTY_API_URL",
    "spooty_api_token":   "SPOOTY_API_TOKEN",
    "navidrome_url":      "NAVIDROME_URL",
    "navidrome_user":     "NAVIDROME_USER",
    "navidrome_pass":     "NAVIDROME_PASS",
    "music_inbox_dir":    "MUSIC_INBOX_DIR",
    "music_library_dir": "MUSIC_LIBRARY_DIR",
    "music_archive_dir": "MUSIC_ARCHIVE_DIR",
    "music_spooty_dir":   "MUSIC_SPOOTY_DIR",
    "music_review_dir":   "MUSIC_REVIEW_DIR",
}

# Fields whose values are secret (mask in API responses, never log).
SECRET_FIELDS: frozenset[str] = frozenset({"spooty_api_token", "navidrome_pass"})

# Public set of valid config keys — used by `save_config` to reject typos.
CONFIG_KEYS: frozenset[str] = frozenset(_FIELD_ENV.keys())


class UnknownConfigKey(ValueError):
    """`save_config` was passed a key that is not a field on Config."""


# --------------------------------------------------------------------- internals

_cache_lock = threading.Lock()
_cached: Config | None = None


def _config_path() -> Path:
    """Resolved path to the on-disk config file. Read at call time so
    tests can monkeypatch `$ARCHIVIST_CONFIG_PATH` without re-importing."""
    raw = os.environ.get("ARCHIVIST_CONFIG_PATH")
    if raw:
        return Path(raw)
    return Path.home() / ".config" / "cd-archivist" / "config.json"


def _read_file_data(path: Path) -> dict[str, Any]:
    """Read the JSON file. Returns `{}` if missing or unreadable —
    never raises (the env / default tiers will still cover us)."""
    if not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _resolve_value(field_name: str, file_data: dict[str, Any], default: Any) -> Any:
    """Apply FILE > ENV > DEFAULT precedence for one field."""
    if field_name in file_data and file_data[field_name] is not None:
        return file_data[field_name]
    env_var = _FIELD_ENV.get(field_name)
    if env_var:
        env_val = os.environ.get(env_var)
        if env_val:
            return env_val
    return default


def _compute_config() -> Config:
    path = _config_path()
    file_data = _read_file_data(path)
    kwargs: dict[str, Any] = {}
    for f in fields(Config):
        kwargs[f.name] = _resolve_value(f.name, file_data, f.default)
    return Config(**kwargs)


# --------------------------------------------------------------------- public API

def get_config() -> Config:
    """Return the current resolved config. Cached; call
    `reload_config()` to force a re-read from disk + env."""
    global _cached
    with _cache_lock:
        if _cached is None:
            _cached = _compute_config()
        return _cached


def reload_config() -> None:
    """Clear the cache. The next `get_config()` re-reads disk + env."""
    global _cached
    with _cache_lock:
        _cached = None


def save_config(updates: dict[str, Any]) -> Config:
    """Merge `updates` into the on-disk config and write atomically.

    - Rejects unknown keys with `UnknownConfigKey` *before* touching
      disk; a typo can't bork the file.
    - Merges with the existing file contents (sparse update — keys
      not in `updates` are preserved).
    - Writes to `<path>.tmp` then `os.replace`s into place; concurrent
      readers see the old file or the new one, never half of either.
    - Sets file mode 0600 on the new file.
    - Auto-calls `reload_config()` and returns the newly-cached Config.
    """
    unknown = set(updates.keys()) - CONFIG_KEYS
    if unknown:
        raise UnknownConfigKey(
            f"unknown config key(s): {sorted(unknown)}; "
            f"valid keys: {sorted(CONFIG_KEYS)}"
        )

    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _read_file_data(path)
    merged = {**existing, **updates}

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    # Open with mode 0600 from the start so the file is never readable
    # by other users, even briefly. os.open + fdopen lets us set the
    # mode on creation rather than chmod-ing after the fact.
    fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, sort_keys=True)
            f.write("\n")
    except Exception:
        # Clean up tmp on failure so a half-written file isn't left
        # behind to confuse the next read.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    os.replace(tmp_path, path)
    # Belt-and-braces: ensure the final file is 0600 even if the umask
    # or replace semantics on this platform alter mode bits.
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass

    reload_config()
    return get_config()


def as_dict(config: Config) -> dict[str, Any]:
    """Plain-dict projection of `config` (no masking). API layers that
    return JSON should mask `SECRET_FIELDS` themselves."""
    return asdict(config)


# --------------------------------------------------------------------- summary
# Sprint-11 / settings-link-in-switcher: lane-2 read-only consumer.
# The brand-lockup switcher renders a `<N> knobs · saved <T> ago`
# telemetry hint on the settings row. This helper is the single
# source of truth for those two values so the switcher (and
# anything else that wants the same hint) stays consistent.

import datetime as _dt


def _format_relative(delta_seconds: float) -> str:
    """Human-relative time string: `just now`, `5m ago`, `2h ago`,
    `3d ago`. Anchored at one decimal place is overkill for this UI."""
    s = int(delta_seconds)
    if s < 60:
        return "just now"
    if s < 3600:
        return f"{s // 60}m ago"
    if s < 86400:
        return f"{s // 3600}h ago"
    return f"{s // 86400}d ago"


def get_config_summary() -> dict[str, Any]:
    """Return `{knobs: int, saved: str}` for UI consumers.

    - `knobs` counts config fields whose effective resolved value
      differs from the built-in default. Mirrors "how many knobs has
      the operator actually touched" — env vars + file edits both
      contribute, since both override the default.
    - `saved` is the human-relative time since the config file was
      last written (file mtime). `"never"` when the file is missing.

    Read-only. Never raises — degrades to zero / `"never"` on any
    transient filesystem error so the switcher can't break the page.
    """
    try:
        cfg = get_config()
    except Exception:  # noqa: BLE001 — UI helper must not raise
        return {"knobs": 0, "saved": "never"}

    default = Config()
    knobs = 0
    for f in fields(Config):
        if getattr(cfg, f.name) != getattr(default, f.name):
            knobs += 1

    path = _config_path()
    if not path.is_file():
        saved = "never"
    else:
        try:
            mtime = path.stat().st_mtime
            now = _dt.datetime.now(_dt.UTC).timestamp()
            saved = _format_relative(max(0.0, now - mtime))
        except OSError:
            saved = "never"

    return {"knobs": knobs, "saved": saved}
