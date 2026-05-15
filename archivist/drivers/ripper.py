"""Audio-CD ripper: cdparanoia → flac, wrapped behind a Ripper Protocol.

Per sprint-1 task impl-ripper. The pluggable Ripper interface lets
sprint-2 add DataDiscRipper / DVDVideoRipper without touching this
module's call sites.
"""
from __future__ import annotations

import fcntl
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

# include/uapi/linux/cdrom.h
CDROM_DISC_STATUS = 0x5327
CDS_AUDIO = 100

RipStatus = Literal["success", "partial", "fail"]


@dataclass
class RipResult:
    status: RipStatus
    tracks: list[Path]
    errors: list[str] = field(default_factory=list)


class Ripper(Protocol):
    media_types: set[str]

    def detect(self, device: Path) -> str | None: ...

    def rip(self, device: Path, out_dir: Path) -> RipResult: ...


class CDAudioRipper:
    """Rips audio CDs to FLAC via cdparanoia + flac."""

    media_types: set[str] = {"audio_cd"}

    def detect(self, device: Path) -> str | None:
        fd = os.open(device, os.O_RDONLY | os.O_NONBLOCK)
        try:
            code = fcntl.ioctl(fd, CDROM_DISC_STATUS)
        finally:
            os.close(fd)
        return "audio_cd" if code == CDS_AUDIO else None

    def rip(self, device: Path, out_dir: Path) -> RipResult:
        out_dir.mkdir(parents=True, exist_ok=True)
        errors: list[str] = []

        cdp = subprocess.run(
            ["cdparanoia", "-B", "-d", str(device), "--", "1-", str(out_dir)],
            capture_output=True,
            text=True,
        )
        if cdp.returncode != 0 and cdp.stderr:
            errors.append(cdp.stderr.strip())

        wavs = sorted(out_dir.glob("track*.wav"))
        if not wavs:
            if not errors:
                errors.append(f"cdparanoia exit {cdp.returncode} produced no WAVs")
            return RipResult(status="fail", tracks=[], errors=errors)

        tracks: list[Path] = []
        for wav in wavs:
            enc = subprocess.run(
                ["flac", "--best", str(wav)],
                capture_output=True,
                text=True,
            )
            flac_path = wav.with_suffix(".flac")
            if enc.returncode == 0 and flac_path.exists():
                tracks.append(flac_path)
            else:
                msg = enc.stderr.strip() or f"flac exit {enc.returncode} for {wav.name}"
                errors.append(msg)

        if cdp.returncode == 0 and len(tracks) == len(wavs) and not errors:
            return RipResult(status="success", tracks=tracks, errors=[])
        return RipResult(status="partial", tracks=tracks, errors=errors)
